import { useState } from "react";
import { ChevronDown, Clock, Languages, MapPin, Star, Video } from "lucide-react";
import type { Lang, TraceCaregiver } from "../types";
import { t, type Key } from "../i18n";
import { avatarColor, initials, roleKey } from "../lib";

const FEATURES: Array<[keyof NonNullable<TraceCaregiver["features"]>, Key]> = [
  ["skill", "fSkill"],
  ["time", "fTime"],
  ["distance", "fDistance"],
  ["language", "fLanguage"],
  ["rating", "fRating"],
];

interface Props {
  cg: TraceCaregiver;
  best: boolean;
  tele: boolean;
  lang: Lang;
  onBook: () => void;
}

export default function CaregiverCard({ cg, best, tele, lang, onBook }: Props) {
  const [open, setOpen] = useState(false);
  const pct = Math.round(cg.score * 100);
  const feats = FEATURES.filter(([k]) => cg.features?.[k] != null && !(tele && k === "distance"));

  return (
    <article className={best ? "carer carer--best" : "carer"} aria-label={cg.name}>
      <div className="avatar" style={{ background: avatarColor(cg.caregiver_id) }} aria-hidden="true">
        {initials(cg.name)}
      </div>
      <div className="carer__main">
        <div className="carer__name">
          <strong>{cg.name}</strong>
          <span className="carer__role">{t(lang, roleKey(cg.role))}</span>
          {best && <span className="best-tag">{t(lang, "bestMatch")}</span>}
        </div>
        <div className="carer__facts">
          {cg.rating != null && (
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
            cg.distance_km != null && (
              <span>
                <MapPin size={15} aria-hidden="true" />
                {t(lang, "kmAway", { d: cg.distance_km.toFixed(1) })}
              </span>
            )
          )}
          {cg.languages.length > 0 && (
            <span>
              <Languages size={15} aria-hidden="true" />
              {cg.languages.join(", ")}
            </span>
          )}
        </div>
        <p className="carer__reason">{cg.reason_local}</p>
        {feats.length > 0 && (
          <button type="button" className="linkish" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
            {t(lang, "matchHow")}
            <ChevronDown size={16} aria-hidden="true" />
          </button>
        )}
        {open && (
          <div className="bars">
            {feats.map(([k, label]) => {
              const v = Math.round((cg.features?.[k] ?? 0) * 100);
              return (
                <FeatureRow key={k} label={t(lang, label)} value={v} />
              );
            })}
          </div>
        )}
      </div>
      <div className="carer__side">
        <div className="score" aria-label={`${pct}% ${t(lang, "match")}`}>
          {pct}%<small>{t(lang, "match")}</small>
        </div>
        <button type="button" className="btn btn--primary" onClick={onBook}>
          {t(lang, "book")}
        </button>
      </div>
    </article>
  );
}

function FeatureRow({ label, value }: { label: string; value: number }) {
  return (
    <>
      <span>{label}</span>
      <span className="bars__track" aria-hidden="true">
        <span className="bars__fill" style={{ width: `${value}%`, display: "block" }} />
      </span>
      <span>{value}%</span>
    </>
  );
}
