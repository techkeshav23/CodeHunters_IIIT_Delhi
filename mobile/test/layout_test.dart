// Quality floor: every screen lays out without overflow on a small phone
// (360 x 740 dp) at text scale 1.3, in all three languages and both themes.
// The test font is wider than the real ones, so passing here leaves margin.

import 'dart:convert';
import 'dart:io';

import 'package:carecompass/api.dart';
import 'package:carecompass/i18n.dart';
import 'package:carecompass/main.dart';
import 'package:carecompass/models.dart';
import 'package:carecompass/state.dart';
import 'package:carecompass/strings_mobile.dart';
import 'package:carecompass/util.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

String fx(String name) => File('test/fixtures/$name').readAsStringSync();

http.Response jsonRes(String body, [int status = 200]) =>
    http.Response.bytes(utf8.encode(body), status, headers: {'content-type': 'application/json'});

/// [fixture] as the backend sends it to someone writing in [lang]: the UI
/// follows trace.language, so a Hindi screen needs "hi" replies.
http.Response reply(String fixture, Lang lang) {
  final j = jsonDecode(fx(fixture)) as Map<String, dynamic>;
  (j['trace'] as Map<String, dynamic>)['language'] = lang.code;
  return jsonRes(jsonEncode(j));
}

MockClient server(Lang lang) => MockClient((req) async {
  if (req.url.path == '/v1/labels') return jsonRes(fx('labels.json'));
  if (req.url.path == '/v1/bookings') return jsonRes(fx('booking.json'), 201);
  final body = jsonDecode(req.body) as Map<String, dynamic>;
  final input = (body['user_input'] as String).toLowerCase();
  if (input.contains('seene')) return reply('triage_emergency.json', lang);
  final history = body['conversation_history'] as List;
  return reply(history.isEmpty ? 'triage_followup.json' : 'v2_triage_specialist.json', lang);
});

/// The model-first server: danger-signs question, then a decision with every
/// new trace field; an out-of-scope reply; an emergency the safety net raised.
MockClient modelFirstServer(Lang lang) => MockClient((req) async {
  if (req.url.path == '/v1/labels') return jsonRes(fx('labels.json'));
  final body = jsonDecode(req.body) as Map<String, dynamic>;
  final input = (body['user_input'] as String).toLowerCase();
  if (input.contains('seene')) return reply('v3_triage_emergency.json', lang);
  if (input.contains('mausam')) return reply('v3_triage_scope.json', lang);
  final history = body['conversation_history'] as List;
  return reply(history.isEmpty ? 'v3_triage_danger.json' : 'v3_triage_final.json', lang);
});

Future<void> settle(WidgetTester tester, [int frames = 12]) async {
  for (var i = 0; i < frames; i++) {
    await tester.pump(const Duration(milliseconds: 150));
  }
}

