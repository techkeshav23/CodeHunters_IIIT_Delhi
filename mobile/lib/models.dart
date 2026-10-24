// Dart mirror of web/src/types.ts (the CareCompass API contract, docs/API.md).
// The client is stateless: it sends the whole conversation on every
// /v1/triage call. Parsing is tolerant: unknown fields are ignored and missing
// optional fields become null or empty, so a backend addition never crashes
// the app.

enum Lang { hi, hinglish, en }

Lang langFromCode(String? code, {Lang fallback = Lang.hinglish}) {
  switch (code) {
    case 'hi':
      return Lang.hi;
    case 'hinglish':
      return Lang.hinglish;
    case 'en':
      return Lang.en;
  }
  return fallback;
}

extension LangCode on Lang {
  String get code => switch (this) {
    Lang.hi => 'hi',
    Lang.hinglish => 'hinglish',
    Lang.en => 'en',
  };
}

// ---- enum values: the API accepts the organisers' new names and our old ----
// ---- ones may still appear, so both map to one internal enum.          ----

enum CareKind { paramedic, nurse, lab, teleconsult, specialist, emergency, unknown }

CareKind careKindOf(String? v) {
  switch (v) {
    case 'paramedic_home_visit':
      return CareKind.paramedic;
    case 'home_nursing':
    case 'nurse':
    case 'nurse_home_visit':
      return CareKind.nurse;
    case 'lab_test_home':
      return CareKind.lab;
    case 'teleconsultation':
    case 'gp_teleconsult':
      return CareKind.teleconsult;
    case 'specialist':
    case 'specialist_consult':
      return CareKind.specialist;
    case 'emergency_112':
    case 'emergency_referral':
      return CareKind.emergency;
  }
  return CareKind.unknown;
}

enum UrgencyKind { scheduled, sameDay, emergency }

/// "scheduled"/"routine" -> scheduled, "same_day" -> sameDay,
/// "emergency"/"immediate" -> emergency. Unknown values count as scheduled.
UrgencyKind urgencyKindOf(String? v) {
  switch (v) {
    case 'emergency':
    case 'immediate':
      return UrgencyKind.emergency;
    case 'same_day':
      return UrgencyKind.sameDay;
  }
  return UrgencyKind.scheduled;
}

// ---- small JSON helpers ----

String _s(Object? v, [String fallback = '']) => v is String ? v : (v == null ? fallback : v.toString());
String? _sn(Object? v) => v == null ? null : (v is String ? v : v.toString());
double? _dn(Object? v) => v is num ? v.toDouble() : (v is String ? double.tryParse(v) : null);
double _d(Object? v, [double fallback = 0]) => _dn(v) ?? fallback;
int _i(Object? v, [int fallback = 0]) => v is num ? v.toInt() : (v is String ? int.tryParse(v) ?? fallback : fallback);
bool? _bn(Object? v) => v is bool ? v : null;
List<Object?> _l(Object? v) => v is List ? v : const [];
Map<String, Object?> _m(Object? v) => v is Map ? v.cast<String, Object?>() : const {};
List<String> _ls(Object? v) => _l(v).where((e) => e != null).map((e) => e.toString()).toList();

class LatLng {
  final double lat;
  final double lng;
  const LatLng(this.lat, this.lng);
  Map<String, Object?> toJson() => {'lat': lat, 'lng': lng};
}

class HistoryItem {
  final String role; // "user" | "assistant"
  final String content;
  final String? questionId;
  const HistoryItem({required this.role, required this.content, this.questionId});

  Map<String, Object?> toJson() => {
    'role': role,
    'content': content,
    if (questionId != null) 'question_id': questionId,
  };
}

class TriageRequest {
  final String userInput;
  final String language; // "auto" | Lang code
  final LatLng? location;
  final List<HistoryItem> conversationHistory;
  const TriageRequest({
    required this.userInput,
    this.language = 'auto',
    this.location,
    this.conversationHistory = const [],
  });

  Map<String, Object?> toJson() => {
    'user_input': userInput,
    'language': language,
    'location': location?.toJson(),
    'conversation_history': conversationHistory.map((h) => h.toJson()).toList(),
  };
}

