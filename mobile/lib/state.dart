// App state: preferences, the consult thread, saved chats and saved bookings.
// Mirrors web/src/App.tsx. The conversation history is built exactly like the
// web client: on a follow-up, append the user's turn and the assistant's
// question (with question_id); on a final decision or emergency, start over.
// Chats are kept on the phone only (shared_preferences), never in incognito.

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';
import 'config.dart';
import 'i18n.dart';
import 'models.dart';
import 'util.dart';
import 'voice.dart';

// ---- thread messages ----

sealed class Msg {
  final int id;
  const Msg(this.id);
}

class UserMsg extends Msg {
  final String text;
  const UserMsg(super.id, this.text);
}

class QuestionMsg extends Msg {
  final TriageRequest req;
  final TriageResponse res;
  const QuestionMsg(super.id, this.req, this.res);
}

class DecisionMsg extends Msg {
  final TriageRequest req;
  final TriageResponse res;
  const DecisionMsg(super.id, this.req, this.res);
}

class EmergencyMsg extends Msg {
  final TriageRequest req;
  final TriageResponse res;
  final String userText;
  const EmergencyMsg(super.id, this.req, this.res, this.userText);
}

class ErrorMsg extends Msg {
  final String text;
  final bool usedVoice;
  const ErrorMsg(super.id, this.text, this.usedVoice);
}

// ---- saved chats (History) ----

/// Stored form of a thread message: the user's text, or the request and the
/// raw response body. A failed request (ErrorMsg) is not saved.
Map<String, Object?>? encodeMsg(Msg m) => switch (m) {
  UserMsg() => {'type': 'user', 'text': m.text},
  QuestionMsg() => {'type': 'question', 'req': m.req.toJson(), 'res': m.res.raw},
  DecisionMsg() => {'type': 'decision', 'req': m.req.toJson(), 'res': m.res.raw},
  EmergencyMsg() => {'type': 'emergency', 'req': m.req.toJson(), 'res': m.res.raw, 'user_text': m.userText},
  ErrorMsg() => null,
};

/// Rebuilds a message saved with [encodeMsg]; null if it cannot be read.
Msg? decodeMsg(Map<String, Object?> j, int id) {
  final type = j['type'];
  if (type == 'user') return UserMsg(id, '${j['text'] ?? ''}');
  final rq = j['req'];
  final rs = j['res'];
  if (rq is! Map || rs is! Map) return null;
  final req = TriageRequest.fromJson(rq.cast<String, Object?>());
  final res = TriageResponse.fromJson(rs.cast<String, Object?>());
  final userText = j['user_text'];
  return switch (type) {
    'question' => QuestionMsg(id, req, res),
    'decision' => DecisionMsg(id, req, res),
    'emergency' => EmergencyMsg(id, req, res, userText is String ? userText : req.userInput),
    _ => null,
  };
}

/// The conversation [AppState.send] holds after [msgs]: if the last answer
/// was a question, that request's history, the user's turn and the question
/// (with its question_id); after a decision or emergency, nothing.
List<HistoryItem> historyAfter(List<Msg> msgs) {
  for (final m in msgs.reversed) {
    if (m is QuestionMsg) {
      return [
        ...m.req.conversationHistory,
        HistoryItem(role: 'user', content: m.req.userInput),
        HistoryItem(role: 'assistant', content: m.res.questionText ?? '', questionId: m.res.trace.followUp?.id),
      ];
    }
    if (m is DecisionMsg || m is EmergencyMsg) return [];
  }
  return [];
}

/// History title: the first thing the user said, on one line, ~60 characters.
String chatTitle(List<Msg> msgs) {
  for (final m in msgs) {
    if (m is! UserMsg) continue;
    final line = m.text.replaceAll(RegExp(r'\s+'), ' ').trim();
    final chars = line.characters;
    return chars.length <= 60 ? line : '${chars.take(57).toString().trimRight()}…';
  }
  return '';
}

