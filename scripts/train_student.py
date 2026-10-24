"""Train the triage student: MuRIL fine-tuned on the teacher's messages (scripts/gen_data.py).

Steps:
1. prepare  - clean the generated messages: drop duplicates, drop anything too close to the
              organisers' 340 rows (they are the TEST set), drop non-emergency messages in
              which the red-flag rules see a danger sign, add Roman-script copies of Hindi
              messages and light typos, and build multi-turn examples (vague message ->
              our question -> the answer) so the model reads conversation_history.
2. holdout  - train with some whole case families held out, to pick the number of epochs,
              calibrate the probabilities (temperature) and set the emergency threshold on
              families the model has not seen.
3. final    - train on all families with those settings.
4. export   - ONNX (fp32) into models/student/ (model.onnx, tokenizer.json, meta.json).
5. test     - run the exported model (the exact serving code) on the organisers' 340 rows.

    .venv-train\\Scripts\\python -m scripts.train_student            # all steps
    .venv-train\\Scripts\\python -m scripts.train_student --epochs 4 --skip-holdout
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import internal_care, internal_urgency  # noqa: E402
from app.triage.student import compose  # noqa: E402
from scripts.gen_data import FAMILIES, TAGS, WHO  # noqa: E402

RAW = ROOT / "data" / "generated" / "raw"
PREPARED = ROOT / "data" / "generated" / "train.jsonl"
OUT = ROOT / "models" / "student"
BASE = "google/muril-base-cased"

CARE = ["paramedic", "nurse", "lab", "gp", "emergency", "followup", "out_of_scope"]
URGENCY = ["routine", "same_day", "immediate"]
FLAGS = ["chest_pain", "breathlessness", "unconsciousness", "severe_bleeding", "stroke_symptoms", "seizure",
         "high_fever_infant", "suicidal_ideation", "severe_dehydration", "other_emergency"]
FAMILY = {f[0]: f for f in FAMILIES}

# Our own follow-up questions (as the bot asks them), used to build multi-turn examples.
ASK = {
    "hinglish": ["Zaroor madad karenge. Kiske liye hai, aur kya takleef ya zaroorat hai?",
                 "Kitne din se ho raha hai?", "Mareez ki umar kitni hai?",
                 "Kya saans lene mein dikkat, seene mein dard, behoshi ya bahut tez khoon behna jaisa kuch hai?"],
    "hi": ["ज़रूर मदद करेंगे। किसके लिए है, और क्या तकलीफ़ या ज़रूरत है?", "कितने दिन से हो रहा है?",
           "मरीज़ की उम्र कितनी है?", "क्या सांस लेने में दिक्कत, सीने में दर्द, बेहोशी या बहुत खून बहना जैसा कुछ है?"],
    "en": ["Happy to help. Who is this for, and what is the problem or service you need?",
           "Since how many days?", "How old is the patient?",
           "Is there any trouble breathing, chest pain, fainting or heavy bleeding?"],
}
NO = {"hinglish": ["nahi", "nahi aisa kuch nahi", "na ji"], "hi": ["नहीं", "नहीं, ऐसा कुछ नहीं"], "en": ["no", "no nothing like that"]}
DAYS = {"hinglish": ["2 din se", "kal se", "teen din se", "ek hafte se"], "hi": ["दो दिन से", "कल से", "तीन दिन से"],
        "en": ["2 days", "since yesterday", "about a week"]}


def labels_of(fam_id: str) -> dict:
    _, care, urgency, flags, _, _ = FAMILY[fam_id]
    if care is None:
        c = "out_of_scope" if fam_id.startswith("O_") else "followup"
        return {"care": c, "urgency": None, "flags": []}
    return {"care": internal_care(care), "urgency": internal_urgency(urgency), "flags": list(flags)}


# ---------------------------------------------------------------- 1. prepare
def _typo(text: str, rng: random.Random) -> str:
    words = text.split()
    for _ in range(max(1, len(words) // 6)):
        i = rng.randrange(len(words))
        w = words[i]
        if len(w) > 3 and w.isascii():
            j = rng.randrange(1, len(w) - 1)
            words[i] = rng.choice([w[:j] + w[j + 1:], w[:j] + w[j + 1] + w[j] + w[j + 2:] if j + 2 <= len(w) else w])
    return " ".join(words)


def prepare(seed: int = 13) -> list[dict]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    from app.nlp.extract import extract
    from app.nlp.normalize import to_roman

    rng = random.Random(seed)
    items = []
    for p in sorted(RAW.glob("*.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            d = json.loads(line)
            if d["family"] in FAMILY and d["text"].strip():
                items.append(d)
    print(f"raw: {len(items)} messages in {len({d['family'] for d in items})} families")

    seen, uniq = set(), []
    for d in items:
        key = re.sub(r"\W+", " ", d["text"].casefold()).strip()
        if key not in seen:
            seen.add(key)
            uniq.append(d)
    print(f"after exact de-dup: {len(uniq)}")

    org = list({json.loads(l)["request"]["user_input"] for l in
                (ROOT / "data/sanocare_v1/triage_dataset.jsonl").read_text(encoding="utf-8").splitlines()})
    # our own hard test cases stay out of training too
    for case_file in sorted((ROOT / "eval" / "cases").glob("*.jsonl")):
        for line in case_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                org.append(json.loads(line).get("text") or "")
    org = [o for o in dict.fromkeys(org) if o]
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)).fit([d["text"] for d in uniq] + org)
    sim = cosine_similarity(vec.transform([d["text"] for d in uniq]), vec.transform(org)).max(axis=1)
    close = sim >= 0.80
    print(f"dropped {int(close.sum())} messages too close to a test row (organisers' or our hard cases, cosine >= 0.80)")
    uniq = [d for d, c in zip(uniq, close) if not c]

    kept, dropped_flag = [], Counter()
    for d in uniq:
        lab = labels_of(d["family"])
        if lab["care"] != "emergency" and not d["family"].startswith("H_"):  # H_ families deny danger words on purpose
            ex = extract(d["text"])
            if ex.red_flags:
                dropped_flag[d["family"]] += 1
                continue
        kept.append(d)
    print(f"dropped {sum(dropped_flag.values())} non-emergency messages with a danger sign per the rules: "
          f"{dict(dropped_flag)}")

    rows = []
    for d in kept:
        rows.append({"text": d["text"], "history": [], "family": d["family"], "who": d["who"],
                     "tags": d["tags"], "lang": d["language"], "aug": "", **labels_of(d["family"])})
    # Roman-script copies of some Hindi messages (people type Hindi in Roman letters too)
    for d in [r for r in rows if r["lang"] == "hi" and not r["history"]]:
        if rng.random() < 0.35:
            rows.append({**d, "text": to_roman(d["text"]), "lang": "hinglish", "aug": "roman"})
    # light typos
    for d in [r for r in rows if r["lang"] != "hi" and not r["aug"]]:
        if rng.random() < 0.15:
            rows.append({**d, "text": _typo(d["text"], rng), "aug": "typo"})

    # multi-turn: vague first message -> our question -> the real need as the answer
    by_lang: dict[str, list[dict]] = {}
    for r in rows:
        if not r["aug"]:
            by_lang.setdefault(r["lang"], []).append(r)
    vague = [r for r in rows if r["family"].startswith("F_") and not r["aug"]]
    decided = [r for r in rows if r["care"] not in ("followup", "out_of_scope") and not r["aug"]]
    multi = []
    for _ in range(420):
        first = rng.choice(vague)
        lang = first["lang"]
        ans = rng.choice([r for r in decided if r["lang"] == lang] or decided)
        multi.append({**ans, "history": [("user", first["text"]), ("assistant", ASK[lang][0])], "aug": "multi"})
    # symptom first, then a duration / "no danger" answer: the label stays the first message's
    complaints = [r for r in decided if r["care"] in ("paramedic", "gp")]
    for _ in range(260):
        first = rng.choice(complaints)
        lang = first["lang"]
        if rng.random() < 0.5:
            q, a = ASK[lang][1], rng.choice(DAYS[lang])
        else:
            q, a = ASK[lang][3], rng.choice(NO[lang])
        multi.append({**first, "text": a, "history": [("user", first["text"]), ("assistant", q)], "aug": "multi"})
    # danger revealed in the answer
    emerg = [r for r in decided if r["care"] == "emergency"]
    for _ in range(160):
        first = rng.choice(complaints + vague)
        lang = first["lang"]
        ans = rng.choice([r for r in emerg if r["lang"] == lang] or emerg)
        multi.append({**ans, "history": [("user", first["text"]), ("assistant", ASK[lang][3])], "aug": "multi"})
    rows += multi

    rng.shuffle(rows)
    PREPARED.parent.mkdir(parents=True, exist_ok=True)
    PREPARED.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    c = Counter(r["care"] for r in rows)
    print(f"prepared {len(rows)} training examples -> {PREPARED}\n  care: {dict(c)}\n"
          f"  aug: {dict(Counter(r['aug'] or 'none' for r in rows))}")
    return rows


# ---------------------------------------------------------------- model
def build_model(torch, nn, AutoModel):
    class MultiHead(nn.Module):
        def __init__(self):
            super().__init__()
            self.enc = AutoModel.from_pretrained(BASE)
            h = self.enc.config.hidden_size
            self.drop = nn.Dropout(0.1)
            self.care = nn.Linear(h, len(CARE))
            self.urgency = nn.Linear(h, len(URGENCY))
            self.flags = nn.Linear(h, len(FLAGS))
            self.tags = nn.Linear(h, len(TAGS))
            self.who = nn.Linear(h, len(WHO))

        def forward(self, input_ids, attention_mask):
            h = self.enc(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
            m = attention_mask.unsqueeze(-1).to(h.dtype)
            x = (h * m).sum(1) / m.sum(1).clamp(min=1.0)  # mean of the tokens: learns faster than [CLS] here
            x = self.drop(x)
            return self.care(x), self.urgency(x), self.flags(x), self.tags(x), self.who(x)

    return MultiHead()


def encode_rows(rows, tok, max_len):
    texts = [compose(r["text"], r["history"]) for r in rows]
    enc = tok(texts, truncation=True, max_length=max_len, padding=False)
    out = []
    for r, ids in zip(rows, enc["input_ids"]):
        out.append({
            "ids": ids,
            "care": CARE.index(r["care"]),
            "urgency": URGENCY.index(r["urgency"]) if r["urgency"] else -100,
            "flags": [1.0 if f in r["flags"] else 0.0 for f in FLAGS],
            "tags": [1.0 if t in r["tags"] else 0.0 for t in TAGS],
            "who": WHO.index(r["who"]) if r["who"] in WHO else WHO.index("unknown"),
        })
    return out


def batches(data, bs, shuffle, rng, torch, pad_id):
    idx = list(range(len(data)))
    if shuffle:
        rng.shuffle(idx)
    for i in range(0, len(idx), bs):
        b = [data[j] for j in idx[i:i + bs]]
        L = max(len(x["ids"]) for x in b)
        ids = torch.full((len(b), L), pad_id, dtype=torch.long)
        mask = torch.zeros((len(b), L), dtype=torch.long)
        for k, x in enumerate(b):
            ids[k, :len(x["ids"])] = torch.tensor(x["ids"])
            mask[k, :len(x["ids"])] = 1
        yield (ids, mask, torch.tensor([x["care"] for x in b]), torch.tensor([x["urgency"] for x in b]),
               torch.tensor([x["flags"] for x in b]), torch.tensor([x["tags"] for x in b]),
               torch.tensor([x["who"] for x in b]))


def train(rows, epochs, args, eval_rows=None):
    import torch
    from torch import nn
    from transformers import AutoModel, AutoTokenizer, get_linear_schedule_with_warmup

    torch.manual_seed(args.seed)
    rng = random.Random(args.seed)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(BASE, truncation_side="left")
    data = encode_rows(rows, tok, args.max_len)
    model = build_model(torch, nn, AutoModel).to(dev)
    counts = Counter(r["care"] for r in rows)
    w = torch.tensor([(len(rows) / (len(CARE) * max(counts.get(c, 1), 1))) ** 0.5 for c in CARE], dtype=torch.float)
    w[CARE.index("emergency")] *= 1.5  # missing an emergency costs more than a false alarm
    ce_care = nn.CrossEntropyLoss(weight=w.to(dev))
    ce = nn.CrossEntropyLoss(ignore_index=-100)
    bce = nn.BCEWithLogitsLoss()
    enc = [p for n, p in model.named_parameters() if n.startswith("enc.")]
    heads = [p for n, p in model.named_parameters() if not n.startswith("enc.")]
    opt = torch.optim.AdamW([{"params": enc, "lr": args.lr}, {"params": heads, "lr": args.head_lr}], weight_decay=0.01)
    steps = epochs * ((len(data) + args.bs - 1) // args.bs)
    sched = get_linear_schedule_with_warmup(opt, int(0.1 * steps), steps)
    scaler = torch.amp.GradScaler("cuda", enabled=dev == "cuda")
    history = []
    for ep in range(epochs):
        model.train()
        t0, tot, n, hit = time.time(), 0.0, 0, 0
        for ids, mask, yc, yu, yf, yt, yw in batches(data, args.bs, True, rng, torch, tok.pad_token_id):
            ids, mask = ids.to(dev), mask.to(dev)
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=dev == "cuda"):
                c, u, f, t, wh = model(ids, mask)
            loss = (ce_care(c.float(), yc.to(dev)) + 0.7 * ce(u.float(), yu.to(dev)) + bce(f.float(), yf.to(dev))
                    + 0.5 * bce(t.float(), yt.to(dev)) + 0.3 * ce(wh.float(), yw.to(dev)))
            opt.zero_grad()
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            sched.step()
            tot += loss.item() * len(yc)
            n += len(yc)
            hit += int((c.argmax(1).cpu() == yc).sum())
        msg = f"  epoch {ep + 1}/{epochs}: loss {tot / n:.4f}, train care acc {hit / n:.3f} ({time.time() - t0:.0f}s)"
        if eval_rows:
            logits = predict_logits(model, eval_rows, tok, args, torch, dev)
            acc = float(np.mean(logits["care"].argmax(1) == np.array([CARE.index(r["care"]) for r in eval_rows])))
            history.append(acc)
            msg += f", held-out care acc {acc:.3f}"
        print(msg, flush=True)
    return model, tok, history


def predict_logits(model, rows, tok, args, torch, dev):
    model.eval()
    data = encode_rows(rows, tok, args.max_len)
    outs = {k: [] for k in ("care", "urgency", "flags", "tags", "who")}
    with torch.no_grad():
        for ids, mask, *_ in batches(data, 64, False, None, torch, tok.pad_token_id):
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=dev == "cuda"):
                res = model(ids.to(dev), mask.to(dev))
            for k, v in zip(outs, res):
                outs[k].append(v.float().cpu().numpy())
    return {k: np.concatenate(v) for k, v in outs.items()}


def fit_temperature(logits: np.ndarray, y: np.ndarray) -> float:
    best, best_t = 1e9, 1.0
    for t in np.arange(0.5, 4.01, 0.05):
        z = logits / t
        z = z - z.max(1, keepdims=True)
        p = np.exp(z) / np.exp(z).sum(1, keepdims=True)
        nll = -np.mean(np.log(p[np.arange(len(y)), y] + 1e-9))
        if nll < best:
            best, best_t = nll, float(t)
    return round(best_t, 2)


def softmax(z, t=1.0):
    z = z / t
    z = z - z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


# ---------------------------------------------------------------- export + test
def export(model, tok, meta, args):
    import torch
    OUT.mkdir(parents=True, exist_ok=True)
    model = model.float().cpu().eval()
    ids = torch.tensor([tok(compose("mummy ko teen din se tez bukhar hai aur khansi bhi, ghar pe koi aa sakta hai"))["input_ids"]])
    mask = torch.ones_like(ids)
    fp32 = OUT / "model.fp32.onnx"
    torch.onnx.export(model, (ids, mask), str(fp32), input_names=["input_ids", "attention_mask"],
                      output_names=["care", "urgency", "flags", "tags", "who"],
                      dynamic_axes={"input_ids": {0: "b", 1: "s"}, "attention_mask": {0: "b", 1: "s"}},
                      opset_version=17, dynamo=False)
    # Shipped in fp32. Dynamic int8 quantization (plain, per-channel, reduce-range, with and
    # without the embeddings) agreed with fp32 on only 76-95% of check sentences, and fp32 ONNX
    # already answers in ~22 ms on two CPU threads.
    fp32.replace(OUT / "model.onnx")
    tok.backend_tokenizer.save(str(OUT / "tokenizer.json"))
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    mb = (OUT / "model.onnx").stat().st_size / 1e6
    print(f"exported {OUT / 'model.onnx'} ({mb:.0f} MB, fp32)")


def export_saved(args):
    import torch
    from torch import nn
    from transformers import AutoModel, AutoTokenizer

    meta = json.loads((OUT / "meta.json").read_text(encoding="utf-8"))
    tok = AutoTokenizer.from_pretrained(BASE, truncation_side="left")

    class Eager:  # SDPA attention does not trace correctly to ONNX; eager attention does
        @staticmethod
        def from_pretrained(name):
            return AutoModel.from_pretrained(name, attn_implementation="eager")

    model = build_model(torch, nn, Eager)
    model.load_state_dict(torch.load(OUT / "student.pt", map_location="cpu"))
    with torch.no_grad():
        export(model, tok, meta, args)
    res = test_on_organisers()
    meta["test_organiser_340"] = {k: v for k, v in res.items() if k != "errors"}
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def test_on_organisers() -> dict:
    """Model alone, through the exact serving code, on the organisers' 340 rows (never trained on)."""
    from sklearn.metrics import f1_score

    from app.triage import student as st

    st.get_student.cache_clear()
    s = st.get_student()
    rows = [json.loads(l) for l in (ROOT / "data/sanocare_v1/triage_dataset.jsonl").read_text(encoding="utf-8").splitlines()]
    yc, pc, yu, pu, em_t, em_p, lat = [], [], [], [], [], [], []
    for r in rows:
        hist = [(h.get("role", "user"), h.get("content", "")) for h in r["request"].get("conversation_history") or []
                if isinstance(h, dict)]
        o = s.predict(r["request"]["user_input"], hist)
        lat.append(o.latency_ms)
        gold_c = internal_care(r["response"]["care_type"]) if r["response"]["care_type"] else "followup"
        pred_c = o.top_care  # the care head's own answer (no rules, no guardrails)
        if pred_c == "out_of_scope":
            pred_c = "followup"
        yc.append(gold_c)
        pc.append(pred_c)
        gold_u = internal_urgency(r["response"]["urgency"]) if r["response"]["urgency"] else "none"
        pred_u = "immediate" if pred_c == "emergency" else ("none" if pred_c == "followup" else
                                                           max(("routine", "same_day"), key=o.urgency.get))
        yu.append(gold_u)
        pu.append(pred_u)
        em_t.append(gold_c == "emergency")
        em_p.append(pred_c == "emergency")
    em_t, em_p = np.array(em_t), np.array(em_p)
    res = {
        "n": len(rows),
        "care_accuracy": round(float(np.mean(np.array(yc) == np.array(pc))), 4),
        "care_macro_f1": round(float(f1_score(yc, pc, average="macro")), 4),
        "urgency_macro_f1": round(float(f1_score(yu, pu, average="macro")), 4),
        "emergency_recall": round(float(em_p[em_t].mean()), 4),
        "false_emergency_rate": round(float(em_p[~em_t].mean()), 4),
        "latency_ms_p50": round(float(np.median(lat)), 1),
        "errors": [(r["request"]["user_input"], a, b) for r, a, b in zip(rows, yc, pc) if a != b][:25],
    }
    print(json.dumps({k: v for k, v in res.items() if k != "errors"}, indent=1))
    for e in res["errors"]:
        print("   miss:", e)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument("--head-lr", type=float, default=1e-3)
    ap.add_argument("--max-len", type=int, default=128)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--skip-prepare", action="store_true")
    ap.add_argument("--skip-holdout", action="store_true")
    ap.add_argument("--test-only", action="store_true")
    ap.add_argument("--export-only", action="store_true", help="export saved weights (models/student/student.pt)")
    args = ap.parse_args()
    if args.test_only:
        test_on_organisers()
        return
    if args.export_only:
        export_saved(args)
        return

    rows = ([json.loads(l) for l in PREPARED.read_text(encoding="utf-8").splitlines()] if args.skip_prepare
            else prepare(args.seed))

    # held-out families: two per care class, chosen once (seeded)
    rng = random.Random(args.seed)
    by_care: dict[str, list[str]] = {}
    for fid in FAMILY:
        by_care.setdefault(labels_of(fid)["care"], []).append(fid)
    hold = set()
    for care, fids in by_care.items():
        rng.shuffle(fids)
        hold.update(fids[:2] if len(fids) > 3 else fids[:1] if len(fids) > 1 else [])
    epochs, temp_c, temp_u, em_thr = args.epochs, 1.0, 1.0, 0.5
    holdout_scores = {}
    saved = ROOT / "eval" / "out" / "holdout.json"
    if args.skip_holdout and saved.exists():  # reuse the settings picked on the held-out families
        holdout_scores = json.loads(saved.read_text(encoding="utf-8"))
        temp_c, temp_u = holdout_scores["temperature_care"], holdout_scores["temperature_urgency"]
        em_thr = holdout_scores["emergency_threshold"]
        print(f"reusing holdout settings: T_care {temp_c}, T_urgency {temp_u}, emergency threshold {em_thr}")
    if not args.skip_holdout:
        import torch
        tr = [r for r in rows if r["family"] not in hold]
        ho = [r for r in rows if r["family"] in hold and r["aug"] != "multi"]
        print(f"holdout run: train {len(tr)}, held-out {len(ho)} from families {sorted(hold)}")
        model, tok, hist = train(tr, args.epochs, args, eval_rows=ho)
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        lg = predict_logits(model, ho, tok, args, torch, dev)
        yc = np.array([CARE.index(r["care"]) for r in ho])
        temp_c = fit_temperature(lg["care"], yc)
        uidx = [i for i, r in enumerate(ho) if r["urgency"]]
        temp_u = fit_temperature(lg["urgency"][uidx], np.array([URGENCY.index(ho[i]["urgency"]) for i in uidx]))
        pe = softmax(lg["care"], temp_c)[:, CARE.index("emergency")]
        is_em = yc == CARE.index("emergency")
        flag_any = (1 / (1 + np.exp(-lg["flags"]))).max(1)
        if is_em.any():
            # the threshold that keeps every held-out emergency caught, with headroom, capped at 0.5
            lowest = float(np.minimum(pe[is_em], 1.0).min())
            em_thr = float(np.clip(min(0.5, lowest * 0.8), 0.15, 0.5))
        p = softmax(lg["care"], temp_c)
        conf = p.max(1)
        right = p.argmax(1) == yc
        bins = np.linspace(0, 1, 11)
        ece = sum(abs(right[(conf > a) & (conf <= b)].mean() - conf[(conf > a) & (conf <= b)].mean())
                  * ((conf > a) & (conf <= b)).mean() for a, b in zip(bins[:-1], bins[1:]) if ((conf > a) & (conf <= b)).any())
        caught = (pe[is_em] >= em_thr) | (flag_any[is_em] >= 0.5)
        holdout_scores = {"families": sorted(hold), "n": len(ho), "care_accuracy": round(float(right.mean()), 4),
                          "per_epoch_care_accuracy": [round(a, 4) for a in hist],
                          "temperature_care": temp_c, "temperature_urgency": temp_u,
                          "emergency_threshold": round(em_thr, 3), "ece_after_calibration": round(float(ece), 4),
                          "emergency_recall": round(float(caught.mean()), 4) if is_em.any() else None}
        print("holdout:", json.dumps(holdout_scores))
        (ROOT / "eval" / "out").mkdir(parents=True, exist_ok=True)
        (ROOT / "eval" / "out" / "holdout.json").write_text(json.dumps(holdout_scores), encoding="utf-8")
        if hist:  # the epoch count that did best on unseen families
            epochs = max(4, int(np.argmax(hist)) + 1)
        del model
        torch.cuda.empty_cache()

    print(f"final run on all {len(rows)} examples, {epochs} epochs")
    model, tok, _ = train(rows, epochs, args)
    meta = {
        "name": "MuRIL (fine-tuned)",
        "base": BASE,
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "max_len": args.max_len,
        "heads": {"care": CARE, "urgency": URGENCY, "flags": FLAGS, "tags": TAGS, "who": WHO},
        "temperature": {"care": temp_c, "urgency": temp_u},
        "thresholds": {"emergency": round(em_thr, 3), "flag": 0.5, "tag": 0.5, "band_high": 0.85, "band_low": 0.6},
        "training": {"examples": len(rows), "epochs": epochs, "lr": args.lr, "head_lr": args.head_lr, "batch": args.bs,
                     "data": "data/generated (Claude Opus 5.5 teacher; labels fixed per case family)",
                     "organiser_rows_used_for_training": 0},
        "holdout": holdout_scores,
    }
    # save first, export in a fresh process: exporting next to the training state ran out of RAM
    import torch

    OUT.mkdir(parents=True, exist_ok=True)
    torch.save({k: v.detach().cpu() for k, v in model.state_dict().items()}, OUT / "student.pt")
    tok.backend_tokenizer.save(str(OUT / "tokenizer.json"))
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"saved weights -> {OUT / 'student.pt'}")
    print("next, in a fresh process so the export has the RAM to itself: "
          "python -m scripts.train_student --export-only")


if __name__ == "__main__":
    main()
