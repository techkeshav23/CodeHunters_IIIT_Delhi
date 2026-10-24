import json
from datetime import datetime

import pytest

from app import config
from app.matching import caregivers as cg_mod
from app.matching import ranker
from app.matching.caregivers import DEV_SAMPLE, IST, ORG_ROSTER, _load_rows, next_free, normalise, open_until
from app.matching.ranker import WEIGHTS, haversine_km, needed_skills, rank
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


def test_open_until():
    assert open_until(["daily 09:00-15:00"], REF) == REF.replace(hour=15)
    assert open_until(["daily 11:00-12:00"], REF) == REF.replace(hour=12)   # opens on the dot: free now
    assert open_until(["daily 08:00-11:00"], REF) is None                   # closed on the dot
    assert open_until(["daily 15:00-21:00"], REF) is None                   # not open yet
    assert open_until(["today 10:00", "daily 09:00"], REF) is None          # start times only: no end
    assert open_until(["2026-10-24T10:00:00+05:30/2026-10-24T13:30:00+05:30"], REF).minute == 30
    assert open_until([], REF) is None


def test_home_visit_nearest_same_language_first():
    vit = ["vitals_monitoring"]
    pool = [roster_row("far_hi", "medic", 28.60, 77.27, ["Hindi"], vit),        # ~6.7 km
            roster_row("near_ta", "medic", 28.541, 77.271, ["Tamil"], vit),     # no shared language
            roster_row("near_hi", "medic", 28.542, 77.272, ["Hindi"], vit)]
    out = rank("paramedic", "same_day", extract("papa ko bukhar hai"), HOME, caregivers=pool, ref=REF)
    assert ids(out) == ["near_hi", "far_hi", "near_ta"]
    assert out[0].reason == "Hindi-speaking, 0.3 km away, free now till 6 pm"
    assert out[0].reason_local == "Hindi bolte hain, 0.3 km door, abhi free (shaam 6 baje tak)"
    assert out[0].free_now and out[0].next_slot == REF
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
    assert out[0].reason == "Hindi-speaking, free from 1 pm, ★4.9" and "km" not in out[0].reason
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
    assert "no free slot listed" in out[0].reason and out[1].reason.endswith("free tomorrow from 10 am")
    assert out[1].reason_local.endswith("kal subah 10 baje se free")


@pytest.mark.parametrize("hour, en, hinglish, hindi", [
    (11, "free from 3 pm", "aaj dopahar 3 baje se free", "आज दोपहर 3 बजे से खाली"),
    (16, "free now till 9 pm", "abhi free (raat 9 baje tak)", "अभी खाली (रात 9 बजे तक)"),
    (22, "free tomorrow from 3 pm", "kal dopahar 3 baje se free", "कल दोपहर 3 बजे से खाली"),
])
def test_availability_words_follow_the_clock(hour, en, hinglish, hindi):
    pool = [roster_row("m", "medic", 28.541, 77.271, ["Hindi"], ["vitals_monitoring"], window=("15:00", "21:00"))]
    clock = REF.replace(hour=hour)
    for text, local in (("papa ko bukhar hai", hinglish), ("पापा को बुखार है", hindi), ("my father has fever", en)):
        (m,) = rank("paramedic", "same_day", extract(text), HOME, caregivers=pool, ref=clock)
        assert m.reason == f"Hindi-speaking, 0.1 km away, {en}"
        assert m.reason_local.endswith(local)
        assert m.free_now == (hour == 16) and m.score == 0.99  # the clock never changes the score


def test_injectable_clock_defaults_to_cc_now(monkeypatch):
    pool = [roster_row("m", "medic", 28.541, 77.271, ["Hindi"], ["vitals_monitoring"], window=("15:00", "21:00"))]
    monkeypatch.setattr(config, "NOW_OVERRIDE", "2026-10-24T16:00:00+05:30")
    (m,) = rank("paramedic", "same_day", extract("papa ko bukhar hai"), HOME, caregivers=pool)
    assert m.free_now and m.reason.endswith("free now till 9 pm")


def _tied_pool():
    # same language, place, skill and rating, so the same score; "over" is first on the roster
    vit = ["vitals_monitoring"]
    return [roster_row("over", "medic", 28.541, 77.271, ["Hindi"], vit, window=("08:00", "11:00")),
            roster_row("later", "medic", 28.541, 77.271, ["Hindi"], vit, window=("16:00", "21:00")),
            roster_row("now", "medic", 28.541, 77.271, ["Hindi"], vit, window=("10:00", "14:00"))]