class MatchedCaregiver {
  final String caregiverId;
  final double score;
  final String reason;
  const MatchedCaregiver({required this.caregiverId, required this.score, required this.reason});
  factory MatchedCaregiver.fromJson(Map<String, Object?> j) =>
      MatchedCaregiver(caregiverId: _s(j['caregiver_id']), score: _d(j['score']), reason: _s(j['reason']));
  Map<String, Object?> toJson() => {'caregiver_id': caregiverId, 'score': score, 'reason': reason};
}

// ---- trace (explain=true) ----

class Patient {
  final String? relation;
  final String? relationLabel;
  final double? ageYears;
  final String? ageGroup;
  final bool? pregnant;
  const Patient({this.relation, this.relationLabel, this.ageYears, this.ageGroup, this.pregnant});
  factory Patient.fromJson(Map<String, Object?> j) => Patient(
    relation: _sn(j['relation']),
    relationLabel: _sn(j['relation_label']),
    ageYears: _dn(j['age_years']),
    ageGroup: _sn(j['age_group']),
    pregnant: _bn(j['pregnant']),
  );
}

/// Shape shared by symptoms, services and severity entries.
class LabelItem {
  final String id;
  final String label;
  final String labelLocal;
  const LabelItem({required this.id, required this.label, required this.labelLocal});
  factory LabelItem.fromJson(Map<String, Object?> j) {
    final label = _s(j['label']);
    return LabelItem(id: _s(j['id']), label: label, labelLocal: _s(j['label_local'], label));
  }
}

class Understood {
  final Patient patient;
  final List<LabelItem> symptoms;
  final double? durationDays;
  final String? durationLabel;
  final List<LabelItem> services;
  final List<LabelItem> severity;
  const Understood({
    this.patient = const Patient(),
    this.symptoms = const [],
    this.durationDays,
    this.durationLabel,
    this.services = const [],
    this.severity = const [],
  });
  factory Understood.fromJson(Map<String, Object?> j) => Understood(
    patient: Patient.fromJson(_m(j['patient'])),
    symptoms: _l(j['symptoms']).map((e) => LabelItem.fromJson(_m(e))).toList(),
    durationDays: _dn(j['duration_days']),
    durationLabel: _sn(j['duration_label']),
    services: _l(j['services']).map((e) => LabelItem.fromJson(_m(e))).toList(),
    severity: _l(j['severity']).map((e) => LabelItem.fromJson(_m(e))).toList(),
  );
}

enum CheckStatus { present, absent, notReported }

class Check {
  final String id;
  final String label;
  final String labelLocal;
  final CheckStatus status;
  const Check({required this.id, required this.label, required this.labelLocal, required this.status});
  factory Check.fromJson(Map<String, Object?> j) {
    final label = _s(j['label']);
    final st = switch (_s(j['status'])) {
      'present' => CheckStatus.present,
      'absent' => CheckStatus.absent,
      _ => CheckStatus.notReported,
    };
    return Check(id: _s(j['id']), label: label, labelLocal: _s(j['label_local'], label), status: st);
  }
}

class RedFlag {
  final String id;
  final String label;
  final String labelLocal;
  final String evidence;
  const RedFlag({required this.id, required this.label, required this.labelLocal, required this.evidence});
  factory RedFlag.fromJson(Map<String, Object?> j) {
    final label = _s(j['label']);
    return RedFlag(id: _s(j['id']), label: label, labelLocal: _s(j['label_local'], label), evidence: _s(j['evidence']));
  }
}

class Decision {
  final String? careType;
  final String? urgency;
  final String? careLabel;
  final String? careLabelLocal;
  final String? urgencyLabel;
  final String? urgencyLabelLocal;
  final double confidence;
  final String source;
  final String rule;
  final String? specialty;
  const Decision({
    this.careType,
    this.urgency,
    this.careLabel,
    this.careLabelLocal,
    this.urgencyLabel,
    this.urgencyLabelLocal,
    this.confidence = 0,
    this.source = '',
    this.rule = '',
    this.specialty,
  });
  factory Decision.fromJson(Map<String, Object?> j) => Decision(
    careType: _sn(j['care_type']),
    urgency: _sn(j['urgency']),
    careLabel: _sn(j['care_label']),
    careLabelLocal: _sn(j['care_label_local']),
    urgencyLabel: _sn(j['urgency_label']),
    urgencyLabelLocal: _sn(j['urgency_label_local']),
    confidence: _d(j['confidence']),
    source: _s(j['source']),
    rule: _s(j['rule']),
    specialty: _sn(j['specialty']),
  );
}

