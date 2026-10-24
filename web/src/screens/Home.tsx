import { useState } from "react";
import { Send, MapPin, ChevronRight } from "lucide-react";
import type { Lang } from "../types";
import { t } from "../i18n";
import MicButton from "../components/MicButton";
import { useDictation } from "../useDictation";

const EXAMPLES: Record<Lang, string[]> = {
  hinglish: [
    "Papa ko 2 din se bukhar aur khansi",
    "Dadi ko ghar pe injection lagwana hai",
    "Seene mein dard ho raha hai",
  ],
  hi: [
    "पापा को 2 दिन से बुखार और खांसी",
    "दादी को घर पे इंजेक्शन लगवाना है",
    "सीने में दर्द हो रहा है",
  ],
  en: [
    "My father has had fever and cough for 2 days",
    "My grandmother needs an injection at home",
    "I am having chest pain",
  ],
};

interface Props {
  lang: Lang;
  locationLabel: string;
  locating: boolean;
  onUseLocation: () => void;
  onSubmit: (text: string, usedVoice: boolean) => void;
}

export default function Home({
  lang,
  locationLabel,
  locating,
  onUseLocation,
  onSubmit,
}: Props) {
  const [text, setText] = useState("");
  const dict = useDictation(lang, setText);
  const dev = lang === "hi" ? "hi" : undefined;

  const send = () => {
    const value = text.trim();
    if (!value) return;
    dict.stop();
    onSubmit(value, dict.usedVoice);
    setText("");
    dict.setUsedVoice(false);
  };

  return (
    <div className="stack">
      <p className="tagline" lang={dev}>
        {t(lang, "tagline")}
      </p>

      <div className="home-location">
        <MapPin size={16} aria-hidden="true" />
        <span lang={dev}>{locationLabel}</span>
        <button
          type="button"
          className="btn--link"
          onClick={onUseLocation}
          disabled={locating}
        >
          {locating ? t(lang, "gettingLocation") : t(lang, "useMyLocation")}
        </button>
      </div>

      <MicButton
        state={dict.state}
        supported={dict.supported}
        lang={lang}
        onStart={dict.start}
        onStop={dict.stop}
      />

      <div className="input-area">
        <label htmlFor="home-input" className="sr-only">
          {t(lang, "type")}
        </label>
        <textarea
          id="home-input"
          className="input"
          lang={dev}
          placeholder={t(lang, "type")}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) send();
          }}
        />
        <button
          type="button"
          className="btn btn--primary"
          onClick={send}
          disabled={!text.trim()}
        >
          <Send size={20} aria-hidden="true" />
          {t(lang, "send")}
        </button>
      </div>

      <div className="chips" lang={dev}>
        {EXAMPLES[lang].map((ex) => (
          <button
            type="button"
            className="chip"
            key={ex}
            onClick={() => onSubmit(ex, false)}
          >
            <ChevronRight size={18} aria-hidden="true" />
            {ex}
          </button>
        ))}
      </div>
    </div>
  );
}
