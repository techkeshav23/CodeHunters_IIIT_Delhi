// End-to-end UI flow on a phone-sized screen with the HTTP layer mocked by
// real captured responses: question -> answer -> decision -> booking, the
// "nothing understood" card, the UI following the script, and the emergency
// takeover.

import 'dart:convert';
import 'dart:io';

import 'package:carecompass/api.dart';
import 'package:carecompass/i18n.dart';
import 'package:carecompass/main.dart';
import 'package:carecompass/models.dart';
import 'package:carecompass/state.dart';
import 'package:carecompass/ui/dial.dart';
import 'package:carecompass/ui/emergency.dart';
import 'package:carecompass/ui/thread.dart';
import 'package:carecompass/util.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

String fx(String name) => File('test/fixtures/$name').readAsStringSync();

http.Response jsonRes(String body, [int status = 200]) =>
    http.Response.bytes(utf8.encode(body), status, headers: {'content-type': 'application/json'});

MockClient server() => MockClient((req) async {
  if (req.url.path == '/v1/labels') return jsonRes(fx('labels.json'));
  if (req.url.path == '/v1/bookings') return jsonRes(fx('booking.json'), 201);
  if (req.url.path == '/health') return jsonRes(fx('health.json'));
  final body = jsonDecode(req.body) as Map<String, dynamic>;
  final input = (body['user_input'] as String).toLowerCase();
  if (input.contains('seene')) return jsonRes(fx('v2_triage_emergency.json'));
  final history = body['conversation_history'] as List;
  return jsonRes(fx(history.isEmpty ? 'triage_followup.json' : 'triage_final.json'));
});

Future<void> settle(WidgetTester tester, [int frames = 12]) async {
  for (var i = 0; i < frames; i++) {
    await tester.pump(const Duration(milliseconds: 150));
  }
}

