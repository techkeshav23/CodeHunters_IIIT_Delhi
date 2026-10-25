import pytest

from app.nlp.extract import extract
from app.nlp.normalize import detect_language, phon, tokenize
from app.nlp.translit import transliterate


@pytest.mark.parametrize("deva, roman", [
    ("बुखार", "bukhaar"), ("खांसी", "khaansii"), ("सांस", "saans"), ("दर्द", "dard"),
    ("धड़कन", "dhadkan"), ("चक्कर", "chakkar"), ("समझ", "samajh"), ("कमज़ोरी", "kamzorii"),
    ("नहीं", "nahiin"), ("बेहोश", "behosh"), ("पत्नी", "patnii"),
])
def test_transliteration(deva, roman):
    assert transliterate(deva) == roman


def test_phonetic_keys_merge_spellings():
    assert phon("bukhaar") == phon("bukhar")
    assert phon("seene") == phon("sine")
    assert phon("zyada") == phon("jyada")
    assert phon("ulty") == phon("ulti")


def test_tokenize_marks_sentence_boundaries():
    assert "<c>" in tokenize("seene mein dard nahi hai, saans phool rahi hai")
    assert "<b>" in tokenize("seene mein dard nahi hai. saans phool rahi hai")


def test_negated_list_and_interjection():
    assert flags("I do not have face drooping, speech trouble, leg weakness, chest pain, or trouble walking") == set()
    assert "chest_pain" in flags("No, he has chest pain")


def test_past_history_is_not_current():
    assert flags("Pichle saal heart attack hua tha, ab follow-up karna hai") == set()
    assert "chest_pain" in flags("Pichle saal heart attack hua tha aur ab phir se seene mein dard hai")


def test_not_pregnant_is_not_pregnancy():
    assert flags("I am not pregnant and have lower abdominal pain") == set()


@pytest.mark.parametrize("text, lang", [
    ("papa ko do din se bukhar hai", "hinglish"),
    ("पापा को बुखार है", "hi"),
    ("my father has fever since two days", "en"),
])
def test_language_detection(text, lang):
    assert detect_language(text) == lang


def flags(text):
    return {h.id for h in extract(text).red_flags}


def test_negation_after_symptom():
    assert flags("saans lene mein koi dikkat nahi hai") == set()


def test_negation_before_symptom():
    assert flags("no chest pain, just a cough") == set()


def test_negation_inside_reordered_phrase():
    assert flags("dard nahi hai seene mein") == set()


def test_not_reducing_is_not_negation():
    assert "chest_pain" in flags("dard kam nahi ho raha seene mein")


def test_phrase_with_own_negation_is_positive():
    assert "breathing_difficulty" in flags("saans nahi aa rahi")


def test_negation_scope_stops_at_but():
    assert flags("seene mein dard nahi hai lekin saans phool rahi hai") == {"breathing_difficulty"}


def test_minimiser_does_not_cancel_red_flag():
    assert "chest_pain" in flags("bas thoda seene mein dard hai, gas hogi")


def test_conditional_flag_needs_context():
    assert "infant_danger_sign" in flags("mere 2 mahine ke bete ko bukhar hai")
    assert flags("mere 6 saal ke bete ko bukhar hai") == set()
    assert "pregnancy_emergency" in flags("pregnant hai aur khoon aa raha hai")
    assert flags("khoon ki jaanch karwani hai") == set()


def test_heart_attack_is_not_a_seizure():
    assert flags("dil ka daura aaya hai") == {"chest_pain"}


def test_age_vs_duration():
    ex = extract("Papa 70 saal ke hain, 3 din se bukhar hai")
    assert ex.age_years == 70 and ex.duration_days == 3 and ex.age_group == "older_adult"
    ex = extract("2 mahine se ghutne mein dard hai")
    assert ex.age_years is None and ex.duration_days == 60


@pytest.mark.parametrize("text, flag", [
    ("papa ko chestpain ho raha hai", "chest_pain"),
    ("saansnahi aa rahi", "breathing_difficulty"),
    ("breathingproblem ho rahi hai", "breathing_difficulty"),
    ("behoshhogaye papa", "unconscious"),
])
def test_joined_words_are_split(text, flag):
    assert flag in flags(text)


def test_names_and_plain_words_are_not_split():
    assert extract("sunita ko kamla ne bulaya, hospital jana hai").tokens[:5] == ["sunita", "ko", "kamla", "ne", "bulaya"]


def test_negated_severity_and_spoken_cough():
    assert "severe" not in extract("acidity hai, koi tez dard nahi").severity
    assert "sudden_confusion" in flags("nani ko achanak kuch yaad nahi jagah aur time pata nahi")  # "nahi" is the symptom's
    assert "cough" in extract("माइल्ड कफ है").symptom_ids()  # mild kaf hai


def test_or_lists_do_not_depend_on_the_language_hint():
    for hint in ("auto", "hinglish", "en"):
        assert extract("no fever or chest pain, just a mild cough", hint).red_flags == []


@pytest.mark.parametrize("text, flag", [
    ("खूनबहुतआरहाहैनाकसेसेइतनातोकभीनहीं", "severe_bleeding"),   # each word transliterated on its own
    ("सीनेमेंदर्दहैऔरसांसनहींआरहीमुझे", "breathing_difficulty"),
    ("बच्चेकोझटकेआरहेहैं", "seizure"),
    ("हाथपेंतेलहसफिसलगयाअबकालाहोगया", "severe_burn"),           # hot oil, skin gone black
    ("heartattackhorenahailogmujhekomatfeel", "chest_pain"),        # long run with everyday words
    ("breathingproblabhairha bht takleef", "breathing_difficulty"),
])
def test_run_together_text_is_split(text, flag):
    assert flag in flags(text)


