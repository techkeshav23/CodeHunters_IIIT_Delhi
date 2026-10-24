// The consult flow against a mocked HTTP server that replays real responses:
// history is built exactly like the web client, errors are never turned
// into results, and bookings are saved.

import 'dart:convert';
import 'dart:io';

import 'package:carecompass/api.dart';
import 'package:carecompass/state.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

String fx(String name) => File('test/fixtures/$name').readAsStringSync();

http.Response jsonRes(String body, [int status = 200]) =>
    http.Response.bytes(utf8.encode(body), status, headers: {'content-type': 'application/json'});

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('follow-up, answer, decision, booking', () async {
    final requests = <http.Request>[];
    final client = MockClient((req) async {
      requests.add(req);
      if (req.url.path == '/v1/bookings') return jsonRes(fx('booking.json'), 201);
      final body = jsonDecode(req.body) as Map<String, dynamic>;
      final history = body['conversation_history'] as List;
      return jsonRes(fx(history.isEmpty ? 'triage_followup.json' : 'triage_final.json'));
    });
    final state = AppState(
      api: ApiClient(base: 'https://api.test', client: client),
    );

    final q = await state.send('papa ko do din se bukhar hai aur khansi bhi');
    expect(q, isA<QuestionMsg>());
    expect(requests.single.url.toString(), 'https://api.test/v1/triage?explain=true&policy=safety');
    expect(state.history.map((h) => h.toJson()).toList(), [
      {'role': 'user', 'content': 'papa ko do din se bukhar hai aur khansi bhi'},
      {'role': 'assistant', 'content': 'Kya saans lene mein dikkat ho rahi hai?', 'question_id': 'q_breathing'},
    ]);
    expect(state.answering, isTrue);

    final d = await state.send('Nahi');
    expect(d, isA<DecisionMsg>());
    final sent = jsonDecode(requests.last.body) as Map<String, dynamic>;
    expect(sent['user_input'], 'Nahi');
    expect(sent['language'], 'auto');
    expect((sent['conversation_history'] as List).last, containsPair('question_id', 'q_breathing'));
    expect(state.history, isEmpty, reason: 'a final decision starts a fresh conversation');
    expect(state.messages.map((m) => m.runtimeType.toString()), ['UserMsg', 'QuestionMsg', 'UserMsg', 'DecisionMsg']);

    final res = (d as DecisionMsg).res;
    final saved = await state.book(res.trace.caregivers.first, res, 'gate 2');
    expect(saved.bookingId, startsWith('BK_'));
    expect(state.bookings.first.bookingId, saved.bookingId);
    final bookingBody = jsonDecode(requests.last.body) as Map<String, dynamic>;
    expect(bookingBody, {
      'caregiver_id': 'DEV_CG_003',
      'slot': '2026-10-24T16:00:00+05:30',
      'care_type': 'paramedic_home_visit',
      'urgency': 'same_day',
      'note': 'gate 2',
    });
  });

  test('emergency response becomes an EmergencyMsg and clears history', () async {
    final client = MockClient((_) async => jsonRes(fx('v2_triage_emergency.json')));
    final state = AppState(
      api: ApiClient(base: 'https://api.test', client: client),
    );
    final m = await state.send('Mummy ke seene mein dard hai aur pasina aa raha hai');
    expect(m, isA<EmergencyMsg>());
    expect((m as EmergencyMsg).userText, 'Mummy ke seene mein dard hai aur pasina aa raha hai');
    expect(state.history, isEmpty);
  });

  test('a failed request shows an error with retry, never a result', () async {
    var fail = true;
    final client = MockClient((_) async => fail ? http.Response('oops', 500) : jsonRes(fx('triage_followup.json')));
    final state = AppState(
      api: ApiClient(base: 'https://api.test', client: client),
    );

    final e = await state.send('papa ko bukhar hai');
    expect(e, isA<ErrorMsg>());
    expect(state.history, isEmpty);
    expect(state.last, isNull);
    expect(state.messages.whereType<DecisionMsg>(), isEmpty);

    fail = false;
    final again = await state.retry(e as ErrorMsg);
    expect(again, isA<QuestionMsg>());
    expect(state.messages.whereType<ErrorMsg>(), isEmpty);
    expect(state.messages.whereType<UserMsg>(), hasLength(1), reason: 'retry does not repeat the bubble');
  });

  test('a failed booking throws so the sheet can show the error', () async {
    final client = MockClient(
      (req) async => req.url.path == '/v1/bookings'
          ? http.Response('{"detail":"unknown"}', 404)
          : jsonRes(fx('triage_final.json')),
    );
    final state = AppState(
      api: ApiClient(base: 'https://api.test', client: client),
    );
    final d = await state.send('x') as DecisionMsg;
    expect(() => state.book(d.res.trace.caregivers.first, d.res, ''), throwsA(isA<ApiException>()));
    expect(state.bookings, isEmpty);
  });
}