class FollowUpOption {
  final String value;
  final String label;
  const FollowUpOption({required this.value, required this.label});
  factory FollowUpOption.fromJson(Map<String, Object?> j) =>
      FollowUpOption(value: _s(j['value']), label: _s(j['label']));
}

class FollowUp {
  final String id;
  final String text;
  final String kind; // yes_no | choice | free_text
  final List<FollowUpOption> options;
  final int askedSoFar;
  final int max;
  const FollowUp({
    required this.id,
    required this.text,
    required this.kind,
    required this.options,
    required this.askedSoFar,
    required this.max,
  });
  factory FollowUp.fromJson(Map<String, Object?> j) => FollowUp(
    id: _s(j['id']),
    text: _s(j['text']),
    kind: _s(j['kind'], 'free_text'),
    options: _l(j['options']).map((e) => FollowUpOption.fromJson(_m(e))).toList(),
    askedSoFar: _i(j['asked_so_far'], 1),
    max: _i(j['max'], 3),
  );
}

class EmergencyNumber {
  final String label;
  final String labelLocal;
  final String number;
  const EmergencyNumber({required this.label, required this.labelLocal, required this.number});
  factory EmergencyNumber.fromJson(Map<String, Object?> j) {
    final label = _s(j['label']);
    return EmergencyNumber(label: label, labelLocal: _s(j['label_local'], label), number: _s(j['number']));
  }

  /// Digits only, for a tel: URI ("1800-116-117" -> "1800116117").
  String get dialable => number.replaceAll(RegExp(r'[^0-9+]'), '');
}

class Emergency {
  final String title;
  final String titleLocal;
  final List<EmergencyNumber> numbers;
  final List<String> steps;
  final List<String> stepsLocal;
  const Emergency({
    required this.title,
    required this.titleLocal,
    required this.numbers,
    required this.steps,
    required this.stepsLocal,
  });
  factory Emergency.fromJson(Map<String, Object?> j) {
    final title = _s(j['title']);
    return Emergency(
      title: title,
      titleLocal: _s(j['title_local'], title),
      numbers: _l(j['numbers']).map((e) => EmergencyNumber.fromJson(_m(e))).toList(),
      steps: _ls(j['steps']),
      stepsLocal: _ls(j['steps_local']),
    );
  }
}

/// The 0-1 sub-scores behind a match, in the order the API sent them
/// (skill, time, distance, language, rating today; any new key is kept).
class MatchFeatures {
  final Map<String, double> values;
  const MatchFeatures(this.values);
  factory MatchFeatures.fromJson(Map<String, Object?> j) {
    final out = <String, double>{};
    j.forEach((k, v) {
      final d = _dn(v);
      if (d != null) out[k] = d;
    });
    return MatchFeatures(out);
  }
  double? operator [](String key) => values[key];
  double? get skill => values['skill'];
  double? get time => values['time'];
  double? get distance => values['distance'];
  double? get language => values['language'];
  double? get rating => values['rating'];
  bool get isEmpty => values.isEmpty;
}

class TraceCaregiver {
  final String caregiverId;
  final String name;
  final String role;
  final List<String> languages;
  final List<String> skills;
  final double? distanceKm;
  final String? nextSlot;
  final String? nextSlotLabel;
  final String? nextSlotLabelLocal;
  final double? rating;
  final double score;
  final String reason;
  final String reasonLocal;
  final MatchFeatures? features;

  /// Optional availability window ("09:00"-"15:00") if the API sends one.
  final String? freeFrom;
  final String? freeUntil;
  const TraceCaregiver({
    required this.caregiverId,
    required this.name,
    required this.role,
    this.languages = const [],
    this.skills = const [],
    this.distanceKm,
    this.nextSlot,
    this.nextSlotLabel,
    this.nextSlotLabelLocal,
    this.rating,
    this.score = 0,
    this.reason = '',
    this.reasonLocal = '',
    this.features,
    this.freeFrom,
    this.freeUntil,
  });
  factory TraceCaregiver.fromJson(Map<String, Object?> j) {
    final reason = _s(j['reason']);
    final f = j['features'];
    return TraceCaregiver(
      caregiverId: _s(j['caregiver_id']),
      name: _s(j['name']),
      role: _s(j['role']),
      languages: _ls(j['languages']),
      skills: _ls(j['skills']),
      distanceKm: _dn(j['distance_km']),
      nextSlot: _sn(j['next_slot']),
      nextSlotLabel: _sn(j['next_slot_label']),
      nextSlotLabelLocal: _sn(j['next_slot_label_local']) ?? _sn(j['next_slot_label']),
      rating: _dn(j['rating']),
      score: _d(j['score']),
      reason: reason,
      reasonLocal: _s(j['reason_local'], reason),
      features: f is Map ? MatchFeatures.fromJson(_m(f)) : null,
      freeFrom: _sn(j['free_from']),
      freeUntil: _sn(j['free_until']),
    );
  }
}

