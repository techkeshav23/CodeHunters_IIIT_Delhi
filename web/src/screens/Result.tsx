import { useState } from "react";
import {
  Volume2,
  Square,
  Star,
  MapPin,
  Clock,
  CalendarCheck,
  Languages,
} from "lucide-react";
import type { Lang, TriageResponse, TraceCaregiver } from "../types";
import { t } from "../i18n";
import { speak, stopSpeaking, ttsSupported } from "../voice";
import Explain from "../components/Explain";
import JudgeView from "../components/JudgeView";

interface Props {
  lang: Lang;
  response: TriageResponse;
  request: unknown;
  bookingFor: string | null; // caregiver_id currently being booked
  onBook: (cg: TraceCaregiver) => void;
}

function badgeClass(urgency: string | null): string {
  if (urgency === "immediate") return "badge badge--immediate";
  if (urgency === "same_day") return "badge badge--same_day";
  return "badge badge--routine";
}

export default function Result({
  lang,
  response,
  request,
  bookingFor,
  onBook,
}: Props) {
  const [speaking, setSpeaking] = useState(false);
  const dev = lang === "hi" ? "hi" : undefined;
  const trace = response.trace;
  const d = trace.decision;
  const caregivers = trace.caregivers.slice(0, 3);

  const headline = d.care_label_local ?? d.care_label ?? "";
  const urgencyLabel = d.urgency_label_local ?? d.urgency_label ?? "";

  const toggleRead = () => {
    if (speaking) {
      stopSpeaking();
      setSpeaking(false);
      return;
    }
    const parts = [headline, trace.reasoning_local];
    const first = caregivers[0];
    if (first) parts.push(`${first.name}. ${first.reason_local}`);
    speak(parts.filter(Boolean).join(". "), lang);
    setSpeaking(true);
    // speechSynthesis has no reliable "all done" here; reset after a guess.
    window.setTimeout(() => setSpeaking(false), 12000);
  };

  return (
    <div className="stack">
      <section
        className="decision-card"
        aria-live="polite"
        lang={dev}
      >
        <h1 className="decision-headline">{headline}</h1>
        {urgencyLabel && (
          <span className={badgeClass(d.urgency)}>{urgencyLabel}</span>
        )}
      </section>

      {ttsSupported() && (
        <button
          type="button"
          className="btn btn--ghost"
          onClick={toggleRead}
          aria-pressed={speaking}
        >
          {speaking ? (
            <>
              <Square size={20} aria-hidden="true" /> {t(lang, "stopReading")}
            </>
          ) : (
            <>
              <Volume2 size={20} aria-hidden="true" /> {t(lang, "read")}
            </>
          )}
        </button>
      )}

      <Explain trace={trace} lang={lang} />

      <div className="stack">
        {caregivers.map((cg, i) => (
          <article className="cg-card" key={cg.caregiver_id} lang={dev}>
            <div className="cg-top">
              <div>
                <div className="cg-rank">#{i + 1}</div>
                <div className="cg-name">{cg.name}</div>
                <div className="cg-role">{cg.role}</div>
              </div>
              {cg.rating != null && (
                <span className="cg-rating">
                  <Star size={15} fill="currentColor" aria-hidden="true" />
                  {cg.rating.toFixed(1)}
                </span>
              )}
            </div>

            {cg.languages.length > 0 && (
              <div className="cg-langs">
                <Languages size={16} aria-hidden="true" style={{ color: "var(--teal-600)" }} />
                {cg.languages.map((l) => (
                  <span className="tag" key={l}>
                    {l}
                  </span>
                ))}
              </div>
            )}

            <div className="cg-meta">
              {cg.distance_km != null && (
                <span>
                  <MapPin size={15} aria-hidden="true" />
                  {cg.distance_km} km {t(lang, "distance")}
                </span>
              )}
              {(cg.next_slot_label_local ?? cg.next_slot_label) && (
                <span>
                  <Clock size={15} aria-hidden="true" />
                  {cg.next_slot_label_local ?? cg.next_slot_label}
                </span>
              )}
            </div>

            <p className="cg-reason">{cg.reason_local || cg.reason}</p>

            <button
              type="button"
              className="btn btn--primary"
              onClick={() => onBook(cg)}
              disabled={bookingFor !== null}
            >
              <CalendarCheck size={20} aria-hidden="true" />
              {bookingFor === cg.caregiver_id ? t(lang, "booking") : t(lang, "book")}
            </button>
          </article>
        ))}
      </div>

      <JudgeView
        request={request}
        response={response}
        timingMs={trace.timing_ms}
        lang={lang}
      />
    </div>
  );
}