/// What a chat came to, for the History list: [SavedChat.outcome] is
/// "decision", "unclear" (nothing understood), "emergency", "question"
/// (still waiting for an answer) or "none" (no reply yet).
({String kind, String? label, int level}) chatOutcome(List<Msg> msgs, Lang lang) {
  for (final m in msgs.reversed) {
    switch (m) {
      case DecisionMsg(:final res) when res.trace.decision.unclear:
        return (kind: 'unclear', label: null, level: 0);
      case DecisionMsg(:final res):
        final label = [careLabel(res, lang), urgencyLabel(res, lang)].where((s) => s.trim().isNotEmpty).join(' · ');
        return (kind: 'decision', label: label, level: urgencyLevel(res.urgency ?? res.trace.decision.urgency));
      case EmergencyMsg(:final res):
        return (kind: 'emergency', label: res.trace.emergency?.titleLocal ?? t(lang, K.sosPageTitle), level: 2);
      case QuestionMsg():
        return (kind: 'question', label: null, level: 0);
      case UserMsg() || ErrorMsg():
        break;
    }
  }
  return (kind: 'none', label: null, level: 0);
}

/// A consult thread saved on this phone. Messages stay in their stored form
/// until the chat is opened.
class SavedChat {
  final String id;
  final DateTime startedAt;
  final DateTime updatedAt;
  final String title;
  final String outcome; // decision | unclear | emergency | question | none
  final String? outcomeLabel; // care + urgency, or the emergency title
  final int level; // 0-2, colours the outcome
  final List<Map<String, Object?>> messages;
  const SavedChat({
    required this.id,
    required this.startedAt,
    required this.updatedAt,
    required this.title,
    required this.outcome,
    this.outcomeLabel,
    this.level = 0,
    required this.messages,
  });

  /// Null for an entry that cannot be read (it is then left out).
  static SavedChat? tryParse(Map<String, Object?> j) {
    try {
      final id = j['id'];
      final msgs = j['messages'];
      if (id is! String || id.isEmpty || msgs is! List) return null;
      final out = j['outcome'] is Map ? (j['outcome'] as Map).cast<String, Object?>() : const <String, Object?>{};
      final epoch = DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);
      return SavedChat(
        id: id,
        startedAt: DateTime.tryParse('${j['started_at']}') ?? epoch,
        updatedAt: DateTime.tryParse('${j['updated_at']}') ?? epoch,
        title: j['title'] is String ? j['title'] as String : '',
        outcome: out['kind'] is String ? out['kind'] as String : 'none',
        outcomeLabel: out['label'] is String ? out['label'] as String : null,
        level: out['level'] is num ? (out['level'] as num).toInt() : 0,
        messages: msgs.whereType<Map>().map((m) => m.cast<String, Object?>()).toList(),
      );
    } catch (_) {
      return null;
    }
  }

  Map<String, Object?> toJson() => {
    'id': id,
    'started_at': startedAt.toUtc().toIso8601String(),
    'updated_at': updatedAt.toUtc().toIso8601String(),
    'title': title,
    'outcome': {'kind': outcome, 'label': outcomeLabel, 'level': level},
    'messages': messages,
  };
}

enum Backend { wait, ok, bad }

enum ThemePref { auto, light, dark }

class AppState extends ChangeNotifier {
  AppState({ApiClient? api, Voice? voice}) : api = api ?? ApiClient(), voice = voice ?? Voice();

  final ApiClient api;
  final Voice voice;
  SharedPreferences? _prefs;

  // ---- preferences ----
  Lang lang = Lang.hinglish;
  bool autoRead = true;
  bool largeText = false;
  ThemePref theme = ThemePref.light; // light by default, as on the web

  // ---- navigation ----
  int tab = 0;

  // ---- consult ----
  final List<Msg> messages = [];
  List<HistoryItem> history = [];
  bool busy = false;
  ({TriageRequest req, TriageResponse res})? last;
  int _nextId = 1;

  /// Id of the decision the user is adding details to ("Aur jaankari
  /// jodein"), or null. Its conversation is already back in [history].
  int? addingTo;

  // ---- saved chats (History) ----
  static const maxChats = 30;
  static const _chatsKey = 'cc_chats';

  /// Newest first.
  List<SavedChat> chats = [];

  /// Id of the open thread in [chats]; null until it is first saved, and
  /// always null in incognito.
  String? chatId;
  DateTime? _chatStarted;

