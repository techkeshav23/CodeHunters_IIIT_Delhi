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
  // who decided (decision card), confidence as words, never a raw %
  srcModel,
  srcModelSafety,
  srcSafetyNet,
  srcLlm,
  srcRules,
  bandHigh,
  bandMedium,
  bandLow,
  sosBySafetyNet,
  // "add more details" after a decision
  addMore,
  addMoreHint,
  addMoreNote,
  // safety checks (trace.guardrails) in "Yeh faisla kyon?"
  safetyChecks,
  grFired,
  grPass,
}

// (hinglish, hi, en)
const Map<M, (String, String, String)> _m = {
  M.urgScheduled: ('Time fix karke', 'समय तय करके', 'Scheduled'),
  M.careLab: ('Ghar par sample / lab test', 'घर पर सैंपल / लैब टेस्ट', 'Home lab test'),
  M.roleLab: ('Lab technician', 'लैब टेक्नीशियन', 'Lab technician'),
  M.roleMedic: ('Medic', 'मेडिक', 'Medic'),
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
  M.srcModel: ('{name} model ne tay kiya', '{name} मॉडल ने तय किया', 'Decided by {name} model'),
  M.srcModelSafety: (
    '{name} model aur suraksha niyamon ne tay kiya',
    '{name} मॉडल और सुरक्षा नियमों ने तय किया',
    'Decided by {name} model + safety rules',
  ),
  M.srcSafetyNet: ('Suraksha niyamon ne tay kiya', 'सुरक्षा नियमों ने तय किया', 'Decided by safety rules'),
  M.srcLlm: (
    'Model ko pakka nahi tha, isliye Claude ne doosri baar jaancha',
    'मॉडल को पक्का नहीं था, इसलिए Claude ने दोबारा जाँचा',
    'The model was unsure, so Claude did a second check',
  ),
  M.srcRules: ('Niyamon ne tay kiya', 'नियमों ने तय किया', 'Decided by rules'),
  M.bandHigh: ('Pakka bharosa', 'पक्का भरोसा', 'High confidence'),
  M.bandMedium: ('Theek-thaak bharosa', 'ठीक-ठाक भरोसा', 'Medium confidence'),
  M.bandLow: ('Kam bharosa', 'कम भरोसा', 'Low confidence'),
  M.sosBySafetyNet: (
    'Humari suraksha jaanch ne ise emergency maana',
    'हमारी सुरक्षा जाँच ने इसे इमरजेंसी माना',
    'Our safety check marked this as an emergency',
  ),
  M.addMore: ('Aur jaankari jodein', 'और जानकारी जोड़ें', 'Add more details'),
  M.addMoreHint: ('Aur kya batana hai?', 'और क्या बताना है?', 'What else should we know?'),
  M.addMoreNote: (
    'Pichhli baat ke saath jodkar dobara dekhenge',
    'पिछली बात के साथ जोड़कर दोबारा देखेंगे',
    "We'll look again with what you said before",
  ),
  M.safetyChecks: ('Suraksha jaanch', 'सुरक्षा जाँच', 'Safety checks'),
  M.grFired: ('Laagu hua', 'लागू हुआ', 'Applied'),
  M.grPass: ('Theek', 'ठीक', 'Passed'),
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
