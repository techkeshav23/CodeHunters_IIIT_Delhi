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
  // chats: new, incognito, history saved on the phone
  newChat,
  history,
  historyTitle,
  historySub,
  historyEmpty,
  incognito,
  incognitoShort,
  incognitoBanner,
  incognitoOff,
  incognitoRemoved,
  chatPending,
  chatNoReply,
  chatDelete,
  deleteAll,
  deleteAllTitle,
  deleteAllText,
  deleteYes,
  timeNow,
  timeMins,
  timeToday,
  timeYesterday,
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
  M.newChat: ('Nayi chat', 'नई चैट', 'New chat'),
  M.history: ('History', 'हिस्ट्री', 'History'),
  M.historyTitle: ('Pichhli chats', 'पिछली चैट', 'Chat history'),
  M.historySub: ('Sirf is phone par save hain.', 'सिर्फ़ इस फ़ोन पर सेव हैं।', 'Saved on this phone only.'),
  M.historyEmpty: (
    'Abhi koi chat save nahi hai. Har jaanch yahan apne aap save hogi.',
    'अभी कोई चैट सेव नहीं है। हर जाँच यहाँ अपने-आप सेव होगी।',
    'No saved chats yet. Every check is saved here on its own.',
  ),
  M.incognito: ('Incognito chat', 'इनकॉग्निटो चैट', 'Incognito chat'),
  M.incognitoShort: ('Incognito', 'इनकॉग्निटो', 'Incognito'),
  M.incognitoBanner: (
    'Incognito: yeh baatcheet save nahi hogi',
    'इनकॉग्निटो: यह बातचीत सेव नहीं होगी',
    "Incognito: this chat won't be saved",
  ),
  M.incognitoOff: ('Incognito band karein', 'इनकॉग्निटो बंद करें', 'Turn off incognito'),
  M.incognitoRemoved: (
    'Yeh chat history se hata di gayi',
    'यह चैट हिस्ट्री से हटा दी गई',
    'This chat was removed from history',
  ),
  M.chatPending: ('Sawaal baaki hai', 'सवाल बाकी है', 'Question pending'),
  M.chatNoReply: ('Jawab nahi aaya', 'जवाब नहीं आया', 'No reply yet'),
  M.chatDelete: ('Chat hatayein', 'चैट हटाएँ', 'Delete chat'),
  M.deleteAll: ('Saari history mitayein', 'सारी हिस्ट्री मिटाएँ', 'Delete all history'),
  M.deleteAllTitle: ('Saari history mitayein?', 'सारी हिस्ट्री मिटाएँ?', 'Delete all history?'),
  M.deleteAllText: (
    '{n} chats is phone se hat jayengi. Bookings nahi hatengi.',
    '{n} चैट इस फ़ोन से हट जाएँगी। बुकिंग नहीं हटेंगी।',
    '{n} chats will be removed from this phone. Your bookings stay.',
  ),
  M.deleteYes: ('Haan, mitayein', 'हाँ, मिटाएँ', 'Yes, delete'),
  M.timeNow: ('Abhi', 'अभी', 'Just now'),
  M.timeMins: ('{n} min pehle', '{n} मिनट पहले', '{n} min ago'),
  M.timeToday: ('Aaj {t}', 'आज {t}', 'Today {t}'),
  M.timeYesterday: ('Kal {t}', 'कल {t}', 'Yesterday {t}'),
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
