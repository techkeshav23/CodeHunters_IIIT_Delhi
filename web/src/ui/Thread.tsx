import { useState } from "react";
import {
  ChevronDown,
  FlaskConical,
  Gauge,
  HeartPulse,
  Info,
  MessageSquarePlus,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Siren,
  Stethoscope,
  Syringe,
  Video,
  Volume2,
  Square,
} from "lucide-react";
import type { FollowUpOption, Lang, TraceCaregiver, TriageResponse } from "../types";
import { specialtyLabel, t, type Key } from "../i18n";
import {
  bandKey,
  careKey,
  careKind,
  decisionModelClass,
  decisionSource,
  isRemoteCarer,
  modelShortName,
  safetyChoseUrgent,
  structuredChips,
  topModelClass,
  type CareKind,
  type Msg,
  urgencyLevel,
  fmtDays,
} from "../lib";
import { BrandMark } from "./Brand";
import Dial from "./Dial";
import CaseDetails from "./CaseDetails";
import CaregiverCard from "./CaregiverCard";
import { speak, speechFor, stopSpeaking, ttsSupported, type Speech } from "../voice";

interface Props {
  messages: Msg[];
  busy: boolean;
  lang: Lang;
  onAnswer: (text: string) => void;
  onBook: (cg: TraceCaregiver, res: TriageResponse) => void;
  onRetry: (msg: Extract<Msg, { kind: "error" }>) => void;
  onOpenEmergency: (msg: Extract<Msg, { kind: "emergency" }>) => void;
  onNewCheck: () => void;
  // "Add more details": the next message re-runs the triage on this case's whole conversation
  onAddMore: (msg: Extract<Msg, { kind: "decision" }>) => void;
  adding: boolean;
}

