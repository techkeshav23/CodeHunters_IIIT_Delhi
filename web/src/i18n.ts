// All UI text in three languages. Text that comes from the API (*_local fields,
// questions, reasons) is already in the user's language and is shown as is.
import type { Lang } from "./types";

type Entry = { hinglish: string; hi: string; en: string };

const S = {
  // shell
  navCheck: { hinglish: "Jaanch", hi: "जाँच", en: "Check" },
  navBookings: { hinglish: "Bookings", hi: "बुकिंग", en: "Bookings" },
  navSos: { hinglish: "Emergency", hi: "इमरजेंसी", en: "Emergency" },
  navSosShort: { hinglish: "SOS", hi: "SOS", en: "SOS" },
  navHow: { hinglish: "Kaise kaam karta hai", hi: "कैसे काम करता है", en: "How it works" },
  navHowShort: { hinglish: "Jaankari", hi: "जानकारी", en: "About" },
  navSettings: { hinglish: "Settings", hi: "सेटिंग्स", en: "Settings" },
  sosCardTitle: { hinglish: "112 par call", hi: "112 पर कॉल", en: "Call 112" },
  sosCardSub: { hinglish: "Khatre ke lakshan ho to abhi", hi: "ख़तरे के लक्षण हों तो अभी", en: "If there are danger signs" },
  serviceOk: { hinglish: "Seva chalu hai", hi: "सेवा चालू है", en: "Service is up" },
  serviceBad: { hinglish: "Server se sampark nahi", hi: "सर्वर से संपर्क नहीं", en: "Can't reach the server" },
  serviceWait: { hinglish: "Jod rahe hain…", hi: "जोड़ रहे हैं…", en: "Connecting…" },
  serviceMock: { hinglish: "Sample data par chal raha hai", hi: "सैंपल डेटा पर चल रहा है", en: "Running on sample data" },
  newCheck: { hinglish: "Nayi jaanch", hi: "नई जाँच", en: "New check" },
  disclaimer: {
    hinglish: "Demo: sirf synthetic data. Yeh medical salah nahi hai. Emergency mein 112 par call karein.",
    hi: "डेमो: सिर्फ़ सिंथेटिक डेटा। यह चिकित्सा सलाह नहीं है। इमरजेंसी में 112 पर कॉल करें।",
    en: "Demo: synthetic data only. This is not medical advice. In an emergency, call 112.",
  },

  // start
  hello: { hinglish: "Batayein, kya taklif hai?", hi: "बताइए, क्या तकलीफ़ है?", en: "Tell us what's wrong" },
  helloSub: {
    hinglish: "Bolkar ya likhkar batayein. Hum batayenge kaunsi care chahiye, kitni jaldi, aur kaun sabse sahi rahega.",
    hi: "बोलकर या लिखकर बताइए। हम बताएँगे कौन-सी देखभाल चाहिए, कितनी जल्दी, और कौन सबसे सही रहेगा।",
    en: "Speak or type. We'll tell you what care fits, how soon, and who is best placed to help.",
  },
  quickPicks: { hinglish: "Ya inme se chunein", hi: "या इनमें से चुनें", en: "Or pick one" },
  tryExample: { hinglish: "Udaharan dekhein", hi: "उदाहरण देखें", en: "Try an example" },
  pickFever: { hinglish: "Bukhar", hi: "बुखार", en: "Fever" },
  pickCough: { hinglish: "Khansi, zukam", hi: "खांसी, ज़ुकाम", en: "Cough or cold" },
  pickStomach: { hinglish: "Pet dard, dast", hi: "पेट दर्द, दस्त", en: "Stomach upset" },
  pickInjury: { hinglish: "Chot lagi", hi: "चोट लगी", en: "An injury" },
  pickInjection: { hinglish: "Ghar pe injection", hi: "घर पर इंजेक्शन", en: "Injection at home" },
  pickDoctor: { hinglish: "Doctor se baat", hi: "डॉक्टर से बात", en: "Talk to a doctor" },
  pickElder: { hinglish: "Bujurg ki dekhbhal", hi: "बुज़ुर्ग की देखभाल", en: "Care for an elder" },
  pickBp: { hinglish: "BP, sugar check", hi: "बीपी, शुगर जाँच", en: "BP or sugar check" },
  seedFever: { hinglish: "Bukhar hai ", hi: "बुखार है ", en: "Fever " },
  seedCough: { hinglish: "Khansi aur zukam hai ", hi: "खांसी और ज़ुकाम है ", en: "Cough and cold " },
  seedStomach: { hinglish: "Pet mein dard aur dast hai ", hi: "पेट में दर्द और दस्त है ", en: "Stomach pain and loose motions " },
  seedInjury: { hinglish: "Chot lagi hai ", hi: "चोट लगी है ", en: "Got hurt " },
  seedInjection: { hinglish: "Ghar pe injection lagwana hai ", hi: "घर पर इंजेक्शन लगवाना है ", en: "Need an injection at home " },
  seedDoctor: { hinglish: "Doctor se baat karni hai ", hi: "डॉक्टर से बात करनी है ", en: "I want to talk to a doctor " },
  seedElder: { hinglish: "Bujurg ki dekhbhal ke liye attendant chahiye ", hi: "बुज़ुर्ग की देखभाल के लिए अटेंडेंट चाहिए ", en: "Need an attendant for an elderly person " },
  seedBp: { hinglish: "Ghar pe BP aur sugar check karwana hai ", hi: "घर पर बीपी और शुगर जाँच करवानी है ", en: "Need a BP and sugar check at home " },
  ex1: { hinglish: "Papa ko do din se bukhar hai aur khansi bhi", hi: "पापा को दो दिन से बुखार है और खांसी भी", en: "My father has had fever and cough for two days" },
  ex2: { hinglish: "Dadi ko roz insulin ka injection ghar pe lagwana hai", hi: "दादी को रोज़ इंसुलिन का इंजेक्शन घर पर लगवाना है", en: "My grandmother needs a daily insulin injection at home" },
  ex3: { hinglish: "2 mahine se ghutne mein dard hai", hi: "दो महीने से घुटने में दर्द है", en: "My knee has hurt for two months" },

  // composer
  placeholder: { hinglish: "Likhein ya bolein…", hi: "लिखिए या बोलिए…", en: "Type or speak…" },
  placeholderAnswer: { hinglish: "Ya apne shabdon mein…", hi: "या अपने शब्दों में…", en: "Or in your own words…" },
  send: { hinglish: "Bhejein", hi: "भेजिए", en: "Send" },
  micStart: { hinglish: "Bolkar batayein", hi: "बोलकर बताइए", en: "Speak" },
  micStop: { hinglish: "Sunna band karein", hi: "सुनना बंद करें", en: "Stop listening" },
  listening: { hinglish: "Sun rahe hain… bolte rahiye", hi: "सुन रहे हैं… बोलते रहिए", en: "Listening… keep talking" },
  voiceOff: { hinglish: "Bolne ke liye Chrome kholein", hi: "बोलने के लिए Chrome खोलें", en: "Voice works in Chrome" },
  locDemo: { hinglish: "Okhla, New Delhi (demo)", hi: "ओखला, नई दिल्ली (डेमो)", en: "Okhla, New Delhi (demo)" },
  locYours: { hinglish: "Aapki location", hi: "आपकी लोकेशन", en: "Your location" },
  locFailed: { hinglish: "Location nahi mili, demo location", hi: "लोकेशन नहीं मिली, डेमो लोकेशन", en: "Couldn't get location, using demo" },
  locUse: { hinglish: "Meri location lein", hi: "मेरी लोकेशन लें", en: "Use my location" },
  locFinding: { hinglish: "Dhoondh rahe hain…", hi: "ढूँढ रहे हैं…", en: "Finding you…" },

  // thread
  you: { hinglish: "Aap", hi: "आप", en: "You" },
  thinking: { hinglish: "Samajh rahe hain", hi: "समझ रहे हैं", en: "Understanding" },
  questionOf: { hinglish: "Sawaal {n} / {max}", hi: "सवाल {n} / {max}", en: "Question {n} of {max}" },
  readAloud: { hinglish: "Sunaiye", hi: "सुनाइए", en: "Read aloud" },
  stopReading: { hinglish: "Rokein", hi: "रोकिए", en: "Stop" },
  errorText: {
    hinglish: "Server se jawab nahi aaya. Internet check karke dobara koshish karein. Emergency ho to 112 par call karein.",
    hi: "सर्वर से जवाब नहीं आया। इंटरनेट जाँचकर दोबारा कोशिश करें। इमरजेंसी हो तो 112 पर कॉल करें।",
    en: "No answer from the server. Check the internet and try again. In an emergency, call 112.",
  },
  retry: { hinglish: "Dobara koshish karein", hi: "दोबारा कोशिश करें", en: "Try again" },

  // decision
  ourAdvice: { hinglish: "Humara sujhav", hi: "हमारा सुझाव", en: "Our recommendation" },
  urgRoutine: { hinglish: "Kuch dinon mein", hi: "कुछ दिनों में", en: "In a few days" },
  urgSameDay: { hinglish: "Aaj hi", hi: "आज ही", en: "Today" },
  urgNow: { hinglish: "Abhi", hi: "अभी", en: "Now" },
  whyThis: { hinglish: "Yeh faisla kyon?", hi: "यह फ़ैसला क्यों?", en: "Why this decision?" },
  understood: { hinglish: "Humne kya samjha", hi: "हमने क्या समझा", en: "What we understood" },
  checked: { hinglish: "Humne kya jaancha", hi: "हमने क्या जाँचा", en: "What we checked" },
  reasonTitle: { hinglish: "Faisla", hi: "फ़ैसला", en: "The decision" },
  stPresent: { hinglish: "Hai", hi: "है", en: "Present" },
  stAbsent: { hinglish: "Nahi hai", hi: "नहीं है", en: "Not present" },
  stUnknown: { hinglish: "Bataya nahi", hi: "बताया नहीं", en: "Not mentioned" },
  specialist: { hinglish: "Vibhag: {x}", hi: "विभाग: {x}", en: "Department: {x}" },
  daysFor: { hinglish: "{x} se", hi: "{x} से", en: "for {x}" },
  carersTitle: { hinglish: "Aapke liye sabse sahi", hi: "आपके लिए सबसे सही", en: "Best matches for you" },
  bestMatch: { hinglish: "Sabse sahi", hi: "सबसे सही", en: "Best match" },
  match: { hinglish: "match", hi: "मैच", en: "match" },
  matchHow: { hinglish: "Match kaise hua", hi: "मैच कैसे हुआ", en: "How we matched" },
  fSkill: { hinglish: "Kaam ka anubhav", hi: "काम का अनुभव", en: "Skill fit" },
  fTime: { hinglish: "Jaldi free", hi: "जल्दी खाली", en: "Free soon" },
  fDistance: { hinglish: "Paas mein", hi: "पास में", en: "Nearby" },
  fLanguage: { hinglish: "Aapki bhasha", hi: "आपकी भाषा", en: "Your language" },
  fRating: { hinglish: "Rating", hi: "रेटिंग", en: "Rating" },
  kmAway: { hinglish: "{d} km", hi: "{d} किमी", en: "{d} km" },
  videoCall: { hinglish: "Video call", hi: "वीडियो कॉल", en: "Video call" },
  book: { hinglish: "Book karein", hi: "बुक करें", en: "Book" },
  noCarers: {
    hinglish: "Abhi koi caregiver free nahi mila. Thodi der baad dobara dekhein.",
    hi: "अभी कोई केयरगिवर खाली नहीं मिला। थोड़ी देर बाद दोबारा देखें।",
    en: "No caregiver is free right now. Please check again shortly.",
  },
  roleParamedic: { hinglish: "Paramedic", hi: "पैरामेडिक", en: "Paramedic" },
  roleNurse: { hinglish: "Nurse", hi: "नर्स", en: "Nurse" },
  roleGp: { hinglish: "Doctor (GP)", hi: "डॉक्टर (GP)", en: "Doctor (GP)" },
  roleSpecialist: { hinglish: "Specialist doctor", hi: "विशेषज्ञ डॉक्टर", en: "Specialist doctor" },
  rolePhysio: { hinglish: "Physiotherapist", hi: "फ़िज़ियोथेरेपिस्ट", en: "Physiotherapist" },

  // booking
  confirmTitle: { hinglish: "Booking pakki karein", hi: "बुकिंग पक्की करें", en: "Confirm the booking" },
  bWho: { hinglish: "Kaun", hi: "कौन", en: "Who" },
  bWhen: { hinglish: "Kab", hi: "कब", en: "When" },
  bWhere: { hinglish: "Kahan", hi: "कहाँ", en: "Where" },
  bWhat: { hinglish: "Kis liye", hi: "किसलिए", en: "For" },
  bNote: { hinglish: "Kuch aur batana hai? (zaroori nahi)", hi: "कुछ और बताना है? (ज़रूरी नहीं)", en: "Anything else they should know? (optional)" },
  confirm: { hinglish: "Pakki karein", hi: "पक्की करें", en: "Confirm" },
  back: { hinglish: "Wapas", hi: "वापस", en: "Back" },
  booking: { hinglish: "Pakki ho rahi hai…", hi: "पक्की हो रही है…", en: "Confirming…" },
  booked: { hinglish: "Booking pakki ho gayi", hi: "बुकिंग पक्की हो गई", en: "Booking confirmed" },
  bookedText: {
    hinglish: "{name} {time} aapse judenge. Haalat bigde to intezaar mat kijiye, 112 par call kijiye.",
    hi: "{name} {time} आपसे जुड़ेंगे। हालत बिगड़े तो इंतज़ार मत कीजिए, 112 पर कॉल कीजिए।",
    en: "{name} will reach you {time}. If things get worse, don't wait: call 112.",
  },
  bookingId: { hinglish: "Booking number", hi: "बुकिंग नंबर", en: "Booking number" },
  seeBookings: { hinglish: "Meri bookings dekhein", hi: "मेरी बुकिंग देखें", en: "See my bookings" },
  close: { hinglish: "Band karein", hi: "बंद करें", en: "Close" },
  bookFailed: { hinglish: "Booking nahi ho payi. Dobara koshish karein.", hi: "बुकिंग नहीं हो पाई। दोबारा कोशिश करें।", en: "The booking didn't go through. Please try again." },
  toastBooked: { hinglish: "Booking pakki", hi: "बुकिंग पक्की", en: "Booked" },

  // bookings view
  bookingsTitle: { hinglish: "Meri bookings", hi: "मेरी बुकिंग", en: "My bookings" },
  bookingsSub: { hinglish: "Is phone par ki gayi bookings.", hi: "इस फ़ोन पर की गई बुकिंग।", en: "Bookings made on this device." },
  bookingsEmpty: {
    hinglish: "Abhi koi booking nahi. Jaanch shuru karein, hum sahi caregiver dhoondh denge.",
    hi: "अभी कोई बुकिंग नहीं। जाँच शुरू कीजिए, हम सही केयरगिवर ढूँढ देंगे।",
    en: "No bookings yet. Start a check and we'll find the right caregiver.",
  },
  startCheck: { hinglish: "Jaanch shuru karein", hi: "जाँच शुरू करें", en: "Start a check" },
  confirmed: { hinglish: "Pakki", hi: "पक्की", en: "Confirmed" },

  // emergency
  sosNow: { hinglish: "Abhi 112 par call karein", hi: "अभी 112 पर कॉल करें", en: "Call 112 now" },
  callNow: { hinglish: "Abhi call karein", hi: "अभी कॉल करें", en: "Call now" },
  sosOther: { hinglish: "Aur numbers", hi: "और नंबर", en: "Other numbers" },
  sosSteps: { hinglish: "Tab tak kya karein", hi: "तब तक क्या करें", en: "While you wait" },
  sosSeen: { hinglish: "Humein kya dikha", hi: "हमें क्या दिखा", en: "What we noticed" },
  sosYouSaid: { hinglish: "Aapne likha", hi: "आपने लिखा", en: "You wrote" },
  sosBack: { hinglish: "Baatcheet par wapas", hi: "बातचीत पर वापस", en: "Back to the chat" },
  sosTag: { hinglish: "Khatre ke lakshan", hi: "ख़तरे के लक्षण", en: "Danger signs" },
  sosPageTitle: { hinglish: "Emergency madad", hi: "इमरजेंसी मदद", en: "Emergency help" },
  sosPageSub: {
    hinglish: "Neeche diye lakshan dikhein to booking ka intezaar mat karein. Turant call karein.",
    hi: "नीचे दिए लक्षण दिखें तो बुकिंग का इंतज़ार मत कीजिए। तुरंत कॉल कीजिए।",
    en: "If you see any of these signs, don't wait for a booking. Call straight away.",
  },
  sosSignsTitle: { hinglish: "In lakshanon par turant call", hi: "इन लक्षणों पर तुरंत कॉल", en: "Call at once for" },
  sosNumbersTitle: { hinglish: "Helpline numbers", hi: "हेल्पलाइन नंबर", en: "Helplines" },
  tapToCall: { hinglish: "Call karne ke liye dabayein", hi: "कॉल करने के लिए दबाएँ", en: "Tap to call" },

  // how it works
  howTitle: { hinglish: "CareCompass kaise kaam karta hai", hi: "CareCompass कैसे काम करता है", en: "How CareCompass works" },
  howSub: {
    hinglish: "Har message 1 millisecond se kam mein in kadmon se guzarta hai. Har faisle ka kaaran dikhaya jata hai.",
    hi: "हर संदेश 1 मिलीसेकंड से कम में इन कदमों से गुज़रता है। हर फ़ैसले का कारण दिखाया जाता है।",
    en: "Every message goes through these steps in under a millisecond, and every decision shows its reason.",
  },
  step1: { hinglish: "Samajhna", hi: "समझना", en: "Understand" },
  step1t: { hinglish: "Hindi, Hinglish, English, voice typing aur galat spelling bhi.", hi: "हिंदी, हिंग्लिश, अंग्रेज़ी, वॉइस टाइपिंग और ग़लत स्पेलिंग भी।", en: "Hindi, Hinglish and English, voice typing and misspellings too." },
  step2: { hinglish: "Khatre ki jaanch", hi: "ख़तरे की जाँच", en: "Danger check" },
  step2t: { hinglish: "Sabse pehle 25 tarah ke khatre ke lakshan. Mile to seedha emergency.", hi: "सबसे पहले 25 तरह के ख़तरे के लक्षण। मिलें तो सीधे इमरजेंसी।", en: "First, 25 kinds of danger signs. If one is found, straight to emergency." },
  step3: { hinglish: "Zarurat par sawaal", hi: "ज़रूरत पर सवाल", en: "Ask only if needed" },
  step3t: { hinglish: "Sirf tab, jab jawab se faisla badal sake. Zyada se zyada 3.", hi: "सिर्फ़ तब, जब जवाब से फ़ैसला बदल सके। ज़्यादा से ज़्यादा 3।", en: "Only when the answer can change the decision. Three at most." },
  step4: { hinglish: "Faisla", hi: "फ़ैसला", en: "Decide" },
  step4t: { hinglish: "Kaunsi care aur kitni jaldi, bina bimari ya dawai ka naam liye.", hi: "कौन-सी देखभाल और कितनी जल्दी, बिना बीमारी या दवाई का नाम लिए।", en: "What care and how soon, without naming a disease or a medicine." },
  step5: { hinglish: "Caregiver match", hi: "केयरगिवर मैच", en: "Match" },
  step5t: { hinglish: "Skill, free time, doori, bhasha aur rating se, har ek ka kaaran.", hi: "कौशल, खाली समय, दूरी, भाषा और रेटिंग से, हर एक का कारण।", en: "By skill, free time, distance, language and rating, each with a reason." },
  step6: { hinglish: "Booking", hi: "बुकिंग", en: "Book" },
  step6t: { hinglish: "Ek tap mein pakki booking.", hi: "एक टैप में पक्की बुकिंग।", en: "One tap to confirm." },
  rulesTitle: { hinglish: "Suraksha ke niyam", hi: "सुरक्षा के नियम", en: "Safety rules" },
  rule1: { hinglish: "Khatre ka lakshan ho to koi sawaal nahi, seedha 112.", hi: "ख़तरे का लक्षण हो तो कोई सवाल नहीं, सीधे 112।", en: "A danger sign gets no questions, only the call for help." },
  rule2: { hinglish: "Sandeh ho to zyada jaldi wali care chunte hain.", hi: "संदेह हो तो ज़्यादा जल्दी वाली देखभाल चुनते हैं।", en: "When in doubt, we choose the more urgent care." },
  rule3: { hinglish: "Bimari ya dawai ka naam kabhi nahi.", hi: "बीमारी या दवाई का नाम कभी नहीं।", en: "Never a diagnosis or a medicine." },
  rule4: { hinglish: "Har faisle aur har match ka kaaran dikhta hai.", hi: "हर फ़ैसले और हर मैच का कारण दिखता है।", en: "Every decision and every match shows its reason." },
  testedTitle: { hinglish: "Kitna parkha gaya", hi: "कितना परखा गया", en: "How it was tested" },
  stat1: { hinglish: "mushkil test messages, har emergency pakdi", hi: "मुश्किल टेस्ट संदेश, हर इमरजेंसी पकड़ी", en: "tricky test messages, every emergency caught" },
  stat2: { hinglish: "public English cases (CARE-Bench) mein urgent ko aaj ya abhi care", hi: "पब्लिक अंग्रेज़ी केस (CARE-Bench) में अर्जेंट को आज या अभी देखभाल", en: "of urgent public cases (CARE-Bench) sent to same-day or immediate care" },
  stat3: { hinglish: "jawab ka samay, server ke andar", hi: "जवाब का समय, सर्वर के अंदर", en: "to decide, inside the server" },
  apiTitle: { hinglish: "Judges ke liye: API", hi: "जजों के लिए: API", en: "For judges: the API" },
  apiSub: {
    hinglish: "Aakhri request aur jawab, bilkul waise jaise API ne bheja.",
    hi: "आख़िरी रिक्वेस्ट और जवाब, बिल्कुल वैसे जैसे API ने भेजा।",
    en: "The last request and response, exactly as the API sent them.",
  },
  apiEmpty: { hinglish: "Pehle ek jaanch karein, phir yahan JSON dikhega.", hi: "पहले एक जाँच करें, फिर यहाँ JSON दिखेगा।", en: "Run a check first; the JSON shows up here." },
  apiDocs: { hinglish: "Poori API docs kholein", hi: "पूरी API डॉक्स खोलें", en: "Open the full API docs" },
  copy: { hinglish: "Copy karein", hi: "कॉपी करें", en: "Copy" },
  copied: { hinglish: "Copy ho gaya", hi: "कॉपी हो गया", en: "Copied" },
  request: { hinglish: "Request", hi: "रिक्वेस्ट", en: "Request" },
  response: { hinglish: "Jawab", hi: "जवाब", en: "Response" },
  answeredIn: { hinglish: "{ms} ms mein jawab", hi: "{ms} ms में जवाब", en: "Answered in {ms} ms" },

  // settings
  settingsTitle: { hinglish: "Settings", hi: "सेटिंग्स", en: "Settings" },
  setLang: { hinglish: "Bhasha", hi: "भाषा", en: "Language" },
  setLangSub: { hinglish: "Buttons aur menu ki bhasha. Jawab aapki likhi bhasha mein aata hai.", hi: "बटन और मेन्यू की भाषा। जवाब आपकी लिखी भाषा में आता है।", en: "Language of the buttons and menus. Answers follow the language you write in." },
  setText: { hinglish: "Akshar ka size", hi: "अक्षर का आकार", en: "Text size" },
  setTextSub: { hinglish: "Bade akshar padhne mein aasaan.", hi: "बड़े अक्षर पढ़ने में आसान।", en: "Larger text is easier to read." },
  textNormal: { hinglish: "Normal", hi: "सामान्य", en: "Normal" },
  textLarge: { hinglish: "Bade", hi: "बड़े", en: "Large" },
  setRead: { hinglish: "Jawab padhkar sunayein", hi: "जवाब पढ़कर सुनाएँ", en: "Read answers aloud" },
  setReadSub: { hinglish: "Jab aap bolkar batayein, sawaal aur faisla sunaya jayega.", hi: "जब आप बोलकर बताएँ, सवाल और फ़ैसला सुनाया जाएगा।", en: "When you speak, questions and decisions are read back to you." },
  on: { hinglish: "Chalu", hi: "चालू", en: "On" },
  off: { hinglish: "Band", hi: "बंद", en: "Off" },
  setTheme: { hinglish: "Rang", hi: "रंग", en: "Theme" },
  themeAuto: { hinglish: "Phone jaisa", hi: "फ़ोन जैसा", en: "Match device" },
  themeLight: { hinglish: "Halka", hi: "हल्का", en: "Light" },
  themeDark: { hinglish: "Gehra", hi: "गहरा", en: "Dark" },
  setLoc: { hinglish: "Location", hi: "लोकेशन", en: "Location" },
  setLocSub: { hinglish: "Ghar aane wale caregiver ki doori isi se nikalti hai.", hi: "घर आने वाले केयरगिवर की दूरी इसी से निकलती है।", en: "Used to work out how far home-visit caregivers are." },
} satisfies Record<string, Entry>;

