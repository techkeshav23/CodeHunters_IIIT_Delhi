// HTTP contract with the backend (docs/API.md) plus a mock mode so the UI is
// never blocked. Flip VITE_USE_MOCKS=0 once the backend on :8000 is live.

import type {
  BookingRequest,
  BookingResponse,
  HealthResponse,
  TriageRequest,
  TriageResponse,
} from "./types";

import emergencyMock from "./mocks/triage_emergency.json";
import finalMock from "./mocks/triage_final.json";
import followupMock from "./mocks/triage_followup.json";
import labMock from "./mocks/triage_lab.json";
import nurseMock from "./mocks/triage_nurse.json";
import specialistMock from "./mocks/triage_specialist.json";
import bookingMock from "./mocks/booking.json";

// "same-origin": the site's own server proxies /v1 and /health to the API (production)
const RAW_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";
export const API_BASE: string = RAW_BASE === "same-origin" ? "" : RAW_BASE;

export const USE_MOCKS: boolean =
  (import.meta.env.VITE_USE_MOCKS as string | undefined) === "1";

// Follow-up policy for /v1/triage (backend agent's call): "safety" adds a
// breathing question for fever/cough so the smart-intake step shows in the demo.
// One constant so we can flip it; the API default is "minimal".
const TRIAGE_POLICY = "safety";

const MOCK_DELAY_MS = 400;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ---- mock selection (spec section 10) ----

const EMERGENCY_WORDS = [
  "seena",
  "seene",
  "chest",
  "saans nahi",
  "behosh",
  "beehosh",
  // Devanagari
  "सीने",
  "सीना",
  "बेहोश",
  "सांस नहीं",
  "साँस नहीं",
];
const SYMPTOM_WORDS = [
  "bukhar",
  "fever",
  "khansi",
  "cough",
  "dard",
  "pain",
  "injection",
  "chot",
  "injury",
  "ulti",
  "vomit",
  "dast",
  "diarr",
  "sugar",
  "bp",
  // Devanagari
  "बुखार",
  "खांसी",
  "खाँसी",
  "दर्द",
  "इंजेक्शन",
  "उल्टी",
  "चोट",
];

// Route the other care types in mock mode so the demo can show them without
// the backend: home_nursing (injections, dressing), lab_test_home (sample
// collection) and teleconsultation with a specialty (joint pain).
const NURSE_WORDS = ["injection", "insulin", "inject", "इंजेक्शन", "tanke", "dressing", "drip"];
const LAB_WORDS = ["lab", "blood test", "sample", "cbc", "thyroid", "लैब", "सैंपल", "ब्लड टेस्ट"];
const SPECIALIST_WORDS = [
  "ghutne",
  "ghutno",
  "knee",
  "joint",
  "ortho",
  "specialist",
  "घुटने",
  "jodo",
];

function hasAny(text: string, words: string[]): boolean {
  const low = text.toLowerCase();
  return words.some((w) => low.includes(w));
}

function countAssistantTurns(req: TriageRequest): number {
  return req.conversation_history.filter((h) => h.role === "assistant").length;
}

function firstUserMessage(req: TriageRequest): string {
  const firstUser = req.conversation_history.find((h) => h.role === "user");
  return firstUser ? firstUser.content : req.user_input;
}

function pickMockTriage(req: TriageRequest): TriageResponse {
  // Emergency always wins, even mid-conversation.
  if (hasAny(req.user_input, EMERGENCY_WORDS)) {
    return emergencyMock.response as TriageResponse;
  }

  // Direct-care requests (no follow-up): nursing for injections, a home lab
  // test for sample collection, a doctor teleconsult for joint pain.
  if (hasAny(req.user_input, NURSE_WORDS)) {
    return nurseMock.response as TriageResponse;
  }
  if (hasAny(req.user_input, LAB_WORDS)) {
    return labMock.response as TriageResponse;
  }
  if (hasAny(req.user_input, SPECIALIST_WORDS)) {
    return specialistMock.response as TriageResponse;
  }

  // The follow-up path is chosen by the FIRST message being vague (no known
  // symptom word). Once in that path, we walk turn_1 -> turn_2 -> final.
  const firstMsg = firstUserMessage(req);
  const vagueStart = !hasAny(firstMsg, SYMPTOM_WORDS) && !hasAny(firstMsg, EMERGENCY_WORDS);

  if (vagueStart) {
    const asked = countAssistantTurns(req);
    if (asked === 0) return followupMock.turn_1.response as TriageResponse;
    if (asked === 1) return followupMock.turn_2.response as TriageResponse;
    return finalMock.response as TriageResponse;
  }

  return finalMock.response as TriageResponse;
}

