// Voice in (Web Speech API) and voice out (speechSynthesis). Spec section 7.
// Degrades gracefully: if recognition is unsupported, callers hide the mic.

import type { Lang } from "./types";

// --- minimal typings for the vendor-prefixed SpeechRecognition API ---

interface SpeechRecognitionAlternative {
  transcript: string;
}
interface SpeechRecognitionResult {
  0: SpeechRecognitionAlternative;
  isFinal: boolean;
  length: number;
}
interface SpeechRecognitionResultList {
  length: number;
  [index: number]: SpeechRecognitionResult;
}
interface SpeechRecognitionEvent extends Event {
  resultIndex: number;
  results: SpeechRecognitionResultList;
}
interface SpeechRecognitionErrorEvent extends Event {
  error: string;
}
interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((e: SpeechRecognitionEvent) => void) | null;
  onerror: ((e: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getRecognitionCtor(): SpeechRecognitionCtor | null {
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function voiceSupported(): boolean {
  return getRecognitionCtor() !== null;
}

export function ttsSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

// Map UI language to a BCP-47 recognition/synthesis locale.
// Hinglish uses Hindi recognition since users speak Hindi words (spec section 7).
function localeFor(lang: Lang): string {
  return lang === "en" ? "en-IN" : "hi-IN";
}

export interface Recognizer {
  start(): void;
  stop(): void;
  abort(): void;
}

export interface RecognizerCallbacks {
  onTranscript: (text: string, isFinal: boolean) => void;
  onStart?: () => void;
  onEnd?: () => void;
  onError?: (error: string) => void;
}

// Create a one-shot recognizer. Streams interim transcripts so the user can
// see/fix the text before sending. Stops after a pause (continuous = false).
export function createRecognizer(
  lang: Lang,
  cb: RecognizerCallbacks,
): Recognizer | null {
  const Ctor = getRecognitionCtor();
  if (!Ctor) return null;

  const rec = new Ctor();
  rec.lang = localeFor(lang);
  rec.continuous = false;
  rec.interimResults = true;
  rec.maxAlternatives = 1;

  rec.onstart = () => cb.onStart?.();
  rec.onend = () => cb.onEnd?.();
  rec.onerror = (e) => cb.onError?.(e.error);
  rec.onresult = (e) => {
    let interim = "";
    let finalText = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      const text = r[0].transcript;
      if (r.isFinal) finalText += text;
      else interim += text;
    }
    if (finalText) cb.onTranscript(finalText, true);
    else if (interim) cb.onTranscript(interim, false);
  };

  return {
    start: () => {
      try {
        rec.start();
      } catch {
        // start() throws if already started; ignore.
      }
    },
    stop: () => {
      try {
        rec.stop();
      } catch {
        /* ignore */
      }
    },
    abort: () => {
      try {
        rec.abort();
      } catch {
        /* ignore */
      }
    },
  };
}

// --- text to speech ---

let cachedVoices: SpeechSynthesisVoice[] = [];

function loadVoices(): SpeechSynthesisVoice[] {
  if (!ttsSupported()) return [];
  const v = window.speechSynthesis.getVoices();
  if (v.length) cachedVoices = v;
  return cachedVoices;
}

if (ttsSupported()) {
  loadVoices();
  window.speechSynthesis.onvoiceschanged = () => loadVoices();
}

function pickVoice(lang: Lang): SpeechSynthesisVoice | null {
  const voices = loadVoices();
  const prefix = lang === "en" ? "en" : "hi";
  return (
    voices.find((v) => v.lang.toLowerCase().startsWith(prefix)) ??
    // For Hinglish, an English Indian voice is an acceptable fallback.
    (lang !== "en"
      ? voices.find((v) => v.lang.toLowerCase().startsWith("en")) ?? null
      : null)
  );
}

export function speak(
  text: string,
  lang: Lang,
  opts?: { onEnd?: () => void },
): void {
  if (!ttsSupported() || !text.trim()) {
    opts?.onEnd?.();
    return;
  }
  const synth = window.speechSynthesis;
  synth.cancel(); // stop anything already speaking
  const u = new SpeechSynthesisUtterance(text);
  const voice = pickVoice(lang);
  if (voice) u.voice = voice;
  u.lang = localeFor(lang);
  u.rate = 0.9; // slightly slow (spec section 7)
  if (opts?.onEnd) {
    u.onend = () => opts.onEnd?.();
    u.onerror = () => opts.onEnd?.();
  }
  synth.speak(u);
}

export function stopSpeaking(): void {
  if (ttsSupported()) window.speechSynthesis.cancel();
}
