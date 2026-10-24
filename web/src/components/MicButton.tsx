import { Mic, Loader2, Square } from "lucide-react";
import type { Lang } from "../types";
import { t } from "../i18n";

export type MicState = "idle" | "listening" | "processing";

interface Props {
  state: MicState;
  supported: boolean;
  lang: Lang;
  onStart: () => void;
  onStop: () => void;
  showLabel?: boolean;
}

export default function MicButton({
  state,
  supported,
  lang,
  onStart,
  onStop,
  showLabel = true,
}: Props) {
  if (!supported) {
    return <p className="voice-hint">{t(lang, "voiceOnlyChrome")}</p>;
  }

  const listening = state === "listening";
  const processing = state === "processing";

  const cls =
    "mic-btn" +
    (listening ? " mic-btn--listening" : "") +
    (processing ? " mic-btn--processing" : "");

  const label = listening ? t(lang, "listening") : t(lang, "speak");

  return (
    <div className="mic-wrap">
      <button
        type="button"
        className={cls}
        onClick={listening ? onStop : onStart}
        disabled={processing}
        aria-label={listening ? t(lang, "listening") : t(lang, "speak")}
        aria-pressed={listening}
      >
        {processing ? (
          <Loader2 size={48} className="spin-icon" aria-hidden="true" />
        ) : listening ? (
          <Square size={44} aria-hidden="true" fill="currentColor" />
        ) : (
          <Mic size={52} aria-hidden="true" />
        )}
      </button>
      {showLabel && (
        <span className="mic-label" aria-hidden="true">
          {label}
        </span>
      )}
    </div>
  );
}
