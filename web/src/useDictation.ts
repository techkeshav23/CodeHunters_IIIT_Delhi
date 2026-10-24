import { useCallback, useEffect, useRef, useState } from "react";
import type { Lang } from "./types";
import { createRecognizer, voiceSupported, type Recognizer } from "./voice";

export type MicState = "idle" | "listening";

// Drives the mic for a single text box. The live transcript is pushed into the
// box via setText so the user can fix it before sending (spec section 7).
// `usedVoice` lets the result screen auto-read when the user spoke.
export function useDictation(lang: Lang, setText: (t: string) => void) {
  const [state, setState] = useState<MicState>("idle");
  const [usedVoice, setUsedVoice] = useState(false);
  const recRef = useRef<Recognizer | null>(null);
  const supported = voiceSupported();

  const stop = useCallback(() => {
    recRef.current?.stop();
  }, []);

  const start = useCallback(() => {
    if (!supported) return;
    setUsedVoice(true);
    const rec = createRecognizer(lang, {
      onStart: () => setState("listening"),
      onEnd: () => setState("idle"),
      onError: () => setState("idle"),
      onTranscript: (text) => {
        // Replace the box with the latest transcript (interim or final).
        setText(text);
      },
    });
    recRef.current = rec;
    rec?.start();
  }, [lang, supported, setText]);

  // Abort any active recognition on unmount / screen change.
  useEffect(() => {
    return () => recRef.current?.abort();
  }, []);

  return { state, supported, usedVoice, start, stop, setUsedVoice };
}