export type Key = keyof typeof S;

export function t(lang: Lang, key: Key, vars?: Record<string, string | number>): string {
  let s = S[key][lang] ?? S[key].en;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(String(v));
  return s;
}

// department names for decision.specialty; unknown ids are shown as sent
const SPECIALTIES: Record<string, Record<Lang, string>> = {
  orthopaedics: { hinglish: "Haddi aur jod (Orthopaedics)", hi: "हड्डी और जोड़ (Orthopaedics)", en: "Orthopaedics (bones and joints)" },
  dermatology: { hinglish: "Twacha (Skin)", hi: "त्वचा (Skin)", en: "Dermatology (skin)" },
  ent: { hinglish: "Kaan, naak, gala (ENT)", hi: "कान, नाक, गला (ENT)", en: "ENT (ear, nose, throat)" },
  neurology: { hinglish: "Dimag aur nasein (Neurology)", hi: "दिमाग़ और नसें (Neurology)", en: "Neurology" },
  gastroenterology: { hinglish: "Pet aur pachan (Gastro)", hi: "पेट और पाचन (Gastro)", en: "Gastroenterology (digestion)" },
  urology: { hinglish: "Kidney aur peshab (Urology)", hi: "किडनी और पेशाब (Urology)", en: "Urology" },
  ophthalmology: { hinglish: "Aankh (Eye)", hi: "आँख (Eye)", en: "Ophthalmology (eye)" },
  dental: { hinglish: "Daant (Dental)", hi: "दाँत (Dental)", en: "Dental" },
  cardiology: { hinglish: "Dil (Cardiology)", hi: "दिल (Cardiology)", en: "Cardiology (heart)" },
  psychiatry: { hinglish: "Mann ka swasthya (Psychiatry)", hi: "मन का स्वास्थ्य (Psychiatry)", en: "Psychiatry (mental health)" },
  gynaecology: { hinglish: "Mahila aur pregnancy (Gynaecology)", hi: "महिला और गर्भावस्था (Gynaecology)", en: "Gynaecology" },
  physiotherapy: { hinglish: "Physiotherapy", hi: "फ़िज़ियोथेरेपी", en: "Physiotherapy" },
  paediatrics: { hinglish: "Bachchon ke doctor (Paediatrics)", hi: "बच्चों के डॉक्टर (Paediatrics)", en: "Paediatrics (children)" },
};

export function specialtyLabel(lang: Lang, id: string): string {
  return SPECIALTIES[id]?.[lang] ?? id;
}

export const LANG_LABEL: Record<Lang, string> = { hi: "हिंदी", hinglish: "Hinglish", en: "English" };
export const LANG_SHORT: Record<Lang, string> = { hi: "हि", hinglish: "Hi", en: "En" };