  /// Incognito: the open thread is never written to the phone.
  bool incognito = false;

  /// Bumped whenever the thread is swapped (new chat, opened chat), so a
  /// reply still loading for the old thread is dropped.
  int get thread => _thread;
  int _thread = 0;

  // ---- bookings ----
  List<SavedBooking> bookings = [];

  // ---- backend status ----
  Backend backend = Backend.wait;
  Timer? _healthTimer;

  final LatLng location = kDemoLocation;

  String get locationLabel => t(lang, K.locDemo);

  bool get answering => messages.isNotEmpty && messages.last is QuestionMsg;

  /// True while the next message adds details to the last decision.
  bool get addingDetails => addingTo != null && messages.isNotEmpty && messages.last.id == addingTo;

  Future<void> load() async {
    try {
      final p = await SharedPreferences.getInstance();
      _prefs = p;
      lang = langFromCode(p.getString('cc_lang'));
      autoRead = p.getBool('cc_autoread') ?? true;
      largeText = p.getBool('cc_large') ?? false;
      theme = ThemePref.values.asNameMap()[p.getString('cc_theme')] ?? ThemePref.light;
      voice.warmUp();
      final raw = p.getString('cc_bookings');
      if (raw != null) {
        final list = jsonDecode(raw);
        if (list is List) {
          bookings = list.whereType<Map>().map((m) => SavedBooking.fromJson(m.cast<String, Object?>())).toList();
        }
      }
      final rawChats = p.getString(_chatsKey);
      if (rawChats != null) {
        final list = jsonDecode(rawChats);
        if (list is List) {
          chats = list
              .whereType<Map>()
              .map((m) => SavedChat.tryParse(m.cast<String, Object?>()))
              .whereType<SavedChat>()
              .toList();
        }
      }
    } catch (_) {
      // Storage unavailable: run with defaults.
    }
    notifyListeners();
    _checkHealth();
    _healthTimer = Timer.periodic(const Duration(seconds: 20), (_) => _checkHealth());
  }

  Future<void> _checkHealth() async {
    Backend next;
    try {
      final h = await api.health();
      next = h.status == 'ok' ? Backend.ok : Backend.bad;
    } catch (_) {
      next = Backend.bad;
    }
    if (next == backend) return; // no rebuild when nothing changed
    backend = next;
    notifyListeners();
  }

  void setLang(Lang l) {
    lang = l;
    _prefs?.setString('cc_lang', l.code);
    notifyListeners();
  }

  /// The UI follows the script the person writes in ([send] passes each
  /// reply's trace.language): Devanagari ("hi") switches it to Hindi, Roman
  /// ("hinglish" or "en") switches a Hindi UI to Hinglish. Hinglish and
  /// English are never swapped here (short Roman words like "ok" often read
  /// as English), so a choice on the language button stays until the other
  /// script is used.
  void followWriting(Lang wrote) {
    if (wrote == Lang.hi && lang != Lang.hi) setLang(Lang.hi);
    if (wrote != Lang.hi && lang == Lang.hi) setLang(Lang.hinglish);
  }

  void setAutoRead(bool v) {
    autoRead = v;
    _prefs?.setBool('cc_autoread', v);
    notifyListeners();
  }

  void setLargeText(bool v) {
    largeText = v;
    _prefs?.setBool('cc_large', v);
    notifyListeners();
  }

  void setTheme(ThemePref v) {
    theme = v;
    _prefs?.setString('cc_theme', v.name);
    notifyListeners();
  }

  void setTab(int i) {
    if (tab == i) return;
    tab = i;
    notifyListeners();
  }

