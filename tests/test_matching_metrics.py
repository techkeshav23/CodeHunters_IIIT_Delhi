from datetime import datetime

from app.matching.caregivers import IST, normalise, next_free
from app.matching.ranker import rank
from app.nlp.extract import extract
from eval.metrics import macro_f1, mrr, ndcg_at_k

REF = datetime(2026, 10, 24, 11, 0, tzinfo=IST)


def cg(cid, role, lat, lng, slots, langs, skills=(), rating=4.5, specialty=None):
    return normalise({"caregiver_id": cid, "role": role, "location": {"lat": lat, "lng": lng},
                      "availability": list(slots), "languages": list(langs), "skills": list(skills),
                      "rating": rating, "rating_count": 50, "specialty": specialty})


def test_next_free_formats():
    assert next_free(["today 16:00"], REF).hour == 16
    assert next_free(["today 09:00"], REF) is None
    assert next_free(["today 09:00", "tomorrow 10:00"], REF).day == 25
    assert next_free(["daily 09:00-20:00"], REF) == REF
    assert next_free(["2026-10-24T15:30:00+05:30"], REF).minute == 30


def test_home_visit_prefers_near_and_hindi():
    pool = [cg("far", "paramedic", 28.40, 77.32, ["today 12:00"], ["Hindi"]),
            cg("near_en", "paramedic", 28.541, 77.271, ["today 12:00"], ["English"]),
            cg("near_hi", "paramedic", 28.542, 77.272, ["today 12:00"], ["Hindi"])]
    ex = extract("papa ko bukhar hai")
    out = rank("paramedic", "same_day", ex, (28.54, 77.27), caregivers=pool, ref=REF)
    assert [m.caregiver.id for m in out][0] == "near_hi"
    assert "km away" in out[0].reason and "free at 12 pm" in out[0].reason


def test_teleconsult_ignores_distance():
    pool = [cg("far_soon", "gp", 28.90, 77.60, ["today 11:30"], ["Hindi"]),
            cg("near_late", "gp", 28.541, 77.271, ["tomorrow 18:00"], ["Hindi"])]
    out = rank("gp", "same_day", extract("halka zukam hai"), (28.54, 77.27), caregivers=pool, ref=REF)
    assert out[0].caregiver.id == "far_soon" and "km" not in out[0].reason


def test_specialist_specialty_first():
    pool = [cg("derm", "specialist", 28.55, 77.27, ["tomorrow 10:00"], ["Hindi"], specialty="dermatology"),
            cg("ortho", "specialist", 28.55, 77.27, ["tomorrow 10:00"], ["Hindi"], specialty="orthopaedics")]
    out = rank("specialist", "routine", extract("2 mahine se ghutne mein dard"), (28.54, 77.27),
               specialty="orthopaedics", caregivers=pool, ref=REF)
    assert out[0].caregiver.id == "ortho"


def test_emergency_gets_no_caregivers():
    assert rank("emergency", "immediate", extract("behosh"), (28.54, 77.27), ref=REF) == []


def test_metrics():
    assert macro_f1(["a", "a", "b"], ["a", "a", "b"]) == 1.0
    assert abs(macro_f1(["a", "b"], ["a", "a"]) - (2 / 3) / 2) < 1e-9
    assert ndcg_at_k(["x", "y", "z"], ["x", "y"], 3) == 1.0
    assert ndcg_at_k(["z", "y", "x"], ["x"], 3) < 1.0
    assert mrr(["z", "x"], ["x"]) == 0.5
