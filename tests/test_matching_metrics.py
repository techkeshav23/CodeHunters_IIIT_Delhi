import json
from datetime import datetime

import pytest

from app import config
from app.matching import caregivers as cg_mod
from app.matching.caregivers import DEV_SAMPLE, IST, ORG_ROSTER, _load_rows, next_free, normalise
from app.matching.ranker import WEIGHTS, haversine_km, rank
from app.nlp.extract import extract
from eval.metrics import macro_f1, mrr, ndcg_at_k

REF = datetime(2026, 10, 24, 11, 0, tzinfo=IST)
HOME = (28.54, 77.27)
LABELS = config.ORG_DATA_DIR / "triage_dataset.jsonl"


def roster_row(cid, role, lat, lng, langs, skills=(), rating=4.5, radius=10, window=("09:00", "18:00"),
               active=True, **extra):
    """A caregiver written the way the organisers' caregivers.csv writes one."""
    return normalise({"caregiver_id": cid, "name": cid.title(), "role": role, "base_lat": lat, "base_lng": lng,
                      "languages": ";".join(langs), "skills": ";".join(skills), "rating": rating,
                      "max_radius_km": radius, "free_from": window[0], "free_until": window[1],
                      "active": str(active), **extra})


def cg(cid, role, lat, lng, slots, langs, skills=(), rating=4.5, specialty=None):
    """A caregiver in the dev sample's layout (location dict, slot list, no radius)."""
    return normalise({"caregiver_id": cid, "role": role, "location": {"lat": lat, "lng": lng},
                      "availability": list(slots), "languages": list(langs), "skills": list(skills),
                      "rating": rating, "rating_count": 50, "specialty": specialty})


def ids(matches):
    return [m.caregiver.id for m in matches]


def test_next_free_formats():
    assert next_free(["today 16:00"], REF).hour == 16
    assert next_free(["today 09:00"], REF) is None
    assert next_free(["today 09:00", "tomorrow 10:00"], REF).day == 25
    assert next_free(["daily 09:00-20:00"], REF) == REF
    assert next_free(["2026-10-24T15:30:00+05:30"], REF).minute == 30
    assert next_free(["daily 09:00-15:00"], REF) == REF  # the roster's window, already open


def test_home_visit_nearest_same_language_first():
    vit = ["vitals_monitoring"]
    pool = [roster_row("far_hi", "medic", 28.60, 77.27, ["Hindi"], vit),        # ~6.7 km
            roster_row("near_ta", "medic", 28.541, 77.271, ["Tamil"], vit),     # no shared language
            roster_row("near_hi", "medic", 28.542, 77.272, ["Hindi"], vit)]
    out = rank("paramedic", "same_day", extract("papa ko bukhar hai"), HOME, caregivers=pool, ref=REF)
    assert ids(out) == ["near_hi", "far_hi", "near_ta"]
    assert out[0].reason == "Hindi-speaking, 0.3 km away, free 09:00–18:00"
    assert out[0].reason_local == "Hindi bolte hain, 0.3 km door, 09:00–18:00 free"
    assert out[2].features["language"] == 0.0 and out[0].features["language"] == 1.0
    assert all(set(m.features) == set(WEIGHTS) and all(0 <= v <= 1 for v in m.features.values()) for m in out)
    assert [m.score for m in out] == sorted((m.score for m in out), reverse=True)


def test_score_is_the_reference_blend():
    pool = [roster_row("a", "medic", 28.55, 77.27, ["Hindi"], ["vitals_monitoring"], rating=4.4, radius=12),
            roster_row("lo", "medic", 28.70, 77.10, ["Hindi"], ["vitals_monitoring"], rating=3.8, radius=5),
            roster_row("hi", "medic", 28.70, 77.10, ["Hindi"], ["vitals_monitoring"], rating=5.0, radius=5)]
    (m,) = rank("paramedic", "same_day", extract("papa ko bukhar hai"), HOME, caregivers=pool, ref=REF)
    d = haversine_km(*HOME, 28.55, 77.27)
    # proximity scales by the largest radius on the roster (12 km), rating by its range (3.8 to 5.0)
    expected = 0.35 * 1 + 0.30 * (1 - d / 12) + 0.20 * 1 + 0.15 * ((4.4 - 3.8) / 1.2)
    assert m.distance_km == 1.1 and m.score == round(expected, 2) == 0.90
    assert m.features == {"language": 1.0, "distance": 0.91, "skill": 1.0, "rating": 0.5}


