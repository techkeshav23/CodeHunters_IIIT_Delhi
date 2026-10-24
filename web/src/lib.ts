// Small shared helpers and the app's own data types.
import type { Lang, ModelOutput, Trace, TraceCaregiver, TriageRequest, TriageResponse } from "./types";
import { t, type Key } from "./i18n";

export type View = "check" | "bookings" | "sos" | "how" | "settings";

export type Msg =
  | { id: number; kind: "user"; text: string }
  | { id: number; kind: "question"; req: TriageRequest; res: TriageResponse }
  | { id: number; kind: "decision"; req: TriageRequest; res: TriageResponse }
  | { id: number; kind: "emergency"; req: TriageRequest; res: TriageResponse; userText: string }
  | { id: number; kind: "error"; text: string; usedVoice: boolean };

export interface SavedBooking {
  booking_id: string;
  caregiver_id: string;
  caregiver_name: string;
  role: string;
  slot_label: string | null;
  care_label: string | null;
  urgency_label: string | null;
  created_at: string;
}

export interface BookingTarget {
  caregiver: TraceCaregiver;
  res: TriageResponse;
}

// Any one signal is enough: an emergency block, a red flag, an emergency care
// type or an emergency urgency (old or new values).
export function isEmergency(res: TriageResponse): boolean {
  return (
    res.trace?.emergency != null ||
    (res.red_flags?.length ?? 0) > 0 ||
    careKind(res.care_type) === "emergency" ||
    urgencyLevel(res.urgency) === 2
  );
}

