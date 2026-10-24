// Small display helpers, ported from web/src/lib.ts. Formatting only: no
// triage logic lives in the app.

import 'dart:ui';

import 'i18n.dart';
import 'models.dart';
import 'strings_mobile.dart';

String initials(String name) {
  final parts = name.replaceFirst(RegExp(r'^dr\.?\s+', caseSensitive: false), '').trim().split(RegExp(r'\s+'));
  final first = parts.isNotEmpty && parts.first.isNotEmpty ? parts.first[0] : '';
  final last = parts.length > 1 && parts.last.isNotEmpty ? parts.last[0] : '';
  return (first + last).toUpperCase();
}

// Avatar colours stay inside the palette: neem, deep teal, haldi-brown, plum-slate.
const _avatar = [
  Color(0xFF0D5A50),
  Color(0xFF21706A),
  Color(0xFF9A6A00),
  Color(0xFF5B4A6B),
  Color(0xFF3D6B4F),
  Color(0xFF7A4B2A),
];

Color avatarColor(String seed) {
  var h = 0;
  for (final ch in seed.codeUnits) {
    h = (h * 31 + ch) & 0xFFFFFFFF;
  }
  return _avatar[h % _avatar.length];
}

/// Role name for a caregiver card. The organisers' roster uses "medic",
/// "doctor" and "phlebotomist"; our older sample used "paramedic", "nurse",
/// "gp", "specialist" (those keep the web app's labels).
String roleLabel(String role, Lang lang) {
  final r = role.toLowerCase().trim();
  if (r == 'medic') return tm(lang, M.roleMedic);
  if (r == 'doctor') return tm(lang, M.roleDoctor);
  if (r.contains('phleb') || r.contains('sample')) return tm(lang, M.roleSampleCollector);
  if (r.contains('lab')) return tm(lang, M.roleLab);
  return t(lang, roleKey(role));
}

K roleKey(String role) {
  final r = role.toLowerCase();
  if (r.contains('physio')) return K.rolePhysio;
  if (r.contains('nurse')) return K.roleNurse;
  if (r.contains('paramedic')) return K.roleParamedic;
  if (r.contains('special') || r.contains('consult')) return K.roleSpecialist;
  return K.roleGp;
}

/// 0 = scheduled/routine, 1 = same_day, 2 = emergency/immediate.
int urgencyLevel(String? urgency) => switch (urgencyKindOf(urgency)) {
  UrgencyKind.emergency => 2,
  UrgencyKind.sameDay => 1,
  UrgencyKind.scheduled => 0,
};

/// Fixed urgency label for a level (the dial and the fallback chip). The
/// lowest level is "scheduled" in the organisers' schema.
String urgencyText(int level, Lang lang) => switch (level) {
  2 => t(lang, K.urgNow),
  1 => t(lang, K.urgSameDay),
  _ => tm(lang, M.urgScheduled),
};

/// Video consult (teleconsultation, or the old gp_teleconsult).
bool isTele(String? careType) => careKindOf(careType) == CareKind.teleconsult;

/// Care label shown on a decision: the API's own text when present,
/// otherwise our fallback for the care type.
String careLabel(TriageResponse res, Lang lang) {
  final local = res.trace.decision.careLabelLocal;
  if (local != null && local.trim().isNotEmpty) return local;
  return switch (res.careKind) {
    CareKind.paramedic => t(lang, K.roleParamedic),
    CareKind.nurse => t(lang, K.roleNurse),
    CareKind.lab => tm(lang, M.careLab),
    CareKind.teleconsult => '${t(lang, K.roleGp)} · ${t(lang, K.videoCall)}',
    CareKind.specialist => t(lang, K.roleSpecialist),
    CareKind.emergency => t(lang, K.sosPageTitle),
    CareKind.unknown => res.careType ?? '',
  };
}

/// Urgency label: the API's own text when present, else ours.
String urgencyLabel(TriageResponse res, Lang lang) {
  final local = res.trace.decision.urgencyLabelLocal;
  if (local != null && local.trim().isNotEmpty) return local;
  return urgencyText(urgencyLevel(res.urgency ?? res.trace.decision.urgency), lang);
}

