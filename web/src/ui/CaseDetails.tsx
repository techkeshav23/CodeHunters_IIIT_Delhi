import { Check, CircleHelp, TriangleAlert } from "lucide-react";
import type { Lang, TriageResponse } from "../types";
import { t } from "../i18n";
import { fmtDays, modelClassKey, titleCase, topModelClass } from "../lib";

// "What we understood / what we checked / why": shown in the desktop side panel
// and inline under a decision on smaller screens.
export default function CaseDetails({ res, lang }: { res: TriageResponse; lang: Lang }) {
  const tr = res.trace;
  const u = tr.understood;
  const chips: string[] = [];
  if (u.patient.relation_label) chips.push(titleCase(u.patient.relation_label));
  if (u.patient.age_years != null && u.patient.age_years >= 1) chips.push(`${Math.round(u.patient.age_years)}y`);
  for (const s of u.symptoms ?? []) chips.push(s.label_local);
  for (const s of u.services ?? []) chips.push(s.label_local);
  const dur = fmtDays(u.duration_days, lang);
  if (dur) chips.push(dur);
  const checks = tr.checks ?? [];
  // the learned model's top class, only when the model is loaded
  const top = topModelClass(tr.model);
  const topKey = top ? modelClassKey(top.cls) : null;

  return (
    <div className="details">
      <div className="details__group">
        <h3>{t(lang, "understood")}</h3>
        <div className="details__chips">
          {chips.length ? (
            chips.map((c, i) => (
              <span key={i} className={i === 0 && u.patient.relation_label ? "chip chip--haldi" : "chip"}>
                {c}
              </span>
            ))
          ) : (
            <span className="case-panel__empty">-</span>
          )}
        </div>
      </div>

      {checks.length > 0 && (
        <div className="details__group">
          <h3>{t(lang, "checked")}</h3>
          <ul className="checks">
            {checks.map((c) => (
              <li key={c.id}>
                <span
                  className={
                    "ico " + (c.status === "present" ? "ico--present" : c.status === "absent" ? "ico--absent" : "ico--unknown")
                  }
                  aria-hidden="true"
                >
                  {c.status === "present" ? <TriangleAlert size={14} /> : c.status === "absent" ? <Check size={14} /> : <CircleHelp size={14} />}
                </span>
                <span>
                  {c.label_local}
                  <small>{t(lang, c.status === "present" ? "stPresent" : c.status === "absent" ? "stAbsent" : "stUnknown")}</small>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="details__group">
        <h3>{t(lang, "reasonTitle")}</h3>
        <p className="why-text">{tr.reasoning_local}</p>
        <p className="meta-line">
          {tr.decision.rule} | {Math.round((tr.decision.confidence ?? 0) * 100)}% | {tr.timing_ms} ms
        </p>
        {top && (
          <p className="meta-line" title={tr.model?.version ? `model ${tr.model.version}` : undefined}>
            {t(lang, "modelLine", { x: topKey ? t(lang, topKey) : top.cls.replace(/_/g, " "), pct: top.pct })}
          </p>
        )}
      </div>
    </div>
  );
}