void main() {
  setUp(() {});

  testWidgets('question -> answer -> decision -> booking', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 2.625;
    addTearDown(tester.view.reset);

    final state = AppState(
      api: ApiClient(base: 'https://api.test', client: server()),
    );
    await tester.pumpWidget(CareCompassApp(state: state));
    await settle(tester);

    expect(find.text('Batayein, kya taklif hai?'), findsOneWidget);
    expect(find.text('Jaanch'), findsOneWidget);

    // tap the first example: it is sent straight away
    final ex1 = find.text('Papa ko do din se bukhar hai aur khansi bhi');
    await tester.scrollUntilVisible(ex1, 200, scrollable: find.byType(Scrollable).first);
    await tester.tap(ex1);
    await settle(tester);

    expect(find.text('Kya saans lene mein dikkat ho rahi hai?'), findsOneWidget);
    expect(find.text('Sawaal 1 / 3'), findsOneWidget);
    expect(find.text('Haan'), findsOneWidget);

    await tester.tap(find.text('Nahi'));
    await settle(tester, 20);

    expect(find.text('Humara sujhav'), findsNothing, reason: 'no label above the care title');
    expect(find.text('Paramedic ghar aakar check karenge'), findsOneWidget);

    final list = find.byType(Scrollable).first;
    await tester.scrollUntilVisible(find.text('Ravi Kumar'), 200, scrollable: list);
    await settle(tester);
    expect(find.text('(95%)'), findsOneWidget); // the match score sits in the "Match kaise hua" toggle
    expect(find.text('Sabse sahi'), findsOneWidget);

    // "Match kaise hua" breakdown: the skill bar is the needed skill, the
    // rating shows its stars (4.8), not the roster-scaled 85%
    await tester.tap(find.text('Match kaise hua').first);
    await settle(tester);
    expect(find.text('Zaroori skill'), findsOneWidget);
    expect(find.text('85%'), findsNothing);
    expect(find.text('4.8'), findsNWidgets(2));

    // book the best match
    await tester.ensureVisible(find.text('Book karein').first);
    await settle(tester, 4);
    await tester.tap(find.text('Book karein').first);
    await settle(tester);
    expect(find.text('Booking pakki karein'), findsOneWidget);
    await tester.tap(find.text('Pakki karein'));
    await settle(tester);
    expect(find.text('Booking pakki ho gayi'), findsOneWidget);
    expect(find.textContaining('BK_'), findsOneWidget);
    expect(state.bookings, hasLength(1));

    await tester.tap(find.text('Meri bookings dekhein'));
    await settle(tester);
    expect(state.tab, 1);
    expect(find.text('Meri bookings'), findsOneWidget);
    expect(find.text('Ravi Kumar'), findsOneWidget);
  });

  testWidgets('model-first decision: who decided, safety net, safety checks, add more details', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 2.625;
    addTearDown(tester.view.reset);

    final sent = <Map<String, dynamic>>[];
    final client = MockClient((req) async {
      if (req.url.path == '/v1/labels') return jsonRes(fx('labels.json'));
      if (req.url.path == '/health') return jsonRes(fx('health.json'));
      final body = jsonDecode(req.body) as Map<String, dynamic>;
      sent.add(body);
      final input = (body['user_input'] as String).toLowerCase();
      if (input.contains('seene')) return jsonRes(fx('v3_triage_emergency.json'));
      final history = body['conversation_history'] as List;
      return jsonRes(fx(history.isEmpty ? 'v3_triage_danger.json' : 'v3_triage_final.json'));
    });
    final state = AppState(api: ApiClient(base: 'https://api.test', client: client));
    await tester.pumpWidget(CareCompassApp(state: state));
    await settle(tester);

    final ex1 = find.text('Papa ko do din se bukhar hai aur khansi bhi');
    await tester.scrollUntilVisible(ex1, 200, scrollable: find.byType(Scrollable).first);
    await tester.tap(ex1);
    await settle(tester);

    // danger-signs question: two big yes/no targets
    expect(find.text('Sawaal 1 / 4'), findsOneWidget);
    expect(find.text('Haan'), findsOneWidget);
    expect(tester.getSize(find.ancestor(of: find.text('Nahi'), matching: find.byType(Container)).first).height,
        greaterThanOrEqualTo(58));
    await tester.tap(find.text('Nahi'));
    await settle(tester, 20);

    // safety-net advice under the reason; who decided is in "Yeh faisla kyon?"
    expect(find.textContaining('112 par call kijiye'), findsOneWidget);
    expect(find.textContaining('tay kiya'), findsNothing);

    // why: who decided (in words), structured chips and the safety checks, the fired one first
    await tester.ensureVisible(find.text('Yeh faisla kyon?'));
    await settle(tester, 4);
    await tester.tap(find.text('Yeh faisla kyon?'));
    await settle(tester);
    expect(find.text('MuRIL model aur suraksha niyamon ne tay kiya · Pakka bharosa'), findsOneWidget);
    // "who" from the words only ("Papa"), not the model's guess ("Buzurg") or a stand-in age
    expect(find.text('Papa'), findsOneWidget);
    expect(find.text('Buzurg'), findsNothing);
    expect(find.text('70y'), findsNothing);
    expect(find.text('Suraksha jaanch'), findsOneWidget);
    expect(find.textContaining('Laagu hua · 70 saal'), findsOneWidget);
    // the passed checks fold into one row that opens to the full list
    expect(find.text('Suraksha jaal (khatre ke niyam)'), findsNothing);
    final passed = find.textContaining(RegExp(r'^\d+ suraksha jaanch theek rahin$'));
    await tester.ensureVisible(passed);
    await settle(tester, 4);
    await tester.tap(passed);
    await settle(tester);
    final firedY = tester.getTopLeft(find.text('Buzurg, bachche ya pregnancy ka niyam')).dy;
    final passY = tester.getTopLeft(find.text('Suraksha jaal (khatre ke niyam)')).dy;
    expect(firedY, lessThan(passY));

    // anything else to add: the box gets focus and the next send carries the earlier turns
    await tester.ensureVisible(find.text('Kuch aur batana hai?'));
    await settle(tester, 4);
    await tester.tap(find.text('Kuch aur batana hai?'));
    await settle(tester);
    expect(state.addingDetails, isTrue);
    expect(find.text('Pichhli baat ke saath jodkar dobara dekhenge'), findsOneWidget);
    expect(tester.widget<TextField>(find.byType(TextField)).focusNode!.hasFocus, isTrue);
    await tester.enterText(find.byType(TextField), 'aur ulti bhi ho rahi hai');
    await tester.pump();
    await tester.tap(find.byTooltip('Bhejein'));
    await settle(tester, 20);
    final history = (sent.last['conversation_history'] as List).cast<Map<String, dynamic>>();
    expect(sent.last['user_input'], 'aur ulti bhi ho rahi hai');
    expect(history.first['content'], 'Papa ko do din se bukhar hai aur khansi bhi');
    expect(history.last, {'role': 'user', 'content': 'Nahi'});
    expect(find.text('Pichhli baat ke saath jodkar dobara dekhenge'), findsNothing);

    // an emergency the safety net raised: the takeover goes straight from the title to the 112 call
    await tester.enterText(find.byType(TextField), 'Mummy ke seene mein dard hai');
    await tester.pump();
    await tester.tap(find.byTooltip('Bhejein'));
    await settle(tester);
    expect(find.text('Abhi call karein'), findsOneWidget);
    expect(find.text('Humari suraksha jaanch ne ise emergency maana'), findsNothing);

    // back in the chat, the earlier decisions can no longer be booked
    await tester.tap(find.text('Wapas'));
    await settle(tester);
    await tester.scrollUntilVisible(find.text('Book karein').first, -200, scrollable: find.byType(Scrollable).first);
    await settle(tester, 4);
    expect(find.text(t(Lang.hinglish, K.bookLocked)), findsWidgets);
    final bookButtons = find.ancestor(of: find.text('Book karein'), matching: find.byWidgetPredicate((w) => w is FilledButton));
    expect(bookButtons, findsWidgets);
    expect(tester.widgetList<FilledButton>(bookButtons).every((b) => !b.enabled), isTrue);
    await tester.tap(find.text('Book karein').first, warnIfMissed: false);
    await settle(tester);
    expect(find.text('Booking pakki karein'), findsNothing);
  });

  testWidgets('quick pick in one tap; decision card: title with Sunaiye, reason, one caregiver, calm links',
      (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 2.625;
    addTearDown(tester.view.reset);

    final client = MockClient((req) async {
      if (req.url.path == '/v1/labels') return jsonRes(fx('labels.json'));
      if (req.url.path == '/health') return jsonRes(fx('health.json'));
      final history = (jsonDecode(req.body) as Map<String, dynamic>)['conversation_history'] as List;
      return jsonRes(fx(history.isEmpty ? 'v3_triage_danger.json' : 'v3_triage_final.json'));
    });
    final state = AppState(api: ApiClient(base: 'https://api.test', client: client));
    await tester.pumpWidget(CareCompassApp(state: state));
    await settle(tester);

    // six quick picks; one tap sends the pick's sentence
    expect(find.text(t(Lang.hinglish, K.pickElder)), findsNothing);
    expect(find.text(t(Lang.hinglish, K.pickBp)), findsNothing);
    await tester.ensureVisible(find.text('Bukhar'));
    await settle(tester, 4);
    await tester.tap(find.text('Bukhar'));
    await settle(tester);
    expect(state.messages.whereType<UserMsg>().map((m) => m.text), ['Bukhar hai']);
    expect(find.text('Sawaal 1 / 4'), findsOneWidget);

    // answer options are rounded rectangles, not pills
    final option = find.ancestor(of: find.text('Nahi'), matching: find.byType(Container)).first;
    expect((tester.widget<Container>(option).decoration! as BoxDecoration).borderRadius, BorderRadius.circular(16));
    await tester.tap(find.text('Nahi'));
    await settle(tester, 20);

    // the card: care title with "Sunaiye" beside it, the reason in full, the safety-net box; no chips
    Finder inCard(String text) => find.descendant(of: find.byType(DecisionCard), matching: find.text(text));
    double top(Finder f) => tester.getTopLeft(f).dy;
    final title = inCard('Paramedic ghar aakar check karenge');
    final reason = inCard('2 din se bukhar aur khansi, saans ki dikkat nahi hai. Aaj ek paramedic ghar aakar check karenge.');
    final speak = inCard(t(Lang.hinglish, K.readAloud));
    expect(speak, findsOneWidget);
    expect(top(speak), lessThan(tester.getBottomLeft(title).dy), reason: 'beside the care title');
    expect(tester.widget<Text>(reason).maxLines, isNull);
    expect(top(title), lessThan(top(reason)));
    expect(top(reason), lessThan(top(find.textContaining('112 par call kijiye'))));
    expect(find.text('3 din se'), findsNothing, reason: 'no duration chip');
    expect(find.textContaining('tay kiya'), findsNothing, reason: 'who decided is in the why panel');

    // one calm row of links; the why panel starts with who decided, no model %
    final why = inCard('Yeh faisla kyon?');
    final fresh = inCard('Nayi chat');
    expect(inCard('Kuch aur batana hai?'), findsOneWidget);
    expect(fresh, findsOneWidget);
    expect(inCard('Nayi jaanch'), findsNothing);
    await tester.ensureVisible(why);
    await settle(tester, 4);
    await tester.tap(why);
    await settle(tester);
    expect(find.text('MuRIL model aur suraksha niyamon ne tay kiya · Pakka bharosa'), findsOneWidget);
    expect(find.textContaining('Model ka bharosa'), findsNothing);
    await tester.tap(why);
    await settle(tester);

    // one caregiver, bookable; "Aur 2 dekhein" shows the others
    expect(find.text('Naveen Sharma'), findsOneWidget);
    expect(find.text('Rahul Gupta'), findsNothing);
    expect(find.text('Sabse sahi'), findsOneWidget);
    expect(find.text('Book karein'), findsOneWidget);
    final more = find.text('Aur 2 dekhein');
    await tester.ensureVisible(more);
    await settle(tester, 4);
    await tester.tap(more);
    await settle(tester);
    expect(find.text('Rahul Gupta'), findsOneWidget);
    expect(find.text('Rahul Bisht'), findsOneWidget);
    expect(find.text('Book karein'), findsNWidgets(3));
    expect(more, findsNothing);

    // "+ Nayi chat" starts over
    await tester.ensureVisible(fresh);
    await settle(tester, 4);
    await tester.tap(fresh);
    await settle(tester);
    expect(state.messages, isEmpty);
    expect(find.text('Batayein, kya taklif hai?'), findsOneWidget);
  });

  testWidgets('an out-of-scope reply is not counted as a question', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 2.625;
    addTearDown(tester.view.reset);

    final client = MockClient((req) async {
      if (req.url.path == '/v1/labels') return jsonRes(fx('labels.json'));
      if (req.url.path == '/health') return jsonRes(fx('health.json'));
      return jsonRes(fx('v3_triage_scope.json'));
    });
    final state = AppState(api: ApiClient(base: 'https://api.test', client: client));
    await tester.pumpWidget(CareCompassApp(state: state));
    await settle(tester);

    await tester.enterText(find.byType(TextField), 'kal mausam kaisa rahega?');
    await tester.pump();
    await tester.tap(find.byTooltip('Bhejein'));
    await settle(tester);
    expect(find.textContaining('Main sirf sehat ki dekhbhal'), findsOneWidget);
    expect(find.textContaining('Sawaal'), findsNothing);
  });

  testWidgets('nothing understood: a plain card with a doctor or a new chat, no dial', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 2.625;
    addTearDown(tester.view.reset);

    // the real reply after three answers the backend could not read
    final client = MockClient((req) async {
      if (req.url.path == '/v1/labels') return jsonRes(fx('labels.json'));
      if (req.url.path == '/health') return jsonRes(fx('health.json'));
      return jsonRes(fx('v3_triage_unclear_final_en.json'));
    });
    final state = AppState(api: ApiClient(base: 'https://api.test', client: client));
    await tester.pumpWidget(CareCompassApp(state: state));
    await settle(tester);

    await tester.enterText(find.byType(TextField), 'chai le lo chai');
    await tester.pump();
    await tester.tap(find.byTooltip('Bhejein'));
    await settle(tester);

    expect(find.text('Maaf kijiye, hum samajh nahi paaye'), findsOneWidget);
    expect(
      find.text('Koi taklif ho to doctor se phone par baat kar sakte hain, ya nayi chat shuru karein.'),
      findsOneWidget,
    );
    // none of the normal decision card
    expect(find.byType(Dial), findsNothing);
    expect(find.text('Humara sujhav'), findsNothing);
    expect(find.text('Talk to a doctor (teleconsultation)'), findsNothing);
    expect(find.text('Today'), findsNothing, reason: 'no urgency chip');
    expect(find.textContaining('tay kiya'), findsNothing, reason: 'no "decided by" line');
    expect(find.textContaining('call 112 right away'), findsNothing, reason: 'no safety-net box');
    expect(find.text('Yeh faisla kyon?'), findsNothing);
    expect(find.text('Kuch aur batana hai?'), findsNothing);
    expect(find.text(t(Lang.hinglish, K.carersTitle)), findsNothing);
    expect(state.chats.single.outcome, 'unclear');

    // "Doctor se baat karein" shows this reply's caregivers, bookable as usual
    await tester.tap(find.text('Doctor se baat karein'));
    await settle(tester);
    final book = find.text('Book karein').first;
    await tester.scrollUntilVisible(book, 200, scrollable: find.byType(Scrollable).first);
    await Scrollable.ensureVisible(tester.element(book), alignment: 0.5); // clear of the text box
    await settle(tester, 4);
    expect(find.text(t(Lang.hinglish, K.carersTitle)), findsOneWidget);
    await tester.tap(book);
    await settle(tester);
    expect(find.text('Booking pakki karein'), findsOneWidget);
    await tester.tap(find.text('Wapas').last);
    await settle(tester);

    // in the sidebar it reads "Samajh nahi aaya"
    await tester.tap(find.byTooltip('Chats'));
    await settle(tester);
    expect(find.text('Samajh nahi aaya'), findsOneWidget);
    await tester.tap(find.text('chai le lo chai').last);
    await settle(tester);

    // "Nayi chat" starts over
    await Scrollable.ensureVisible(tester.element(find.text('Nayi chat')), alignment: 0.5);
    await settle(tester, 4);
    await tester.tap(find.text('Nayi chat'));
    await settle(tester);
    expect(state.messages, isEmpty);
    expect(find.text('Batayein, kya taklif hai?'), findsOneWidget);
  });

  testWidgets('the UI follows the script; a repeated helper line is shown once', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400 * 3); // the whole thread stays built
    tester.view.devicePixelRatio = 2.625;
    addTearDown(tester.view.reset);

    // real replies to "चाय ले लो चाय" and two more answers it could not read
    final client = MockClient((req) async {
      if (req.url.path == '/v1/labels') return jsonRes(fx('labels.json'));
      if (req.url.path == '/health') return jsonRes(fx('health.json'));
      final body = jsonDecode(req.body) as Map<String, dynamic>;
      final history = body['conversation_history'] as List;
      if (!hasDevanagari(body['user_input'] as String)) return jsonRes(fx('v3_triage_danger.json'));
      return jsonRes(fx(history.isEmpty ? 'v3_triage_unclear_hi.json' : 'v3_triage_unclear_again_hi.json'));
    });
    final state = AppState(api: ApiClient(base: 'https://api.test', client: client));
    await tester.pumpWidget(CareCompassApp(state: state));
    await settle(tester);
    expect(find.text('Jaanch'), findsOneWidget);

    Future<void> say(String text) async {
      await tester.enterText(find.byType(TextField), text);
      await tester.pump();
      await tester.tap(find.byTooltip(t(state.lang, K.send)));
      await settle(tester);
    }

    // Devanagari: the whole UI turns Hindi, the language button says so
    await say('चाय ले लो चाय');
    expect(state.lang, Lang.hi);
    expect(find.text('जाँच'), findsOneWidget);
    expect(find.text('हिंदी'), findsOneWidget);

    await say('अब्बा डब्बा जब्बा');
    await say('ला ला ला');
    expect(find.byType(QuestionCard), findsNWidgets(3));
    const helper = 'अभी साफ़ नहीं है कि तकलीफ़ क्या है, इसलिए एक सवाल।';
    expect(find.text(helper), findsOneWidget, reason: 'only on the first of three cards that share it');
    expect(find.textContaining('माफ़ कीजिए, मैं समझ नहीं पाया।'), findsOneWidget);
    expect(find.textContaining('माफ़ कीजिए, अभी भी समझ नहीं आया।'), findsNWidgets(2), reason: 'questions always show');

    // Roman again: back to Hinglish
    await say('Papa ko bukhar hai');
    expect(state.lang, Lang.hinglish);
    expect(find.text('Jaanch'), findsOneWidget);
    expect(find.text('Hinglish'), findsOneWidget);
  });

  testWidgets('emergency opens the red takeover with 112, 102, 108', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 2.625;
    addTearDown(tester.view.reset);

    final state = AppState(
      api: ApiClient(base: 'https://api.test', client: server()),
    );
    await tester.pumpWidget(CareCompassApp(state: state));
    await settle(tester);

    await tester.enterText(find.byType(TextField), 'Mummy ke seene mein dard hai aur pasina aa raha hai');
    await tester.pump();
    await tester.tap(find.byTooltip('Bhejein'));
    await settle(tester);

    expect(find.text('Yeh emergency ho sakti hai'), findsOneWidget);
    expect(find.text('112'), findsWidgets);
    expect(find.text('Abhi call karein'), findsOneWidget);
    expect(find.text('102'), findsOneWidget);
    expect(find.text('108'), findsOneWidget);
    expect(find.text('Tab tak kya karein'), findsOneWidget);
    expect(find.text('Book karein'), findsNothing);

    // back to the chat: the emergency stays in the thread with a call button
    await tester.tap(find.text('Wapas'));
    await settle(tester);
    expect(find.text('Abhi 112 par call karein'), findsOneWidget);

    // that button dials 112 itself; tapping the card title opens the full screen again
    const launcher = MethodChannel('plugins.flutter.io/url_launcher');
    final dialled = <Object?>[];
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(launcher, (call) async {
      dialled.add((call.arguments as Map)['url']);
      return true;
    });
    addTearDown(() => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(launcher, null));
    await tester.tap(find.text('Abhi 112 par call karein'));
    await settle(tester);
    expect(dialled, ['tel:112']);
    expect(find.byType(EmergencyTakeover), findsNothing);
    await tester.tap(find.text('Yeh emergency ho sakti hai'));
    await settle(tester);
    expect(find.byType(EmergencyTakeover), findsOneWidget);
  });
}