def test_english_request_and_score_cap():
    pool = [roster_row("hi_only", "medic", 28.541, 77.271, ["Hindi"], ["wound_dressing"], rating=5.0),
            roster_row("en", "medic", 28.541, 77.271, ["Hindi", "English"], ["wound_dressing"], rating=5.0),
            roster_row("low", "medic", 28.541, 77.271, ["Hindi"], ["wound_dressing"], rating=4.0)]
    out = rank("nurse", "same_day", extract("Need wound dressing at home after surgery"), HOME,
               caregivers=pool, ref=REF)
    # Hindi counts for English requests too (as in the labels), so the tie keeps roster order
    assert ids(out) == ["hi_only", "en", "low"]
    assert out[0].score == out[1].score == 0.99  # capped
    assert out[0].reason.startswith("Hindi-speaking") and out[1].reason.startswith("English-speaking")


def test_teleconsult_ignores_distance():
    pool = [roster_row("near", "doctor", 28.541, 77.271, ["Hindi"], ["teleconsultation"], rating=4.2, radius=5),
            roster_row("far", "doctor", 28.90, 77.60, ["Hindi"], ["teleconsultation"], rating=4.9, radius=5,
                       window=("13:00", "16:00"))]
    out = rank("gp", "same_day", extract("halka zukam hai"), HOME, caregivers=pool, ref=REF)
    assert ids(out) == ["far", "near"]  # 50 km away, outside its radius, still matched: it is a video call
    assert out[0].reason == "Hindi-speaking, free 13:00–16:00, ★4.9" and "km" not in out[0].reason
    assert out[0].features["distance"] == 1.0


def test_inactive_and_out_of_radius_never_returned():
    vit = ["vitals_monitoring"]
    pool = [roster_row("inactive", "medic", 28.5401, 77.2701, ["Hindi"], vit, rating=5.0, active=False),
            roster_row("outside", "medic", 28.59, 77.27, ["Hindi"], vit, radius=5),     # 5.6 km, serves 5
            roster_row("inside", "medic", 28.56, 77.27, ["Hindi"], vit, radius=5),      # 2.2 km
            roster_row("no_skill", "medic", 28.541, 77.271, ["Hindi"], ["wound_dressing"])]
    out = rank("paramedic", "same_day", extract("papa ko bukhar hai"), HOME, top_k=10, caregivers=pool, ref=REF)
    assert ids(out) == ["inside"]
    assert rank("paramedic", "same_day", extract("papa ko bukhar hai"), HOME, caregivers=pool[:2], ref=REF) == []
    assert ids(rank("gp", "same_day", extract("halka zukam hai"), HOME, caregivers=[
        roster_row("doc_off", "doctor", 28.54, 77.27, ["Hindi"], active=False)], ref=REF)) == []


def test_nursing_needs_the_procedure_asked_for():
    pool = [roster_row("dresser", "medic", 28.541, 77.271, ["Hindi"], ["wound_dressing", "elderly_care"]),
            roster_row("injector", "medic", 28.55, 77.28, ["Hindi"], ["injection_im"]),
            roster_row("phlebo", "phlebotomist", 28.541, 77.271, ["Hindi"], ["sample_collection"])]
    assert ids(rank("nurse", "same_day", extract("ghar pe IM injection lagwana hai"), HOME,
                    caregivers=pool, ref=REF)) == ["injector"]
    assert ids(rank("nurse", "same_day", extract("operation ke baad ghar pe dressing karani hai"), HOME,
                    caregivers=pool, ref=REF)) == ["dresser"]
    assert ids(rank("lab", "routine", extract("cbc aur thyroid test ghar se sample lekar"), HOME,
                    caregivers=pool, ref=REF)) == ["phlebo"]