  /// Sends [text] to /v1/triage with the conversation so far. Returns the
  /// message added to the thread (so the UI can open the emergency screen).
  Future<Msg?> send(String text, {bool usedVoice = false, bool retry = false}) async {
    final clean = text.trim();
    if (clean.isEmpty || busy) return null;
    voice.stopSpeaking();
    final thread = _thread;
    if (!retry) {
      if (messages.isEmpty) _chatStarted = DateTime.now();
      messages.add(UserMsg(_nextId++, clean));
      _saveChat();
    }
    busy = true;
    notifyListeners();

    final req = TriageRequest(
      userInput: clean,
      language: 'auto',
      location: location,
      conversationHistory: List.unmodifiable(history),
    );
    addingTo = null;
    Msg added;
    try {
      final res = await api.triage(req);
      if (thread != _thread) return null; // the user moved to another chat meanwhile
      last = (req: req, res: res);
      followWriting(res.trace.language);
      final voiceLang = res.trace.language;
      if (res.isEmergency) {
        added = EmergencyMsg(_nextId++, req, res, clean);
        history = [];
        if (usedVoice && autoRead) {
          voice.speak(speechFor(res.trace.speech, '${res.trace.emergency?.titleLocal ?? ''}. ${t(lang, K.sosNow)}', voiceLang));
        }
      } else if (res.questionText != null) {
        final q = res.questionText!;
        added = QuestionMsg(_nextId++, req, res);
        history = [
          ...history,
          HistoryItem(role: 'user', content: clean),
          HistoryItem(role: 'assistant', content: q, questionId: res.trace.followUp?.id),
        ];
        if (usedVoice && autoRead) voice.speak(speechFor(res.trace.speech, q, voiceLang));
      } else {
        added = DecisionMsg(_nextId++, req, res);
        history = [];
        if (usedVoice && autoRead) voice.speak(speechFor(res.trace.speech, decisionSummary(res), voiceLang));
      }
    } catch (_) {
      if (thread != _thread) return null;
      // Never fabricate a result: show the error with a retry button.
      added = ErrorMsg(_nextId++, clean, usedVoice);
    }
    messages.add(added);
    busy = false;
    _saveChat();
    notifyListeners();
    return added;
  }

  Future<Msg?> retry(ErrorMsg m) {
    messages.removeWhere((x) => x.id == m.id);
    return send(m.text, usedVoice: m.usedVoice, retry: true);
  }

  /// "Nayi chat", and every "Nayi jaanch" button: an empty thread. The open
  /// chat is already in History (each message saves it); an incognito one is
  /// dropped. Always leaves incognito.
  void newChat() {
    _clearThread();
    incognito = false;
    tab = 0;
    notifyListeners();
  }

  /// "Incognito chat": nothing in this thread is saved from now on. From the
  /// start view this is a new chat; on an open saved chat it also takes that
  /// chat out of History. Returns true when a saved chat was removed.
  bool goIncognito() {
    if (incognito) return false;
    final id = chatId;
    incognito = true;
    chatId = null;
    final removed = id != null && _dropChat(id);
    tab = 0;
    notifyListeners();
    return removed;
  }

  /// Opens a chat from History in the Jaanch thread. If it ends on a
  /// question, [history] is rebuilt exactly as [send] left it, so the next
  /// message answers it; otherwise the next message starts a new case.
  void openChat(SavedChat c) {
    if (!incognito && c.id == chatId) {
      setTab(0);
      return;
    }
    _clearThread();
    incognito = false;
    for (final j in c.messages) {
      final m = decodeMsg(j, _nextId++);
      if (m != null) messages.add(m);
    }
    // A last message with no reply (app closed or request failed): offer the
    // retry, as right after a failed request.
    final tail = messages.isEmpty ? null : messages.last;
    if (tail is UserMsg) messages.add(ErrorMsg(_nextId++, tail.text, false));
    history = historyAfter(messages);
    chatId = c.id;
    _chatStarted = c.startedAt;
    tab = 0;
    notifyListeners();
  }

  /// Deletes one saved chat. If it is the open one, the thread is cleared
  /// too, so the next message does not save it again.
  void deleteChat(String id) {
    if (!_dropChat(id)) return;
    if (id == chatId) _clearThread();
    notifyListeners();
  }

  /// "Saari history mitayein" (after the confirm dialog).
  void deleteAllChats() {
    final wasOpen = chatId != null;
    chats = [];
    _writeChats();
    if (wasOpen) _clearThread();
    notifyListeners();
  }

  void _clearThread() {
    voice.stopSpeaking();
    if (incognito) last = null; // nothing of an incognito chat stays behind
    messages.clear();
    history = [];
    addingTo = null;
    busy = false;
    chatId = null;
    _chatStarted = null;
    _thread++;
  }