// ---- public API ----

export async function triage(req: TriageRequest): Promise<TriageResponse> {
  if (USE_MOCKS) {
    await delay(MOCK_DELAY_MS);
    return pickMockTriage(req);
  }

  const res = await fetch(
    `${API_BASE}/v1/triage?explain=true&policy=${TRIAGE_POLICY}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    },
  );
  if (!res.ok) {
    throw new Error(`Triage failed: ${res.status}`);
  }
  return (await res.json()) as TriageResponse;
}

function mockBooking(req: BookingRequest): BookingResponse {
  // Try to name the caregiver from the final-mock roster; fall back to the
  // booking sample. Booking id is random so repeated demos look distinct.
  const roster = [
    ...finalMock.response.trace.caregivers,
    ...nurseMock.response.trace.caregivers,
    ...labMock.response.trace.caregivers,
    ...specialistMock.response.trace.caregivers,
  ] as Array<{ caregiver_id: string; name: string }>;
  const match = roster.find((c) => c.caregiver_id === req.caregiver_id);
  const id = "BK_" + Math.random().toString(36).slice(2, 8).toUpperCase();
  return {
    booking_id: id,
    status: "confirmed",
    caregiver_id: req.caregiver_id,
    caregiver_name: match?.name ?? bookingMock.response.caregiver_name,
    slot: req.slot,
    created_at: new Date().toISOString(),
  };
}

export async function createBooking(req: BookingRequest): Promise<BookingResponse> {
  if (USE_MOCKS) {
    await delay(MOCK_DELAY_MS);
    return mockBooking(req);
  }

  const res = await fetch(`${API_BASE}/v1/bookings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    throw new Error(`Booking failed: ${res.status}`);
  }
  return (await res.json()) as BookingResponse;
}

export async function health(): Promise<HealthResponse> {
  if (USE_MOCKS) {
    await delay(150);
    return { status: "ok", version: "mock", model: "mock" };
  }
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) {
    throw new Error(`Health failed: ${res.status}`);
  }
  return (await res.json()) as HealthResponse;
}

// ---- labels for the emergency page (red-flag names, helplines) ----

export interface LabelsResponse {
  red_flags: Array<{ id: string; label: string; label_hinglish: string; label_hi: string }>;
  emergency_numbers: Array<{ label: string; label_hi: string; number: string }>;
  helplines: Record<string, { label: string; label_hi: string; number: string }>;
}

const FALLBACK_LABELS: LabelsResponse = {
  red_flags: [],
  emergency_numbers: [
    { label: "Emergency (all India)", label_hi: "Emergency (poore Bharat mein)", number: "112" },
    { label: "Ambulance in Delhi (CATS, free)", label_hi: "Delhi ambulance (CATS, free)", number: "102" },
    { label: "Ambulance in many states", label_hi: "Kai rajyon mein ambulance", number: "108" },
  ],
  helplines: {
    self_harm_risk: { label: "Tele-MANAS mental health helpline", label_hi: "Tele-MANAS helpline", number: "14416" },
    poisoning: { label: "AIIMS Poisons Information Centre", label_hi: "AIIMS zeher helpline", number: "1800-116-117" },
  },
};

export async function labels(): Promise<LabelsResponse> {
  if (USE_MOCKS) return FALLBACK_LABELS;
  try {
    const res = await fetch(`${API_BASE}/v1/labels`);
    if (!res.ok) return FALLBACK_LABELS;
    return (await res.json()) as LabelsResponse;
  } catch {
    return FALLBACK_LABELS;
  }
}