export default function Thread(p: Props) {
  const lastQuestion = [...p.messages].reverse().find((m) => m.kind === "question");
  const lastId = p.messages[p.messages.length - 1]?.id;
  // no booking from a decision that a later emergency in this chat has overtaken
  const lastEmergency = p.messages.map((m) => m.kind).lastIndexOf("emergency");
  return (
    <div className="thread" aria-live="polite">
      {p.messages.map((m, i) => {
        if (m.kind === "user") {
          return (
            <div key={m.id} className="msg msg--user">
              <div className="bubble">{m.text}</div>
            </div>
          );
        }
        return (
          <div key={m.id} className="msg">
            <span className="msg__avatar" aria-hidden="true">
              <BrandMark size={22} />
            </span>
            <div className="msg__body">
              {m.kind === "question" && (
                <Question res={m.res} lang={p.lang} live={m.id === lastQuestion?.id && m.id === lastId && !p.busy} onAnswer={p.onAnswer} />
              )}
              {m.kind === "decision" && (
                <Decision
                  res={m.res}
                  lang={p.lang}
                  onBook={p.onBook}
                  locked={i < lastEmergency}
                  onNewCheck={p.onNewCheck}
                  onAddMore={m.id === lastId && !p.busy ? () => p.onAddMore(m) : undefined}
                  adding={p.adding}
                />
              )}
              {m.kind === "emergency" && (
                <div className="error" style={{ background: "var(--sindoor-soft)" }}>
                  <strong>{m.res.trace.emergency?.title_local ?? t(p.lang, "sosPageTitle")}</strong>
                  <button type="button" className="btn btn--danger" onClick={() => p.onOpenEmergency(m)}>
                    <Siren size={18} aria-hidden="true" />
                    {t(p.lang, "sosNow")}
                  </button>
                </div>
              )}
              {m.kind === "error" && (
                <div className="error" role="alert">
                  <p>{t(p.lang, "errorText")}</p>
                  <button type="button" className="btn btn--ghost" onClick={() => p.onRetry(m)}>
                    <RotateCcw size={18} aria-hidden="true" />
                    {t(p.lang, "retry")}
                  </button>
                </div>
              )}
            </div>
          </div>
        );
      })}
      {p.busy && (
        <div className="msg">
          <span className="msg__avatar" aria-hidden="true">
            <BrandMark size={22} />
          </span>
          <div className="typing" role="status">
            {t(p.lang, "thinking")}
            <span className="typing__dots" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function ReadAloud({ text, lang, speech }: { text: string; lang: Lang; speech?: Speech | null }) {
  const [on, setOn] = useState(false);
  if (!ttsSupported()) return null;
  return (
    <button
      type="button"
      className="btn btn--quiet"
      aria-pressed={on}
      onClick={() => {
        if (on) {
          stopSpeaking();
          setOn(false);
        } else {
          setOn(true);
          speak(speechFor(speech, text, lang), { onEnd: () => setOn(false) });
        }
      }}
    >
      {on ? <Square size={16} aria-hidden="true" /> : <Volume2 size={18} aria-hidden="true" />}
      {on ? t(lang, "stopReading") : t(lang, "readAloud")}
    </button>
  );
}

// "Samjha: Bukhar · 3 din se · Buzurg" from trace.structured; nothing for older builds
function UnderstoodRow({ res, lang }: { res: TriageResponse; lang: Lang }) {
  const chips = structuredChips(res.trace, lang);
  if (!chips) return null;
  return (
    <div className="understood-row">
      <span className="understood-row__label">{t(lang, "understoodShort")}:</span>
      {chips.map((c) => (
        <span key={c.text} className={c.kind === "who" ? "chip chip--haldi" : "chip"}>
          {c.text}
        </span>
      ))}
    </div>
  );
}

// A question's tap answers. A yes/no question that arrives without options (e.g.
// q_danger from an older build) still gets Haan / Nahi in the user's language.
function optionsOf(res: TriageResponse): FollowUpOption[] {
  const fu = res.trace.follow_up;
  if (!fu) return [];
  if (Array.isArray(fu.options) && fu.options.length > 0) return fu.options;
  if (fu.kind === "yes_no") {
    const l = res.trace.language;
    return [
      { value: "yes", label: t(l, "optYes") },
      { value: "no", label: t(l, "optNo") },
    ];
  }
  return [];
}

function Question({ res, lang, live, onAnswer }: { res: TriageResponse; lang: Lang; live: boolean; onAnswer: (t: string) => void }) {
  const fu = res.trace.follow_up;
  const text = res.follow_up_question ?? fu?.text ?? "";
  const n = fu?.asked_so_far ?? 1;
  const max = fu?.max ?? 3;
  const voiceLang = res.trace.language;
  const options = optionsOf(res);
  // two answers (Haan / Nahi) sit side by side as big buttons, even on a phone
  const pair = options.length === 2 && (fu?.kind === "yes_no" || options.every((o) => o.value === "yes" || o.value === "no"));
  // a polite out-of-scope reply is not one of the triage questions: no progress dots
  const counted = fu?.id !== "q_scope";
  return (
    <section className="question" aria-label={text}>
      <div className="question__meta">
        {counted ? (
          <span className="progress" aria-label={t(lang, "questionOf", { n, max })}>
            {Array.from({ length: max }, (_, i) => (
              <i key={i} className={i < n ? "on" : ""} />
            ))}
            <span style={{ marginLeft: 6 }}>{t(lang, "questionOf", { n, max })}</span>
          </span>
        ) : (
          <span />
        )}
        <ReadAloud text={text} lang={voiceLang} speech={res.trace.speech} />
      </div>
      <UnderstoodRow res={res} lang={lang} />
      <p className="question__text" lang={voiceLang === "hi" ? "hi" : undefined}>
        {text}
      </p>
      {res.trace.reasoning_local && <p className="question__why">{res.trace.reasoning_local}</p>}
      {live && options.length > 0 && (
        <div className={pair ? "options options--pair" : "options"} role="group" aria-label={text}>
          {options.map((o) => (
            <button
              key={o.value}
              type="button"
              className="option"
              data-value={o.value}
              lang={voiceLang === "hi" ? "hi" : undefined}
              onClick={() => onAnswer(o.label)}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

const CARE_ICON: Record<CareKind, typeof Stethoscope> = {
  paramedic: HeartPulse,
  nurse: Syringe,
  lab: FlaskConical,
  doctor: Video,
  emergency: Siren,
};
const URGENCY_KEY: Key[] = ["urgRoutine", "urgSameDay", "urgNow"];

// trace.caregivers carries the full cards; if it ever comes back empty while the
// six-field answer still names caregivers, show those rather than nothing.
function carersOf(res: TriageResponse): TraceCaregiver[] {
  const full = res.trace?.caregivers;
  if (Array.isArray(full) && full.length > 0) return full;
  return (res.matched_caregivers ?? []).map((m) => ({
    caregiver_id: m.caregiver_id,
    name: m.caregiver_id,
    role: "",
    languages: [],
    skills: [],
    distance_km: null,
    next_slot: null,
    next_slot_label: null,
    next_slot_label_local: null,
    rating: null,
    score: m.score,
    reason: m.reason,
    reason_local: m.reason,
    features: null,
  }));
}

// Who made this call, in plain words: the model and how sure it was (no percentages
// here; "Why" has the numbers), a safety check that chose more urgent care, or the
// second check (Claude) when the model was unsure. Older answers show nothing.
function SourceLine({ res, lang }: { res: TriageResponse; lang: Lang }) {
  const src = decisionSource(res);
  const band = bandKey(res.trace.model?.band);
  // a safety check switched the model's pick (e.g. fever_home_visit: doctor -> paramedic): the
  // band is the model's confidence in another class, so the card does not say the model decided
  const top = topModelClass(res.trace.model);
  const decided = decisionModelClass(res);
  const overridden = src.includes("safety_net") && !!top && !!decided && top.cls !== decided.cls;
  const lines: JSX.Element[] = [];
  if (src === "llm") {
    lines.push(
      <p key="llm" className="decision__source">
        <ShieldCheck size={15} aria-hidden="true" />
        <span>{t(lang, "srcLlm")}</span>
      </p>,
    );
  } else if (src.startsWith("model") && band && !overridden) {
    lines.push(
      <p key="model" className="decision__source">
        <Gauge size={15} aria-hidden="true" />
        <span>
          {t(lang, "decidedBy", { x: modelShortName(res.trace.model) })} · <b>{t(lang, band)}</b>
        </span>
      </p>,
    );
  }
  if (safetyChoseUrgent(res)) {
    lines.push(
      <p key="safety" className="decision__source">
        <ShieldAlert size={15} aria-hidden="true" />
        <span>{t(lang, "srcSafety")}</span>
      </p>,
    );
  }
  return lines.length ? <>{lines}</> : null;
}

function Decision({
  res,
  lang,
  onBook,
  locked,
  onNewCheck,
  onAddMore,
  adding,
}: {
  res: TriageResponse;
  lang: Lang;
  onBook: (cg: TraceCaregiver, res: TriageResponse) => void;
  locked: boolean;
  onNewCheck: () => void;
  onAddMore?: () => void;
  adding: boolean;
}) {
  const [why, setWhy] = useState(false);
  const d = res.trace.decision;
  const level = urgencyLevel(res.urgency);
  const carers = carersOf(res);
  const voiceLang = res.trace.language;
  // a duration in the "Samjha" row (trace.structured) is not repeated as a chip
  const inRow = structuredChips(res.trace, lang)?.some((c) => c.kind === "duration") ?? false;
  const dur = inRow ? null : fmtDays(res.trace.understood?.duration_days ?? null, lang);
  const kind = careKind(res.care_type ?? d.care_type);
  const CareIcon = kind ? CARE_ICON[kind] : null;
  const fallbackCare = careKey(res.care_type ?? d.care_type);
  const careLabel = d.care_label_local || d.care_label || (fallbackCare ? t(lang, fallbackCare) : "");
  const urgencyLabel = d.urgency_label_local || d.urgency_label || (res.urgency ? t(lang, URGENCY_KEY[level]) : "");
  const safetyNet = res.trace.safety_net_local?.trim() || null;
  const summary = [careLabel, urgencyLabel, res.trace.reasoning_local, safetyNet].filter(Boolean).join(". ");

  return (
    <section className="decision" aria-label={t(lang, "ourAdvice")}>
      <div className="decision__top">
        <Dial level={level} lang={lang} />
        <div className="decision__head">
          <span className="decision__kicker">
            {CareIcon && (
              <span className={kind === "emergency" ? "care-ico care-ico--danger" : "care-ico"} data-care={kind} aria-hidden="true">
                <CareIcon size={16} />
              </span>
            )}
            {t(lang, "ourAdvice")}
          </span>
          <h2 className="decision__care" lang={voiceLang === "hi" ? "hi" : undefined}>
            {careLabel}
          </h2>
          <div className="decision__chips">
            {urgencyLabel && (
              <span className={level === 1 ? "chip chip--haldi" : level === 2 ? "chip chip--danger" : "chip chip--brand"}>
                {urgencyLabel}
              </span>
            )}
            {d.specialty && <span className="chip">{t(lang, "specialist", { x: specialtyLabel(lang, d.specialty) })}</span>}
            {dur && <span className="chip">{dur}</span>}
          </div>
          <UnderstoodRow res={res} lang={lang} />
          <p className="decision__reason">{res.trace.reasoning_local}</p>
          {safetyNet && (
            <p className="safety-net" lang={voiceLang === "hi" ? "hi" : undefined}>
              <Info size={17} aria-hidden="true" />
              <span>{safetyNet}</span>
            </p>
          )}
          <SourceLine res={res} lang={lang} />
        </div>
      </div>
      <div className="decision__actions">
        <ReadAloud text={summary} lang={voiceLang} speech={res.trace.speech} />
        <button type="button" className="btn btn--quiet why-toggle" aria-expanded={why} onClick={() => setWhy((w) => !w)}>
          {t(lang, "whyThis")}
          <ChevronDown size={18} aria-hidden="true" style={{ transform: why ? "rotate(180deg)" : undefined }} />
        </button>
        {onAddMore && (
          <button type="button" className="btn btn--quiet" aria-pressed={adding} onClick={onAddMore}>
            <MessageSquarePlus size={17} aria-hidden="true" />
            {t(lang, "addMore")}
          </button>
        )}
        <button type="button" className="btn btn--quiet" onClick={onNewCheck}>
          <RotateCcw size={16} aria-hidden="true" />
          {t(lang, "newCheck")}
        </button>
      </div>
      {why && (
        <div className="why">
          <CaseDetails res={res} lang={lang} />
        </div>
      )}
      <div className="carers">
        <h3 className="carers__title">{t(lang, "carersTitle")}</h3>
        {carers.length === 0 && <p className="case-panel__empty">{t(lang, "noCarers")}</p>}
        {locked && carers.length > 0 && <p className="case-panel__empty">{t(lang, "bookLocked")}</p>}
        {carers.map((cg, i) => (
          <CaregiverCard
            key={cg.caregiver_id}
            cg={cg}
            best={i === 0}
            tele={isRemoteCarer(res.care_type, cg.role)}
            lang={lang}
            onBook={locked ? undefined : () => onBook(cg, res)}
          />
        ))}
      </div>
    </section>
  );
}
