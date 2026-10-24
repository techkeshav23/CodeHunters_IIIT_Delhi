// Types for the CareCompass API contract (docs/API.md). The client is stateless:
// it sends the whole conversation on every /v1/triage call.

export type Lang = "hi" | "hinglish" | "en";

export interface LatLng {
  lat: number;
  lng: number;
}

export interface HistoryItem {
  role: "user" | "assistant";
  content: string;
  question_id?: string;
}

export interface TriageRequest {
  user_input: string;
  language: "auto" | Lang;
  location: LatLng | null;
  conversation_history: HistoryItem[];
}

export interface MatchedCaregiver {
  caregiver_id: string;
  score: number;
  reason: string;
}

// ---- trace (explain=true) ----

export interface Patient {
  relation: string | null;
  relation_label: string | null;
  age_years: number | null;
  age_group: string | null;
  pregnant: boolean | null;
}

export interface Symptom {
  id: string;
  label: string;
  label_local: string;
}

export interface Understood {
  patient: Patient;
  symptoms: Symptom[];
  duration_days: number | null;
  duration_label: string | null;
  services: Array<{ id: string; label: string; label_local: string }>;
  severity: Array<{ id: string; label: string; label_local: string }>;
}

export type CheckStatus = "present" | "absent" | "not_reported";

export interface Check {
  id: string;
  label: string;
  label_local: string;
  status: CheckStatus;
}

export interface RedFlag {
  id: string;
  label: string;
  label_local: string;
  evidence: string;
}

export interface Decision {
  care_type: string | null;
  urgency: string | null;
  care_label: string | null;
  care_label_local: string | null;
  urgency_label: string | null;
  urgency_label_local: string | null;
  confidence: number;
  source: string;
  rule: string;
}

export interface FollowUpOption {
  value: string;
  label: string;
}

export interface FollowUp {
  id: string;
  text: string;
  kind: "yes_no" | "choice" | "free_text";
  options: FollowUpOption[];
  asked_so_far: number;
  max: number;
}

export interface EmergencyNumber {
  label: string;
  label_local: string;
  number: string;
}

export interface Emergency {
  title: string;
  title_local: string;
  numbers: EmergencyNumber[];
  steps: string[];
  steps_local: string[];
}

export interface TraceCaregiver {
  caregiver_id: string;
  name: string;
  role: string;
  languages: string[];
  skills: string[];
  distance_km: number | null;
  next_slot: string | null;
  next_slot_label: string | null;
  next_slot_label_local: string | null;
  rating: number | null;
  score: number;
  reason: string;
  reason_local: string;
}

export interface Trace {
  version: string;
  language: Lang;
  understood: Understood;
  checks: Check[];
  red_flags: RedFlag[];
  decision: Decision;
  reasoning_local: string;
  follow_up: FollowUp | null;
  emergency: Emergency | null;
  caregivers: TraceCaregiver[];
  timing_ms: number;
}

export interface TriageResponse {
  follow_up_question: string | null;
  care_type: string | null;
  urgency: string | null;
  red_flags: string[];
  reasoning: string;
  matched_caregivers: MatchedCaregiver[];
  trace: Trace;
}

// ---- bookings ----

export interface BookingRequest {
  caregiver_id: string;
  slot: string | null;
  care_type: string | null;
  urgency: string | null;
  note: string;
}

export interface BookingResponse {
  booking_id: string;
  status: string;
  caregiver_id: string;
  caregiver_name: string;
  slot: string | null;
  created_at: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  caregivers_source?: string;
  caregivers?: number;
  model?: string;
}
