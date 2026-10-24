import { Check, CircleHelp, ShieldAlert, TriangleAlert } from "lucide-react";
import type { Lang, TriageResponse } from "../types";
import { t } from "../i18n";
import { decisionModelClass, fmtDays, modelClassKey, structuredChips, titleCase } from "../lib";

// "What we understood / what we checked / safety checks / why": shown in the desktop
// side panel and inline under a decision on smaller screens.
export default function CaseDetails({ res, lang }: { res: TriageResponse; lang: Lang }) {
  const tr = res.trace;
  const u = tr.understood;
  // the model's structured symptoms when the API sends them, else what the rules understood
  const structured = structuredChips(tr, lang);
  const chips: Array<{ text: string; warm: boolean }> = [];
  if (structured) {
    for (const c of structured) chips.push({ text: c.text, warm: c.kind === "who" });
    const dur = structured.some((c) => c.kind === "duration") ? null : fmtDays(u?.duration_days ?? null, lang);
    if (dur) chips.push({ text: dur, warm: false });
  } else if (u) {
    if (u.patient?.relation_label) chips.push({ text: titleCase(u.patient.relation_label), warm: true });
    if (u.patient?.age_years != null && u.patient.age_years >= 1) chips.push({ text: `${Math.round(u.patient.age_years)}y`, warm: false });
    for (const s of u.symptoms ?? []) chips.push({ text: s.label_local, warm: false });
    for (const s of u.services ?? []) chips.push({ text: s.label_local, warm: false });
    const dur = fmtDays(u.duration_days, lang);
    if (dur) chips.push({ text: dur, warm: false });
  }
  const checks = tr.checks ?? [];
  // safety checks: the ones that changed or guarded the answer first
  const guards = (tr.guardrails ?? [])
    .filter((g) => g && (g.label_local || g.label))
    .sort((a, b) => Number(b.status === "fired") - Number(a.status === "fired"));
  // the learned model's support for the decision shown, only when the model is loaded
  const top = decisionModelClass(res);
  const topKey = top ? modelClassKey(top.cls) : null;
  const modelName = tr.model?.name ? tr.model.name : t(lang, "modelWord");
  const modelTitle = [tr.model?.version ? `model ${tr.model.version}` : null, tr.model?.latency_ms != null ? `${tr.model.latency_ms} ms` : null]
    .filter(Boolean)
    .join(" · ");
  const meta = [
    tr.decision.rule,
    tr.decision.source,
    `${Math.round((tr.decision.confidence ?? 0) * 100)}%`,
    `${tr.timing_ms} ms`,
  ].filter(Boolean);

  return (
    <div className="details">
      <div className="details__group">
        <h3>{t(lang, "understood")}</h3>
        <div className="details__chips">
          {chips.length ? (
            chips.map((c, i) => (
              <span key={i} className={c.warm ? "chip chip--haldi" : "chip"}>
                {c.text}
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

      {guards.length > 0 && (
        <div className="details__group">
          <h3>{t(lang, "safetyChecks")}</h3>
          <ul className="checks">
            {guards.map((g) => {
              const fired = g.status === "fired";
              return (
                <li key={g.id} className={fired ? "is-fired" : "is-pass"}>
                  <span className={fired ? "ico ico--fired" : "ico ico--absent"} aria-hidden="true">
                    {fired ? <ShieldAlert size={14} /> : <Check size={13} />}
                  </span>
                  {fired ? (
                    <span>
                      <strong>{g.label_local || g.label}</strong>
                      <small>{g.note_local || t(lang, "guardFired")}</small>
                    </span>
                  ) : (
                    <span>
                      {g.label_local || g.label}
                      <span className="sr-only">: {t(lang, "guardPassed")}</span>
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <div className="details__group">
        <h3>{t(lang, "reasonTitle")}</h3>
        <p className="why-text">{tr.reasoning_local}</p>
        <p className="meta-line">{meta.join(" | ")}</p>
        {top && (
          <p className="meta-line" title={modelTitle || undefined}>
            {t(lang, "modelLine", { m: modelName, x: topKey ? t(lang, topKey) : top.cls.replace(/_/g, " "), pct: top.pct })}
          </p>
        )}
      </div>
    </div>
  );
}