/// What to read aloud and in which voice (trace.speech): Devanagari with
/// "hi-IN" for Hindi and Hinglish, "en-IN" for English. [alt] is the on-screen
/// text, read with an English voice when the phone has no Hindi voice.
class Speech {
  final String text;
  final String locale;
  final String? alt;
  const Speech(this.text, this.locale, {this.alt});

  static Speech? fromJson(Object? j) {
    if (j is! Map) return null;
    final m = _m(j);
    final text = _s(m['text']).trim();
    if (text.isEmpty) return null;
    final locale = _s(m['locale']);
    return Speech(text, locale.isEmpty ? 'hi-IN' : locale);
  }
}

class Trace {
  final String version;
  final Lang language;
  final Understood understood;
  final List<Check> checks;
  final List<RedFlag> redFlags;
  final Decision decision;
  final String reasoningLocal;
  final FollowUp? followUp;
  final Emergency? emergency;
  final List<TraceCaregiver> caregivers;
  final Speech? speech;
  final double timingMs;

  /// trace.model.probabilities (class -> probability), when a model ran.
  final Map<String, double> modelProbabilities;
  const Trace({
    this.version = '',
    this.language = Lang.hinglish,
    this.understood = const Understood(),
    this.checks = const [],
    this.redFlags = const [],
    this.decision = const Decision(),
    this.reasoningLocal = '',
    this.followUp,
    this.emergency,
    this.caregivers = const [],
    this.speech,
    this.timingMs = 0,
    this.modelProbabilities = const {},
  });

  /// Highest model probability (0-1), or null when no model output came back.
  double? get modelTopProbability =>
      modelProbabilities.isEmpty ? null : modelProbabilities.values.reduce((a, b) => a > b ? a : b);

  /// The model's probability for the class that was decided (care type, or "followup"),
  /// so the line backs up what the user sees; falls back to the top probability.
  double? modelSupportFor(String? careType, {bool followUp = false}) {
    if (modelProbabilities.isEmpty) return null;
    final c = (careType ?? '').toLowerCase();
    final cls = followUp
        ? 'followup'
        : c.startsWith('emergency')
            ? 'emergency'
            : c.contains('lab')
                ? 'lab'
                : c.contains('nurs')
                    ? 'nurse'
                    : c.contains('paramedic')
                        ? 'paramedic'
                        : (c.contains('teleconsult') || c.contains('specialist') || c == 'gp')
                            ? 'gp'
                            : null;
    return (cls != null ? modelProbabilities[cls] : null) ?? modelTopProbability;
  }
  factory Trace.fromJson(Map<String, Object?> j) {
    final fu = j['follow_up'];
    final em = j['emergency'];
    return Trace(
      version: _s(j['version']),
      language: langFromCode(_sn(j['language'])),
      understood: Understood.fromJson(_m(j['understood'])),
      checks: _l(j['checks']).map((e) => Check.fromJson(_m(e))).toList(),
      redFlags: _l(j['red_flags']).map((e) => RedFlag.fromJson(_m(e))).toList(),
      decision: Decision.fromJson(_m(j['decision'])),
      reasoningLocal: _s(j['reasoning_local']),
      followUp: fu is Map ? FollowUp.fromJson(_m(fu)) : null,
      emergency: em is Map ? Emergency.fromJson(_m(em)) : null,
      caregivers: _l(j['caregivers']).map((e) => TraceCaregiver.fromJson(_m(e))).toList(),
      speech: Speech.fromJson(j['speech']),
      timingMs: _d(j['timing_ms']),
      modelProbabilities: _m(_m(j['model'])['probabilities']).map((k, v) => MapEntry(k, _d(v))),
    );
  }
}

