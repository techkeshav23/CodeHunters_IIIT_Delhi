import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle } from "lucide-react";
import type {
  BookingRequest,
  BookingResponse,
  HistoryItem,
  Lang,
  LatLng,
  TraceCaregiver,
  TriageRequest,
  TriageResponse,
} from "./types";
import { t } from "./i18n";
import { triage, createBooking, health, USE_MOCKS } from "./api";
import { stopSpeaking } from "./voice";
import Header, { type BackendState } from "./components/Header";
import Footer from "./components/Footer";
import Home from "./screens/Home";
import FollowUp from "./screens/FollowUp";
import Result from "./screens/Result";
import Booking from "./screens/Booking";
import Emergency from "./screens/Emergency";

const DEMO_LOCATION: LatLng = { lat: 28.5459, lng: 77.2732 };

type LocMode = "demo" | "yours" | "failed";

function loadLang(): Lang {
  try {
    const v = localStorage.getItem("cc_lang");
    if (v === "hi" || v === "en" || v === "hinglish") return v;
  } catch {
    /* localStorage may be blocked */
  }
  return "hinglish";
}

export default function App() {
  const [lang, setLangState] = useState<Lang>(loadLang);
  const [location, setLocation] = useState<LatLng>(DEMO_LOCATION);
  const [locMode, setLocMode] = useState<LocMode>("demo");
  const [locating, setLocating] = useState(false);

  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [response, setResponse] = useState<TriageResponse | null>(null);
  const [lastRequest, setLastRequest] = useState<TriageRequest | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [cameFromVoice, setCameFromVoice] = useState(false);

  const [booking, setBooking] = useState<BookingResponse | null>(null);
  const [bookingSlotLabel, setBookingSlotLabel] = useState<string | null>(null);
  const [bookingFor, setBookingFor] = useState<string | null>(null);

  const [backend, setBackend] = useState<BackendState>("wait");
  const retryRef = useRef<() => void>(() => {});

  const setLang = (l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem("cc_lang", l);
    } catch {
      /* ignore */
    }
  };

  // ---- backend health (skipped in mock mode) ----
  useEffect(() => {
    if (USE_MOCKS) return;
    let alive = true;
    const check = async () => {
      try {
        const h = await health();
        if (alive) setBackend(h.status === "ok" ? "ok" : "bad");
      } catch {
        if (alive) setBackend("bad");
      }
    };
    check();
    const id = window.setInterval(check, 20000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);

  // ---- triage submit ----
  const submit = useCallback(
    async (text: string, usedVoice: boolean) => {
      stopSpeaking();
      setCameFromVoice(usedVoice);
      setStatus("loading");
      const req: TriageRequest = {
        user_input: text,
        language: "auto",
        location,
        conversation_history: history,
      };
      setLastRequest(req);
      retryRef.current = () => void submit(text, usedVoice);
      try {
        const res = await triage(req);
        // Append to history only when a follow-up continues the conversation.
        if (res.follow_up_question) {
          setHistory((h) => [
            ...h,
            { role: "user", content: text },
            {
              role: "assistant",
              content: res.follow_up_question as string,
              question_id: res.trace.follow_up?.id,
            },
          ]);
        }
        setResponse(res);
        setStatus("idle");
      } catch {
        setStatus("error");
      }
    },
    [location, history],
  );

  // ---- booking ----
  const book = useCallback(
    async (cg: TraceCaregiver) => {
      if (!response) return;
      setBookingFor(cg.caregiver_id);
      const req: BookingRequest = {
        caregiver_id: cg.caregiver_id,
        slot: cg.next_slot,
        care_type: response.care_type,
        urgency: response.urgency,
        note: "",
      };
      retryRef.current = () => void book(cg);
      try {
        const b = await createBooking(req);
        setBooking(b);
        setBookingSlotLabel(cg.next_slot_label_local ?? cg.next_slot_label ?? null);
        setStatus("idle");
      } catch {
        setStatus("error");
      } finally {
        setBookingFor(null);
      }
    },
    [response],
  );

  const restart = () => {
    stopSpeaking();
    setResponse(null);
    setBooking(null);
    setBookingSlotLabel(null);
    setHistory([]);
    setLastRequest(null);
    setCameFromVoice(false);
    setStatus("idle");
  };

  const useMyLocation = () => {
    if (!("geolocation" in navigator)) {
      setLocMode("failed");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setLocMode("yours");
        setLocating(false);
      },
      () => {
        setLocMode("failed");
        setLocating(false);
      },
      { timeout: 8000, enableHighAccuracy: false },
    );
  };

  const locationLabel =
    locMode === "yours"
      ? t(lang, "locationYours")
      : locMode === "failed"
        ? t(lang, "locationFailed")
        : t(lang, "locationDemo");

  // ---- view selection ----
  const isEmergency =
    response != null &&
    (response.trace.emergency != null || response.red_flags.length > 0);
  const isFollowUp = response != null && response.follow_up_question != null;

  // Emergency takes over the whole viewport (impossible to miss).
  if (isEmergency && status !== "loading" && response) {
    return (
      <Emergency
        lang={lang}
        response={response}
        cameFromVoice={cameFromVoice}
        onRestart={restart}
      />
    );
  }

  let body: React.ReactNode;
  if (status === "loading") {
    body = (
      <div className="loading" aria-live="polite">
        <div className="spinner" aria-hidden="true" />
        <p>{t(lang, "thinking")}</p>
      </div>
    );
  } else if (status === "error") {
    body = (
      <div className="error-box" role="alert">
        <AlertTriangle size={40} aria-hidden="true" />
        <p>{t(lang, "networkError")}</p>
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => retryRef.current()}
        >
          {t(lang, "retry")}
        </button>
      </div>
    );
  } else if (booking) {
    body = (
      <Booking
        lang={lang}
        booking={booking}
        slotLabel={bookingSlotLabel}
        onRestart={restart}
      />
    );
  } else if (!response) {
    body = (
      <Home
        lang={lang}
        locationLabel={locationLabel}
        locating={locating}
        onUseLocation={useMyLocation}
        onSubmit={submit}
      />
    );
  } else if (isFollowUp) {
    body = (
      <FollowUp
        lang={lang}
        response={response}
        request={lastRequest}
        cameFromVoice={cameFromVoice}
        onAnswer={submit}
      />
    );
  } else {
    body = (
      <Result
        lang={lang}
        response={response}
        request={lastRequest}
        bookingFor={bookingFor}
        onBook={book}
      />
    );
  }

  return (
    <div className="app">
      <Header
        lang={lang}
        onLang={setLang}
        backend={backend}
        usingMocks={USE_MOCKS}
      />
      <main className="main">{body}</main>
      <Footer lang={lang} />
    </div>
  );
}
