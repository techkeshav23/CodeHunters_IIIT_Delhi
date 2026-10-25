import { useEffect, useState } from "react";
import {
  Bandage,
  BriefcaseMedical,
  CalendarCheck,
  Check,
  Copy,
  ExternalLink,
  Mic,
  Pill,
  Phone,
  ShieldCheck,
  Stethoscope,
  Thermometer,
  TriangleAlert,
  Wind,
} from "lucide-react";
import type { Lang, TriageRequest, TriageResponse } from "../types";
import { t, LANG_LABEL, type Key } from "../i18n";
import { API_BASE, labels, type LabelsResponse } from "../api";
import { avatarColor, initials, roleKey, type SavedBooking } from "../lib";

/* ---------------- start screen (empty consult) ---------------- */

const PICKS: Array<{ icon: typeof Thermometer; label: Key; seed: Key }> = [
  { icon: Thermometer, label: "pickFever", seed: "seedFever" },
  { icon: Wind, label: "pickCough", seed: "seedCough" },
  { icon: Pill, label: "pickStomach", seed: "seedStomach" },
  { icon: Bandage, label: "pickInjury", seed: "seedInjury" },
  { icon: BriefcaseMedical, label: "pickInjection", seed: "seedInjection" },
  { icon: Stethoscope, label: "pickDoctor", seed: "seedDoctor" },
];

// Voice first: the one big action is the mic (it starts dictation in the composer below);
// quick picks and examples are small and secondary. One tap on either starts the check.
export function Start({ lang, onExample, onMic, micSupported }: {
  lang: Lang;
  onExample: (text: string) => void;
  onMic: () => void;
  micSupported: boolean;
}) {
  return (
    <div className="start">
      <div className="start__hello">
        <h1 lang={lang === "hi" ? "hi" : undefined}>{t(lang, "hello")}</h1>
        <p>{t(lang, "helloSub")}</p>
      </div>
      <div className="voice-hero">
        <button type="button" className="voice-hero__mic" onClick={onMic} disabled={!micSupported}
          aria-label={t(lang, "micStart")}>
          <Mic size={44} aria-hidden="true" />
        </button>
        <span className="voice-hero__label">{micSupported ? t(lang, "micStart") : t(lang, "voiceOff")}</span>
      </div>
      <div className="picks">
        <span className="picks__label">{t(lang, "quickPicks")}</span>
        <div className="picks__row">
          {PICKS.map((p) => (
            <button key={p.label} type="button" className="pick" onClick={() => onExample(t(lang, p.seed))}>
              <p.icon size={18} aria-hidden="true" />
              {t(lang, p.label)}
            </button>
          ))}
        </div>
      </div>
      <div className="picks">
        <span className="picks__label">{t(lang, "tryExample")}</span>
        <div className="examples">
          {(["ex1", "ex2", "ex3"] as Key[]).map((k) => (
            <button key={k} type="button" className="example" onClick={() => onExample(t(lang, k))}>
              “{t(lang, k)}”
            </button>
          ))}
        </div>
      </div>
      <p className="notice">{t(lang, "disclaimer")}</p>
    </div>
  );
}

/* ---------------- bookings ---------------- */

