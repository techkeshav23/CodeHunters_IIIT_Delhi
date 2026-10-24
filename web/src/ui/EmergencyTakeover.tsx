import { useEffect, useRef } from "react";
import { ArrowLeft, Phone, RotateCcw, ShieldAlert, TriangleAlert } from "lucide-react";
import type { Lang, TriageResponse } from "../types";
import { t } from "../i18n";
import { raisedBySafety } from "../lib";

interface Props {
  res: TriageResponse;
  userText: string;
  lang: Lang;
  onBack: () => void;
  onNewCheck: () => void;
}

// Full-screen, impossible to miss. No booking, no caregivers: only call-for-help.
export default function EmergencyTakeover({ res, userText, lang, onBack, onNewCheck }: Props) {
  const em = res.trace.emergency;
  const callRef = useRef<HTMLAnchorElement>(null);
  useEffect(() => {
    callRef.current?.focus();
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);
  const others = (em?.numbers ?? []).filter((n) => n.number !== "112");
  // trace.red_flags carries our ids with labels; res.red_flags (the organisers'
  // ids) is never shown. A flag without a label is skipped, never shown as an id.
  const flags: Array<{ id: string; text: string; evidence: string }> = [];
  for (const f of res.trace?.red_flags ?? []) {
    const text = f.label_local || f.label;
    if (text && !flags.some((x) => x.id === f.id)) flags.push({ id: f.id, text, evidence: f.evidence });
  }

  return (
    <div className="sos" role="alertdialog" aria-modal="true" aria-labelledby="sos-title">
      <div className="sos__inner">
        <div className="sos__top">
          <span className="sos__badge">
            <TriangleAlert size={18} aria-hidden="true" />
            {t(lang, "sosTag")}
          </span>
          <button type="button" className="btn btn--on-red" onClick={onBack} aria-label={t(lang, "sosBack")}>
            <ArrowLeft size={18} aria-hidden="true" />
            {t(lang, "back")}
          </button>
        </div>
        <h1 id="sos-title">{em?.title_local ?? t(lang, "sosPageTitle")}</h1>
        {raisedBySafety(res) && (
          <p className="sos__why">
            <ShieldAlert size={18} aria-hidden="true" />
            {t(lang, "sosRaised")}
          </p>
        )}
        <a ref={callRef} className="call-big" href="tel:112" aria-label={t(lang, "sosNow")}>
          <Phone size={34} aria-hidden="true" />
          <span className="call-big__text">
            <b>112</b>
            <span>{t(lang, "callNow")}</span>
          </span>
        </a>
        {others.length > 0 && (
          <div className="call-list" aria-label={t(lang, "sosOther")}>
            {others.map((n) => (
              <a key={n.number} className="call-small" href={`tel:${n.number.replace(/[^0-9]/g, "")}`}>
                <strong>{n.number}</strong>
                <span>{n.label_local}</span>
              </a>
            ))}
          </div>
        )}
        {em?.steps_local && em.steps_local.length > 0 && (
          <div className="sos__block">
            <h2>{t(lang, "sosSteps")}</h2>
            <ol className="sos__steps">
              {em.steps_local.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ol>
          </div>
        )}
        {flags.length > 0 && (
          <div className="sos__block">
            <h2>{t(lang, "sosSeen")}</h2>
            <div className="sos__flags">
              {flags.map((f) => (
                <div key={f.id} className="sos__flag">
                  <strong>{f.text}</strong>
                  {f.evidence && <small>"{f.evidence}"</small>}
                </div>
              ))}
            </div>
            <small style={{ opacity: 0.85 }}>
              {t(lang, "sosYouSaid")}: "{userText}"
            </small>
          </div>
        )}
        <div className="sos__actions">
          <button type="button" className="btn btn--on-red" onClick={onNewCheck}>
            <RotateCcw size={18} aria-hidden="true" />
            {t(lang, "newCheck")}
          </button>
        </div>
      </div>
    </div>
  );
}
