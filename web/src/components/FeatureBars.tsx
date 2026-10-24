import { useState } from "react";
import { ChevronDown, ChevronUp, BarChart3 } from "lucide-react";
import type { Lang, MatchFeatures } from "../types";
import { t, type StringKey } from "../i18n";

// The five 0-1 sub-scores behind a caregiver match (backend `features`),
// shown as small labelled bars inside each card's "why this match" (spec
// explainability extra). Collapsed by default to keep cards compact.
const ROWS: Array<{ key: keyof MatchFeatures; label: StringKey }> = [
  { key: "skill", label: "featSkill" },
  { key: "time", label: "featTime" },
  { key: "distance", label: "featDistance" },
  { key: "language", label: "featLanguage" },
  { key: "rating", label: "featRating" },
];

interface Props {
  features: MatchFeatures;
  lang: Lang;
}

export default function FeatureBars({ features, lang }: Props) {
  const [open, setOpen] = useState(false);
  const rows = ROWS.filter((r) => typeof features[r.key] === "number");
  if (rows.length === 0) return null;

  return (
    <div className="feat">
      <button
        type="button"
        className="feat__toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <BarChart3 size={15} aria-hidden="true" />
        <span style={{ marginRight: "auto" }}>{t(lang, "matchWhy")}</span>
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>

      {open && (
        <ul className="feat__list">
          {rows.map((r) => {
            const v = Math.max(0, Math.min(1, features[r.key] as number));
            const pct = Math.round(v * 100);
            const label = t(lang, r.label);
            return (
              <li className="feat__row" key={r.key}>
                <span className="feat__label">{label}</span>
                <span
                  className="feat__track"
                  role="meter"
                  aria-label={`${label}: ${pct}%`}
                  aria-valuenow={pct}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <span className="feat__fill" style={{ width: `${pct}%` }} />
                </span>
                <span className="feat__pct">{pct}%</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
