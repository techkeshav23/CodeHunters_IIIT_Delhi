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
import bookingMock from "./mocks/booking.json";

export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";

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
  const roster = (finalMock.response.trace.caregivers ?? []) as Array<{
    caregiver_id: string;
    name: string;
  }>;
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
