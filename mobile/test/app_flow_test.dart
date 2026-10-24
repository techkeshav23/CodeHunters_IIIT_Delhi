// End-to-end UI flow on a phone-sized screen with the HTTP layer mocked by
// real captured responses: question -> answer -> decision -> booking, and
// the emergency takeover.

import 'dart:convert';
import 'dart:io';

import 'package:carecompass/api.dart';
import 'package:carecompass/main.dart';
import 'package:carecompass/state.dart';
import 'package:flutter/material.dart';
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

    expect(find.text('Humara sujhav'), findsOneWidget);
    expect(find.text('Paramedic ghar aakar check karenge'), findsOneWidget);

    final list = find.byType(Scrollable).first;
    await tester.scrollUntilVisible(find.text('Ravi Kumar'), 200, scrollable: list);
    await settle(tester);
    expect(find.text('95%'), findsOneWidget);
    expect(find.text('Sabse sahi'), findsOneWidget);

    // "Match kaise hua" breakdown
    await tester.tap(find.text('Match kaise hua').first);
    await settle(tester);
    expect(find.text('Kaam ka anubhav'), findsOneWidget);

    // book the best match
    await tester.ensureVisible(find.text('Book karein').first);
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
  });
}
