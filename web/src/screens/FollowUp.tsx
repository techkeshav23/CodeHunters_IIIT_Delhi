import { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import type { Lang, TriageResponse } from "../types";
import { t } from "../i18n";
import { speak } from "../voice";
import MicButton from "../components/MicButton";
import JudgeView from "../components/JudgeView";
import { useDictation } from "../useDictation";

interface Props {
  lang: Lang;
  response: TriageResponse;
  request: unknown;
  cameFromVoice: boolean;
  onAnswer: (text: string, usedVoice: boolean) => void;
}

export default function FollowUp({
  lang,
  response,
  request,
  cameFromVoice,
  onAnswer,
}: Props) {
  const [text, setText] = useState("");
  const dict = useDictation(lang, setText);
  const dev = lang === "hi" ? "hi" : undefined;
  const fu = response.trace.follow_up;
  const question = response.follow_up_question ?? fu?.text ?? "";

  // Auto-read the question aloud if the user is in a voice flow (spec section 4).
  const spokenFor = useRef<string>("");
  useEffect(() => {
    if (cameFromVoice && question && spokenFor.current !== question) {
      spokenFor.current = question;
      speak(question, lang);
    }
  }, [cameFromVoice, question, lang]);

  const sendFree = () => {
    const value = text.trim();
    if (!value) return;
    dict.stop();
    onAnswer(value, dict.usedVoice);
    setText("");
    dict.setUsedVoice(false);
  };

  return (
    <div className="stack">
      {fu && (
        <span className="progress-pill">
          {t(lang, "question")} {fu.asked_so_far} / {fu.max}
        </span>
      )}

      <h1 className="followup-q" lang={dev} aria-live="polite">
        {question}
      </h1>

      {fu && fu.options.length > 0 && (
        <div className="stack" lang={dev}>
          {fu.options.map((o) => (
            <button
              type="button"
              className="option-btn"
              key={o.value}
              onClick={() => onAnswer(o.label, false)}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}

      <MicButton
        state={dict.state}
        supported={dict.supported}
        lang={lang}
        onStart={dict.start}
        onStop={dict.stop}
      />

      <div className="input-area">
        <label htmlFor="fu-input" className="sr-only">
          {t(lang, "type")}
        </label>
        <textarea
          id="fu-input"
          className="input"
          lang={dev}
          placeholder={t(lang, "type")}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) sendFree();
          }}
        />
        <button
          type="button"
          className="btn btn--primary"
          onClick={sendFree}
          disabled={!text.trim()}
        >
          <Send size={20} aria-hidden="true" />
          {t(lang, "send")}
        </button>
      </div>

      <JudgeView
        request={request}
        response={response}
        timingMs={response.trace.timing_ms}
        lang={lang}
      />
    </div>
  );
}
