import { useEffect, useRef, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Gauge,
  Info,
  Phone,
  Plus,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Volume2,
  Square,
} from "lucide-react";
import type { FollowUpOption, Lang, TraceCaregiver, TriageResponse } from "../types";
import { specialtyLabel, t, type Key } from "../i18n";
import {
  bandKey,
  careKey,
  decisionModelClass,
  decisionSource,
  isRemoteCarer,
  isUnclear,
  modelShortName,
  safetyChoseUrgent,
  structuredChips,
  topModelClass,
  type Msg,
  urgencyLevel,
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
  // a question's helper line is shown once, not again on the next question with the same line
  let prevWhy: string | null = null;
  return (
    <div className="thread" aria-live="polite">
      {p.messages.map((m, i) => {
        let showWhy = true;
        if (m.kind === "question") {
          const why = m.res.trace.reasoning_local?.trim() || null;
          showWhy = why !== prevWhy;
          prevWhy = why;
        }
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
                <Question
                  res={m.res}
                  lang={p.lang}
                  live={m.id === lastQuestion?.id && m.id === lastId && !p.busy}
                  showWhy={showWhy}
                  onAnswer={p.onAnswer}
                />
              )}
              {m.kind === "decision" && isUnclear(m.res) && (
                <Unclear res={m.res} lang={p.lang} onBook={p.onBook} locked={i < lastEmergency} onNewCheck={p.onNewCheck} />
              )}
              {m.kind === "decision" && !isUnclear(m.res) && (
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
              {/* the red button calls 112 straight away; the title reopens the full emergency screen */}
              {m.kind === "emergency" && (
                <div className="error">
                  <button type="button" className="sos-reopen" onClick={() => p.onOpenEmergency(m)}>
                    <strong>{m.res.trace.emergency?.title_local ?? t(p.lang, "sosPageTitle")}</strong>
                    <ChevronRight size={18} aria-hidden="true" />
                  </button>
                  <a className="btn btn--danger" href="tel:112">
                    <Phone size={18} aria-hidden="true" />
                    {t(p.lang, "sosNow")}
                  </a>
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

function Question({
  res,
  lang,
  live,
  showWhy,
  onAnswer,
}: {
  res: TriageResponse;
  lang: Lang;
  live: boolean;
  showWhy: boolean;
  onAnswer: (t: string) => void;
}) {
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
      {showWhy && res.trace.reasoning_local && <p className="question__why">{res.trace.reasoning_local}</p>}
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
// here), a safety check that chose more urgent care, or the second check (Claude) when
// the model was unsure. Older answers show nothing. Shown at the top of "Yeh faisla
// kyon?" (inline under the card, and in the desktop side panel), not on the card.
export function SourceLine({ res, lang }: { res: TriageResponse; lang: Lang }) {
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
  return lines.length ? <div className="decision__sources">{lines}</div> : null;
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
  const voiceLang = res.trace.language;
  const fallbackCare = careKey(res.care_type ?? d.care_type);
  const careLabel = d.care_label_local || d.care_label || (fallbackCare ? t(lang, fallbackCare) : "");
  // the dial shows how soon; the urgency is still read aloud
  const urgencyLabel = d.urgency_label_local || d.urgency_label || (res.urgency ? t(lang, URGENCY_KEY[level]) : "");
  const safetyNet = res.trace.safety_net_local?.trim() || null;
  const summary = [careLabel, urgencyLabel, res.trace.reasoning_local, safetyNet].filter(Boolean).join(". ");

  // dial, care, reason, safety net; who decided is at the top of "Yeh faisla kyon?"
  return (
    <section className="decision" aria-label={t(lang, "ourAdvice")}>
      <div className="decision__top">
        <Dial level={level} lang={lang} />
        <div className="decision__head">
          <div className="decision__title">
            <h2 className="decision__care" lang={voiceLang === "hi" ? "hi" : undefined}>
              {careLabel}
            </h2>
            <ReadAloud text={summary} lang={voiceLang} speech={res.trace.speech} />
          </div>
          {d.specialty && (
            <div className="decision__chips">
              <span className="chip">{t(lang, "specialist", { x: specialtyLabel(lang, d.specialty) })}</span>
            </div>
          )}
          <p className="decision__reason">{res.trace.reasoning_local}</p>
          {safetyNet && (
            <p className="safety-net" lang={voiceLang === "hi" ? "hi" : undefined}>
              <Info size={17} aria-hidden="true" />
              <span>{safetyNet}</span>
            </p>
          )}
        </div>
      </div>
      <div className="decision__actions">
        <button type="button" className="btn btn--quiet why-toggle" aria-expanded={why} onClick={() => setWhy((w) => !w)}>
          {t(lang, "whyThis")}
          <ChevronDown size={18} aria-hidden="true" style={{ transform: why ? "rotate(180deg)" : undefined }} />
        </button>
        {onAddMore && (
          <button type="button" className="btn btn--quiet" aria-pressed={adding} onClick={onAddMore}>
            {t(lang, "addMore")}
          </button>
        )}
        <button type="button" className="btn btn--quiet" onClick={onNewCheck}>
          <Plus size={17} aria-hidden="true" />
          {t(lang, "newChat")}
        </button>
      </div>
      {why && (
        <div className="why">
          <SourceLine res={res} lang={lang} />
          <CaseDetails res={res} lang={lang} />
        </div>
      )}
      <Carers res={res} lang={lang} onBook={onBook} locked={locked} />
    </section>
  );
}

function Carers({
  res,
  lang,
  onBook,
  locked,
}: {
  res: TriageResponse;
  lang: Lang;
  onBook: (cg: TraceCaregiver, res: TriageResponse) => void;
  locked: boolean;
}) {
  const [first, ...rest] = carersOf(res);
  // the best match only; "Aur 2 dekhein" shows the rest and takes focus to them
  const [all, setAll] = useState(false);
  const restRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (all) restRef.current?.focus({ preventScroll: true });
  }, [all]);
  const card = (cg: TraceCaregiver, best: boolean) => (
    <CaregiverCard
      key={cg.caregiver_id}
      cg={cg}
      best={best}
      tele={isRemoteCarer(res.care_type, cg.role)}
      lang={lang}
      onBook={locked ? undefined : () => onBook(cg, res)}
    />
  );
  return (
    <div className="carers">
      <h3 className="carers__title">{t(lang, "carersTitle")}</h3>
      {!first && <p className="case-panel__empty">{t(lang, "noCarers")}</p>}
      {locked && first && <p className="case-panel__empty">{t(lang, "bookLocked")}</p>}
      {first && card(first, true)}
      {rest.length > 0 &&
        (all ? (
          <div className="carers__rest" ref={restRef} tabIndex={-1}>
            {rest.map((cg) => card(cg, false))}
          </div>
        ) : (
          <button type="button" className="btn btn--quiet carers__more" onClick={() => setAll(true)}>
            {t(lang, "carersMore", { n: rest.length })}
            <ChevronDown size={18} aria-hidden="true" />
          </button>
        ))}
    </div>
  );
}

// Nothing was understood after three answers (rule fallback_unclear): the doctor call
// that comes back is a safe default, not a finding, so no dial, urgency or reasons.
// "Doctor se baat karein" shows this response's caregivers, booked as usual.
function Unclear({
  res,
  lang,
  onBook,
  locked,
  onNewCheck,
}: {
  res: TriageResponse;
  lang: Lang;
  onBook: (cg: TraceCaregiver, res: TriageResponse) => void;
  locked: boolean;
  onNewCheck: () => void;
}) {
  const [carersOpen, setCarersOpen] = useState(false);
  return (
    <section className="decision" aria-label={t(lang, "unclearTitle")}>
      <div className="unclear">
        <h2 className="unclear__title">{t(lang, "unclearTitle")}</h2>
        <p className="unclear__text">{t(lang, "unclearText")}</p>
        <div className="unclear__actions">
          <button type="button" className="btn btn--primary" aria-expanded={carersOpen} onClick={() => setCarersOpen((o) => !o)}>
            <Phone size={18} aria-hidden="true" />
            {t(lang, "unclearDoctor")}
          </button>
          <button type="button" className="btn btn--ghost" onClick={onNewCheck}>
            <Plus size={18} aria-hidden="true" />
            {t(lang, "newChat")}
          </button>
        </div>
      </div>
      {carersOpen && <Carers res={res} lang={lang} onBook={onBook} locked={locked} />}
    </section>
  );
}
