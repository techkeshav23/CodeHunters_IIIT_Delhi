// App state: preferences, the consult thread, and saved bookings.
// Mirrors web/src/App.tsx. The conversation history is built exactly like the
// web client: on a follow-up, append the user's turn and the assistant's
// question (with question_id); on a final decision or emergency, start over.

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';
import 'config.dart';
import 'i18n.dart';
import 'models.dart';
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
    if (!retry) messages.add(UserMsg(_nextId++, clean));
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
      last = (req: req, res: res);
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
      // Never fabricate a result: show the error with a retry button.
      added = ErrorMsg(_nextId++, clean, usedVoice);
    }
    messages.add(added);
    busy = false;
    notifyListeners();
    return added;
  }

  Future<Msg?> retry(ErrorMsg m) {
    messages.removeWhere((x) => x.id == m.id);
    return send(m.text, usedVoice: m.usedVoice, retry: true);
  }

  void newCheck() {
    voice.stopSpeaking();
    messages.clear();
    history = [];
    addingTo = null;
    tab = 0;
    notifyListeners();
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
