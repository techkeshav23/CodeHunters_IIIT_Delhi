// Parses real responses captured from the CareCompass API (test/fixtures).
// v1 fixtures use the original enum values; v2_* use the organisers' values
// (emergency_112 / emergency, teleconsultation, home_nursing, ...).

import 'dart:convert';
import 'dart:io';

import 'package:carecompass/i18n.dart';
import 'package:carecompass/models.dart';
import 'package:carecompass/state.dart';
import 'package:carecompass/strings_mobile.dart';
import 'package:carecompass/util.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, Object?> fixture(String name) =>
    (jsonDecode(File('test/fixtures/$name').readAsStringSync()) as Map).cast<String, Object?>();

TriageResponse triage(String name) => TriageResponse.fromJson(fixture(name));

void main() {
  group('follow-up question (papa ko do din se bukhar hai aur khansi bhi)', () {
    final r = triage('triage_followup.json');

    test('asks one yes/no question with three options', () {
      expect(r.followUpQuestion, 'Kya saans lene mein dikkat ho rahi hai?');
      expect(r.questionText, r.followUpQuestion);
      expect(r.careType, isNull);
      expect(r.urgency, isNull);
      expect(r.matchedCaregivers, isEmpty);
      final fu = r.trace.followUp!;
      expect(fu.id, 'q_breathing');
      expect(fu.kind, 'yes_no');
      expect(fu.options.map((o) => o.label), ['Haan', 'Nahi', 'Pata nahi']);
      expect(fu.options.map((o) => o.value), ['yes', 'no', 'unknown']);
      expect(fu.askedSoFar, 1);
      expect(fu.max, 3);
    });

    test('is not an emergency and carries what was understood', () {
      expect(r.isEmergency, isFalse);
      expect(r.trace.language, Lang.hinglish);
      expect(r.trace.understood.patient.relationLabel, 'Papa');
      expect(r.trace.understood.symptoms.map((s) => s.id), containsAll(['fever', 'cough']));
      expect(r.trace.understood.durationDays, 2);
      expect(r.trace.checks.single.status, CheckStatus.notReported);
    });
  });

  group('final decision after answering "Nahi"', () {
    final r = triage('triage_final.json');

    test('same-day paramedic visit with three ranked caregivers', () {
      expect(r.followUpQuestion, isNull);
      expect(r.careType, 'paramedic_home_visit');
      expect(r.careKind, CareKind.paramedic);
      expect(r.urgency, 'same_day');
      expect(urgencyLevel(r.urgency), 1);
      expect(r.isEmergency, isFalse);
      expect(r.matchedCaregivers, hasLength(3));
      expect(r.trace.caregivers, hasLength(3));
      expect(r.trace.checks.single.status, CheckStatus.absent);
      expect(r.trace.decision.careLabelLocal, isNotEmpty);
      expect(careLabel(r, Lang.hinglish), r.trace.decision.careLabelLocal);
      expect(urgencyLabel(r, Lang.hinglish), 'Aaj hi');
    });

    test('caregiver cards have every field the UI shows', () {
      final cg = r.trace.caregivers.first;
      expect(cg.caregiverId, 'DEV_CG_003');
      expect(cg.name, 'Ravi Kumar');
      expect(cg.role, 'paramedic');
      expect(cg.languages, contains('Hindi'));
      expect(cg.distanceKm, closeTo(1.5, 1e-9));
      expect(cg.nextSlot, startsWith('2026-'));
      expect(cg.nextSlotLabelLocal, isNotEmpty);
      expect(cg.rating, closeTo(4.8, 1e-9));
      expect(cg.score, closeTo(0.95, 1e-9));
      expect(cg.reasonLocal, isNotEmpty);
      final f = cg.features!;
      expect(f.values.keys, ['skill', 'time', 'distance', 'language', 'rating']);
      expect(f.skill, 1.0);
      expect(r.trace.modelProbabilities, isEmpty, reason: 'v1 server had no model block');
      // ranked best first
      final scores = r.trace.caregivers.map((c) => c.score).toList();
      expect(scores, orderedEquals([...scores]..sort((a, b) => b.compareTo(a))));
    });

    test('schema fields round-trip for the judges panel', () {
      final s = r.schemaFields;
      expect(s.keys, ['follow_up_question', 'care_type', 'urgency', 'red_flags', 'reasoning', 'matched_caregivers']);
      expect((s['matched_caregivers'] as List).first, containsPair('caregiver_id', 'DEV_CG_003'));
    });
  });

  group('emergency (Mummy ke seene mein dard hai aur pasina aa raha hai)', () {
    final r = triage('triage_emergency.json');

    test('is an emergency with numbers, steps and the red flag evidence', () {
      expect(r.careType, 'emergency_referral');
      expect(r.careKind, CareKind.emergency);
      expect(r.urgency, 'immediate');
      expect(urgencyLevel(r.urgency), 2);
      expect(r.isEmergency, isTrue);
      expect(r.redFlags, ['chest_pain']);
      expect(r.matchedCaregivers, isEmpty);
      expect(r.trace.caregivers, isEmpty);
      final em = r.trace.emergency!;
      expect(em.titleLocal, 'Yeh emergency ho sakti hai');
      expect(em.numbers.map((n) => n.number), ['112', '102', '108']);
      expect(em.stepsLocal, hasLength(3));
      final flag = r.trace.redFlags.single;
      expect(flag.id, 'chest_pain');
      expect(flag.labelLocal, isNotEmpty);
      expect(flag.evidence, 'seene mein dard');
    });
  });

  group('Hindi (Devanagari) input', () {
    final r = triage('triage_hindi_nurse.json');

    test('keeps Devanagari text intact', () {
      expect(r.trace.language, Lang.hi);
      expect(r.careKind, CareKind.nurse);
      expect(hasDevanagari(r.trace.reasoningLocal), isTrue);
      expect(hasDevanagari(r.trace.decision.careLabelLocal!), isTrue);
      expect(hasDevanagari(r.trace.caregivers.first.nextSlotLabelLocal!), isTrue);
    });
  });

  test('specialist routing exposes the department', () {
    final r = triage('triage_specialist.json');
    expect(r.trace.decision.specialty, 'orthopaedics');
    expect(specialtyLabel(Lang.hinglish, r.trace.decision.specialty!), 'Haddi aur jod (Orthopaedics)');
    expect(specialtyLabel(Lang.en, 'unknown_dept'), 'unknown_dept');
  });

  group('new enum values (organisers\' schema)', () {
    test('emergency_112 / emergency is an emergency', () {
      final r = triage('v2_triage_emergency.json');
      expect(r.careType, 'emergency_112');
      expect(r.urgency, 'emergency');
      expect(r.careKind, CareKind.emergency);
      expect(urgencyLevel(r.urgency), 2);
      expect(r.isEmergency, isTrue);
      expect(r.trace.redFlags.first.labelLocal, isNotEmpty);
    });

    test('teleconsultation keeps the specialty and is a video call', () {
      final r = triage('v2_triage_specialist.json');
      expect(r.careType, 'teleconsultation');
      expect(r.careKind, CareKind.teleconsult);
      expect(isTele(r.careType), isTrue);
      expect(r.isEmergency, isFalse);
      expect(r.trace.decision.specialty, 'orthopaedics');
      expect(roleLabel(r.trace.caregivers.first.role, Lang.en), 'Doctor');
    });

    test('final decision with the organisers\' caregiver roster', () {
      final r = triage('v2_triage_final.json');
      expect(r.trace.modelTopProbability, closeTo(0.506, 1e-9));
      expect(r.careKind, CareKind.paramedic);
      expect(r.trace.caregivers, isNotEmpty);
      expect(roleLabel(r.trace.caregivers.first.role, Lang.hinglish), 'Paramedic');
      expect(roleLabel('phlebotomist', Lang.en), 'Sample collector');
      expect(roleLabel('doctor', Lang.hi), 'डॉक्टर');
      // the older sample roster keeps the web app's labels
      expect(roleLabel('paramedic', Lang.en), 'Paramedic');
      expect(roleLabel('nurse', Lang.en), 'Nurse');
    });

    test('old and new values map to the same internal enum', () {
      expect(careKindOf('nurse'), careKindOf('home_nursing'));
      expect(careKindOf('gp_teleconsult'), careKindOf('teleconsultation'));
      expect(careKindOf('emergency_referral'), careKindOf('emergency_112'));
      expect(careKindOf('lab_test_home'), CareKind.lab);
      expect(careKindOf(null), CareKind.unknown);
      expect(urgencyKindOf('immediate'), urgencyKindOf('emergency'));
      expect(urgencyKindOf('routine'), urgencyKindOf('scheduled'));
      expect(urgencyLevel('scheduled'), 0);
    });

    test('urgency "emergency" alone triggers the emergency screen', () {
      final r = TriageResponse.fromJson({'care_type': 'paramedic_home_visit', 'urgency': 'emergency', 'red_flags': []});
      expect(r.isEmergency, isTrue);
    });

    test('lab_test_home falls back to our label when the API sends none', () {
      final r = TriageResponse.fromJson({'care_type': 'lab_test_home', 'urgency': 'scheduled', 'trace': {}});
      expect(careLabel(r, Lang.hinglish), 'Ghar par sample / lab test');
      expect(careLabel(r, Lang.hi), 'घर पर सैंपल / लैब टेस्ट');
      expect(careLabel(r, Lang.en), 'Home lab test');
      expect(urgencyLabel(r, Lang.hinglish), 'Time fix karke');
      expect(urgencyText(0, Lang.hi), 'समय तय करके');
    });
  });

  test('booking, health and labels parse', () {
    final b = BookingResponse.fromJson(fixture('booking.json'));
    expect(b.bookingId, startsWith('BK_'));
    expect(b.status, 'confirmed');
    expect(b.caregiverName, 'Ravi Kumar');

    final h = HealthResponse.fromJson(fixture('health.json'));
    expect(h.status, 'ok');

    final l = LabelsResponse.fromJson(fixture('labels.json'));
    expect(l.redFlags, isNotEmpty);
    expect(l.allNumbers.first.number, '112');
    expect(l.allNumbers.map((n) => n.number).toSet().length, l.allNumbers.length);
    expect(l.allNumbers.map((n) => n.number), contains('14416'));
  });

  test('missing or odd fields never throw', () {
    final r = TriageResponse.fromJson({
      'follow_up_question': null,
      'care_type': 'something_new',
      'urgency': null,
      'red_flags': null,
      'trace': {
        'caregivers': [
          {'caregiver_id': 'X', 'name': 'A B', 'score': '0.5', 'features': null, 'languages': null},
        ],
        'follow_up': 'not a map',
        'model': 'not a map',
        'structured': 5,
        'guardrails': 'not a list',
        'safety_net_local': '   ',
      },
    });
    expect(r.careKind, CareKind.unknown);
    expect(r.trace.followUp, isNull);
    expect(r.trace.caregivers.single.score, 0.5);
    expect(r.trace.caregivers.single.languages, isEmpty);
    expect(r.isEmergency, isFalse);
    expect(r.trace.speech, isNull);
    expect(r.trace.model, isNull);
    expect(r.trace.structured, isNull);
    expect(r.trace.guardrails, isEmpty);
    expect(r.trace.safetyNetLocal, isNull);
    expect(decidedByText(r.trace, Lang.en), isNull);
  });

  test('odd values inside the model-first fields never throw', () {
    final r = TriageResponse.fromJson({
      'care_type': 'home_nursing',
      'urgency': 'scheduled',
      'trace': {
        'model': {
          'name': null,
          'probabilities': {'nurse': '0.8', 'gp': 'x', 'lab': null},
          'urgency_probabilities': 'x',
          'confidence': 'high',
          'band': 'very_high',
        },
        'decision': {'source': 7},
        'structured': {
          'symptoms': [null, 3, {'id': 'fever'}, {'id': 'cough', 'label': 'Cough'}],
          'who': null,
          'duration_days': 'two',
        },
        'guardrails': [null, 1, {}, {'id': 'urgency_floor', 'status': 'fired'}, {'label': 'Something new'}],
        'safety_net_local': 42,
      },
    });
    final m = r.trace.model!;
    expect(m.probabilities, {'nurse': 0.8});
    expect(m.urgencyProbabilities, isEmpty);
    expect(m.confidence, isNull);
    expect(m.band, isNull);
    expect(m.shortName, isEmpty);
    expect(r.trace.decision.source, '7');
    final st = r.trace.structured!;
    expect(st.symptoms.map((s) => s.labelLocal), ['Cough'], reason: 'entries without any label are dropped');
    expect(st.durationDays, isNull);
    expect(st.whoChip, isNull);
    expect(r.trace.guardrails.map((g) => g.id), ['urgency_floor', '']);
    expect(r.trace.guardrails.first.fired, isTrue);
    expect(r.trace.guardrails.first.labelLocal, 'urgency_floor', reason: 'falls back to the id');
    expect(r.trace.guardrails.last.fired, isFalse);
    expect(r.trace.safetyNetLocal, '42');
    expect(decidedByText(r.trace, Lang.en), isNull, reason: 'unknown source');
  });

  group('model-first trace (fine-tuned MuRIL + safety net)', () {
    test('final decision: model block, source, structured, guardrails, safety net', () {
      final r = triage('v3_triage_final.json');
      expect(r.isEmergency, isFalse);
      expect(r.careKind, CareKind.paramedic);

      final m = r.trace.model!;
      expect(m.name, 'MuRIL (fine-tuned)');
      expect(m.shortName, 'MuRIL');
      expect(m.confidence, closeTo(0.93, 1e-9));
      expect(m.band, ConfidenceBand.high);
      expect(m.probabilities.keys, containsAll(['paramedic', 'nurse', 'lab', 'gp', 'emergency', 'followup', 'out_of_scope']));
      expect(m.urgencyProbabilities['same_day'], closeTo(0.66, 1e-9));
      expect(m.latencyMs, closeTo(41.7, 1e-9));
      expect(m.version, isNotEmpty);
      // the old field still works for the "Model ka bharosa" line
      expect(r.trace.modelProbabilities, m.probabilities);
      expect(r.trace.modelSupportFor(r.careType), closeTo(0.93, 1e-9));

      final d = r.trace.decision;
      expect(d.source, 'model+safety_net');
      expect(d.byModel, isTrue);
      expect(d.bySafetyNet, isTrue);
      expect(d.byLlm, isFalse);

      final st = r.trace.structured!;
      expect(st.symptoms.map((s) => s.id), ['fever', 'cough']);
      expect(st.symptoms.map((s) => s.labelLocal), ['Bukhar', 'Khansi']);
      expect(st.who, 'elderly');
      expect(st.whoChip, 'Buzurg');
      expect(st.durationDays, 3);
      expect(st.ageYears, 70);
      expect(st.isEmpty, isFalse);

      expect(r.trace.guardrails, hasLength(9));
      final fired = r.trace.guardrailsFiredFirst;
      expect(fired.first.id, 'vulnerable_floor');
      expect(fired.first.fired, isTrue);
      expect(fired.first.noteLocal, contains('aaj hi'));
      expect(fired.skip(1).every((g) => !g.fired), isTrue);
      expect(r.trace.raisedBySafetyNet, isFalse, reason: 'the model decided too');

      expect(r.trace.safetyNetLocal, contains('112'));
      expect(decisionSummary(r), endsWith(r.trace.safetyNetLocal!));
    });

    test('"Decided by" line in three languages, band words not percentages', () {
      final r = triage('v3_triage_final.json');
      expect(decidedByText(r.trace, Lang.hinglish), 'MuRIL model aur suraksha niyamon ne tay kiya · Pakka bharosa');
      expect(decidedByText(r.trace, Lang.hi), 'MuRIL मॉडल और सुरक्षा नियमों ने तय किया · पक्का भरोसा');
      expect(decidedByText(r.trace, Lang.en), 'Decided by MuRIL model + safety rules · High confidence');
      for (final l in Lang.values) {
        expect(decidedByText(r.trace, l), isNot(contains('%')));
      }
      expect(bandText(ConfidenceBand.medium, Lang.en), 'Medium confidence');
      expect(bandText(ConfidenceBand.low, Lang.hinglish), 'Kam bharosa');

      final llm = triage('v3_triage_llm.json');
      expect(llm.trace.decision.byLlm, isTrue);
      expect(llm.trace.model!.band, ConfidenceBand.low);
      expect(decidedByText(llm.trace, Lang.en), 'The model was unsure, so Claude did a second check');
      expect(llm.trace.guardrailsFiredFirst.take(2).map((g) => g.id), ['low_confidence', 'llm_fallback']);

      final plain = TriageResponse.fromJson({
        'trace': {
          'model': {'name': 'MuRIL (fine-tuned)', 'band': 'medium'},
          'decision': {'source': 'model'},
        },
      });
      expect(decidedByText(plain.trace, Lang.en), 'Decided by MuRIL model · Medium confidence');
      // a safety rule switched the model's pick (gp -> paramedic): no band for the class it did not choose
      final switched = TriageResponse.fromJson({
        'trace': {
          'model': {
            'name': 'MuRIL (fine-tuned)',
            'band': 'medium',
            'probabilities': {'gp': 0.73, 'paramedic': 0.26},
          },
          'decision': {'source': 'model+safety_net', 'care_type': 'paramedic_home_visit'},
        },
      });
      expect(decidedByText(switched.trace, Lang.en), 'Decided by MuRIL model + safety rules');
      final rules = TriageResponse.fromJson({
        'trace': {
          'decision': {'source': 'rules'},
          'guardrails': [
            {'id': 'safety_net', 'status': 'pass'},
          ],
        },
      });
      expect(decidedByText(rules.trace, Lang.hinglish), 'Niyamon ne tay kiya');
    });

    test('emergency raised by the safety net', () {
      final r = triage('v3_triage_emergency.json');
      expect(r.isEmergency, isTrue);
      expect(r.trace.decision.source, 'safety_net');
      expect(r.trace.raisedBySafetyNet, isTrue);
      expect(emergencyRaisedText(r.trace, Lang.hinglish), tm(Lang.hinglish, M.sosBySafetyNet));
      // the model called it too: say both did, never that the safety check alone raised it
      TriageResponse src(String s) => TriageResponse.fromJson({
        'trace': {
          'decision': {'source': s},
        },
      });
      expect(emergencyRaisedText(src('model+safety_net').trace, Lang.en), t(Lang.en, K.sosBoth));
      expect(src('model+safety_net').trace.raisedBySafetyNet, isFalse);
      expect(emergencyRaisedText(src('model').trace, Lang.en), isNull);
      expect(r.trace.guardrailsFiredFirst.first.id, 'safety_net');
      expect(r.trace.safetyNetLocal, isNull);
      expect(decidedByText(r.trace, Lang.en), 'Decided by safety rules');
    });

    test('danger-signs and out-of-scope follow-ups', () {
      final q = triage('v3_triage_danger.json');
      expect(q.isEmergency, isFalse);
      expect(q.trace.followUp!.id, 'q_danger');
      expect(q.trace.followUp!.options.map((o) => o.label), ['Haan', 'Nahi']);
      expect(q.trace.followUp!.max, 4);
      expect(q.trace.structured!.whoChip, 'Papa');

      final s = triage('v3_triage_scope.json');
      expect(s.trace.followUp!.id, 'q_scope');
      expect(s.trace.followUp!.options, isEmpty);
      expect(s.questionText, isNotNull);
      expect(s.trace.structured!.isEmpty, isTrue, reason: '"unknown" who with no symptoms adds nothing');
    });

    test('older servers: none of the new fields, no "Decided by" line', () {
      for (final name in ['triage_final.json', 'v2_triage_final.json', 'v2_triage_emergency.json', 'triage_followup.json']) {
        final r = triage(name);
        expect(r.trace.structured, isNull, reason: name);
        expect(r.trace.guardrails, isEmpty, reason: name);
        expect(r.trace.safetyNetLocal, isNull, reason: name);
        expect(r.trace.model?.band, isNull, reason: name);
        expect(r.trace.raisedBySafetyNet, isFalse, reason: name);
        expect(decidedByText(r.trace, Lang.en), isNull, reason: name);
      }
      // the v2 model block still parses its probabilities
      expect(triage('v2_triage_final.json').trace.model!.probabilities['paramedic'], closeTo(0.506, 1e-9));
    });
  });

  test('read-aloud text (trace.speech) parses', () {
    final r = TriageResponse.fromJson({
      'trace': {
        'language': 'hinglish',
        'speech': {'locale': 'hi-IN', 'text': 'आज एक पैरामेडिक घर आकर जाँच करेंगे।'},
      },
    });
    expect(r.trace.speech?.locale, 'hi-IN');
    expect(r.trace.speech?.text, startsWith('आज'));
    expect(Speech.fromJson({'text': '  '}), isNull);
  });

  test('request JSON matches the API contract', () {
    const req = TriageRequest(
      userInput: 'Nahi',
      location: LatLng(28.5459, 77.2732),
      conversationHistory: [
        HistoryItem(role: 'user', content: 'papa ko do din se bukhar hai aur khansi bhi'),
        HistoryItem(role: 'assistant', content: 'Kya saans lene mein dikkat ho rahi hai?', questionId: 'q_breathing'),
      ],
    );
    final j = req.toJson();
    expect(j['user_input'], 'Nahi');
    expect(j['language'], 'auto');
    expect(j['location'], {'lat': 28.5459, 'lng': 77.2732});
    final h = j['conversation_history'] as List;
    expect(h.first, {'role': 'user', 'content': 'papa ko do din se bukhar hai aur khansi bhi'});
    expect(h.last, containsPair('question_id', 'q_breathing'));
  });

  test('UI strings exist in all three languages', () {
    for (final k in K.values) {
      for (final l in Lang.values) {
        expect(t(l, k), isNotEmpty, reason: '$k/$l');
      }
    }
    expect(t(Lang.hinglish, K.questionOf, {'n': 1, 'max': 3}), 'Sawaal 1 / 3');
    expect(t(Lang.hinglish, K.urgRoutine), 'Time fix karke');
  });

  test('mobile-only strings exist in all three languages', () {
    for (final k in M.values) {
      for (final l in Lang.values) {
        expect(tm(l, k), isNotEmpty, reason: '$k/$l');
      }
    }
    expect(tm(Lang.hinglish, M.addMore), 'Kuch aur batana hai?');
    expect(tm(Lang.hi, M.addMore), 'कुछ और बताना है?');
    expect(tm(Lang.en, M.addMore), 'Anything else to add?');
    expect(tm(Lang.hi, M.seeMore, {'n': 2}), 'और 2 देखें');
  });
}
