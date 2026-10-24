import { useCallback, useEffect, useRef, type KeyboardEvent } from "react";
import { MapPin, Mic, SendHorizontal, Square } from "lucide-react";
import type { Lang } from "../types";
import { t } from "../i18n";
import { useDictation } from "../useDictation";

interface Props {
  lang: Lang;
  value: string;
  onChange: (v: string) => void;
  onSend: (text: string, usedVoice: boolean) => void;
  busy: boolean;
  answering: boolean;
  locationLabel: string;
  locating: boolean;
  onUseLocation: () => void;
  inputRef: React.RefObject<HTMLTextAreaElement>;
}

export default function Composer(p: Props) {
  const setText = useCallback((v: string) => p.onChange(v), [p.onChange]);
  const mic = useDictation(p.lang, setText);
  const sentByVoice = useRef(false);

  // grow with the text, up to a limit
  useEffect(() => {
    const el = p.inputRef.current;
    if (!el) return;
    el.style.height = "";
    if (p.value) el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
    el.style.overflowY = el.scrollHeight > 220 ? "auto" : "hidden";
  }, [p.value, p.inputRef]);

  const send = () => {
    const text = p.value.trim();
    if (!text || p.busy) return;
    mic.stop();
    p.onSend(text, mic.usedVoice || sentByVoice.current);
    mic.setUsedVoice(false);
    sentByVoice.current = false;
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      send();
    }
  };

  const listening = mic.state === "listening";

  // the start screen's big mic asks the composer to listen
  useEffect(() => {
    const onMic = () => {
      if (!mic.supported || listening) return;
      sentByVoice.current = true;
      mic.start();
      p.inputRef.current?.focus();
    };
    window.addEventListener("cc:mic", onMic);
    return () => window.removeEventListener("cc:mic", onMic);
  }, [mic, listening, p.inputRef]);

  return (
    <div className="dock">
      <div className="composer">
        <div className="composer__box">
          <label htmlFor="cc-input" className="sr-only">
            {t(p.lang, "placeholder")}
          </label>
          <textarea
            id="cc-input"
            ref={p.inputRef}
            rows={1}
            value={p.value}
            placeholder={listening ? t(p.lang, "listening") : t(p.lang, p.answering ? "placeholderAnswer" : "placeholder")}
            onChange={(e) => p.onChange(e.target.value)}
            onKeyDown={onKey}
            lang={p.lang === "hi" ? "hi" : undefined}
          />
          {mic.supported && (
            <button
              type="button"
              className="mic"
              data-state={mic.state}
              aria-label={listening ? t(p.lang, "micStop") : t(p.lang, "micStart")}
              aria-pressed={listening}
              onClick={() => {
                if (listening) mic.stop();
                else {
                  sentByVoice.current = true;
                  mic.start();
                }
              }}
            >
              {listening ? <Square size={20} fill="currentColor" /> : <Mic size={24} />}
            </button>
          )}
          <button
            type="button"
            className="send"
            aria-label={t(p.lang, "send")}
            disabled={!p.value.trim() || p.busy}
            onClick={send}
          >
            <SendHorizontal size={22} />
          </button>
        </div>
        <div className="composer__meta">
          <span className="composer__hint">
            <MapPin size={14} aria-hidden="true" />
            {p.locationLabel}
            <button type="button" onClick={p.onUseLocation} disabled={p.locating}>
              {p.locating ? t(p.lang, "locFinding") : t(p.lang, "locUse")}
            </button>
          </span>
          {listening ? (
            <span className="listening-note" aria-live="polite">
              {t(p.lang, "listening")}
            </span>
          ) : !mic.supported ? (
            <span>{t(p.lang, "voiceOff")}</span>
          ) : null}
        </div>
      </div>
    </div>
  );
}
