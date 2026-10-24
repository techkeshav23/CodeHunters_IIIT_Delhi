// Small shared helpers and the app's own data types.
import type { Lang, TraceCaregiver, TriageRequest, TriageResponse } from "./types";
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

export function isEmergency(res: TriageResponse): boolean {
  return res.trace?.emergency != null || res.red_flags.length > 0;
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

export function roleKey(role: string): Key {
  const r = role.toLowerCase();
  if (r.includes("physio")) return "rolePhysio";
  if (r.includes("nurse")) return "roleNurse";
  if (r.includes("paramedic")) return "roleParamedic";
  if (r.includes("special") || r.includes("consult")) return "roleSpecialist";
  return "roleGp";
}

export function urgencyLevel(urgency: string | null): 0 | 1 | 2 {
  if (urgency === "immediate") return 2;
  if (urgency === "same_day") return 1;
  return 0;
}

export function isTele(careType: string | null): boolean {
  return !!careType && careType.includes("teleconsult");
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
