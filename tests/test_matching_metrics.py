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


def test_specialty_words_and_roles():
    pool = [cg("ent", "specialist", 28.55, 77.27, ["tomorrow 10:00"], ["Hindi"], specialty="ENT"),
            cg("mind", "specialist", 28.55, 77.27, ["today 12:00"], ["Hindi"], specialty="mental health"),
            cg("neuro", "specialist", 28.55, 77.27, ["today 12:00"], ["Hindi"], specialty="neurology"),
            cg("uro", "specialist", 28.55, 77.27, ["tomorrow 10:00"], ["Hindi"], specialty="urology"),
            cg("heart", "Cardiologist", 28.55, 77.27, ["tomorrow 10:00"], ["Hindi"])]
    ex = extract("kaan mein dard hai")

    def top(specialty):
        return rank("specialist", "routine", ex, (28.54, 77.27), specialty=specialty, caregivers=pool, ref=REF)[0]
    assert top("ent").caregiver.id == "ent"            # not "mental health"
    assert top("urology").caregiver.id == "uro"        # not "neurology"
    assert top("cardiology").caregiver.id == "heart"   # matched by role alone
    assert top("psychiatry").caregiver.id == "mind"


def test_no_free_slot_is_demoted_not_dropped():
    pool = [cg("gone", "paramedic", 28.541, 77.271, ["today 09:00"], ["Hindi"]),
            cg("tomorrow", "paramedic", 28.55, 77.28, ["tomorrow 10:00"], ["Hindi"])]
    out = rank("paramedic", "routine", extract("papa ka BP check karna hai"), (28.54, 77.27), caregivers=pool, ref=REF)
    assert [m.caregiver.id for m in out] == ["tomorrow", "gone"]
    assert "no free slot" in out[1].reason


def test_loader_tolerates_odd_files(tmp_path):
    from app.matching.caregivers import _load_rows
    p = tmp_path / "cg.json"
    p.write_text('\ufeff{"CG_9": {"role": "MBBS", "languages": "", "rating": "NaN", "rating_count": null},'
                 ' "CG_10": {"role": "nurse", "skills": "[\\"wound dressing\\"]"}}', encoding="utf-8")
    rows = {c.id: c for c in _load_rows(p)}
    assert set(rows) == {"CG_9", "CG_10"}
    assert rows["CG_9"].rating is None and rows["CG_9"].languages == [] and rows["CG_10"].skills == ["wound dressing"]
    csv_path = tmp_path / "cg.csv"
    csv_path.write_text("name,role,languages\nAsha,nurse,\"[\"\"Hindi\"\", \"\"English\"\"]\"\n", encoding="utf-8")
    (only,) = _load_rows(csv_path)
    assert only.id == "CG_001" and only.languages == ["Hindi", "English"]
