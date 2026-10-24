import { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  AlertCircle,
  CheckCircle2,
  HelpCircle,
} from "lucide-react";
import type { Lang, Trace, CheckStatus } from "../types";
import { t } from "../i18n";

function CheckIcon({ status }: { status: CheckStatus }) {
  if (status === "present")
    return (
      <span className="check-icon check-icon--present">
        <AlertCircle size={22} aria-hidden="true" />
      </span>
    );
  if (status === "absent")
    return (
      <span className="check-icon check-icon--absent">
        <CheckCircle2 size={22} aria-hidden="true" />
      </span>
    );
  return (
    <span className="check-icon check-icon--not_reported">
      <HelpCircle size={22} aria-hidden="true" />
    </span>
  );
}

interface Props {
  trace: Trace;
  lang: Lang;
}

// The "Kyon?" panel (spec section 6): what we understood, what we checked,
// and why. All content comes from the trace (already in the user's language).
export default function Explain({ trace, lang }: Props) {
  const [open, setOpen] = useState(false);
  const u = trace.understood;
  const dev = lang === "hi" ? "hi" : undefined;

  const understoodChips: string[] = [];
  if (u.patient?.relation_label) {
    let p = u.patient.relation_label;
    if (u.patient.age_years != null) p += `, ${u.patient.age_years} ${t(lang, "years")}`;
    understoodChips.push(p);
  }
  for (const s of u.symptoms) understoodChips.push(s.label_local);
  if (u.duration_label) understoodChips.push(u.duration_label);
  for (const s of u.services) understoodChips.push(s.label_local);

  return (
    <section className="explain">
      <button
        type="button"
        className="explain__head"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span>{t(lang, "why")}</span>
        {open ? <ChevronUp size={22} /> : <ChevronDown size={22} />}
      </button>

      {open && (
        <div className="explain__body" lang={dev}>
          {understoodChips.length > 0 && (
            <div>
              <div className="explain__group-title">{t(lang, "understood")}</div>
              <div className="explain__chips">
                {understoodChips.map((c, i) => (
                  <span className="u-chip" key={i}>
                    {c}
                  </span>
                ))}
              </div>
            </div>
          )}

          {trace.checks.length > 0 && (
            <div>
              <div className="explain__group-title">{t(lang, "checked")}</div>
              <div>
                {trace.checks.map((c) => (
                  <div className="check-row" key={c.id}>
                    <CheckIcon status={c.status} />
                    <span>{c.label_local}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {trace.reasoning_local && (
            <div>
              <div className="explain__group-title">{t(lang, "decisionWhy")}</div>
              <p className="reasoning">{trace.reasoning_local}</p>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
