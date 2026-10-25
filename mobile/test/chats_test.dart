// Chat history on the phone: saved after every message and back after a
// restart, never saved in incognito, deleted one by one or all at once, and a
// restored chat that ends on a question carries on with the same
// conversation_history (question_id included). The ☰ sidebar drives it all.

import 'dart:convert';
import 'dart:io';

import 'package:carecompass/api.dart';
import 'package:carecompass/i18n.dart';
import 'package:carecompass/main.dart';
import 'package:carecompass/models.dart';
import 'package:carecompass/state.dart';
import 'package:carecompass/strings_mobile.dart';
import 'package:carecompass/theme.dart';
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

  test('incognito chats are never saved, and never touch a saved chat', () async {
    final sent = <Map<String, dynamic>>[];
    final state = await boot(server(sent));

    state.goIncognito();
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

    // on an open saved chat: a new, empty incognito chat; the saved one stays
    // in History exactly as it was
    await state.send('Dadi ko roz insulin ka injection ghar pe lagwana hai');
    expect(state.chats, hasLength(1));
    final stored = jsonEncode(await storedChats());
    state.goIncognito();
    expect(state.incognito, isTrue);
    expect(state.messages, isEmpty, reason: 'a new chat, not the saved one under the banner');
    expect(state.chatId, isNull);
    expect(state.chats, hasLength(1));
    expect(jsonEncode(await storedChats()), stored);
    await state.send('Bukhar hai');
    expect(state.messages.whereType<UserMsg>().map((m) => m.text), ['Bukhar hai']);
    expect(jsonEncode(await storedChats()), stored, reason: 'nothing of the incognito chat is added to it');

    // tapping it again while incognito: another new, empty incognito chat
    state.goIncognito();
    expect(state.incognito, isTrue);
    expect(state.messages, isEmpty);
    expect(state.last, isNull, reason: 'nothing of the incognito chat stays behind');
    expect(jsonEncode(await storedChats()), stored);

    // opening a saved chat from History leaves incognito and drops its thread
    state.newChat();
    await state.send('Bukhar hai');
    final saved = state.chats.first;
    state.newChat();
    state.goIncognito();
    await state.send('Mummy ko sir dard hai');
    expect(state.chats, hasLength(2));
    state.openChat(saved);
    expect(state.incognito, isFalse);
    expect(state.messages.whereType<UserMsg>().map((m) => m.text), ['Bukhar hai']);
    const titles = ['Bukhar hai', 'Dadi ko roz insulin ka injection ghar pe lagwana hai'];
    expect(state.chats.map((c) => c.title), titles);

    final again = await boot(server(sent));
    expect(again.chats.map((c) => c.title), titles);
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

  testWidgets('the ☰ sidebar: New chat, Incognito, opening and deleting chats, from any tab', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 2.625;
    addTearDown(tester.view.reset);

    final state = AppState(api: ApiClient(base: 'https://api.test', client: server([])));
    await tester.pumpWidget(CareCompassApp(state: state));
    await settle(tester);
    const lang = Lang.hinglish;

    Future<void> openSidebar() async {
      await tester.tap(find.byTooltip(tm(lang, M.chats)));
      await settle(tester);
      expect(find.byType(Drawer), findsOneWidget);
    }

    Future<void> say(String text) async {
      await tester.enterText(find.byType(TextField), text);
      await tester.pump();
      await tester.tap(find.byTooltip('Bhejein'));
      await settle(tester);
    }

    // no bar above the thread any more; the sidebar starts empty
    expect(find.text(tm(lang, M.incognito)), findsNothing);
    await openSidebar();
    expect(find.text(tm(lang, M.newChat)), findsOneWidget);
    expect(find.text(tm(lang, M.incognito)), findsOneWidget);
    expect(find.text(tm(lang, M.historyEmpty)), findsOneWidget);
    expect(find.text(tm(lang, M.historySub)), findsOneWidget);
    expect(find.text(tm(lang, M.deleteAll)), findsNothing);
    await tester.tap(find.text(tm(lang, M.newChat)));
    await settle(tester);
    expect(find.byType(Drawer), findsNothing);

    await say('Papa ko do din se bukhar hai aur khansi bhi');
    expect(find.text('Sawaal 1 / 4'), findsOneWidget);

    // New chat keeps the chat: listed under "Aaj" with what it came to
    await openSidebar();
    expect(find.text(tm(lang, M.groupToday)), findsOneWidget);
    expect(find.text(tm(lang, M.chatPending)), findsOneWidget);
    await tester.tap(find.text(tm(lang, M.newChat)));
    await settle(tester);
    expect(find.byType(Drawer), findsNothing);
    expect(state.messages, isEmpty);
    expect(state.chats, hasLength(1));

    // Incognito: banner, nothing saved
    await openSidebar();
    await tester.tap(find.text(tm(lang, M.incognito)));
    await settle(tester);
    expect(find.byType(Drawer), findsNothing);
    expect(find.text(tm(lang, M.incognitoBanner)), findsOneWidget);
    await say('Mummy ko sir dard hai');
    expect(find.text(tm(lang, M.incognitoBanner)), findsOneWidget);
    expect(state.chats, hasLength(1));

    // from another tab: tapping a chat opens it in Jaanch and leaves incognito
    await tester.tap(find.text(t(lang, K.navBookings)).last);
    await settle(tester);
    expect(state.tab, 1);
    await openSidebar();
    await tester.tap(find.text('Papa ko do din se bukhar hai aur khansi bhi').last);
    await settle(tester);
    expect(find.byType(Drawer), findsNothing);
    expect(state.tab, 0);
    expect(state.incognito, isFalse);
    expect(find.text(tm(lang, M.incognitoBanner)), findsNothing);
    expect(find.text('Sawaal 1 / 4'), findsOneWidget);
    expect(find.text('Haan'), findsOneWidget, reason: 'the question can still be answered');

    // answer it: the restored conversation goes on
    await tester.tap(find.text('Nahi'));
    await settle(tester, 20);
    expect(find.text(t(lang, K.whyThis)), findsOneWidget);
    expect(state.chats.single.outcome, 'decision');

    // on this open saved chat, "Bina save kiye chat" opens a new, empty
    // incognito chat; the saved one stays in History as it was
    final saved = state.chats.single;
    await openSidebar();
    await tester.tap(find.text(tm(lang, M.incognito)));
    await settle(tester);
    expect(find.text(tm(lang, M.incognitoBanner)), findsOneWidget);
    expect(state.messages, isEmpty);
    expect(find.text('Batayein, kya taklif hai?'), findsOneWidget);
    expect(find.text(t(lang, K.whyThis)), findsNothing, reason: 'the old chat is not left under the banner');
    expect(state.chats.single, same(saved));
    await say('Mummy ko sir dard hai');
    expect(state.chats.single, same(saved), reason: 'nothing of the incognito chat is added to it');

    // the banner's cross leaves incognito and drops the thread
    await tester.tap(find.byTooltip(tm(lang, M.incognitoOff)));
    await settle(tester);
    expect(state.incognito, isFalse);
    expect(state.messages, isEmpty);
    expect(find.text('Batayein, kya taklif hai?'), findsOneWidget);

    // ⋮ -> Mitayein deletes a chat (here the open one, so the thread clears)
    await say('Bukhar hai');
    expect(state.chats, hasLength(2));
    await openSidebar();
    await tester.tap(find.byTooltip(tm(lang, M.chatMenu)).first); // newest first: the open one
    await settle(tester);
    await tester.tap(find.text(tm(lang, M.chatDelete)));
    await settle(tester);
    expect(state.chats.map((c) => c.title), ['Papa ko do din se bukhar hai aur khansi bhi']);
    expect(state.messages, isEmpty);
    await tester.tap(find.byTooltip(tm(lang, M.chatMenu)));
    await settle(tester);
    await tester.tap(find.text(tm(lang, M.chatDelete)));
    await settle(tester);
    expect(state.chats, isEmpty);
    expect(find.text(tm(lang, M.historyEmpty)), findsOneWidget, reason: 'the sidebar stays open');
  });

  testWidgets('the sidebar groups chats into Aaj / Kal / Pehle and marks the open one', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 2.625;
    addTearDown(tester.view.reset);

    final now = DateTime.now();
    SavedChat chat(String id, String title, int daysBack, String outcome, [String? label]) => SavedChat(
      id: id,
      startedAt: now.subtract(Duration(days: daysBack)),
      updatedAt: now.subtract(Duration(days: daysBack)),
      title: title,
      outcome: outcome,
      outcomeLabel: label,
      level: outcome == 'emergency' ? 2 : 0,
      messages: [
        {'type': 'user', 'text': title},
      ],
    );
    final state = AppState(api: ApiClient(base: 'https://api.test', client: server([])));
    state.chats = [
      chat('b', 'Seene mein dard', 1, 'emergency', 'Yeh emergency ho sakti hai'),
      chat('c', 'Chai le lo chai', 5, 'unclear'),
    ];
    await tester.pumpWidget(CareCompassApp(state: state));
    await settle(tester);
    const lang = Lang.hinglish;

    // a new chat today, still open
    await tester.enterText(find.byType(TextField), 'Bukhar hai');
    await tester.pump();
    await tester.tap(find.byTooltip('Bhejein'));
    await settle(tester);
    await tester.tap(find.byTooltip(tm(lang, M.chats)));
    await settle(tester);

    Finder inSidebar(String text) => find.descendant(of: find.byType(Drawer), matching: find.text(text));
    double y(String text) => tester.getTopLeft(inSidebar(text)).dy;
    final order = [
      tm(lang, M.groupToday),
      'Bukhar hai',
      tm(lang, M.groupYesterday),
      'Seene mein dard',
      tm(lang, M.groupEarlier),
      'Chai le lo chai',
    ];
    for (var i = 1; i < order.length; i++) {
      expect(y(order[i - 1]), lessThan(y(order[i])), reason: '${order[i - 1]} above ${order[i]}');
    }

    // what each came to: an emergency in the danger colour, "Samajh nahi aaya"
    expect(tester.widget<Text>(inSidebar('Yeh emergency ho sakti hai')).style!.color, CC.light.sindoor);
    expect(inSidebar(tm(lang, M.chatUnclear)), findsOneWidget);
    expect(inSidebar(tm(lang, M.chatPending)), findsOneWidget);

    // the open chat is the selected row
    final selected = find.descendant(
      of: find.byType(Drawer),
      matching: find.byWidgetPredicate((w) => w is Semantics && w.properties.selected == true),
    );
    expect(selected, findsOneWidget);
    expect(tester.widget<Semantics>(selected).properties.label, startsWith('Bukhar hai'));
  });
}