def test_specialist_specialty_first():
    pool = [cg("derm", "specialist", 28.55, 77.27, ["tomorrow 10:00"], ["Hindi"], specialty="dermatology"),
            cg("ortho", "specialist", 28.55, 77.27, ["tomorrow 10:00"], ["Hindi"], specialty="orthopaedics")]
    out = rank("specialist", "routine", extract("2 mahine se ghutne mein dard"), (28.54, 77.27),
               specialty="orthopaedics", caregivers=pool, ref=REF)
    assert out[0].caregiver.id == "ortho" and "other department" in out[1].reason


def test_specialist_falls_back_to_the_rosters_doctors():
    pool = [roster_row("doc", "doctor", 28.7, 77.1, ["Hindi"], ["teleconsultation"]),
            roster_row("medic", "medic", 28.54, 77.27, ["Hindi"], ["vitals_monitoring"])]
    out = rank("specialist", "routine", extract("2 mahine se ghutne mein dard"), HOME,
               specialty="orthopaedics", caregivers=pool, ref=REF)
    assert ids(out) == ["doc"] and "km" not in out[0].reason


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


def test_availability_is_shown_not_scored():
    pool = [cg("gone", "paramedic", 28.541, 77.271, ["today 09:00"], ["Hindi"], ["vitals check"]),
            cg("tomorrow", "paramedic", 28.55, 77.28, ["tomorrow 10:00"], ["Hindi"], ["vitals check"])]
    out = rank("paramedic", "routine", extract("papa ka BP check karna hai"), (28.54, 77.27), caregivers=pool, ref=REF)
    assert ids(out) == ["gone", "tomorrow"]  # nearer first; a past slot does not drop anyone
    assert "no free slot listed" in out[0].reason and out[1].reason.endswith("free tomorrow 10:00")


def test_dev_sample_uses_the_same_recipe():
    pool = _load_rows(DEV_SAMPLE)
    out = rank("paramedic", "same_day", extract("papa ko bukhar hai"), HOME, caregivers=pool, ref=REF)
    assert out and all(m.distance_km <= config.MAX_HOME_VISIT_KM for m in out)
    assert all("km away" in m.reason and set(m.features) == set(WEIGHTS) for m in out)
    assert [m.score for m in out] == sorted((m.score for m in out), reverse=True)
    nurse = rank("nurse", "same_day", extract("ghar pe injection lagwana hai"), HOME, caregivers=pool, ref=REF)
    assert nurse and all("injection" in m.caregiver.skills for m in nurse)
    assert not any(m.caregiver.role == "paramedic" for m in nurse)  # "medic" is not "paramedic"


def test_loader_reads_the_organisers_roster(tmp_path):
    rows = {c.id: c for c in _load_rows(ORG_ROSTER)}
    assert len(rows) == 60 and sum(not c.active for c in rows.values()) == 8
    c = rows["CG_002"]
    assert (c.role, c.lat, c.lng, c.radius_km, c.area) == ("medic", 28.4704, 77.5004, 5.0, "Greater Noida")
    assert c.languages == ["Hindi", "English", "Punjabi"] and "injection_im" in c.skills
    assert (c.free_from, c.free_until, c.window, c.slots) == ("09:00", "15:00", "09:00–15:00", ["daily 09:00-15:00"])
    assert (c.tier, c.qualification, c.experience_years, c.gender, c.rating) == ("base", "B.Sc Nursing", 9.0, "male", 4.2)
    assert not rows["CG_007"].active and rows["CG_001"].tier is None
    p = tmp_path / "roster.csv"
    p.write_text("Caregiver ID,Role,Languages,Skills,Base Lat,Base Lng,Max Radius KM,Free From,Free Until,Active\n"
                 "X1,medic,Hindi; English,injection_im;wound_dressing,28.5,77.2,7,9:00:00,6 pm,FALSE\n", encoding="utf-8")
    (x,) = _load_rows(p)
    assert (x.id, x.radius_km, x.free_from, x.free_until, x.active) == ("X1", 7.0, "09:00", "18:00", False)
    assert x.languages == ["Hindi", "English"] and x.skills == ["injection_im", "wound_dressing"]


