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
  // the API now sends plain ids here (e.g. "severe"); older builds sent objects
  severity: Array<string | { id: string; label: string; label_local: string }>;
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
  // organisers' values: paramedic_home_visit | home_nursing | lab_test_home |
  // teleconsultation | emergency_112 (older builds: nurse, specialist, emergency_referral)
  care_type: string | null;
  // emergency | same_day | scheduled (older builds: immediate, routine)
  urgency: string | null;
  care_label: string | null;
  care_label_local: string | null;
  urgency_label: string | null;
  urgency_label_local: string | null;
  confidence: number;
  source: string;
  rule: string;
  // Set for specialist routing (e.g. "orthopaedics"); null otherwise.
  specialty?: string | null;
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
  // Named 0-1 sub-scores behind the match. The keys change with the ranker
  // (today: language, distance, skill, rating), so render whatever arrives.
  features?: MatchFeatures | null;
}

export type MatchFeatures = Record<string, number | null | undefined>;

// The learned model's output (only when the model is loaded). Classes today:
// paramedic, nurse, lab, gp, emergency, followup.
export interface ModelOutput {
  probabilities: Record<string, number>;
  version?: string;
}

export interface Trace {
  version: string;
  language: Lang;
  mode?: string;
  understood: Understood;
  model?: ModelOutput | null;
  checks: Check[];
  red_flags: RedFlag[];
  decision: Decision;
  reasoning_local: string;
  follow_up: FollowUp | null;
  emergency: Emergency | null;
  caregivers: TraceCaregiver[];
  /** Read-aloud text: Devanagari for Hindi and Hinglish ("hi-IN"), English otherwise ("en-IN"). */
  speech?: { locale: string; text: string } | null;
  timing_ms: number;
}

export interface TriageResponse {
  follow_up_question: string | null;
  care_type: string | null;
  urgency: string | null;
  // organisers' flag ids where one exists (chest_pain, breathlessness, ...), else ours.
  // Never shown to people: the UI uses trace.red_flags[].label_local.
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