void main() {
  for (final lang in Lang.values) {
    for (final theme in [ThemePref.light, ThemePref.dark]) {
      testWidgets('all screens at 360dp, text x1.3, ${lang.code}, ${theme.name}', (tester) async {
        tester.view.physicalSize = const Size(360 * 3, 740 * 3);
        tester.view.devicePixelRatio = 3;
        tester.platformDispatcher.textScaleFactorTestValue = 1.3;
        addTearDown(tester.view.reset);
        addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);

        final state = AppState(
          api: ApiClient(base: 'https://api.test', client: server(lang)),
        );
        state.setLang(lang);
        state.setTheme(theme);
        state.setLargeText(true); // x1.18 on top of the system 1.3
        await tester.pumpWidget(CareCompassApp(state: state));
        await settle(tester);

        // start -> question -> decision (teleconsult with specialty)
        Future<void> tapIt(Finder f) async {
          if (f.evaluate().isEmpty) {
            await tester.scrollUntilVisible(f, 150, scrollable: find.byType(Scrollable).first);
          }
          await tester.ensureVisible(f);
          await settle(tester, 6);
          await tester.tap(f);
          await settle(tester);
        }

        await tapIt(find.text(t(lang, K.ex1)));
        await tapIt(find.text('Nahi'));
        await settle(tester, 10);
        await tapIt(find.text(t(lang, K.whyThis)));
        await tapIt(find.text(t(lang, K.matchHow)).first);
        await tapIt(find.text(t(lang, K.book)).first);
        await tapIt(find.text(t(lang, K.confirm)));
        await tapIt(find.text(t(lang, K.close)));
        await tapIt(find.text(tm(lang, M.seeMore, {'n': 2}))); // the other two caregivers

        // other tabs
        for (final k in [K.navBookings, K.navSosShort, K.navHowShort, K.navSettings]) {
          await tester.tap(find.text(t(lang, k)).last);
          await settle(tester);
          final list = find.byType(Scrollable).first;
          await tester.drag(list, const Offset(0, -3000));
          await settle(tester, 4);
        }

        // emergency takeover
        await tester.tap(find.text(t(lang, K.navCheck)).last);
        await settle(tester);
        await tester.enterText(find.byType(TextField), 'Mummy ke seene mein dard hai aur pasina aa raha hai');
        await tester.pump();
        await tester.tap(find.byTooltip(t(lang, K.send)));
        await settle(tester);
        expect(find.text(t(lang, K.callNow)), findsOneWidget);
        await tester.drag(find.byType(Scrollable).last, const Offset(0, -3000));
        await settle(tester, 4);
      });

      testWidgets('model-first decision at 360dp, text x1.3, ${lang.code}, ${theme.name}', (tester) async {
        tester.view.physicalSize = const Size(360 * 3, 740 * 3);
        tester.view.devicePixelRatio = 3;
        tester.platformDispatcher.textScaleFactorTestValue = 1.3;
        addTearDown(tester.view.reset);
        addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);

        final state = AppState(
          api: ApiClient(base: 'https://api.test', client: modelFirstServer(lang)),
        );
        state.setLang(lang);
        state.setTheme(theme);
        state.setLargeText(true);
        await tester.pumpWidget(CareCompassApp(state: state));
        await settle(tester);

        Future<void> tapIt(Finder f) async {
          if (f.evaluate().isEmpty) {
            await tester.scrollUntilVisible(f, 150, scrollable: find.byType(Scrollable).first);
          }
          await tester.ensureVisible(f);
          await settle(tester, 6);
          await tester.tap(f);
          await settle(tester);
        }

        Future<void> say(String text) async {
          await tester.enterText(find.byType(TextField), text);
          await tester.pump();
          await tester.tap(find.byTooltip(t(lang, K.send)));
          await settle(tester);
        }

        // danger-signs question -> decision with model line, safety net, safety checks
        await tapIt(find.text(t(lang, K.ex1)));
        await tapIt(find.text('Nahi'));
        await settle(tester, 10);
        await tapIt(find.text(t(lang, K.whyThis)));
        expect(find.text(decidedByText(state.last!.res.trace, lang)!), findsOneWidget); // top of the why panel
        expect(find.text(tm(lang, M.safetyChecks)), findsOneWidget);
        await tester.drag(find.byType(Scrollable).first, const Offset(0, -3000));
        await settle(tester, 4);

        // add more details: the note above the box, then send
        await tapIt(find.text(tm(lang, M.addMore)));
        expect(find.text(tm(lang, M.addMoreNote)), findsOneWidget);
        await say('aur ulti bhi ho rahi hai');

        // an out-of-scope reply, then an emergency the safety net raised
        await say('kal mausam kaisa rahega?');
        await say('Mummy ke seene mein dard hai');
        expect(find.text(t(lang, K.callNow)), findsOneWidget); // the takeover leads with the 112 call
        await tester.drag(find.byType(Scrollable).last, const Offset(0, -3000));
        await settle(tester, 4);
      });

      testWidgets('chat sidebar, incognito and history at 360dp, text x1.3, ${lang.code}, ${theme.name}', (tester) async {
        tester.view.physicalSize = const Size(360 * 3, 740 * 3);
        tester.view.devicePixelRatio = 3;
        tester.platformDispatcher.textScaleFactorTestValue = 1.3;
        addTearDown(tester.view.reset);
        addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);

        final state = AppState(
          api: ApiClient(base: 'https://api.test', client: server(lang)),
        );
        state.setLang(lang);
        state.setTheme(theme);
        state.setLargeText(true);
        await tester.pumpWidget(CareCompassApp(state: state));
        await settle(tester);

        // the top bar: ☰, brand, the full language name, 112 (both pills 44 dp tall)
        expect(find.byTooltip(tm(lang, M.chats)), findsOneWidget);
        expect(find.text(langShort[lang]!), findsOneWidget);
        for (final pill in [langShort[lang]!, '112']) {
          expect(tester.getSize(find.ancestor(of: find.text(pill), matching: find.byType(Container)).first).height, 44);
        }

        Future<void> say(String text) async {
          await tester.enterText(find.byType(TextField), text);
          await tester.pump();
          await tester.ensureVisible(find.byTooltip(t(lang, K.send))); // below the fold on the start view
          await settle(tester, 4);
          await tester.tap(find.byTooltip(t(lang, K.send)));
          await settle(tester);
        }

        Future<void> tapIt(Finder f) async {
          await tester.ensureVisible(f);
          await settle(tester, 4);
          await tester.tap(f);
          await settle(tester);
        }

        Future<void> openSidebar() => tapIt(find.byTooltip(tm(lang, M.chats)));
        // the decision card has its own "+ Nayi chat" too
        final newChat = find.descendant(of: find.byType(Drawer), matching: find.text(tm(lang, M.newChat)));

        // three chats: a decision, a pending question, an emergency
        await say(t(lang, K.ex1));
        await tapIt(find.text('Nahi'));
        await openSidebar();
        await tapIt(newChat);
        await say(t(lang, K.ex2));
        await openSidebar();
        await tapIt(newChat);
        await say('Mummy ke seene mein dard hai aur pasina aa raha hai');
        await tapIt(find.text(t(lang, K.back)));
        expect(state.chats, hasLength(3));
        await openSidebar();
        await tapIt(newChat);

        // incognito: banner on the start view and in the thread
        await openSidebar();
        await tapIt(find.text(tm(lang, M.incognito)));
        expect(find.text(tm(lang, M.incognitoBanner)), findsOneWidget);
        await say('Bukhar hai');
        expect(find.text(tm(lang, M.incognitoBanner)), findsOneWidget);
        expect(state.chats, hasLength(3));

        // sidebar: rows under "Aaj", delete-all dialog (cancel), delete one, open one
        await openSidebar();
        expect(find.text(tm(lang, M.groupToday)), findsOneWidget);
        expect(find.text(tm(lang, M.chatPending)), findsOneWidget);
        await tapIt(find.text(tm(lang, M.deleteAll)));
        expect(find.text(tm(lang, M.deleteAllTitle)), findsOneWidget);
        await tapIt(find.text(t(lang, K.back)).last);
        await tapIt(find.byTooltip(tm(lang, M.chatMenu)).first);
        await tapIt(find.text(tm(lang, M.chatDelete)));
        expect(state.chats, hasLength(2));
        await tapIt(find.text(t(lang, K.ex1)).last);
        expect(state.incognito, isFalse);
        expect(find.byType(Drawer), findsNothing);
        await tester.drag(find.byType(Scrollable).first, const Offset(0, 3000));
        await settle(tester, 4);

        // this saved chat switched to incognito leaves History
        await openSidebar();
        await tapIt(find.text(tm(lang, M.incognito)));
        expect(find.text(tm(lang, M.incognitoRemoved)), findsOneWidget);
        expect(find.text(tm(lang, M.incognitoBanner)), findsOneWidget);
        expect(state.chats, hasLength(1));

        // delete all, confirmed: the empty state
        await openSidebar();
        await tapIt(find.text(tm(lang, M.deleteAll)));
        await tapIt(find.text(tm(lang, M.deleteYes)));
        expect(state.chats, isEmpty);
        expect(find.text(tm(lang, M.historyEmpty)), findsOneWidget);
      });

      testWidgets('error card at 360dp, text x1.3, ${lang.code}, ${theme.name}', (tester) async {
        tester.view.physicalSize = const Size(360 * 3, 740 * 3);
        tester.view.devicePixelRatio = 3;
        tester.platformDispatcher.textScaleFactorTestValue = 1.3;
        addTearDown(tester.view.reset);
        addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);

        final client = MockClient((req) async {
          if (req.url.path == '/v1/labels') return jsonRes(fx('labels.json'));
          return http.Response('oops', 500);
        });
        final state = AppState(api: ApiClient(base: 'https://api.test', client: client));
        state.setLang(lang);
        state.setTheme(theme);
        state.setLargeText(true);
        await tester.pumpWidget(CareCompassApp(state: state));
        await settle(tester);

        await tester.enterText(find.byType(TextField), 'Bukhar hai');
        await tester.pump();
        await tester.ensureVisible(find.byTooltip(t(lang, K.send)));
        await settle(tester, 4);
        await tester.tap(find.byTooltip(t(lang, K.send)));
        await settle(tester);
        expect(find.text(t(lang, K.retry)), findsOneWidget); // wraps rather than overflows
      });

      testWidgets('nothing-understood card at 360dp, text x1.3, ${lang.code}, ${theme.name}', (tester) async {
        tester.view.physicalSize = const Size(360 * 3, 740 * 3);
        tester.view.devicePixelRatio = 3;
        tester.platformDispatcher.textScaleFactorTestValue = 1.3;
        addTearDown(tester.view.reset);
        addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);

        final client = MockClient((req) async {
          if (req.url.path == '/v1/labels') return jsonRes(fx('labels.json'));
          return reply(lang == Lang.hi ? 'v3_triage_unclear_final_hi.json' : 'v3_triage_unclear_final_en.json', lang);
        });
        final state = AppState(api: ApiClient(base: 'https://api.test', client: client));
        state.setLang(lang);
        state.setTheme(theme);
        state.setLargeText(true);
        await tester.pumpWidget(CareCompassApp(state: state));
        await settle(tester);

        await tester.enterText(find.byType(TextField), 'abba dabba jabba');
        await tester.pump();
        await tester.ensureVisible(find.byTooltip(t(lang, K.send)));
        await settle(tester, 4);
        await tester.tap(find.byTooltip(t(lang, K.send)));
        await settle(tester);

        expect(find.text(tm(lang, M.unclearTitle)), findsOneWidget);
        final doctor = find.text(tm(lang, M.unclearDoctor));
        await tester.ensureVisible(doctor);
        await settle(tester, 4);
        await tester.tap(doctor);
        await settle(tester);
        await tester.drag(find.byType(Scrollable).first, const Offset(0, -3000));
        await settle(tester, 4);
        expect(find.text(t(lang, K.book)), findsWidgets);
      });
    }
  }
}