def test_default_source_order(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CAREGIVERS_PATH", None)
    monkeypatch.setattr(config, "PROVIDED_DIR", tmp_path)
    assert cg_mod.source_path() == (ORG_ROSTER, "sanocare_v1")
    cg_mod.load.cache_clear()
    try:
        pool, source = cg_mod.load()
        assert source == "sanocare_v1" and len(pool) == 60
        (tmp_path / "caregivers.json").write_text('[{"caregiver_id": "P1", "role": "nurse"}]', encoding="utf-8")
        assert cg_mod.source_path()[1] == "provided"
        monkeypatch.setattr(config, "CAREGIVERS_PATH", str(tmp_path / "missing.csv"))
        assert cg_mod.source_path()[1] == "env"
        cg_mod.load.cache_clear()
        pool, source = cg_mod.load()  # unreadable env file: the next source, and /health says so
        assert source.startswith("provided_fallback") and [c.id for c in pool] == ["P1"]
    finally:
        cg_mod.load.cache_clear()


def test_loader_tolerates_odd_files(tmp_path):
    p = tmp_path / "cg.json"
    p.write_text('﻿{"CG_9": {"role": "MBBS", "languages": "", "rating": "NaN", "rating_count": null},'
                 ' "CG_10": {"role": "nurse", "skills": "[\\"wound dressing\\"]"}}', encoding="utf-8")
    rows = {c.id: c for c in _load_rows(p)}
    assert set(rows) == {"CG_9", "CG_10"}
    assert rows["CG_9"].rating is None and rows["CG_9"].languages == [] and rows["CG_10"].skills == ["wound dressing"]
    assert rows["CG_9"].active and rows["CG_9"].radius_km is None and rows["CG_9"].window is None
    csv_path = tmp_path / "cg.csv"
    csv_path.write_text("name,role,languages\nAsha,nurse,\"[\"\"Hindi\"\", \"\"English\"\"]\"\n", encoding="utf-8")
    (only,) = _load_rows(csv_path)
    assert only.id == "CG_001" and only.languages == ["Hindi", "English"]


# ---- the organisers' reference labels ------------------------------------------------------

def _labelled():
    lines = LABELS.read_text(encoding="utf-8").splitlines()
    return {r["id"]: r for r in (json.loads(line) for line in lines if line.strip())}


def _ours(row, pool):
    req, resp = row["request"], row["response"]
    loc = req["location"]
    return rank(config.internal_care(resp["care_type"]), config.internal_urgency(resp["urgency"]),
                extract(req["user_input"]), (loc["lat"], loc["lng"]), caregivers=pool, ref=REF)


@pytest.mark.parametrize("rid", ["S0003", "S0006", "S0007", "S0012", "S0023", "S0036", "S0037", "S0058",
                                 "S0069", "S0072", "S0099", "S0001", "S0031"])
def test_reproduces_labelled_rows(rid):
    row = _labelled()[rid]
    gold = row["response"]["matched_caregivers"]
    ours = _ours(row, _load_rows(ORG_ROSTER))
    # each label keeps the first 1-3 of the reference ranking; an empty label means nobody is eligible
    assert [(m.caregiver.id, m.score) for m in ours[:len(gold)]] == [(g["caregiver_id"], g["score"]) for g in gold]
    assert bool(ours) == bool(gold)
    for m, g in zip(ours, gold):
        # same facts and wording; the labels name the request's language even when the caregiver
        # does not list it, we name the one they share
        assert m.reason.split(", ")[1:] == g["reason"].split(", ")[1:]
        if row["detected_language"] != "English" or "English" in m.caregiver.languages:
            assert m.reason == g["reason"]


def test_reproduces_all_labelled_rows():
    pool = _load_rows(ORG_ROSTER)
    rows = [r for r in _labelled().values() if r["response"]["care_type"] not in (None, "emergency_112")]
    same = 0
    for r in rows:
        gold = [g["caregiver_id"] for g in r["response"]["matched_caregivers"]]
        ours = [m.caregiver.id for m in _ours(r, pool)]
        same += ours[:len(gold)] == gold and bool(ours) == bool(gold)
    assert len(rows) == 245 and same / len(rows) >= 0.95  # 245/245 when written