def test_ties_keep_roster_order_by_default():
    out = rank("paramedic", "same_day", extract("papa ko bukhar hai"), HOME, caregivers=_tied_pool(), ref=REF)
    assert ids(out) == ["over", "later", "now"]  # the labels' order: availability does not decide
    assert len({m.score for m in out}) == 1
    assert out[0].reason.endswith("free tomorrow from 8 am") and out[2].reason.endswith("free now till 2 pm")


def test_ties_by_availability():
    ex = extract("papa ko bukhar hai")
    same_day = rank("paramedic", "same_day", ex, HOME, caregivers=_tied_pool(), ref=REF, ties="available")
    assert ids(same_day) == ["later", "now", "over"]  # still free today beats a window that is over
    routine = rank("paramedic", "routine", ex, HOME, caregivers=_tied_pool(), ref=REF, ties="available")
    assert ids(routine) == ["over", "later", "now"]   # a scheduled request: roster order
    soonest = rank("paramedic", "routine", ex, HOME, caregivers=_tied_pool(), ref=REF, ties="soonest")
    assert ids(soonest) == ["now", "later", "over"]   # free now, 4 pm today, 8 am tomorrow
    assert {m.score for m in same_day + routine + soonest} == {same_day[0].score}
    # availability only breaks ties: a better score still wins
    pool = _tied_pool()[:1] + [roster_row("far_now", "medic", 28.60, 77.27, ["Hindi"], ["vitals_monitoring"],
                                          window=("10:00", "14:00"))]
    assert ids(rank("paramedic", "same_day", ex, HOME, caregivers=pool, ref=REF, ties="soonest")) == ["over", "far_now"]


def test_tie_mode_from_env(monkeypatch):
    monkeypatch.setattr(ranker, "TIES", "available")
    assert ids(rank("paramedic", "same_day", extract("papa ko bukhar hai"), HOME,
                    caregivers=_tied_pool(), ref=REF))[0] == "later"
    monkeypatch.setattr(ranker, "TIES", "nonsense")  # an unknown mode: roster order
    assert ids(rank("paramedic", "same_day", extract("papa ko bukhar hai"), HOME,
                    caregivers=_tied_pool(), ref=REF))[0] == "over"


def test_advanced_procedures_need_a_senior_medic():
    iv = ["injection_iv", "injection_im"]
    std = roster_row("std", "medic", 28.541, 77.271, ["Hindi"], iv, rating=5.0, tier="standard")
    adv = roster_row("adv", "medic", 28.56, 77.27, ["Hindi"], iv, rating=4.0, tier="advanced")
    exp = roster_row("exp", "medic", 28.57, 77.27, ["Hindi"], iv + ["catheter_care"], rating=4.0, tier="expert")
    drip = extract("ghar pe drip lagwani hai")
    assert needed_skills(drip, "nurse") == ["injection_iv"]
    out = rank("nurse", "same_day", drip, HOME, caregivers=[std, adv, exp], ref=REF)
    assert ids(out) == ["adv", "exp"]  # the standard medic scores higher but is left out
    assert out[0].reason.endswith(", advanced-tier medic") and out[0].reason_local.endswith(", advanced medic")
    assert out[1].reason.endswith(", expert-tier medic")
    # nobody senior in range: the others, saying so
    far_adv = roster_row("adv", "medic", 28.70, 77.27, ["Hindi"], iv, tier="advanced", radius=5)
    (m,) = rank("nurse", "same_day", drip, HOME, caregivers=[std, far_adv], ref=REF)
    assert m.caregiver.id == "std"
    assert m.reason.endswith(", standard-tier medic (no advanced-tier medic in range)")
    assert m.reason_local.endswith(", standard medic (paas mein advanced medic nahi)")
    (m,) = rank("nurse", "same_day", extract("घर पर ड्रिप लगवानी है"), HOME, caregivers=[std], ref=REF)
    assert m.reason_local.endswith(", स्टैंडर्ड मेडिक (पास में एडवांस्ड मेडिक नहीं)")
    # catheter care too; an IM injection does not need a senior medic
    cath = roster_row("cath_std", "medic", 28.541, 77.271, ["Hindi"], ["catheter_care"], tier="standard")
    assert ids(rank("nurse", "same_day", extract("papa ka catheter badalna hai"), HOME,
                    caregivers=[cath, exp], ref=REF)) == ["exp"]
    im = rank("nurse", "same_day", extract("ghar pe IM injection lagwana hai"), HOME, caregivers=[std, adv], ref=REF)
    assert ids(im) == ["std", "adv"] and "tier" not in im[0].reason