export function BookingsView({ lang, bookings, onStart }: { lang: Lang; bookings: SavedBooking[]; onStart: () => void }) {
  return (
    <div className="view">
      <div className="page-head">
        <h1>{t(lang, "bookingsTitle")}</h1>
        <p>{t(lang, "bookingsSub")}</p>
      </div>
      {bookings.length === 0 ? (
        <div className="empty">
          <CalendarCheck size={36} aria-hidden="true" color="var(--brand)" />
          <p>{t(lang, "bookingsEmpty")}</p>
          <button type="button" className="btn btn--primary" onClick={onStart}>
            {t(lang, "startCheck")}
          </button>
        </div>
      ) : (
        <div className="thread">
          {bookings.map((b) => (
            <article key={b.booking_id} className="booking-row">
              <div className="avatar" style={{ background: avatarColor(b.caregiver_id) }} aria-hidden="true">
                {initials(b.caregiver_name)}
              </div>
              <div className="booking-row__main">
                <strong>{b.caregiver_name}</strong>
                <span>{[b.role ? t(lang, roleKey(b.role)) : null, b.care_label].filter(Boolean).join(", ")}</span>
                <span>
                  {b.slot_label ?? ""} | {t(lang, "bookingId")}: {b.booking_id}
                </span>
              </div>
              <span className="chip chip--brand">
                <Check size={14} aria-hidden="true" />
                {t(lang, "confirmed")}
              </span>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------------- emergency info ---------------- */

// /v1/labels lists our own flag ids (breathing_difficulty, chest_pain, ...), not the
// organisers' ids the triage API now returns in red_flags. These two are not
// signs a family can watch for, so they stay off the list.
const HIDE_FLAGS = new Set(["possible_emergency", "emergency_requested"]);

export function SosView({ lang }: { lang: Lang }) {
  const [data, setData] = useState<LabelsResponse | null>(null);
  useEffect(() => {
    let alive = true;
    labels().then((d) => alive && setData(d));
    return () => {
      alive = false;
    };
  }, []);
  // several flags share one helpline (e.g. 14416), so list each number once
  const numbers = [...(data?.emergency_numbers ?? []), ...Object.values(data?.helplines ?? {})].filter(
    (n, i, all) => all.findIndex((m) => m.number === n.number) === i,
  );
  const flagLabel = (f: LabelsResponse["red_flags"][number]) =>
    (lang === "hi" ? f.label_hi : lang === "hinglish" ? f.label_hinglish : f.label) || f.label;
  return (
    <div className="view">
      <div className="page-head">
        <h1>{t(lang, "sosPageTitle")}</h1>
        <p>{t(lang, "sosPageSub")}</p>
      </div>
      <div className="numbers">
        {numbers.map((n, i) => (
          <a key={n.number} className={i === 0 ? "number number--main" : "number"} href={`tel:${n.number.replace(/[^0-9]/g, "")}`}>
            <span>
              <strong>{n.number}</strong>
              <br />
              <span>{lang === "en" ? n.label : n.label_hi}</span>
            </span>
            <Phone size={24} aria-hidden="true" />
          </a>
        ))}
      </div>
      {data && data.red_flags.length > 0 && (
        <section className="panel">
          <h2>{t(lang, "sosSignsTitle")}</h2>
          <ul className="signs">
            {data.red_flags
              .filter((f) => !HIDE_FLAGS.has(f.id) && !!flagLabel(f))
              .map((f) => (
                <li key={f.id} lang={lang === "hi" ? "hi" : undefined}>
                  <TriangleAlert size={16} aria-hidden="true" />
                  {flagLabel(f)}
                </li>
              ))}
          </ul>
        </section>
      )}
    </div>
  );
}

/* ---------------- how it works ---------------- */

export function HowView({ lang, last }: { lang: Lang; last: { req: TriageRequest; res: TriageResponse } | null }) {
  const steps: Array<[Key, Key]> = [
    ["step1", "step1t"],
    ["step2", "step2t"],
    ["step3", "step3t"],
    ["step4", "step4t"],
    ["step5", "step5t"],
    ["step6", "step6t"],
  ];
  return (
    <div className="view view--wide">
      <div className="page-head">
        <h1>{t(lang, "howTitle")}</h1>
        <p>{t(lang, "howSub")}</p>
      </div>
      <ol className="steps">
        {steps.map(([a, b]) => (
          <li key={a}>
            <strong>{t(lang, a)}</strong>
            <span>{t(lang, b)}</span>
          </li>
        ))}
      </ol>
      <section className="panel">
        <h2>{t(lang, "rulesTitle")}</h2>
        <ul className="rules">
          {(["rule1", "rule2", "rule3", "rule4"] as Key[]).map((k) => (
            <li key={k}>
              <ShieldCheck size={18} aria-hidden="true" />
              {t(lang, k)}
            </li>
          ))}
        </ul>
      </section>
      <section className="panel">
        <h2>{t(lang, "testedTitle")}</h2>
        <div className="stats">
          <div className="stat">
            <strong>93%</strong>
            <span>{t(lang, "stat1")}</span>
          </div>
          <div className="stat">
            <strong>209/209</strong>
            <span>{t(lang, "stat2")}</span>
          </div>
          <div className="stat">
            <strong>&lt; 0.1 s</strong>
            <span>{t(lang, "stat3")}</span>
          </div>
        </div>
      </section>
      <ApiPanel lang={lang} last={last} />
    </div>
  );
}

function ApiPanel({ lang, last }: { lang: Lang; last: { req: TriageRequest; res: TriageResponse } | null }) {
  const [copied, setCopied] = useState<string | null>(null);
  const copy = async (what: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(what);
      window.setTimeout(() => setCopied(null), 1500);
    } catch {
      /* clipboard blocked; the text is selectable */
    }
  };
  const req = last ? JSON.stringify(last.req, null, 2) : "";
  // the six schema fields first; the trace is for the web app
  const res = last
    ? JSON.stringify(
        {
          follow_up_question: last.res.follow_up_question,
          care_type: last.res.care_type,
          urgency: last.res.urgency,
          red_flags: last.res.red_flags,
          reasoning: last.res.reasoning,
          matched_caregivers: last.res.matched_caregivers,
        },
        null,
        2,
      )
    : "";
  return (
    <section className="panel">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>{t(lang, "apiTitle")}</h2>
        <a className="btn btn--ghost" href={`${API_BASE}/docs`} target="_blank" rel="noreferrer">
          <ExternalLink size={16} aria-hidden="true" />
          {t(lang, "apiDocs")}
        </a>
      </div>
      <p style={{ color: "var(--ink-2)" }}>{t(lang, "apiSub")}</p>
      {!last ? (
        <p className="case-panel__empty">{t(lang, "apiEmpty")}</p>
      ) : (
        <>
          <span className="chip chip--brand" style={{ width: "fit-content" }}>
            {t(lang, "answeredIn", { ms: last.res.trace.timing_ms })}
          </span>
          {[
            ["request", req],
            ["response", res],
          ].map(([k, text]) => (
            <div key={k} className="details__group">
              <div className="row" style={{ justifyContent: "space-between" }}>
                <h3 style={{ fontSize: "1rem" }}>POST /v1/triage: {t(lang, k as Key)}</h3>
                <button type="button" className="btn btn--quiet" onClick={() => copy(k, text)}>
                  {copied === k ? <Check size={16} aria-hidden="true" /> : <Copy size={16} aria-hidden="true" />}
                  {copied === k ? t(lang, "copied") : t(lang, "copy")}
                </button>
              </div>
              <pre className="code">{text}</pre>
            </div>
          ))}
        </>
      )}
    </section>
  );
}

/* ---------------- settings ---------------- */

export type Theme = "auto" | "light" | "dark";

interface SettingsProps {
  lang: Lang;
  onLang: (l: Lang) => void;
  large: boolean;
  onLarge: (v: boolean) => void;
  autoRead: boolean;
  onAutoRead: (v: boolean) => void;
  theme: Theme;
  onTheme: (v: Theme) => void;
  locationLabel: string;
  locating: boolean;
  onUseLocation: () => void;
}

export function SettingsView(p: SettingsProps) {
  const L = p.lang;
  return (
    <div className="view">
      <div className="page-head">
        <h1>{t(L, "settingsTitle")}</h1>
      </div>
      <section className="panel">
        <Setting title={t(L, "setLang")} sub={t(L, "setLangSub")}>
          <div className="segmented" role="group" aria-label={t(L, "setLang")}>
            {(["hi", "hinglish", "en"] as Lang[]).map((l) => (
              <button key={l} type="button" aria-pressed={L === l} onClick={() => p.onLang(l)}>
                {LANG_LABEL[l]}
              </button>
            ))}
          </div>
        </Setting>
        <Setting title={t(L, "setText")} sub={t(L, "setTextSub")}>
          <div className="segmented" role="group" aria-label={t(L, "setText")}>
            <button type="button" aria-pressed={!p.large} onClick={() => p.onLarge(false)}>
              {t(L, "textNormal")}
            </button>
            <button type="button" aria-pressed={p.large} onClick={() => p.onLarge(true)} style={{ fontSize: "1.1em" }}>
              {t(L, "textLarge")}
            </button>
          </div>
        </Setting>
        <Setting title={t(L, "setRead")} sub={t(L, "setReadSub")}>
          <div className="segmented" role="group" aria-label={t(L, "setRead")}>
            <button type="button" aria-pressed={p.autoRead} onClick={() => p.onAutoRead(true)}>
              {t(L, "on")}
            </button>
            <button type="button" aria-pressed={!p.autoRead} onClick={() => p.onAutoRead(false)}>
              {t(L, "off")}
            </button>
          </div>
        </Setting>
        <Setting title={t(L, "setTheme")} sub="">
          <div className="segmented" role="group" aria-label={t(L, "setTheme")}>
            {(["auto", "light", "dark"] as Theme[]).map((th) => (
              <button key={th} type="button" aria-pressed={p.theme === th} onClick={() => p.onTheme(th)}>
                {t(L, th === "auto" ? "themeAuto" : th === "light" ? "themeLight" : "themeDark")}
              </button>
            ))}
          </div>
        </Setting>
        <Setting title={t(L, "setLoc")} sub={`${t(L, "setLocSub")} ${p.locationLabel}.`}>
          <button type="button" className="btn btn--ghost" onClick={p.onUseLocation} disabled={p.locating}>
            {p.locating ? t(L, "locFinding") : t(L, "locUse")}
          </button>
        </Setting>
      </section>
      <p className="notice">{t(L, "disclaimer")}</p>
    </div>
  );
}

function Setting({ title, sub, children }: { title: string; sub: string; children: React.ReactNode }) {
  return (
    <div className="setting">
      <div className="setting__text">
        <strong>{title}</strong>
        {sub && <span>{sub}</span>}
      </div>
      {children}
    </div>
  );
}
