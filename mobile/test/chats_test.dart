// Chat history on the phone: saved after every message and back after a
// restart, never saved in incognito, deleted one by one or all at once, and a
// restored chat that ends on a question carries on with the same
// conversation_history (question_id included).

import 'dart:convert';
import 'dart:io';

import 'package:carecompass/api.dart';
import 'package:carecompass/main.dart';
import 'package:carecompass/models.dart';
import 'package:carecompass/state.dart';
import 'package:carecompass/strings_mobile.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

String fx(String name) => File('test/fixtures/$name').readAsStringSync();

http.Response jsonRes(String body, [int status = 200]) =>
    http.Response.bytes(utf8.encode(body), status, headers: {'content-type': 'application/json'});

/// Question while the conversation is empty, a decision after it; an
/// emergency for "seene". Records every /v1/triage body.
MockClient server(List<Map<String, dynamic>> sent) => MockClient((req) async {
  if (req.url.path == '/health') return jsonRes(fx('health.json'));
  if (req.url.path == '/v1/labels') return jsonRes(fx('labels.json'));
  final body = jsonDecode(req.body) as Map<String, dynamic>;
  sent.add(body);
  if ((body['user_input'] as String).toLowerCase().contains('seene')) return jsonRes(fx('v3_triage_emergency.json'));
  final history = body['conversation_history'] as List;
  return jsonRes(fx(history.isEmpty ? 'v3_triage_danger.json' : 'v3_triage_final.json'));
});

Future<AppState> boot(MockClient client) async {
  final state = AppState(api: ApiClient(base: 'https://api.test', client: client));
  await state.load();
  addTearDown(() async {
    await pumpEventQueue(); // let the first health check finish
    state.dispose();
  });
  return state;
}

Future<List<dynamic>?> storedChats() async {
  final raw = (await SharedPreferences.getInstance()).getString('cc_chats');
  return raw == null ? null : jsonDecode(raw) as List<dynamic>;
}

/// A chat-bar button by its accessible name (its label may be folded into
/// an icon on a narrow screen).
Finder bar(String label) =>
    find.byWidgetPredicate((w) => w is Semantics && (w.properties.label ?? '').startsWith(label));