def test_no_tier_on_the_roster_means_no_tier_rule():
    iv = ["injection_iv"]
    pool = [roster_row("a", "medic", 28.541, 77.271, ["Hindi"], iv), roster_row("b", "medic", 28.55, 77.27, ["Hindi"], iv)]
    out = rank("nurse", "same_day", extract("ghar pe drip lagwani hai"), HOME, caregivers=pool, ref=REF)
    assert ids(out) == ["a", "b"] and not any("tier" in m.reason for m in out)


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
                                 "S0069", "S0072", "S0099", "S0001", "S0031", "S0105"])
def test_reproduces_labelled_rows(rid):
    row = _labelled()[rid]
    gold = row["response"]["matched_caregivers"]
    ours = _ours(row, _load_rows(ORG_ROSTER))
    # each label keeps the first 1-3 of the reference ranking; an empty label means nobody is eligible
    assert [(m.caregiver.id, m.score) for m in ours[:len(gold)]] == [(g["caregiver_id"], g["score"]) for g in gold]
    assert bool(ours) == bool(gold)
    for m, g in zip(ours, gold):
        # same facts and wording, except availability: the labels write the roster's window, we
        # say what it means at the clock's time. The labels name the request's language even when
        # the caregiver does not list it; we name the one they share.
        mine, theirs = m.reason.split(", "), g["reason"].split(", ")
        (free,) = [p for p in theirs if p.startswith("free ")]
        assert f"free {m.caregiver.window}" == free  # the window the label shows is the one we read
        clock_words = ranker._free_parts(next_free(m.caregiver.slots, REF), open_until(m.caregiver.slots, REF), REF)
        assert clock_words[0] in mine
        assert [p for p in mine[1:] if p != clock_words[0]] == [p for p in theirs[1:] if p != free]
        if row["detected_language"] != "English" or "English" in m.caregiver.languages:
            assert m.reason == g["reason"].replace(free, clock_words[0])


def test_reproduces_all_labelled_rows():
    pool = _load_rows(ORG_ROSTER)
    rows = [r for r in _labelled().values() if r["response"]["care_type"] not in (None, "emergency_112")]
    same = 0
    for r in rows:
        gold = [g["caregiver_id"] for g in r["response"]["matched_caregivers"]]
        matches = _ours(r, pool)
        ours = [m.caregiver.id for m in matches]
        same += ours[:len(gold)] == gold and bool(ours) == bool(gold)
        assert not any("tier" in m.reason for m in matches)  # no labelled row asks for IV or catheter care
    assert len(rows) == 245 and same / len(rows) >= 0.95  # 245/245 when written


@pytest.mark.parametrize("hour", [7, 11, 13, 15, 17, 19, 22])
def test_labels_reproduced_at_any_hour(hour):
    # with the default (roster) tie order the clock changes the words, never the list
    from scripts.eval_matching import evaluate
    rows = list(_labelled().values())
    m = evaluate(rows, _load_rows(ORG_ROSTER), show=0, ref=REF.replace(hour=hour))
    assert (m["label_has_caregivers"], m["list_match"], m["list_and_scores_match"], m["ndcg_at_3"]) == (209, 1.0, 1.0, 1.0)
    assert m["empty_agreement"] == 1.0 and m["reason_same_except_lang_time"] == 1.0


def test_availability_ties_reorder_labelled_ties():
    # why ties="available" is not the default: at 11:00 CG_014's window (08:00-11:00) has just
    # closed, so the equal-score CG_019 (free now) goes first; the label keeps roster order
    row = _labelled()["S0105"]
    assert [g["caregiver_id"] for g in row["response"]["matched_caregivers"]] == ["CG_014"]
    loc = row["request"]["location"]
    out = rank("nurse", "same_day", extract(row["request"]["user_input"]), (loc["lat"], loc["lng"]),
               caregivers=_load_rows(ORG_ROSTER), ref=REF, ties="available")
    assert ids(out)[:2] == ["CG_019", "CG_014"] and out[0].score == out[1].score


def test_eval_script_uses_a_fixed_clock(monkeypatch, capsys):
    from scripts import eval_matching
    monkeypatch.setattr(config, "NOW_OVERRIDE", None)  # main() sets it; restored after the test
    monkeypatch.setattr(ranker, "TIES", "roster")
    assert eval_matching.main(["--json", "--min-list-match", "1.0"]) == 0
    first = capsys.readouterr().out
    assert config.NOW_OVERRIDE == eval_matching.DEFAULT_NOW
    assert eval_matching.main(["--json"]) == 0
    assert capsys.readouterr().out == first  # repeatable
    m = json.loads(first)
    assert m["list_match"] == 1.0 and m["list_match_by_ties"]["roster"] == "209/209"
