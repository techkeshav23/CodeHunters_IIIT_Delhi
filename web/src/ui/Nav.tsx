import { CalendarCheck, Info, Phone, Settings, Siren, Stethoscope } from "lucide-react";
import type { Lang } from "../types";
import { LANG_LABEL, LANG_SHORT, t, type Key } from "../i18n";
import type { View } from "../lib";
import { Brand, BrandMark } from "./Brand";
import { useHeightVar } from "../useHeightVar";

export type Backend = "ok" | "bad" | "wait" | "mock";

const ITEMS: Array<{ id: View; icon: typeof Stethoscope; label: Key; short: Key }> = [
  { id: "check", icon: Stethoscope, label: "navCheck", short: "navCheck" },
  { id: "bookings", icon: CalendarCheck, label: "navBookings", short: "navBookings" },
  { id: "sos", icon: Siren, label: "navSos", short: "navSosShort" },
  { id: "how", icon: Info, label: "navHow", short: "navHowShort" },
  { id: "settings", icon: Settings, label: "navSettings", short: "navSettings" },
];
const LANGS: Lang[] = ["hi", "hinglish", "en"];

interface NavProps {
  view: View;
  lang: Lang;
  onView: (v: View) => void;
  onLang: (l: Lang) => void;
  backend: Backend;
  bookingsCount: number;
}

export function Sidebar({ view, lang, onView, onLang, backend, bookingsCount }: NavProps) {
  const statusKey: Key = backend === "ok" ? "serviceOk" : backend === "bad" ? "serviceBad" : backend === "mock" ? "serviceMock" : "serviceWait";
  return (
    <aside className="sidebar" aria-label="Raahat">
      <Brand onClick={() => onView("check")} />
      <nav className="nav">
        {ITEMS.map((it) => (
          <button
            key={it.id}
            type="button"
            className={it.id === "sos" ? "nav__item nav__item--sos" : "nav__item"}
            aria-current={view === it.id ? "page" : undefined}
            onClick={() => onView(it.id)}
            title={t(lang, it.label)}
          >
            <it.icon size={21} aria-hidden="true" />
            <span>
              {t(lang, it.label)}
              {it.id === "bookings" && bookingsCount > 0 ? ` (${bookingsCount})` : ""}
            </span>
          </button>
        ))}
      </nav>
      <div className="sidebar__foot">
        <a className="sos-card" href="tel:112" aria-label={t(lang, "sosNow")}>
          <span className="sos-card__icon" aria-hidden="true">
            <Phone size={20} />
          </span>
          <strong>{t(lang, "sosCardTitle")}</strong>
          <small>{t(lang, "sosCardSub")}</small>
        </a>
        <div className="langs" role="group" aria-label={t(lang, "setLang")}>
          {LANGS.map((l) => (
            <button key={l} type="button" aria-pressed={lang === l} onClick={() => onLang(l)} lang={l === "hi" ? "hi" : undefined}>
              {LANG_LABEL[l]}
            </button>
          ))}
        </div>
        <div className={`status status--${backend === "mock" ? "wait" : backend}`} title={t(lang, statusKey)}>
          <span className="status__dot" aria-hidden="true" />
          <span className="status__text">{t(lang, statusKey)}</span>
        </div>
      </div>
    </aside>
  );
}

export function TopBar({ lang, onLang, onView }: Pick<NavProps, "lang" | "onLang" | "onView">) {
  const next = LANGS[(LANGS.indexOf(lang) + 1) % LANGS.length];
  // the chat bar sticks just under this bar on phones (0 when hidden on desktop)
  const heightRef = useHeightVar("--topbar-h");
  return (
    <header className="topbar" ref={heightRef}>
      <button type="button" className="brand" onClick={() => onView("check")} style={{ border: 0, background: "none", padding: 0 }}>
        <BrandMark size={32} />
        <span className="brand__name">
          <span>Raahat</span>
        </span>
      </button>
      <div className="topbar__right">
        <button
          type="button"
          className="lang-pill"
          onClick={() => onLang(next)}
          aria-label={`${t(lang, "setLang")}: ${LANG_LABEL[lang]}`}
        >
          {LANG_SHORT[lang]}
        </button>
        <a className="call-pill" href="tel:112" aria-label={t(lang, "sosNow")}>
          <Phone size={16} aria-hidden="true" />
          112
        </a>
      </div>
    </header>
  );
}

export function BottomNav({ view, lang, onView }: Pick<NavProps, "view" | "lang" | "onView">) {
  return (
    <nav className="bottomnav" aria-label="Raahat">
      {ITEMS.map((it) => (
        <button
          key={it.id}
          type="button"
          className={it.id === "sos" ? "tab tab--sos" : "tab"}
          aria-current={view === it.id ? "page" : undefined}
          onClick={() => onView(it.id)}
        >
          {it.id === "sos" ? (
            <span className="tab__orb">
              <it.icon size={26} aria-hidden="true" />
            </span>
          ) : (
            <it.icon size={23} aria-hidden="true" />
          )}
          <span>{t(lang, it.short)}</span>
        </button>
      ))}
    </nav>
  );
}