/// Confidence as plain words ("Pakka bharosa"), never a raw percentage.
String bandText(ConfidenceBand band, Lang lang) => switch (band) {
  ConfidenceBand.high => tm(lang, M.bandHigh),
  ConfidenceBand.medium => tm(lang, M.bandMedium),
  ConfidenceBand.low => tm(lang, M.bandLow),
};

/// "Decided by MuRIL model · High confidence" for the decision card, from
/// trace.decision.source and trace.model. Null for responses from servers
/// that predate the fine-tuned model (their "model" was a different one).
String? decidedByText(Trace tr, Lang lang) {
  final d = tr.decision;
  final m = tr.model;
  final fresh =
      m?.name != null ||
      m?.band != null ||
      tr.guardrails.isNotEmpty ||
      const {'model+safety_net', 'safety_net', 'llm'}.contains(d.source);
  if (!fresh) return null;
  final name = (m?.shortName.isNotEmpty ?? false) ? m!.shortName : 'MuRIL';
  final band = m?.band;
  final withBand = band == null ? '' : ' · ${bandText(band, lang)}';
  return switch (d.source) {
    'model' => tm(lang, M.srcModel, {'name': name}) + withBand,
    'model+safety_net' => tm(lang, M.srcModelSafety, {'name': name}) + withBand,
    'safety_net' => tm(lang, M.srcSafetyNet),
    'llm' => tm(lang, M.srcLlm),
    'rules' => tm(lang, M.srcRules),
    _ => null,
  };
}

String? fmtDays(double? days, Lang lang) {
  if (days == null) return null;
  final d = days.round();
  final w = (days / 7).round().clamp(1, 1 << 30);
  final m = (days / 30).round().clamp(1, 1 << 30);
  switch (lang) {
    case Lang.en:
      if (days < 1) return 'since today';
      if (days < 7) return '$d day${d == 1 ? '' : 's'}';
      if (days < 30) return '$w week${w == 1 ? '' : 's'}';
      return '$m month${m == 1 ? '' : 's'}';
    case Lang.hi:
      if (days < 1) return 'आज से';
      if (days < 7) return '$d दिन से';
      if (days < 30) return '$w हफ़्ते से';
      return '$m महीने से';
    case Lang.hinglish:
      if (days < 1) return 'aaj se';
      if (days < 7) return '$d din se';
      if (days < 30) return '$w hafte se';
      return '$m mahine se';
  }
}

const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const _monthsHi = ['जन', 'फ़र', 'मार्च', 'अप्रैल', 'मई', 'जून', 'जुलाई', 'अग', 'सित', 'अक्टू', 'नव', 'दिस'];

/// When a saved chat was last used: "Abhi", "5 min pehle", "Aaj 3:42 PM",
/// "Kal 9:10 PM", else "12 Oct, 9:10 PM".
String chatTime(DateTime when, Lang lang, {DateTime? now}) {
  final n = now ?? DateTime.now();
  final w = when.toLocal();
  final mins = n.difference(w).inMinutes;
  if (mins < 1) return tm(lang, M.timeNow);
  if (mins < 60) return tm(lang, M.timeMins, {'n': mins});
  final h = w.hour % 12 == 0 ? 12 : w.hour % 12;
  final clock = '$h:${w.minute.toString().padLeft(2, '0')} ${w.hour < 12 ? 'AM' : 'PM'}';
  final days = DateTime(n.year, n.month, n.day).difference(DateTime(w.year, w.month, w.day)).inDays;
  if (days == 0) return tm(lang, M.timeToday, {'t': clock});
  if (days == 1) return tm(lang, M.timeYesterday, {'t': clock});
  final month = (lang == Lang.hi ? _monthsHi : _months)[w.month - 1];
  final year = w.year == n.year ? '' : ' ${w.year}';
  return '${w.day} $month$year, $clock';
}

String titleCase(String s) => s.replaceAllMapped(RegExp(r'\b\w'), (m) => m.group(0)!.toUpperCase());

/// True when the text contains Devanagari, so we can pick the Devanagari face first.
bool hasDevanagari(String s) => RegExp(r'[ऀ-ॿ]').hasMatch(s);
