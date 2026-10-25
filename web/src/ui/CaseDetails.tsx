import { useState } from "react";
import { Check, ChevronDown, CircleHelp, ShieldAlert, TriangleAlert } from "lucide-react";
import type { Lang, TriageResponse } from "../types";
import { t } from "../i18n";
import { fmtDays, structuredChips, titleCase } from "../lib";

// "What we understood / what we checked / safety checks": shown in the desktop side
// panel and inline under a decision on smaller screens. The decision and its reason
// are on the card above, so they are not repeated here.
export default function CaseDetails({ res, lang }: { res: TriageResponse; lang: Lang }) {
  const [showPassed, setShowPassed] = useState(false);
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
  // safety checks: the ones that changed or guarded the answer are shown; the ones
  // that passed fold into one row that opens on tap
  const guards = (tr.guardrails ?? []).filter((g) => g && (g.label_local || g.label));
  const fired = guards.filter((g) => g.status === "fired");
  const passed = guards.filter((g) => g.status !== "fired");

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
            {fired.map((g) => (
              <li key={g.id} className="is-fired">
                <span className="ico ico--fired" aria-hidden="true">
                  <ShieldAlert size={14} />
                </span>
                <span>
                  <strong>{g.label_local || g.label}</strong>
                  <small>{g.note_local || t(lang, "guardFired")}</small>
                </span>
              </li>
            ))}
            {passed.length > 0 && (
              <li className="is-pass">
                <button
                  type="button"
                  className="linkish checks__more"
                  aria-expanded={showPassed}
                  onClick={() => setShowPassed((o) => !o)}
                >
                  <span className="ico ico--absent" aria-hidden="true">
                    <Check size={13} />
                  </span>
                  {/* TODO(i18n): add guardsPassed = "{n} jaanch theek rahin" / "{n} जाँच ठीक रहीं" / "{n} checks passed" */}
                  {passed.length} {t(lang, "guardPassed")}
                  <ChevronDown size={16} aria-hidden="true" />
                </button>
              </li>
            )}
            {showPassed &&
              passed.map((g) => (
                <li key={g.id} className="is-pass">
                  <span className="ico ico--absent" aria-hidden="true">
                    <Check size={13} />
                  </span>
                  <span>
                    {g.label_local || g.label}
                    <span className="sr-only">: {t(lang, "guardPassed")}</span>
                  </span>
                </li>
              ))}
          </ul>
        </div>
      )}
    </div>
  );
}
