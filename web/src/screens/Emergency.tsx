import { useEffect, useRef } from "react";
import { Phone, PhoneCall, AlertTriangle } from "lucide-react";
import type { Lang, TriageResponse } from "../types";
import { t } from "../i18n";
import { speak } from "../voice";

interface Props {
  lang: Lang;
  response: TriageResponse;
  cameFromVoice: boolean;
  onRestart: () => void;
}

// Full red screen (spec section 4.5). No booking, no caregiver cards here.
// Designed to be impossible to miss: a missed emergency cannot win.
export default function Emergency({
  lang,
  response,
  cameFromVoice,
  onRestart,
}: Props) {
  const em = response.trace.emergency;
  const dev = lang === "hi" ? "hi" : undefined;

  const title =
    em?.title_local ?? em?.title ?? response.reasoning ?? t(lang, "call112");
  const numbers = em?.numbers ?? [
    { label: "Emergency", label_local: "Emergency", number: "112" },
  ];
  const steps = em?.steps_local ?? em?.steps ?? [];
  const flags = response.trace.red_flags;

  // Read the emergency aloud once if the user was in a voice flow.
  const spoken = useRef(false);
  useEffect(() => {
    if (cameFromVoice && !spoken.current) {
      spoken.current = true;
      speak(title, lang);
    }
  }, [cameFromVoice, title, lang]);

  return (
    <div className="emergency" role="alertdialog" aria-label={title}>
      <div className="emergency__inner" lang={dev}>
        <h1 className="emergency__title">
          <AlertTriangle size={44} aria-hidden="true" />
          {title}
        </h1>

        <a
          className="emergency__call-big"
          href="tel:112"
          aria-label={t(lang, "call112")}
        >
          <PhoneCall size={34} aria-hidden="true" />
          112
        </a>

        <div className="emergency__numbers">
          {numbers
            .filter((n) => n.number !== "112")
            .map((n) => (
              <a
                className="emergency__num"
                href={`tel:${n.number}`}
                key={n.number}
              >
                <span>{n.label_local || n.label}</span>
                <span className="emergency__num-dial">
                  <Phone size={18} aria-hidden="true" />
                  {n.number}
                </span>
              </a>
            ))}
        </div>

        {steps.length > 0 && (
          <ol className="emergency__steps">
            {steps.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        )}

        {flags.length > 0 && (
          <div className="emergency__flags">
            <div className="section-title" style={{ color: "#fff" }}>
              {t(lang, "redFlagsFound")}
            </div>
            {flags.map((f) => (
              <div className="emergency__flag" key={f.id}>
                <strong>{f.label_local || f.label}</strong>
                {f.evidence && (
                  <span className="emergency__flag-ev"> — “{f.evidence}”</span>
                )}
              </div>
            ))}
          </div>
        )}

        <button
          type="button"
          className="emergency__restart"
          onClick={onRestart}
        >
          {t(lang, "restart")}
        </button>
      </div>
    </div>
  );
}
