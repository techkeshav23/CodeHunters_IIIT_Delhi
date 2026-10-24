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

// Android Chrome repeats final results in continuous mode, so phones keep the
// one-shot mode (stops after a pause); desktop listens continuously and stops
// itself after a short silence, so a pause mid-sentence does not cut the user off.
// ("Desktop site" on Android sends a Linux UA without "Android": a touch Linux that is not a Chromebook.)
const ONE_SHOT =
  typeof navigator !== "undefined" &&
  (/Android/i.test(navigator.userAgent) ||
    (/Linux/i.test(navigator.userAgent) && !/CrOS/i.test(navigator.userAgent) && navigator.maxTouchPoints > 0));
const SILENCE_MS = 2000;
const MAX_MS = 30_000;

// Create a recognizer. Streams the whole transcript so far (interim + final) so
// the user can see and fix the text before sending.
export function createRecognizer(
  lang: Lang,
  cb: RecognizerCallbacks,
): Recognizer | null {
  const Ctor = getRecognitionCtor();
  if (!Ctor) return null;

  const rec = new Ctor();
  rec.lang = localeFor(lang);
  rec.continuous = !ONE_SHOT;
  rec.interimResults = true;
  rec.maxAlternatives = 1;

  let silence = 0;
  let cap = 0;
  let heard = "";
  const clearTimers = () => {
    window.clearTimeout(silence);
    window.clearTimeout(cap);
  };
  const stopSoon = (ms: number) => {
    window.clearTimeout(silence);
    silence = window.setTimeout(() => {
      try {
        rec.stop();
      } catch {
        /* ignore */
      }
    }, ms);
  };

  rec.onstart = () => {
    if (!ONE_SHOT) cap = window.setTimeout(() => rec.stop(), MAX_MS);
    cb.onStart?.();
  };
  rec.onend = () => {
    clearTimers();
    cb.onEnd?.();
  };
  rec.onerror = (e) => cb.onError?.(e.error);
  rec.onresult = (e) => {
    let text = "";
    let allFinal = true;
    for (let i = 0; i < e.results.length; i++) {
      const r = e.results[i];
      text += r[0].transcript;
      if (!r.isFinal) allFinal = false;
    }
    text = text.replace(/\s+/g, " ").trim();
    if (text) cb.onTranscript(text, allFinal);
    // the silence clock restarts only when new words arrive, not on repeated interim results
    if (!ONE_SHOT && (text !== heard || allFinal)) stopSoon(allFinal ? SILENCE_MS : SILENCE_MS + 1500);
    heard = text;
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
      clearTimers();
      try {
        rec.stop();
      } catch {
        /* ignore */
      }
    },
    abort: () => {
      clearTimers();
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

// speechSynthesis is an EventTarget only from Safari 16; older iOS has just the
// onvoiceschanged property, so one listener is kept there and checked by polling.
function onVoicesChanged(): void {
  loadVoices();
}

if (ttsSupported()) {
  loadVoices();
  const synth = window.speechSynthesis;
  if (typeof synth.addEventListener === "function") synth.addEventListener("voiceschanged", onVoicesChanged);
  else synth.onvoiceschanged = onVoicesChanged;
}

// Chrome fills the voice list asynchronously; wait briefly for it once.
function whenVoices(): Promise<void> {
  if (loadVoices().length) return Promise.resolve();
  return new Promise((resolve) => {
    let waited = 0;
    const tick = () => {
      if (loadVoices().length || waited >= 1200) resolve();
      else {
        waited += 100;
        window.setTimeout(tick, 100);
      }
    };
    tick();
  });
}

// Rank voices for a locale: neural/online voices (Edge "... Online (Natural)",
// Chrome "Google हिन्दी") sound human; the old Windows desktop voices
// (Kalpana, Hemant, Heera, Ravi) sound robotic and come first in the list.
function voiceScore(v: SpeechSynthesisVoice, locale: string): number {
  const lang = v.lang.toLowerCase().replace("_", "-");
  const want = locale.toLowerCase();
  if (!lang.startsWith(want.slice(0, 2))) return -Infinity;
  const name = v.name.toLowerCase();
  let s = lang === want ? 30 : 0;
  if (/natural|neural|wavenet|enhanced|premium/.test(name)) s += 100;
  if (/google/.test(name)) s += 50;
  if (/online/.test(name) || !v.localService) s += 40;
  if (/swara|neerja/.test(name)) s += 5;
  if (/kalpana|hemant|heera|\bravi\b|zira|david|\bmark\b|espeak/.test(name)) s -= 40;
  return s;
}

export function pickVoice(locale: string): SpeechSynthesisVoice | null {
  let best: SpeechSynthesisVoice | null = null;
  let bestScore = -Infinity;
  for (const v of loadVoices()) {
    const s = voiceScore(v, locale);
    if (s > bestScore) {
      best = v;
      bestScore = s;
    }
  }
  return best;
}

// Short chunks: Chrome's online voices stop after ~15 s of one utterance.
// (No regex lookbehind: Safari before 16.4 cannot parse it.)
function chunks(text: string): string[] {
  const out: string[] = [];
  for (const sentence of text.replace(/([.!?।])\s+/g, "$1\n").split("\n")) {
    let rest = sentence.trim();
    while (rest.length > 180) {
      const cut = Math.max(rest.lastIndexOf(", ", 180), rest.lastIndexOf(" ", 180));
      const at = cut > 40 ? cut + 1 : 180;
      out.push(rest.slice(0, at).trim());
      rest = rest.slice(at).trim();
    }
    if (rest) out.push(rest);
  }
  return out;
}

// Keep utterances referenced until they finish (Chrome can drop onend otherwise).
let live: SpeechSynthesisUtterance[] = [];
let generation = 0;
let ending: (() => void) | null = null; // onEnd of what is playing now

function finish(): void {
  const f = ending;
  ending = null;
  f?.();
}

/** What to say and in which voice: the API's trace.speech ("hi-IN" Devanagari or "en-IN").
 * `alt` is the on-screen text, read with an English voice when there is no Hindi voice. */
export interface Speech {
  text: string;
  locale: string;
  alt?: string;
}

export function speechFor(spoken: Speech | null | undefined, shown: string, lang: Lang): Speech {
  return spoken?.text ? { ...spoken, alt: shown } : { text: shown, locale: localeFor(lang) };
}

export function speak(s: Speech, opts?: { onEnd?: () => void }): void {
  if (!ttsSupported() || !s.text.trim()) {
    opts?.onEnd?.();
    return;
  }
  const synth = window.speechSynthesis;
  const busy = synth.speaking || synth.pending;
  synth.cancel(); // stop anything already speaking
  finish(); // the button that was reading goes back to "Sunaiye"
  const gen = ++generation;
  ending = opts?.onEnd ?? null;
  const go = () => {
    if (gen !== generation) return; // stopped or replaced meanwhile
    try {
      queue();
    } catch {
      finish(); // never leave a button stuck on "Rokein"
    }
  };
  const queue = () => {
    let voice = pickVoice(s.locale);
    let text = s.text;
    if (!voice && s.alt && !s.locale.startsWith("en") && loadVoices().length) {
      // no Hindi voice on this device: read the on-screen text with an Indian English voice
      voice = pickVoice("en-IN");
      if (voice) text = s.alt;
    }
    const parts = chunks(text);
    live = parts.map((part, i) => {
      const u = new SpeechSynthesisUtterance(part);
      if (voice) u.voice = voice;
      u.lang = voice?.lang ?? s.locale;
      u.rate = 0.95; // a touch slower than normal, for older listeners
      u.pitch = 1;
      if (i === parts.length - 1) {
        u.onend = () => {
          if (gen === generation) finish();
        };
      }
      u.onerror = () => {
        if (gen === generation) {
          synth.cancel();
          finish();
        }
      };
      return u;
    });
    live.forEach((u) => synth.speak(u));
  };
  // Chrome can drop an utterance queued in the same tick as cancel().
  void whenVoices().then(() => (busy ? window.setTimeout(go, 80) : go()));
}

export function stopSpeaking(): void {
  generation++;
  live = [];
  if (ttsSupported()) window.speechSynthesis.cancel();
  finish();
}