export function initials(name: string): string {
  const parts = name.replace(/^dr\.?\s+/i, "").trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

// Avatar colours stay inside the palette: neem, deep teal, haldi-brown, plum-slate.
const AVATAR = ["#0d5a50", "#21706a", "#9a6a00", "#5b4a6b", "#3d6b4f", "#7a4b2a"];
export function avatarColor(seed: string): string {
  let h = 0;
  for (const ch of seed) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return AVATAR[h % AVATAR.length];
}

export function roleKey(role: string | null | undefined): Key {
  const r = (role ?? "").toLowerCase();
  if (r.includes("physio")) return "rolePhysio";
  if (r.includes("phlebotom") || r.includes("lab")) return "roleLab";
  if (r === "medic") return "roleMedic";
  if (r.includes("nurse")) return "roleNurse";
  if (r.includes("paramedic")) return "roleParamedic";
  if (r.includes("special") || r.includes("consult")) return "roleSpecialist";
  return "roleGp";
}

export function urgencyLevel(urgency: string | null): 0 | 1 | 2 {
  if (urgency === "emergency" || urgency === "immediate") return 2;
  if (urgency === "same_day") return 1;
  return 0;
}

export function isTele(careType: string | null): boolean {
  return !!careType && careType.includes("teleconsult");
}

// The roster's doctors work by video only, whatever the care type says.
export function isRemoteCarer(careType: string | null, role: string | null | undefined): boolean {
  return isTele(careType) || (role ?? "").trim().toLowerCase() === "doctor";
}

// One name per kind of care, for both the organisers' values
// (paramedic_home_visit, home_nursing, lab_test_home, teleconsultation,
// emergency_112) and older ones (nurse, specialist, emergency_referral).
export type CareKind = "paramedic" | "nurse" | "lab" | "doctor" | "emergency";

export function careKind(careType: string | null | undefined): CareKind | null {
  if (!careType) return null;
  const c = careType.toLowerCase();
  if (c.startsWith("emergency")) return "emergency";
  if (c.includes("lab") || c.includes("sample")) return "lab";
  if (c.includes("nurs")) return "nurse";
  if (c.includes("paramedic")) return "paramedic";
  if (c.includes("teleconsult") || c.includes("specialist") || c.includes("doctor") || c === "gp") return "doctor";
  return null;
}

const CARE_KEY: Record<CareKind, Key> = {
  paramedic: "careParamedic",
  nurse: "careNurse",
  lab: "careLab",
  doctor: "careDoctor",
  emergency: "careEmergency",
};

export function careKey(careType: string | null | undefined): Key | null {
  const k = careKind(careType);
  return k ? CARE_KEY[k] : null;
}

// Model classes: paramedic, nurse, lab, gp, emergency, followup, out_of_scope.
// Unknown classes return null and are shown by their own name.
export function modelClassKey(cls: string): Key | null {
  if (cls === "followup" || cls === "follow_up") return "careFollowup";
  if (cls === "out_of_scope") return "careOutOfScope";
  if (cls === "gp") return "careDoctor";
  return careKey(cls);
}

// ---- who decided (trace.decision.source) and how sure the model was ----

export function decisionSource(res: TriageResponse): string {
  return String(res.trace?.decision?.source ?? "").toLowerCase();
}

// the safety net raised this answer ("model+safety_net" or "safety_net")
export function raisedBySafety(res: TriageResponse): boolean {
  return decisionSource(res).includes("safety_net");
}

// For a non-emergency card: the source names the safety net and, when the API lists
// its safety checks, one that raises care (danger signs, vulnerable people, urgency
// floor) actually fired, so the card never claims a change that did not happen.
const RAISING_CHECKS = ["safety_net", "vulnerable_floor", "urgency_floor"];
export function safetyChoseUrgent(res: TriageResponse): boolean {
  if (!raisedBySafety(res)) return false;
  const checks = res.trace?.guardrails;
  if (!Array.isArray(checks) || checks.length === 0) return true;
  return checks.some((g) => RAISING_CHECKS.includes(g.id) && g.status === "fired");
}

const BAND_KEY: Record<string, Key> = { high: "bandHigh", medium: "bandMedium", low: "bandLow" };
export function bandKey(band: string | null | undefined): Key | null {
  return band ? BAND_KEY[band.toLowerCase()] ?? null : null;
}

// "MuRIL (fine-tuned)" -> "MuRIL" for the plain-words line
export function modelShortName(model: ModelOutput | null | undefined): string {
  return (model?.name ?? "").replace(/\s*\(.*?\)\s*/g, " ").trim() || "MuRIL";
}

// ---- Module 1's structured symptoms ----

const WHO_KEY: Record<string, Key> = {
  self: "whoSelf",
  adult: "whoAdult",
  elderly: "whoElderly",
  child: "whoChild",
  infant: "whoInfant",
  pregnant: "whoPregnant",
};

export interface UnderstoodChip {
  text: string;
  kind: "symptom" | "duration" | "who" | "age";
}

// trace.structured as short chips ("Bukhar · 3 din se · Buzurg"), or null when the
// API sent none (older builds) or it found nothing, so callers fall back to
// trace.understood. Symptom labels come from the API in the user's language.
export function structuredChips(tr: Trace | null | undefined, lang: Lang): UnderstoodChip[] | null {
  const s = tr?.structured;
  if (!s || typeof s !== "object") return null;
  const out: UnderstoodChip[] = [];
  const seen = new Set<string>();
  const add = (text: string | null | undefined, kind: UnderstoodChip["kind"]) => {
    const v = (text ?? "").trim();
    if (!v || seen.has(v.toLowerCase())) return;
    seen.add(v.toLowerCase());
    out.push({ text: v, kind });
  };
  for (const sym of s.symptoms ?? []) add(sym.label_local || sym.label || sym.id?.replace(/_/g, " "), "symptom");
  add(fmtDays(s.duration_days ?? null, lang), "duration");
  const who = (s.who ?? "").toLowerCase();
  if (who && who !== "unknown") add(s.who_label_local || (WHO_KEY[who] ? t(lang, WHO_KEY[who]) : null), "who");
  if (s.age_years != null && s.age_years >= 1) add(t(lang, "ageYears", { n: Math.round(s.age_years) }), "age");
  return out.length ? out : null;
}

export function topModelClass(model: ModelOutput | null | undefined): { cls: string; pct: number } | null {
  const probs = model?.probabilities;
  if (!probs || typeof probs !== "object") return null;
  let best: { cls: string; p: number } | null = null;
  for (const [cls, p] of Object.entries(probs)) {
    if (typeof p !== "number" || !Number.isFinite(p)) continue;
    if (!best || p > best.p) best = { cls, p };
  }
  if (!best) return null;
  return { cls: best.cls, pct: Math.round(best.p <= 1 ? best.p * 100 : best.p) };
}

// The model's probability for the class that was actually decided (care type, or
// "followup" when a question was asked), so the line backs up what the user sees
// instead of naming a different class. Falls back to the top class.
const MODEL_CLASS: Record<CareKind, string> = {
  paramedic: "paramedic", nurse: "nurse", lab: "lab", doctor: "gp", emergency: "emergency",
};
export function decisionModelClass(res: TriageResponse): { cls: string; pct: number } | null {
  const probs = res.trace?.model?.probabilities;
  if (!probs || typeof probs !== "object") return null;
  // the second check (Claude) decided because the model was unsure: show what the model itself said
  if (decisionSource(res) === "llm") return topModelClass(res.trace?.model);
  const kind = careKind(res.care_type);
  const cls = res.follow_up_question
    ? res.trace?.follow_up?.id === "q_scope" ? "out_of_scope" : "followup"
    : kind ? MODEL_CLASS[kind] : null;
  const p = cls != null ? probs[cls] : undefined;
  if (typeof p === "number" && Number.isFinite(p)) return { cls: cls as string, pct: Math.round(p <= 1 ? p * 100 : p) };
  return topModelClass(res.trace?.model);
}

export function fmtDays(days: number | null, lang: Lang): string | null {
  if (days == null) return null;
  const d = Math.round(days);
  const w = Math.max(1, Math.round(days / 7));
  const m = Math.max(1, Math.round(days / 30));
  if (lang === "en") {
    if (days < 1) return "since today";
    if (days < 7) return `${d} day${d === 1 ? "" : "s"}`;
    if (days < 30) return `${w} week${w === 1 ? "" : "s"}`;
    return `${m} month${m === 1 ? "" : "s"}`;
  }
  if (lang === "hi") {
    if (days < 1) return "आज से";
    if (days < 7) return `${d} दिन से`;
    if (days < 30) return `${w} हफ़्ते से`;
    return `${m} महीने से`;
  }
  if (days < 1) return "aaj se";
  if (days < 7) return `${d} din se`;
  if (days < 30) return `${w} hafte se`;
  return `${m} mahine se`;
}

export function titleCase(s: string): string {
  return s.replace(/\b\w/g, (c) => c.toUpperCase());
}

export function readJSON<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v ? (JSON.parse(v) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function writeJSON(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage may be blocked */
  }
}
