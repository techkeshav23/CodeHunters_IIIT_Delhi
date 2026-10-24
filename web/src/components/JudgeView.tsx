import { useState } from "react";
import { ChevronDown, ChevronUp, Copy, Check, Code2 } from "lucide-react";
import type { Lang } from "../types";
import { t } from "../i18n";

interface Props {
  request: unknown;
  response: unknown;
  timingMs?: number;
  lang: Lang;
}

function JsonBlock({
  title,
  value,
  copyLabel,
  copiedLabel,
}: {
  title: string;
  value: unknown;
  copyLabel: string;
  copiedLabel: string;
}) {
  const [copied, setCopied] = useState(false);
  const text = JSON.stringify(value, null, 2);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard may be blocked; ignore */
    }
  };

  return (
    <div>
      <div className="judge__block-title">
        <span>{title}</span>
        <button type="button" className="copy-btn" onClick={copy}>
          {copied ? (
            <>
              <Check size={12} /> {copiedLabel}
            </>
          ) : (
            <>
              <Copy size={12} /> {copyLabel}
            </>
          )}
        </button>
      </div>
      <pre>{text}</pre>
    </div>
  );
}

// Collapsible "API request / response" panel (spec section 4), collapsed by
// default. Helps judges see the exact contract and timing.
export default function JudgeView({ request, response, timingMs, lang }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <section className="judge">
      <button
        type="button"
        className="judge__head"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Code2 size={16} aria-hidden="true" />
        <span style={{ marginRight: "auto" }}>{t(lang, "judgeView")}</span>
        {open ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
      </button>

      {open && (
        <div className="judge__body">
          {typeof timingMs === "number" && (
            <div className="judge__timing">
              {t(lang, "timing")}: {timingMs} ms
            </div>
          )}
          <JsonBlock
            title={t(lang, "request")}
            value={request}
            copyLabel={t(lang, "copy")}
            copiedLabel={t(lang, "copied")}
          />
          <JsonBlock
            title={t(lang, "response")}
            value={response}
            copyLabel={t(lang, "copy")}
            copiedLabel={t(lang, "copied")}
          />
        </div>
      )}
    </section>
  );
}
