// Parses real responses captured from the CareCompass API (test/fixtures).
// v1 fixtures use the original enum values; v2_* use the organisers' values
// (emergency_112 / emergency, teleconsultation, home_nursing, ...).

import 'dart:convert';
import 'dart:io';

import 'package:carecompass/i18n.dart';
import 'package:carecompass/models.dart';
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
      expect(roleLabel(r.trace.caregivers.first.role, Lang.hinglish), 'Medic (nurse)');
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
      },
    });
    expect(r.careKind, CareKind.unknown);
    expect(r.trace.followUp, isNull);
    expect(r.trace.caregivers.single.score, 0.5);
    expect(r.trace.caregivers.single.languages, isEmpty);
    expect(r.isEmergency, isFalse);
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
    expect(t(Lang.hinglish, K.urgRoutine), 'Kuch dinon mein');
  });
}