  /// Puts the open thread at the top of History (at most [maxChats]).
  /// Called every time a message is added; never in incognito.
  void _saveChat() {
    if (incognito) return;
    final stored = messages.map(encodeMsg).whereType<Map<String, Object?>>().toList();
    if (stored.isEmpty) return;
    final now = DateTime.now();
    final id = chatId ??= 'c${now.microsecondsSinceEpoch}-$_nextId';
    final out = chatOutcome(messages, lang);
    final chat = SavedChat(
      id: id,
      startedAt: _chatStarted ?? now,
      updatedAt: now,
      title: chatTitle(messages),
      outcome: out.kind,
      outcomeLabel: out.label,
      level: out.level,
      messages: stored,
    );
    chats = [chat, ...chats.where((c) => c.id != id)].take(maxChats).toList();
    _writeChats();
  }

  bool _dropChat(String id) {
    final before = chats.length;
    chats = chats.where((c) => c.id != id).toList();
    if (chats.length == before) return false;
    _writeChats();
    return true;
  }

  void _writeChats() {
    final p = _prefs;
    if (p == null) return;
    try {
      final done = chats.isEmpty
          ? p.remove(_chatsKey)
          : p.setString(_chatsKey, jsonEncode([for (final c in chats) c.toJson()]));
      done.catchError((_) => false);
    } catch (_) {
      // Storage full or unavailable: History still works until the app closes.
    }
  }

  /// "Aur jaankari jodein": puts the conversation that led to [m] (earlier
  /// turns, then the user's last message) back into [history], so the next
  /// message is read together with it instead of as a new case.
  void addMoreDetails(DecisionMsg m) {
    if (busy) return;
    voice.stopSpeaking();
    history = [
      ...m.req.conversationHistory,
      HistoryItem(role: 'user', content: m.req.userInput),
    ];
    addingTo = m.id;
    notifyListeners();
  }

  /// Undo [addMoreDetails]: the next message starts a fresh case again.
  void cancelAddMore() {
    if (addingTo == null) return;
    history = [];
    addingTo = null;
    notifyListeners();
  }

  Future<SavedBooking> book(TraceCaregiver cg, TriageResponse res, String note) async {
    final b = await api.createBooking(
      BookingRequest(
        caregiverId: cg.caregiverId,
        slot: cg.nextSlot,
        careType: res.careType,
        urgency: res.urgency,
        note: note,
      ),
    );
    final s = SavedBooking(
      bookingId: b.bookingId,
      caregiverId: cg.caregiverId,
      caregiverName: b.caregiverName.isNotEmpty ? b.caregiverName : cg.name,
      role: cg.role,
      slotLabel: cg.nextSlotLabelLocal,
      careLabel: res.trace.decision.careLabelLocal,
      urgencyLabel: res.trace.decision.urgencyLabelLocal,
      createdAt: b.createdAt,
    );
    bookings = [s, ...bookings];
    _prefs?.setString('cc_bookings', jsonEncode(bookings.map((e) => e.toJson()).toList()));
    notifyListeners();
    return s;
  }

  @override
  void dispose() {
    _healthTimer?.cancel();
    voice.dispose();
    super.dispose();
  }
}

/// What the read-aloud button says for a decision (same as the web client),
/// ending with the "come back / call 112 if ..." advice when there is one.
String decisionSummary(TriageResponse res) {
  final d = res.trace.decision;
  return [
    d.careLabelLocal,
    d.urgencyLabelLocal,
    res.trace.reasoningLocal,
    res.trace.safetyNetLocal,
  ].where((s) => s != null && s.trim().isNotEmpty).join('. ');
}

/// InheritedNotifier so any widget can read and listen to [AppState].
class AppScope extends InheritedNotifier<AppState> {
  const AppScope({super.key, required AppState state, required super.child}) : super(notifier: state);

  static AppState of(BuildContext context) => context.dependOnInheritedWidgetOfExactType<AppScope>()!.notifier!;

  static AppState read(BuildContext context) => context.getInheritedWidgetOfExactType<AppScope>()!.notifier!;
}
