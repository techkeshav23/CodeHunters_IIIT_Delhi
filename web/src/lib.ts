// Small shared helpers and the app's own data types.
import type { Lang, ModelOutput, TraceCaregiver, TriageRequest, TriageResponse } from "./types";
import type { Key } from "./i18n";

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

// Model classes: paramedic, nurse, lab, gp, emergency, followup. Unknown
// classes return null and are shown by their own name.
export function modelClassKey(cls: string): Key | null {
  if (cls === "followup" || cls === "follow_up") return "careFollowup";
  if (cls === "gp") return "careDoctor";
  return careKey(cls);
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
  const kind = careKind(res.care_type);
  const cls = res.follow_up_question ? "followup" : kind ? MODEL_CLASS[kind] : null;
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