def test_devanagari_runs_split_into_whole_words():
    # a word the lexicon does not know stays whole ("हजम" is not "ह ज म"), and a change of script is a break
    assert "hajam" in extract("पेटमेंदर्दहैपरखानाठीकसेहजमनहीहोरहा").tokens
    assert extract("bodyकेंपड़रहीहै").tokens[0] == "bodi"
    assert flags("पापाकोबुखारहैऔरखांसीभीहै") == set()
    assert flags("खाँसीबहुतदिनसेहैलेकिनतापमाननहींहै") == set()


def test_negation_words_are_never_split():
    from app.nlp.lexicon import get_lexicon
    assert get_lexicon().split_runs(["vithout"], ["without"])[1] == ["without"]


def test_seizure_as_families_describe_it():
    assert "seizure" in flags("pregnant hu 7 mahine, sharir kaap ne laga, aankh roll ho gayi, muh se jhaag aa gya")
    assert "seizure" in flags("baby shaking/jerking full body, eyes rolled back")
    assert flags("peshab mein jhaag aa raha hai") == set()


def test_baby_age_said_the_english_way():
    ex = extract("omg 9 month baby suddenly got fever 40C and now crying")
    assert ex.age_group == "infant" and "abnormal_vitals" in {h.id for h in ex.red_flags}
    assert extract("2 din bachche ko ulti ho rahi").age_years is None


def test_fewer_baby_kicks_in_pregnancy():
    assert "pregnancy_emergency" in flags("7th month pregnant hu, 4 ghante se baby ne ek baar bhi kick nahi kiya")
    assert flags("pregnant hu, baby kick kar raha hai bahut") == set()


def test_thunderclap_headache_needs_the_blow():
    assert "severe_headache" in flags("mummy ko bahut tez sar mein dard, like hammer maara ho")
    assert flags("sar mein hathode baj rahe hain, migraine purana hai") == set()


def test_plan_to_end_it_with_depression():
    assert "self_harm_risk" in flags("dost ko depression hai. bol raha khatam karne ka plan hai")
    assert flags("mujhe depression hai, dawai ka course khatam karne ka plan hai") == set()
    assert "self_harm_risk" in flags("my friend says he wants to kill himself")


def test_behaviour_change_in_a_diabetic():
    assert "low_sugar_signs" in flags("insulin lete hain, ab aggressive ho gaye, sweat bhi ho raha")
    assert flags("diabetic hu, khaane ka taste ajeeb hai") == set()


def test_deep_burn_and_its_look_alikes():
    assert "severe_burn" in flags("garam tel haath pe gir gaya, chamdi kali pad gayi")
    assert flags("burn ka nishan kala ho gaya hai, cream bataiye") == set()
    assert flags("baalon mein tel lagaya, baal kale ho gaye") == set()


def test_heavy_bleeding_in_either_word_order():
    assert "severe_bleeding" in flags("khoon bahut aa raha hai naak se")
    assert "severe_bleeding" in flags("he is bleeding a lot")
    assert flags("khoon bahut kam hai, hemoglobin 8") == set()


def test_months_back_is_history_but_since_is_not():
    assert flags("My grandfather had a stroke 2 months back. He needs physiotherapy") == set()
    assert flags("2 mahine pehle stroke hua tha, physiotherapy chahiye") == set()
    assert "chest_pain" in flags("2 mahine pehle se seene mein dard hai")


def test_fine_now_settles_only_a_clean_later_sentence():
    ex = extract("meeting ke time dikkat horhi breathe karne mein, bus ghabra gya hu. abhi thik hu.")
    assert ex.red_flags == [] and "breathing_difficulty" in ex.settled_flags
    assert "chest_pain" in flags("seene mein dard ho raha hai. abhi thik hu par pasina aa raha")
    assert "chest_pain" in flags("papa ko seene mein dard ho raha hai. abhi theek hain")
    assert "breathing_difficulty" in flags("ab theek se saans nahi le pa rahe")


def test_overdose_in_plain_words():
    for t in ("my mother took 20 of her BP tablets at once", "she took too many tablets", "he has taken too many pills",
              "she took a whole strip of tablets", "papa ne poori strip kha li", "neend ki goliyan kha li",
              "saari goliyan kha li", "mummy ne BP ki 20 tablets ek saath kha li"):
        assert "poisoning" in flags(t), t
    for t in ("doctor ne 2 tablets di hain", "how many tablets can I take", "ek strip mangwani hai",
              "can I take 2 tablets at once", "I take too many tablets daily", "poori strip khani hai kya?"):
        assert flags(t) == set(), t


def test_baby_under_3_months_who_feels_hot():
    for t in ("my 2 month old has a temperature of 101", "6 hafte ka baccha hai, badan bahut garam hai",
              "2 महीने के बच्चे का बदन बहुत गरम है", "my 1 month old baby feels very hot",
              "1 mahine ke bachche ka tapman bahut zyada hai", "2 mahine ka baby, high temperature"):
        assert "infant_danger_sign" in flags(t), t
    for t in ("2 mahine ke bachche ka temperature check karna hai", "my 2 month old needs a temperature check",
              "2 महीने के बच्चे का तापमान चेक करना है", "2 mahine ke bachche ko garam paani se nehla sakte hain",
              "newborn ko garam kapde pehnane hain", "my 6 month old feels very hot"):
        assert flags(t) == set(), t
