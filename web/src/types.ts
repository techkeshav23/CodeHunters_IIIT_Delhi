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
  // who made the call: model | model+safety_net | safety_net | llm (a second check
  // by Claude when the model was unsure) | rules (no model loaded)
  source: string;
  rule: string;
  // Set for specialist routing (e.g. "orthopaedics"); null otherwise.
  specialty?: string | null;
}

export interface FollowUpOption {
  value: string;
  label: string;
}

// ids include q_danger (yes/no danger signs) and q_scope (a polite reply to a
// message that is not a health need; it may come without options)
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

export type ConfidenceBand = "high" | "medium" | "low";

// The learned model's output (only when a model is loaded). Classes: paramedic,
// nurse, lab, gp, emergency, followup, out_of_scope. The fine-tuned MuRIL model
// adds its name, urgency probabilities (routine, same_day, immediate) and a
// calibrated confidence with its band; the older model sent only the first two.
export interface ModelOutput {
  name?: string | null;
  probabilities: Record<string, number>;
  urgency_probabilities?: Record<string, number> | null;
  confidence?: number | null;
  band?: ConfidenceBand | null;
  version?: string;
  latency_ms?: number | null;
}

// Module 1's structured output: the symptoms and services found, and who the care
// is for (self | adult | elderly | child | infant | pregnant | unknown).
export interface Structured {
  symptoms: Symptom[];
  who?: string | null;
  who_label_local?: string | null;
  duration_days?: number | null;
  age_years?: number | null;
}

// One safety check run on this answer: "fired" means it changed or guarded the
// decision, "pass" means it ran and had nothing to add. Ids: safety_net,
// model_emergency, vulnerable_floor, urgency_floor, low_confidence, out_of_scope,
// llm_fallback, clinical_scope, invariants.
export interface Guardrail {
  id: string;
  label: string;
  label_local: string;
  status: "pass" | "fired";
  note_local?: string | null;
}

export interface Trace {
  version: string;
  language: Lang;
  mode?: string;
  understood: Understood;
  model?: ModelOutput | null;
  structured?: Structured | null;
  guardrails?: Guardrail[] | null;
  checks: Check[];
  red_flags: RedFlag[];
  decision: Decision;
  reasoning_local: string;
  /** For non-emergency answers: when to come back or call 112, in the user's language. */
  safety_net_local?: string | null;
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
