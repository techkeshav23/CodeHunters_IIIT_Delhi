// All UI strings live here, in three languages (spec section 8):
//   hinglish (Roman Hindi, default), hi (Devanagari), en.
// API text (*_local, questions) is already in the user's language — never
// translate it here, just show it as-is.

import type { Lang } from "./types";

export const LANGS: Lang[] = ["hinglish", "hi", "en"];

export const LANG_LABELS: Record<Lang, string> = {
  hi: "हिंदी",
  hinglish: "Hinglish",
  en: "English",
};

type Dict = Record<Lang, string>;

export const strings = {
  appName: { hinglish: "CareCompass", hi: "CareCompass", en: "CareCompass" },
  tagline: {
    hinglish: "Batayein kya taklif hai, hum sahi madad dhoondhenge",
    hi: "बताइए क्या तकलीफ़ है, हम सही मदद ढूँढेंगे",
    en: "Tell us what is wrong, we will find the right help",
  },
  speak: {
    hinglish: "Bolkar batayein",
    hi: "बोलकर बताइए",
    en: "Speak",
  },
  type: {
    hinglish: "Ya yahan likhein... jaise: Papa ko 2 din se bukhar hai",
    hi: "या यहाँ लिखिए... जैसे: पापा को 2 दिन से बुखार है",
    en: "Or type here... e.g. My father has had fever for 2 days",
  },
  send: { hinglish: "Bhejein", hi: "भेजिए", en: "Send" },
  listening: {
    hinglish: "Sun rahe hain...",
    hi: "सुन रहे हैं...",
    en: "Listening...",
  },
  thinking: {
    hinglish: "Samajh rahe hain...",
    hi: "समझ रहे हैं...",
    en: "Understanding...",
  },
  why: { hinglish: "Kyon?", hi: "क्यों?", en: "Why?" },
  understood: {
    hinglish: "Humne kya samjha",
    hi: "हमने क्या समझा",
    en: "What we understood",
  },
  checked: {
    hinglish: "Humne kya check kiya",
    hi: "हमने क्या जाँचा",
    en: "What we checked",
  },
  decisionWhy: {
    hinglish: "Faisla kyon",
    hi: "फ़ैसला क्यों",
    en: "Why this decision",
  },
  book: { hinglish: "Book karein", hi: "बुक करें", en: "Book" },
  booking: {
    hinglish: "Book kar rahe hain...",
    hi: "बुक कर रहे हैं...",
    en: "Booking...",
  },
  booked: { hinglish: "Booking ho gayi", hi: "बुकिंग हो गई", en: "Booked" },
  read: { hinglish: "Sunaiye", hi: "सुनाइए", en: "Read aloud" },
  stopReading: { hinglish: "Roekein", hi: "रोकें", en: "Stop" },
  restart: {
    hinglish: "Naya sawaal",
    hi: "फिर से शुरू करें",
    en: "Start over",
  },
  call112: {
    hinglish: "112 par call karein",
    hi: "112 पर कॉल करें",
    en: "Call 112",
  },
  question: { hinglish: "Sawaal", hi: "सवाल", en: "Question" },
  useMyLocation: {
    hinglish: "Meri location istemal karein",
    hi: "मेरी लोकेशन इस्तेमाल करें",
    en: "Use my location",
  },
  locationDemo: {
    hinglish: "Location: Okhla, New Delhi (demo)",
    hi: "लोकेशन: ओखला, नई दिल्ली (डेमो)",
    en: "Location: Okhla, New Delhi (demo)",
  },
  locationYours: {
    hinglish: "Location: aapki jagah",
    hi: "लोकेशन: आपकी जगह",
    en: "Location: your place",
  },
  gettingLocation: {
    hinglish: "Location le rahe hain...",
    hi: "लोकेशन ले रहे हैं...",
    en: "Getting location...",
  },
  locationFailed: {
    hinglish: "Location nahi mili, demo location istemal ho rahi hai",
    hi: "लोकेशन नहीं मिली, डेमो लोकेशन इस्तेमाल हो रही है",
    en: "Could not get location, using demo location",
  },
  voiceOnlyChrome: {
    hinglish: "Voice Chrome mein chalta hai",
    hi: "वॉइस Chrome में चलता है",
    en: "Voice works in Chrome",
  },
  networkError: {
    hinglish: "Connection mein dikkat hai. Dobara koshish karein.",
    hi: "कनेक्शन में दिक्कत है। दोबारा कोशिश करें।",
    en: "Something went wrong with the connection. Please try again.",
  },
  retry: { hinglish: "Dobara koshish karein", hi: "दोबारा कोशिश करें", en: "Try again" },
  distance: { hinglish: "door", hi: "दूर", en: "away" },
  nextFree: { hinglish: "Agla free time", hi: "अगला खाली समय", en: "Next free" },
  rating: { hinglish: "Rating", hi: "रेटिंग", en: "Rating" },
  bookingId: { hinglish: "Booking ID", hi: "बुकिंग आईडी", en: "Booking ID" },
  withCaregiver: { hinglish: "ke saath", hi: "के साथ", en: "with" },
  bookedConfirm: {
    hinglish: "Aapki booking confirm ho gayi hai",
    hi: "आपकी बुकिंग कन्फर्म हो गई है",
    en: "Your booking is confirmed",
  },
  redFlagsFound: {
    hinglish: "Yeh lakshan mile",
    hi: "ये लक्षण मिले",
    en: "Warning signs found",
  },
  judgeView: {
    hinglish: "API request / response",
    hi: "API request / response",
    en: "API request / response",
  },
  request: { hinglish: "Request", hi: "Request", en: "Request" },
  response: { hinglish: "Response", hi: "Response", en: "Response" },
  copy: { hinglish: "Copy", hi: "कॉपी", en: "Copy" },
  copied: { hinglish: "Copy ho gaya", hi: "कॉपी हो गया", en: "Copied" },
  timing: { hinglish: "Samay", hi: "समय", en: "Time" },
  backendOnline: { hinglish: "Backend chalu", hi: "बैकएंड चालू", en: "Backend online" },
  backendOffline: { hinglish: "Backend band", hi: "बैकएंड बंद", en: "Backend offline" },
  usingMocks: { hinglish: "Demo data", hi: "डेमो डेटा", en: "Demo data" },
  footer: {
    hinglish:
      "Demo: sirf synthetic data. Yeh medical salah nahi hai. Emergency mein 112 par call karein.",
    hi: "डेमो: सिर्फ़ सिंथेटिक डेटा। यह मेडिकल सलाह नहीं है। इमरजेंसी में 112 पर कॉल करें।",
    en: "Demo: synthetic data only. This is not medical advice. In an emergency, call 112.",
  },
  langSwitch: {
    hinglish: "Bhasha badlein",
    hi: "भाषा बदलें",
    en: "Change language",
  },
  patient: { hinglish: "Mareez", hi: "मरीज़", en: "Patient" },
  years: { hinglish: "saal", hi: "साल", en: "years" },
  matchWhy: {
    hinglish: "Yeh match kyon",
    hi: "यह मैच क्यों",
    en: "Why this match",
  },
  featSkill: { hinglish: "Skill", hi: "कौशल", en: "Skill" },
  featTime: { hinglish: "Jaldi free", hi: "जल्दी उपलब्ध", en: "Availability" },
  featDistance: { hinglish: "Paas", hi: "नज़दीकी", en: "Nearness" },
  featLanguage: { hinglish: "Bhasha", hi: "भाषा", en: "Language" },
  featRating: { hinglish: "Rating", hi: "रेटिंग", en: "Rating" },
  specialtyLabel: {
    hinglish: "Visheshgya",
    hi: "विशेषज्ञ",
    en: "Specialist",
  },
} satisfies Record<string, Dict>;

export type StringKey = keyof typeof strings;

export function t(lang: Lang, key: StringKey): string {
  return strings[key][lang];
}
