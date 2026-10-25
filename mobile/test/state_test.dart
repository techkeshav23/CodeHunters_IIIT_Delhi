// The consult flow against a mocked HTTP server that replays real responses:
// history is built exactly like the web client, errors are never turned
// into results, and bookings are saved.

import 'dart:convert';
import 'dart:io';

import 'package:carecompass/api.dart';
import 'package:carecompass/models.dart';
import 'package:carecompass/state.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

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
    expect(requests.single.url.toString(), 'https://api.test/v1/triage?explain=true&policy=conversational');
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

  test('"Aur jaankari jodein" sends the earlier conversation with the next message', () async {
    final requests = <Map<String, dynamic>>[];
    final client = MockClient((req) async {
      final body = jsonDecode(req.body) as Map<String, dynamic>;
      requests.add(body);
      final history = body['conversation_history'] as List;
      return jsonRes(fx(history.isEmpty ? 'v3_triage_danger.json' : 'v3_triage_final.json'));
    });
    final state = AppState(
      api: ApiClient(base: 'https://api.test', client: client),
    );

    await state.send('papa ko do din se bukhar hai aur khansi bhi');
    final d = await state.send('Nahi') as DecisionMsg;
    expect(state.history, isEmpty);
    expect(state.addingDetails, isFalse);

    state.addMoreDetails(d);
    expect(state.addingTo, d.id);
    expect(state.addingDetails, isTrue);
    expect(state.history.map((h) => h.toJson()).toList(), [
      {'role': 'user', 'content': 'papa ko do din se bukhar hai aur khansi bhi'},
      {
        'role': 'assistant',
        'content': 'Kya inme se kuch hai: saans phoolna, behoshi, seene mein dard, ya bahut tez bukhar?',
        'question_id': 'q_danger',
      },
      {'role': 'user', 'content': 'Nahi'},
    ]);

    final again = await state.send('aur ulti bhi ho rahi hai');
    expect(again, isA<DecisionMsg>());
    final sent = requests.last;
    expect(sent['user_input'], 'aur ulti bhi ho rahi hai');
    final h = (sent['conversation_history'] as List).cast<Map<String, dynamic>>();
    expect(h.where((e) => e['role'] == 'user').map((e) => e['content']), [
      'papa ko do din se bukhar hai aur khansi bhi',
      'Nahi',
    ]);
    expect(state.addingTo, isNull);
    expect(state.history, isEmpty, reason: 'the new decision starts fresh again');

    // cancelling puts things back to a fresh case
    state.addMoreDetails(again as DecisionMsg);
    expect(state.history, isNotEmpty);
    state.cancelAddMore();
    expect(state.history, isEmpty);
    expect(state.addingDetails, isFalse);

    // a new chat also forgets it
    state.addMoreDetails(again);
    state.newChat();
    expect(state.addingTo, isNull);
    expect(state.history, isEmpty);
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

  test('the UI follows the script the person writes in', () async {
    SharedPreferences.setMockInitialValues({});
    final sent = <Map<String, dynamic>>[];
    // real replies: Devanagari is read as "hi", "chai le lo chai" as "en"
    final client = MockClient((req) async {
      if (req.url.path == '/health') return jsonRes(fx('health.json'));
      final body = jsonDecode(req.body) as Map<String, dynamic>;
      sent.add(body);
      return jsonRes(fx(switch (body['user_input']) {
        'चाय ले लो चाय' => 'v3_triage_unclear_hi.json',
        'chai le lo chai' => 'v3_triage_unclear_en.json',
        _ => 'v3_triage_danger.json', // "hinglish"
      }));
    });
    final state = AppState(api: ApiClient(base: 'https://api.test', client: client));
    await state.load();
    addTearDown(() async {
      await pumpEventQueue(); // let the first health check finish
      state.dispose();
    });
    final prefs = await SharedPreferences.getInstance();
    expect(state.lang, Lang.hinglish);

    // Devanagari: Hindi, saved like the language button
    await state.send('चाय ले लो चाय');
    expect(state.lang, Lang.hi);
    expect(prefs.getString('cc_lang'), 'hi');

    // Roman on a Hindi UI: Hinglish, even when the reply reads it as English
    await state.send('chai le lo chai');
    expect(state.lang, Lang.hinglish);
    expect(prefs.getString('cc_lang'), 'hinglish');

    // never Hinglish <-> English on its own
    await state.send('chai le lo chai');
    expect(state.lang, Lang.hinglish);
    state.setLang(Lang.en);
    await state.send('Papa ko bukhar hai');
    expect(state.lang, Lang.en, reason: 'the button choice stays while the script is the same');
    await state.send('चाय ले लो चाय');
    expect(state.lang, Lang.hi);

    expect(sent.map((b) => b['language']).toSet(), {'auto'}, reason: 'the request is unchanged');
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
