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
    assert "<b>" in tokenize("seene mein dard nahi hai, saans phool rahi hai")


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
