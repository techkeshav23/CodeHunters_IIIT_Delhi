import { Compass, Phone } from "lucide-react";
import type { Lang } from "../types";
import { LANGS, LANG_LABELS, t } from "../i18n";

export type BackendState = "ok" | "bad" | "wait";

interface Props {
  lang: Lang;
  onLang: (l: Lang) => void;
  backend: BackendState;
  usingMocks: boolean;
}

export default function Header({ lang, onLang, backend, usingMocks }: Props) {
  const statusText = usingMocks
    ? t(lang, "usingMocks")
    : backend === "ok"
      ? t(lang, "backendOnline")
      : backend === "bad"
        ? t(lang, "backendOffline")
        : "...";

  const ledClass = usingMocks
    ? "status-dot__led--ok"
    : backend === "ok"
      ? "status-dot__led--ok"
      : backend === "bad"
        ? "status-dot__led--bad"
        : "status-dot__led--wait";

  return (
    <header className="header">
      <div className="header__brand">
        <Compass size={24} aria-hidden="true" />
        <span>{t(lang, "appName")}</span>
      </div>

      <span className="status-dot" title={statusText}>
        <span className={`status-dot__led ${ledClass}`} aria-hidden="true" />
        <span className="sr-only">{statusText}</span>
      </span>

      <div
        className="lang-switch"
        role="group"
        aria-label={t(lang, "langSwitch")}
      >
        {LANGS.map((l) => (
          <button
            key={l}
            type="button"
            aria-pressed={l === lang}
            onClick={() => onLang(l)}
            lang={l === "hi" ? "hi" : undefined}
          >
            {LANG_LABELS[l]}
          </button>
        ))}
      </div>

      <a
        className="btn-112"
        href="tel:112"
        aria-label={t(lang, "call112")}
      >
        <Phone size={16} aria-hidden="true" />
        112
      </a>
    </header>
  );
}