class TriageResponse {
  final String? followUpQuestion;
  final String? careType;
  final String? urgency;
  final List<String> redFlags;
  final String reasoning;
  final List<MatchedCaregiver> matchedCaregivers;
  final Trace trace;

  /// The raw body, kept for the "For judges: the API" panel.
  final Map<String, Object?> raw;

  const TriageResponse({
    this.followUpQuestion,
    this.careType,
    this.urgency,
    this.redFlags = const [],
    this.reasoning = '',
    this.matchedCaregivers = const [],
    this.trace = const Trace(),
    this.raw = const {},
  });

  factory TriageResponse.fromJson(Map<String, Object?> j) => TriageResponse(
    followUpQuestion: _sn(j['follow_up_question']),
    careType: _sn(j['care_type']),
    urgency: _sn(j['urgency']),
    redFlags: _ls(j['red_flags']),
    reasoning: _s(j['reasoning']),
    matchedCaregivers: _l(j['matched_caregivers']).map((e) => MatchedCaregiver.fromJson(_m(e))).toList(),
    trace: Trace.fromJson(_m(j['trace'])),
    raw: j,
  );

  /// The six schema fields only (what automated scoring sees).
  Map<String, Object?> get schemaFields => {
    'follow_up_question': followUpQuestion,
    'care_type': careType,
    'urgency': urgency,
    'red_flags': redFlags,
    'reasoning': reasoning,
    'matched_caregivers': matchedCaregivers.map((m) => m.toJson()).toList(),
  };

  /// Emergency when the care type or urgency says so (old or new enum
  /// values), or, like the web client, when the trace carries an emergency
  /// block or any red flag.
  bool get isEmergency =>
      careKindOf(careType) == CareKind.emergency ||
      urgencyKindOf(urgency) == UrgencyKind.emergency ||
      trace.emergency != null ||
      redFlags.isNotEmpty;

  CareKind get careKind => careKindOf(careType ?? trace.decision.careType);
  UrgencyKind? get urgencyKind =>
      urgency == null && trace.decision.urgency == null ? null : urgencyKindOf(urgency ?? trace.decision.urgency);

  /// Text of the follow-up question, if this response asks one.
  String? get questionText {
    final q = followUpQuestion ?? trace.followUp?.text;
    return (q == null || q.trim().isEmpty) ? null : q;
  }
}

// ---- bookings ----

class BookingRequest {
  final String caregiverId;
  final String? slot;
  final String? careType;
  final String? urgency;
  final String note;
  const BookingRequest({required this.caregiverId, this.slot, this.careType, this.urgency, this.note = ''});
  Map<String, Object?> toJson() => {
    'caregiver_id': caregiverId,
    'slot': slot,
    'care_type': careType,
    'urgency': urgency,
    'note': note,
  };
}

class BookingResponse {
  final String bookingId;
  final String status;
  final String caregiverId;
  final String caregiverName;
  final String? slot;
  final String createdAt;
  const BookingResponse({
    required this.bookingId,
    required this.status,
    required this.caregiverId,
    required this.caregiverName,
    this.slot,
    required this.createdAt,
  });
  factory BookingResponse.fromJson(Map<String, Object?> j) => BookingResponse(
    bookingId: _s(j['booking_id']),
    status: _s(j['status']),
    caregiverId: _s(j['caregiver_id']),
    caregiverName: _s(j['caregiver_name']),
    slot: _sn(j['slot']),
    createdAt: _s(j['created_at']),
  );
}

/// A booking saved on this phone (mirrors web lib.ts SavedBooking).
class SavedBooking {
  final String bookingId;
  final String caregiverId;
  final String caregiverName;
  final String role;
  final String? slotLabel;
  final String? careLabel;
  final String? urgencyLabel;
  final String createdAt;
  const SavedBooking({
    required this.bookingId,
    required this.caregiverId,
    required this.caregiverName,
    required this.role,
    this.slotLabel,
    this.careLabel,
    this.urgencyLabel,
    required this.createdAt,
  });
  factory SavedBooking.fromJson(Map<String, Object?> j) => SavedBooking(
    bookingId: _s(j['booking_id']),
    caregiverId: _s(j['caregiver_id']),
    caregiverName: _s(j['caregiver_name']),
    role: _s(j['role']),
    slotLabel: _sn(j['slot_label']),
    careLabel: _sn(j['care_label']),
    urgencyLabel: _sn(j['urgency_label']),
    createdAt: _s(j['created_at']),
  );
  Map<String, Object?> toJson() => {
    'booking_id': bookingId,
    'caregiver_id': caregiverId,
    'caregiver_name': caregiverName,
    'role': role,
    'slot_label': slotLabel,
    'care_label': careLabel,
    'urgency_label': urgencyLabel,
    'created_at': createdAt,
  };
}

