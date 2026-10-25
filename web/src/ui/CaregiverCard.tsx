import { useState } from "react";
import { ChevronDown, Clock, Languages, MapPin, Star, Video } from "lucide-react";
import type { Lang, TraceCaregiver } from "../types";
import { t, type Key } from "../i18n";
import { avatarColor, initials, roleKey } from "../lib";

// Feature keys change with the ranker; known ones get a label, anything else
// is shown by its own name.
const FEATURE_LABEL: Record<string, Key> = {
  language: "fLanguage",
  languages: "fLanguage",
  distance: "fDistance",
  proximity: "fDistance",
  skill: "fSkill",
  skills: "fSkill",
  skill_match: "fSkill",
  rating: "fRating",
  time: "fTime",
  availability: "fTime",
  slot: "fTime",
};
const DISTANCE_KEYS = new Set(["distance", "proximity"]);

function featureLabel(lang: Lang, key: string): string {
  const k = FEATURE_LABEL[key.toLowerCase()];
  return k ? t(lang, k) : key.replace(/_/g, " ");
}

function clampPct(v: number): number {
  return Math.round(Math.min(1, Math.max(0, v)) * 100);
}

interface Props {
  cg: TraceCaregiver;
  best: boolean;
  // video only: a teleconsultation, or a doctor (the roster's doctors are virtual)
  tele: boolean;
  lang: Lang;
  // left out when booking is off (a later emergency in the same chat)
  onBook?: () => void;
}

export default function CaregiverCard({ cg, best, tele, lang, onBook }: Props) {
  const [open, setOpen] = useState(false);
  const name = cg.name || cg.caregiver_id;
  const score = typeof cg.score === "number" && Number.isFinite(cg.score) ? cg.score : null;
  const pct = score == null ? null : Math.round(score <= 1 ? score * 100 : score);
  const feats = Object.entries(cg.features ?? {})
    .filter((e): e is [string, number] => typeof e[1] === "number" && Number.isFinite(e[1]))
    .filter(([k]) => !(tele && DISTANCE_KEYS.has(k.toLowerCase())));
  const languages = Array.isArray(cg.languages) ? cg.languages : [];
  const reason = cg.reason_local || cg.reason;

  return (
    <article className={best ? "carer carer--best" : "carer"} aria-label={name}>
      <div className="avatar" style={{ background: avatarColor(cg.caregiver_id) }} aria-hidden="true">
        {initials(name)}
      </div>
      <div className="carer__main">
        <div className="carer__name">
          <strong>{name}</strong>
          {cg.role && <span className="carer__role">{t(lang, roleKey(cg.role))}</span>}
          {best && <span className="best-tag">{t(lang, "bestMatch")}</span>}
        </div>
        <div className="carer__facts">
          {typeof cg.rating === "number" && (
            <span>
              <Star size={15} fill="var(--haldi)" stroke="var(--haldi)" aria-hidden="true" />
              {cg.rating.toFixed(1)}
            </span>
          )}
          {cg.next_slot_label_local && (
            <span>
              <Clock size={15} aria-hidden="true" />
              {cg.next_slot_label_local}
            </span>
          )}
          {tele ? (
            <span>
              <Video size={15} aria-hidden="true" />
              {t(lang, "videoCall")}
            </span>
          ) : (
            typeof cg.distance_km === "number" && (
              <span>
                <MapPin size={15} aria-hidden="true" />
                {t(lang, "kmAway", { d: cg.distance_km.toFixed(1) })}
              </span>
            )
          )}
          {languages.length > 0 && (
            <span>
              <Languages size={15} aria-hidden="true" />
              {languages.join(", ")}
            </span>
          )}
        </div>
        {reason && <p className="carer__reason">{reason}</p>}
        {feats.length > 0 && (
          <button type="button" className="linkish" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
            {t(lang, "matchHow")}
            <ChevronDown size={16} aria-hidden="true" />
          </button>
        )}
        {open && (
          <div className="bars">
            {feats.map(([k, v]) =>
              // the rating feature is scaled over the roster (3.9 stars reads as 8%): show the stars
              k.toLowerCase() === "rating" && typeof cg.rating === "number" ? (
                <FeatureRow key={k} label={featureLabel(lang, k)} value={clampPct(cg.rating / 5)} text={`${cg.rating.toFixed(1)}★`} />
              ) : (
                <FeatureRow key={k} label={featureLabel(lang, k)} value={clampPct(v)} />
              ),
            )}
          </div>
        )}
      </div>
      <div className="carer__side">
        {pct != null && (
          <div className="score" aria-label={`${pct}% ${t(lang, "match")}`}>
            {pct}%<small>{t(lang, "match")}</small>
          </div>
        )}
        <button type="button" className="btn btn--primary" onClick={onBook} disabled={!onBook}>
          {t(lang, "book")}
        </button>
      </div>
    </article>
  );
}

function FeatureRow({ label, value, text }: { label: string; value: number; text?: string }) {
  return (
    <>
      <span>{label}</span>
      <span className="bars__track" aria-hidden="true">
        <span className="bars__fill" style={{ width: `${value}%`, display: "block" }} />
      </span>
      <span>{text ?? `${value}%`}</span>
    </>
  );
}