Future<void> settle(WidgetTester tester, [int frames = 12]) async {
  for (var i = 0; i < frames; i++) {
    await tester.pump(const Duration(milliseconds: 150));
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('a chat is saved after every message and restored after a restart', () async {
    final sent = <Map<String, dynamic>>[];
    final state = await boot(server(sent));
    expect(state.chats, isEmpty);

    await state.send('Papa ko do din se bukhar hai aur khansi bhi');
    expect(state.chats, hasLength(1));
    expect(state.chats.first.title, 'Papa ko do din se bukhar hai aur khansi bhi');
    expect(state.chats.first.outcome, 'question');
    expect(await storedChats(), hasLength(1));

    final d = await state.send('Nahi') as DecisionMsg;
    expect(state.chats, hasLength(1), reason: 'the same chat is updated, not duplicated');
    final saved = state.chats.first;
    expect(saved.id, state.chatId);
    expect(saved.outcome, 'decision');
    expect(saved.outcomeLabel, contains(d.res.trace.decision.careLabelLocal));
    expect(saved.outcomeLabel, contains(d.res.trace.decision.urgencyLabelLocal));
    expect(saved.messages.map((m) => m['type']), ['user', 'question', 'user', 'decision']);

    // a long first message becomes a short title
    state.newChat();
    expect(state.messages, isEmpty);
    await state.send('Mummy ko ${'bahut ' * 20}tez sir dard hai');
    expect(state.chats, hasLength(2));
    expect(state.chats.first.title.characters.length, lessThanOrEqualTo(60));
    expect(state.chats.first.title, endsWith('…'));

    // restart: History is read back, the thread starts empty
    final again = await boot(server(sent));
    expect(again.messages, isEmpty);
    expect(again.chats.map((c) => c.id), state.chats.map((c) => c.id));
    expect(again.chats.last.title, saved.title);
    expect(again.chats.last.updatedAt.isAtSameMomentAs(saved.updatedAt), isTrue);

    again.openChat(again.chats.last);
    expect(again.chatId, saved.id);
    expect(again.messages.map((m) => m.runtimeType.toString()), ['UserMsg', 'QuestionMsg', 'UserMsg', 'DecisionMsg']);
    final restored = again.messages.last as DecisionMsg;
    expect(restored.res.careType, d.res.careType);
    expect(restored.res.trace.caregivers.length, d.res.trace.caregivers.length);
    expect(restored.req.toJson(), d.req.toJson());
    expect(again.history, isEmpty, reason: 'after a decision the next message is a new case');
    expect(again.answering, isFalse);
  });

  test('a restored chat that ends on a question continues the same conversation', () async {
    final sent = <Map<String, dynamic>>[];
    // two questions in a row, then a decision
    final client = MockClient((req) async {
      if (req.url.path == '/health') return jsonRes(fx('health.json'));
      final body = jsonDecode(req.body) as Map<String, dynamic>;
      sent.add(body);
      final n = (body['conversation_history'] as List).length;
      return jsonRes(fx(switch (n) {
        0 => 'triage_followup.json',
        2 => 'v3_triage_danger.json',
        _ => 'v3_triage_final.json',
      }));
    });
    final state = await boot(client);
    await state.send('Papa ko do din se bukhar hai aur khansi bhi');
    await state.send('Thodi si');
    expect(state.answering, isTrue);
    final live = state.history.map((h) => h.toJson()).toList();

    final again = await boot(client);
    again.openChat(again.chats.single);
    expect(again.answering, isTrue);
    expect(again.history.map((h) => h.toJson()).toList(), live, reason: 'rebuilt exactly as send() left it');
    expect(again.history.map((h) => h.toJson()).toList(), [
      {'role': 'user', 'content': 'Papa ko do din se bukhar hai aur khansi bhi'},
      {'role': 'assistant', 'content': 'Kya saans lene mein dikkat ho rahi hai?', 'question_id': 'q_breathing'},
      {'role': 'user', 'content': 'Thodi si'},
      {
        'role': 'assistant',
        'content': 'Kya inme se kuch hai: saans phoolna, behoshi, seene mein dard, ya bahut tez bukhar?',
        'question_id': 'q_danger',
      },
    ]);

    final d = await again.send('Nahi');
    expect(d, isA<DecisionMsg>());
    expect(sent.last['user_input'], 'Nahi');
    final h = (sent.last['conversation_history'] as List).cast<Map<String, dynamic>>();
    expect(h, hasLength(4));
    expect(h[1], containsPair('question_id', 'q_breathing'));
    expect(h.last, containsPair('question_id', 'q_danger'));
    expect(again.chats, hasLength(1), reason: 'the answer goes into the same saved chat');
    expect(again.chats.single.outcome, 'decision');
    expect(again.chats.single.messages, hasLength(6));
  });

  test('a chat whose reply never came offers a retry when opened', () async {
    var fail = true;
    final client = MockClient((req) async {
      if (req.url.path == '/health') return jsonRes(fx('health.json'));
      return fail ? http.Response('oops', 500) : jsonRes(fx('v3_triage_danger.json'));
    });
    final state = await boot(client);
    expect(await state.send('papa ko bukhar hai'), isA<ErrorMsg>());
    expect(state.chats.single.outcome, 'none');
    expect(state.chats.single.messages.map((m) => m['type']), ['user'], reason: 'the error itself is not saved');

    final again = await boot(client);
    again.openChat(again.chats.single);
    expect(again.messages.map((m) => m.runtimeType.toString()), ['UserMsg', 'ErrorMsg']);
    fail = false;
    expect(await again.retry(again.messages.last as ErrorMsg), isA<QuestionMsg>());
    expect(again.chats.single.messages.map((m) => m['type']), ['user', 'question']);
  });

  test('incognito chats are never saved', () async {
    final sent = <Map<String, dynamic>>[];
    final state = await boot(server(sent));

    expect(state.goIncognito(), isFalse, reason: 'nothing saved to remove');
    expect(state.incognito, isTrue);
    await state.send('Papa ko do din se bukhar hai aur khansi bhi');
    await state.send('Nahi');
    await state.send('Mummy ke seene mein dard hai');
    expect(state.messages, hasLength(6));
    expect(state.chats, isEmpty);
    expect(state.chatId, isNull);
    expect(await storedChats(), isNull);

    // leaving incognito drops its thread
    state.newChat();
    expect(state.incognito, isFalse);
    expect(state.messages, isEmpty);
    expect(state.last, isNull);

    // a normal chat is saved; switching it to incognito takes it out of History
    await state.send('Dadi ko roz insulin ka injection ghar pe lagwana hai');
    expect(state.chats, hasLength(1));
    expect(state.goIncognito(), isTrue);
    expect(state.messages, isNotEmpty, reason: 'the thread stays on screen');
    expect(state.chats, isEmpty);
    expect(await storedChats(), isNull);
    await state.send('Nahi');
    expect(state.chats, isEmpty);

    // opening a saved chat from History leaves incognito and drops its thread
    state.newChat();
    await state.send('Bukhar hai');
    final saved = state.chats.single;
    state.newChat();
    state.goIncognito();
    await state.send('Mummy ko sir dard hai');
    expect(state.chats, hasLength(1));
    state.openChat(saved);
    expect(state.incognito, isFalse);
    expect(state.messages.whereType<UserMsg>().map((m) => m.text), ['Bukhar hai']);
    expect(state.chats.map((c) => c.title), ['Bukhar hai']);

    final again = await boot(server(sent));
    expect(again.chats.map((c) => c.title), ['Bukhar hai']);
  });

  test('deleting one chat and deleting all', () async {
    final sent = <Map<String, dynamic>>[];
    final state = await boot(server(sent));
    for (final s in ['Bukhar hai', 'Khansi hai', 'Pet mein dard hai']) {
      state.newChat();
      await state.send(s);
    }
    expect(state.chats.map((c) => c.title), ['Pet mein dard hai', 'Khansi hai', 'Bukhar hai']);

    // not the open one: the thread stays
    state.deleteChat(state.chats[1].id);
    expect(state.chats.map((c) => c.title), ['Pet mein dard hai', 'Bukhar hai']);
    expect(state.messages, isNotEmpty);
    expect((await storedChats())!.map((c) => c['title']), ['Pet mein dard hai', 'Bukhar hai']);

    // the open one: the thread is cleared, so the next message does not bring it back
    state.deleteChat(state.chatId!);
    expect(state.chats.map((c) => c.title), ['Bukhar hai']);
    expect(state.messages, isEmpty);
    expect(state.chatId, isNull);
    await state.send('Sir dard hai');
    expect(state.chats.map((c) => c.title), ['Sir dard hai', 'Bukhar hai']);

    final again = await boot(server(sent));
    expect(again.chats.map((c) => c.title), ['Sir dard hai', 'Bukhar hai']);

    state.deleteAllChats();
    expect(state.chats, isEmpty);
    expect(state.messages, isEmpty, reason: 'the open chat was part of History');
    expect(await storedChats(), isNull);
    final empty = await boot(server(sent));
    expect(empty.chats, isEmpty);
  });

  test('at most 30 chats are kept, newest first', () async {
    final state = await boot(server([]));
    for (var i = 0; i < AppState.maxChats + 3; i++) {
      state.newChat();
      await state.send('Bukhar hai $i');
    }
    expect(state.chats, hasLength(AppState.maxChats));
    expect(state.chats.first.title, 'Bukhar hai ${AppState.maxChats + 2}');
    expect(state.chats.last.title, 'Bukhar hai 3');
    expect(await storedChats(), hasLength(AppState.maxChats));
  });

  testWidgets('History sheet opens a saved chat in the thread; New chat and Incognito from the bar', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 2.625;
    addTearDown(tester.view.reset);

    final state = AppState(api: ApiClient(base: 'https://api.test', client: server([])));
    await tester.pumpWidget(CareCompassApp(state: state));
    await settle(tester);
    const lang = Lang.hinglish;

    // start view: History (no count yet) and Incognito chat
    expect(bar(tm(lang, M.history)), findsOneWidget);
    expect(find.text(tm(lang, M.incognito)), findsOneWidget);
    expect(bar(tm(lang, M.newChat)), findsNothing);

    await tester.enterText(find.byType(TextField), 'Papa ko do din se bukhar hai aur khansi bhi');
    await tester.pump();
    await tester.tap(find.byTooltip('Bhejein'));
    await settle(tester);
    expect(find.text('Sawaal 1 / 4'), findsOneWidget);

    // thread bar: New chat keeps the chat in History
    expect(bar(tm(lang, M.incognitoShort)), findsOneWidget);
    await tester.tap(bar(tm(lang, M.newChat)));
    await settle(tester);
    expect(state.messages, isEmpty);
    expect(state.chats, hasLength(1));
    expect(bar('${tm(lang, M.history)} (1)'), findsOneWidget, reason: 'count next to History');

    // incognito from the start view: banner, nothing saved
    await tester.tap(bar(tm(lang, M.incognito)));
    await settle(tester);
    expect(bar(tm(lang, M.incognito)), findsNothing);
    expect(find.text(tm(lang, M.incognitoBanner)), findsOneWidget);
    await tester.enterText(find.byType(TextField), 'Mummy ko sir dard hai');
    await tester.pump();
    await tester.tap(find.byTooltip('Bhejein'));
    await settle(tester);
    expect(find.text(tm(lang, M.incognitoBanner)), findsOneWidget);
    expect(state.chats, hasLength(1));

    // History: the saved chat with its outcome; opening it leaves incognito
    await tester.tap(bar(tm(lang, M.history)));
    await settle(tester);
    expect(find.text(tm(lang, M.historyTitle)), findsOneWidget);
    expect(find.text(tm(lang, M.chatPending)), findsOneWidget);
    await tester.tap(find.text('Papa ko do din se bukhar hai aur khansi bhi').last);
    await settle(tester);
    expect(find.text(tm(lang, M.historyTitle)), findsNothing);
    expect(state.incognito, isFalse);
    expect(find.text(tm(lang, M.incognitoBanner)), findsNothing);
    expect(find.text('Sawaal 1 / 4'), findsOneWidget);
    expect(find.text('Haan'), findsOneWidget, reason: 'the question can still be answered');

    // answer it: the restored conversation goes on
    await tester.tap(find.text('Nahi'));
    await settle(tester, 20);
    expect(find.text('Humara sujhav'), findsOneWidget);
    expect(state.chats.single.outcome, 'decision');

    // switching this saved chat to incognito takes it out of History
    await tester.tap(bar(tm(lang, M.incognitoShort)));
    await settle(tester);
    expect(find.text(tm(lang, M.incognitoRemoved)), findsOneWidget);
    expect(find.text(tm(lang, M.incognitoBanner)), findsOneWidget);
    expect(state.chats, isEmpty);

    // the banner's cross leaves incognito and drops the thread
    await tester.tap(find.byTooltip(tm(lang, M.incognitoOff)));
    await settle(tester);
    expect(state.incognito, isFalse);
    expect(state.messages, isEmpty);
    expect(find.text('Batayein, kya taklif hai?'), findsOneWidget);
  });
}