class HealthResponse {
  final String status;
  final String version;
  final String? caregiversSource;
  final int? caregivers;
  final String? model;
  const HealthResponse({
    required this.status,
    required this.version,
    this.caregiversSource,
    this.caregivers,
    this.model,
  });
  factory HealthResponse.fromJson(Map<String, Object?> j) => HealthResponse(
    status: _s(j['status']),
    version: _s(j['version']),
    caregiversSource: _sn(j['caregivers_source']),
    caregivers: j['caregivers'] is num ? (j['caregivers'] as num).toInt() : null,
    model: _sn(j['model']),
  );
}

// ---- /v1/labels (SOS tab) ----

class LabelsRedFlag {
  final String id;
  final String label;
  final String labelHinglish;
  final String labelHi;
  const LabelsRedFlag({required this.id, required this.label, required this.labelHinglish, required this.labelHi});
  factory LabelsRedFlag.fromJson(Map<String, Object?> j) {
    final label = _s(j['label']);
    return LabelsRedFlag(
      id: _s(j['id']),
      label: label,
      labelHinglish: _s(j['label_hinglish'], label),
      labelHi: _s(j['label_hi'], label),
    );
  }
  String labelFor(Lang lang) => switch (lang) {
    Lang.hi => labelHi,
    Lang.hinglish => labelHinglish,
    Lang.en => label,
  };
}

class LabelsNumber {
  final String label;
  final String labelHi;
  final String number;
  const LabelsNumber({required this.label, required this.labelHi, required this.number});
  factory LabelsNumber.fromJson(Map<String, Object?> j) {
    final label = _s(j['label']);
    return LabelsNumber(label: label, labelHi: _s(j['label_hi'], label), number: _s(j['number']));
  }
  String get dialable => number.replaceAll(RegExp(r'[^0-9+]'), '');
}

class LabelsResponse {
  final List<LabelsRedFlag> redFlags;
  final List<LabelsNumber> emergencyNumbers;
  final Map<String, LabelsNumber> helplines;
  const LabelsResponse({required this.redFlags, required this.emergencyNumbers, required this.helplines});
  factory LabelsResponse.fromJson(Map<String, Object?> j) => LabelsResponse(
    redFlags: _l(j['red_flags']).map((e) => LabelsRedFlag.fromJson(_m(e))).toList(),
    emergencyNumbers: _l(j['emergency_numbers']).map((e) => LabelsNumber.fromJson(_m(e))).toList(),
    helplines: _m(j['helplines']).map((k, v) => MapEntry(k, LabelsNumber.fromJson(_m(v)))),
  );

  /// Same fallback the web client uses when /v1/labels cannot be reached.
  static const LabelsResponse fallback = LabelsResponse(
    redFlags: [],
    emergencyNumbers: [
      LabelsNumber(label: 'Emergency (all India)', labelHi: 'Emergency (poore Bharat mein)', number: '112'),
      LabelsNumber(label: 'Ambulance in Delhi (CATS, free)', labelHi: 'Delhi ambulance (CATS, free)', number: '102'),
      LabelsNumber(label: 'Ambulance in many states', labelHi: 'Kai rajyon mein ambulance', number: '108'),
    ],
    helplines: {
      'self_harm_risk': LabelsNumber(
        label: 'Tele-MANAS mental health helpline',
        labelHi: 'Tele-MANAS helpline',
        number: '14416',
      ),
      'poisoning': LabelsNumber(
        label: 'AIIMS Poisons Information Centre',
        labelHi: 'AIIMS zeher helpline',
        number: '1800-116-117',
      ),
    },
  );

  /// All numbers to show on the SOS tab, de-duplicated, 112 first.
  List<LabelsNumber> get allNumbers {
    final seen = <String>{};
    final out = <LabelsNumber>[];
    for (final n in [...emergencyNumbers, ...helplines.values]) {
      if (n.number.isEmpty || !seen.add(n.number)) continue;
      out.add(n);
    }
    return out;
  }
}
