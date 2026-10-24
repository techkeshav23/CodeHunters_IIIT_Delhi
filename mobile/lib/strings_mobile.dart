// A few UI strings the phone app needs that the web app has no key for.
// No medical text here: labels and device messages only.

import 'models.dart';

enum M {
  urgScheduled,
  careLab,
  roleLab,
  roleMedic,
  roleDoctor,
  roleSampleCollector,
  modelConfidence,
  apiServer,
  voiceUnavailable,
  callFailed,
  appAbout,
}

// (hinglish, hi, en)
const Map<M, (String, String, String)> _m = {
  M.urgScheduled: ('Time fix karke', 'समय तय करके', 'Scheduled'),
  M.careLab: ('Ghar par sample / lab test', 'घर पर सैंपल / लैब टेस्ट', 'Home lab test'),
  M.roleLab: ('Lab technician', 'लैब टेक्नीशियन', 'Lab technician'),
  M.roleMedic: ('Medic (nurse)', 'मेडिक (नर्स)', 'Medic (nurse)'),
  M.roleDoctor: ('Doctor', 'डॉक्टर', 'Doctor'),
  M.roleSampleCollector: ('Sample collector', 'सैंपल कलेक्टर', 'Sample collector'),
  M.modelConfidence: ('Model ka bharosa: {p}%', 'मॉडल का भरोसा: {p}%', 'Model confidence: {p}%'),
  M.apiServer: ('API server', 'API सर्वर', 'API server'),
  M.voiceUnavailable: (
    'Is phone par bolkar likhna uplabdh nahi. Likhkar batayein.',
    'इस फ़ोन पर बोलकर लिखना उपलब्ध नहीं। लिखकर बताइए।',
    'Voice typing is not available on this phone. Please type instead.',
  ),
  M.callFailed: (
    'Dialer nahi khula. {n} khud dial karein.',
    'डायलर नहीं खुला। {n} ख़ुद डायल करें।',
    "Couldn't open the dialer. Please dial {n}.",
  ),
  M.appAbout: ('App ke baare mein', 'ऐप के बारे में', 'About the app'),
};

String tm(Lang lang, M key, [Map<String, Object> vars = const {}]) {
  final e = _m[key]!;
  var s = switch (lang) {
    Lang.hinglish => e.$1,
    Lang.hi => e.$2,
    Lang.en => e.$3,
  };
  vars.forEach((k, v) => s = s.replaceAll('{$k}', v.toString()));
  return s;
}
