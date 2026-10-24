import { useState } from "react";
import { ChevronDown, RotateCcw, Siren, Volume2, Square } from "lucide-react";
import type { Lang, TraceCaregiver, TriageResponse } from "../types";
import { t } from "../i18n";
import { isTele, type Msg, urgencyLevel, fmtDays } from "../lib";
import { BrandMark } from "./Brand";
import Dial from "./Dial";
import CaseDetails from "./CaseDetails";
import CaregiverCard from "./CaregiverCard";
import { speak, stopSpeaking, ttsSupported } from "../voice";

interface Props {
  messages: Msg[];
  busy: boolean;
  lang: Lang;
  onAnswer: (text: string) => void;
  onBook: (cg: TraceCaregiver, res: TriageResponse) => void;
  onRetry: (msg: Extract<Msg, { kind: "error" }>) => void;
  onOpenEmergency: (msg: Extract<Msg, { kind: "emergency" }>) => void;
  onNewCheck: () => void;
}

export default function Thread(p: Props) {
  const lastQuestion = [...p.messages].reverse().find((m) => m.kind === "question");
  const lastId = p.messages[p.messages.length - 1]?.id;
  return (
    <div className="thread" aria-live="polite">
      {p.messages.map((m) => {
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
                <Decision res={m.res} lang={p.lang} onBook={p.onBook} onNewCheck={p.onNewCheck} />
              )}
              {m.kind === "emergency" && (
                <div className="error" style={{ background: "var(--sindoor-soft)" }}>
                  <strong>{m.res.trace.emergency?.title_local}</strong>
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

function ReadAloud({ text, lang }: { text: string; lang: Lang }) {
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
          speak(text, lang, { onEnd: () => setOn(false) });
        }
      }}
    >
      {on ? <Square size={16} aria-hidden="true" /> : <Volume2 size={18} aria-hidden="true" />}
      {on ? t(lang, "stopReading") : t(lang, "readAloud")}
    </button>
  );
}

function Question({ res, lang, live, onAnswer }: { res: TriageResponse; lang: Lang; live: boolean; onAnswer: (t: string) => void }) {
  const fu = res.trace.follow_up;
  const text = res.follow_up_question ?? fu?.text ?? "";
  const n = fu?.asked_so_far ?? 1;
  const max = fu?.max ?? 3;
  const voiceLang = res.trace.language;
  return (
    <section className="question" aria-label={text}>
      <div className="question__meta">
        <span className="progress" aria-label={t(lang, "questionOf", { n, max })}>
          {Array.from({ length: max }, (_, i) => (
            <i key={i} className={i < n ? "on" : ""} />
          ))}
          <span style={{ marginLeft: 6 }}>{t(lang, "questionOf", { n, max })}</span>
        </span>
        <ReadAloud text={text} lang={voiceLang} />
      </div>
      <p className="question__text" lang={voiceLang === "hi" ? "hi" : undefined}>
        {text}
      </p>
      {res.trace.reasoning_local && <p className="question__why">{res.trace.reasoning_local}</p>}
      {live && fu && fu.options.length > 0 && (
        <div className="options" role="group" aria-label={text}>
          {fu.options.map((o) => (
            <button key={o.value} type="button" className="option" data-value={o.value} onClick={() => onAnswer(o.label)}>
              {o.label}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

function Decision({
  res,
  lang,
  onBook,
  onNewCheck,
}: {
  res: TriageResponse;
  lang: Lang;
  onBook: (cg: TraceCaregiver, res: TriageResponse) => void;
  onNewCheck: () => void;
}) {
  const [why, setWhy] = useState(false);
  const d = res.trace.decision;
  const level = urgencyLevel(res.urgency);
  const tele = isTele(res.care_type);
  const carers = res.trace.caregivers ?? [];
  const voiceLang = res.trace.language;
  const dur = fmtDays(res.trace.understood.duration_days, lang);
  const summary = [d.care_label_local, d.urgency_label_local, res.trace.reasoning_local].filter(Boolean).join(". ");

  return (
    <section className="decision" aria-label={t(lang, "ourAdvice")}>
      <div className="decision__top">
        <Dial level={level} lang={lang} />
        <div className="decision__head">
          <span className="decision__kicker">{t(lang, "ourAdvice")}</span>
          <h2 className="decision__care" lang={voiceLang === "hi" ? "hi" : undefined}>
            {d.care_label_local}
          </h2>
          <div className="decision__chips">
            <span className={level === 1 ? "chip chip--haldi" : level === 2 ? "chip chip--danger" : "chip chip--brand"}>
              {d.urgency_label_local}
            </span>
            {d.specialty && <span className="chip">{t(lang, "specialist", { x: d.specialty })}</span>}
            {dur && <span className="chip">{dur}</span>}
          </div>
          <p className="decision__reason">{res.trace.reasoning_local}</p>
        </div>
      </div>
      <div className="decision__actions">
        <ReadAloud text={summary} lang={voiceLang} />
        <button type="button" className="btn btn--quiet why-toggle" aria-expanded={why} onClick={() => setWhy((w) => !w)}>
          {t(lang, "whyThis")}
          <ChevronDown size={18} aria-hidden="true" style={{ transform: why ? "rotate(180deg)" : undefined }} />
        </button>
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
        {carers.map((cg, i) => (
          <CaregiverCard key={cg.caregiver_id} cg={cg} best={i === 0} tele={tele} lang={lang} onBook={() => onBook(cg, res)} />
        ))}
      </div>
    </section>
  );
}
