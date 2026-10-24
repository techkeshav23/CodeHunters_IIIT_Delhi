import { useCallback, useEffect, useRef, useState } from "react";
import type { HistoryItem, Lang, LatLng, TraceCaregiver, TriageRequest, TriageResponse } from "./types";
import { t } from "./i18n";
import { triage, health, USE_MOCKS } from "./api";
import { speak, speechFor, stopSpeaking, voiceSupported } from "./voice";
import {
  chatOutcome,
  chatTitle,
  decodeMsg,
  encodeMsg,
  historyAfter,
  isEmergency,
  MAX_CHATS,
  newChatId,
  readChats,
  readJSON,
  writeChats,
  writeJSON,
  type BookingTarget,
  type Msg,
  type SavedBooking,
  type SavedChat,
  type StoredMsg,
  type View,
} from "./lib";
import { Sidebar, TopBar, BottomNav, type Backend } from "./ui/Nav";
import Composer from "./ui/Composer";
import Thread from "./ui/Thread";
import CaseDetails from "./ui/CaseDetails";
import BookingSheet from "./ui/BookingSheet";
import EmergencyTakeover from "./ui/EmergencyTakeover";
import { ChatBar, IncognitoBanner } from "./ui/ChatBar";
import HistorySheet from "./ui/HistorySheet";
import { useHeightVar } from "./useHeightVar";
import { Start, BookingsView, SosView, HowView, SettingsView, type Theme } from "./views/Views";

const DEMO_LOCATION: LatLng = { lat: 28.5459, lng: 77.2732 };
let nextId = 1;
const nid = () => nextId++;

export default function App() {
  // ---- preferences ----
  const [lang, setLangState] = useState<Lang>(() => readJSON<Lang>("cc_lang", "hinglish"));
  const [large, setLarge] = useState<boolean>(() => readJSON("cc_large", false));
  const [autoRead, setAutoRead] = useState<boolean>(() => readJSON("cc_autoread", true));
  // light by default (the palette is designed for it); dark only when chosen in Settings
  const [theme, setTheme] = useState<Theme>(() => readJSON<Theme>("cc_theme", "light"));
  const micSupported = voiceSupported();
  const setLang = (l: Lang) => {
    setLangState(l);
    writeJSON("cc_lang", l);
  };
  useEffect(() => {
    writeJSON("cc_large", large);
    document.documentElement.classList.toggle("text-large", large);
  }, [large]);
  useEffect(() => writeJSON("cc_autoread", autoRead), [autoRead]);
  useEffect(() => {
    writeJSON("cc_theme", theme);
    if (theme === "auto") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);
  useEffect(() => {
    document.documentElement.lang = lang === "hi" ? "hi" : "en";
  }, [lang]);

  // ---- location ----
  const [location, setLocation] = useState<LatLng>(DEMO_LOCATION);
  const [locMode, setLocMode] = useState<"demo" | "yours" | "failed">("demo");
  const [locating, setLocating] = useState(false);
  const useMyLocation = () => {
    if (!("geolocation" in navigator)) return setLocMode("failed");
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
      { timeout: 8000 },
    );
  };
  const locationLabel = t(lang, locMode === "yours" ? "locYours" : locMode === "failed" ? "locFailed" : "locDemo");

  // ---- backend status ----
  const [backend, setBackend] = useState<Backend>(USE_MOCKS ? "mock" : "wait");
  useEffect(() => {
    if (USE_MOCKS) return;
    let alive = true;
    const check = () =>
      health()
        .then((h) => alive && setBackend(h.status === "ok" ? "ok" : "bad"))
        .catch(() => alive && setBackend("bad"));
    check();
    const id = window.setInterval(check, 20000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);

  // ---- toast ----
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<number>();
  const showToast = (text: string) => {
    setToast(text);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 2200);
  };

  // ---- consult ----
  const [view, setView] = useState<View>("check");
  const [messages, setMessages] = useState<Msg[]>([]);
  // the thread as of now, for code that runs after an await (a reply arriving)
  const msgsRef = useRef<Msg[]>([]);
  const setThread = (next: Msg[]) => {
    msgsRef.current = next;
    setMessages(next);
  };
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState("");
  const [last, setLast] = useState<{ req: TriageRequest; res: TriageResponse } | null>(null);
  const [sos, setSos] = useState<Extract<Msg, { kind: "emergency" }> | null>(null);
  // "Add more details" on a decision: the next message goes with that case's whole
  // conversation, so the triage re-runs on everything said, not only the new words
  const [adding, setAdding] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  // ---- saved chats (History) and incognito; same behaviour as the Android app ----
  const [chats, setChats] = useState<SavedChat[]>(() => readChats());
  const chatsRef = useRef(chats);
  // id of the open thread in chats; null until it is first saved, always null in incognito
  const [chatId, setChatIdState] = useState<string | null>(null);
  const chatIdRef = useRef<string | null>(null);
  // incognito: the open thread is never written to this browser
  const [incognito, setIncognitoState] = useState(false);
  const incognitoRef = useRef(false);
  const startedRef = useRef<string | null>(null);
  // bumped whenever the thread is swapped (new chat, opened chat, deleted), so a
  // reply still loading for the old thread is dropped
  const threadRef = useRef(0);
  const [historyOpen, setHistoryOpen] = useState(false);
  const historyBtnRef = useRef<HTMLButtonElement>(null);
  const chatHeadRef = useHeightVar("--chathead-h");

  const commitChats = (next: SavedChat[]) => {
    const kept = writeChats(next);
    chatsRef.current = kept;
    setChats(kept);
  };
  const setChatId = (id: string | null) => {
    chatIdRef.current = id;
    setChatIdState(id);
  };
  const setIncognito = (on: boolean) => {
    incognitoRef.current = on;
    setIncognitoState(on);
  };

  // Puts the open thread at the top of History (at most MAX_CHATS). Called every
  // time a message is added; never in incognito.
  const saveChat = (msgs: Msg[]) => {
    if (incognitoRef.current) return;
    const stored = msgs.map(encodeMsg).filter((s): s is StoredMsg => s !== null);
    if (stored.length === 0) return;
    const now = new Date().toISOString();
    const id = chatIdRef.current ?? newChatId();
    if (chatIdRef.current !== id) setChatId(id);
    const chat: SavedChat = {
      id,
      started_at: startedRef.current ?? now,
      updated_at: now,
      title: chatTitle(msgs),
      outcome: chatOutcome(msgs, lang),
      messages: stored,
    };
    commitChats([chat, ...chatsRef.current.filter((c) => c.id !== id)].slice(0, MAX_CHATS));
  };

  const pushMsg = (m: Msg) => {
    const next = [...msgsRef.current, m];
    setThread(next);
    saveChat(next);
  };

  const dropChat = (id: string): boolean => {
    if (!chatsRef.current.some((c) => c.id === id)) return false;
    commitChats(chatsRef.current.filter((c) => c.id !== id));
    return true;
  };

  const send = useCallback(
    async (text: string, usedVoice: boolean, retry = false) => {
      const clean = text.trim();
      if (!clean || busy) return;
      stopSpeaking();
      setView("check");
      setAdding(false);
      const thread = threadRef.current;
      if (!retry) {
        if (msgsRef.current.length === 0) startedRef.current = new Date().toISOString();
        pushMsg({ id: nid(), kind: "user", text: clean });
      }
      setDraft("");
      setBusy(true);
      const req: TriageRequest = { user_input: clean, language: "auto", location, conversation_history: history };
      try {
        const res = await triage(req);
        // the user moved to another chat meanwhile: this reply is not for the open thread
        if (thread !== threadRef.current) return;
        setLast({ req, res });
        const voiceLang = res.trace?.language ?? lang;
        if (isEmergency(res)) {
          const msg = { id: nid(), kind: "emergency" as const, req, res, userText: clean };
          pushMsg(msg);
          setHistory([]);
          setSos(msg);
          if (usedVoice && autoRead) speak(speechFor(res.trace.speech, `${res.trace.emergency?.title_local ?? ""}. ${t(lang, "sosNow")}`, voiceLang));
        } else if (res.follow_up_question) {
          pushMsg({ id: nid(), kind: "question", req, res });
          setHistory((h) => [
            ...h,
            { role: "user", content: clean },
            { role: "assistant", content: res.follow_up_question as string, question_id: res.trace.follow_up?.id },
          ]);
          if (usedVoice && autoRead) speak(speechFor(res.trace.speech, res.follow_up_question, voiceLang));
        } else {
          pushMsg({ id: nid(), kind: "decision", req, res });
          setHistory([]);
          if (usedVoice && autoRead) {
            const d = res.trace.decision;
            speak(speechFor(res.trace.speech, [d.care_label_local, d.urgency_label_local, res.trace.reasoning_local].filter(Boolean).join(". "), voiceLang));
          }
        }
      } catch {
        if (thread !== threadRef.current) return;
        pushMsg({ id: nid(), kind: "error", text: clean, usedVoice });
      } finally {
        if (thread === threadRef.current) setBusy(false);
      }
    },
    // pushMsg reads refs only (and lang, listed here)
    [busy, location, history, lang, autoRead],
  );

  const retry = (msg: Extract<Msg, { kind: "error" }>) => {
    setThread(msgsRef.current.filter((x) => x.id !== msg.id));
    void send(msg.text, msg.usedVoice, true);
  };

  // An empty thread; a reply still on its way for the old one is dropped.
  const clearThread = () => {
    stopSpeaking();
    if (incognitoRef.current) setLast(null); // nothing of an incognito chat stays behind
    threadRef.current++;
    setThread([]);
    setHistory([]);
    setAdding(false);
    setBusy(false);
    setSos(null);
    setChatId(null);
    startedRef.current = null;
  };

  // "+ Nayi chat", the banner's cross, and every "Nayi jaanch" button. The open
  // chat is already in History (each message saves it); an incognito one is
  // dropped. Always leaves incognito.
  const newChat = () => {
    clearThread();
    setIncognito(false);
    setDraft("");
    setView("check");
    window.setTimeout(() => inputRef.current?.focus(), 50);
  };

  // "Incognito chat": nothing in this thread is saved from now on. From the start
  // screen this is a new chat; on an open saved chat it also takes that chat out
  // of History.
  const goIncognito = () => {
    if (incognitoRef.current) return;
    const id = chatIdRef.current;
    setIncognito(true);
    setChatId(null);
    setView("check");
    if (id && dropChat(id)) showToast(t(lang, "incognitoRemoved"));
  };

  const closeHistory = useCallback(() => {
    setHistoryOpen(false);
    window.setTimeout(() => historyBtnRef.current?.focus({ preventScroll: true }), 0);
  }, []);

  // Opens a chat from History in the thread. If it ends on a question, history is
  // rebuilt exactly as send() left it, so the next message answers it; otherwise
  // the next message starts a new case.
  const openChat = (c: SavedChat) => {
    closeHistory();
    setView("check");
    if (!incognitoRef.current && c.id === chatIdRef.current) return;
    clearThread();
    setIncognito(false);
    const msgs: Msg[] = [];
    for (const s of c.messages) {
      const m = decodeMsg(s, nid());
      if (m) msgs.push(m);
    }
    // a last message with no reply (tab closed, or the request failed): offer the retry
    const tail = msgs[msgs.length - 1];
    if (tail?.kind === "user") msgs.push({ id: nid(), kind: "error", text: tail.text, usedVoice: false });
    setThread(msgs);
    setHistory(historyAfter(msgs));
    setChatId(c.id);
    startedRef.current = c.started_at;
  };

  // Deletes one saved chat; if it is the open one, the thread is cleared too, so
  // the next message does not save it again.
  const deleteChat = (id: string) => {
    if (!dropChat(id)) return;
    if (id === chatIdRef.current) clearThread();
  };

  // "Saari history mitayein", after the confirm step. Bookings stay.
  const deleteAllChats = () => {
    const wasOpen = chatIdRef.current !== null;
    commitChats([]);
    if (wasOpen) clearThread();
  };

  // the decision's own request holds the conversation before it (questions with
  // their ids, answers) and the message that led to it; the next send carries both
  const addMore = (msg: Extract<Msg, { kind: "decision" }>) => {
    stopSpeaking();
    setHistory([...(msg.req.conversation_history ?? []), { role: "user", content: msg.req.user_input }]);
    setAdding(true);
    // focus in the tap itself so phones open the keyboard
    inputRef.current?.focus();
  };

  // keep the newest message in view
  // a new answer scrolls to its own top (decision headline first); a sent message scrolls to the end
  useEffect(() => {
    if (messages.length === 0) return;
    const lastMsg = messages[messages.length - 1];
    if (lastMsg.kind === "user" || busy) {
      endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    } else {
      const nodes = document.querySelectorAll(".thread > .msg");
      nodes[nodes.length - 1]?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [messages, busy]);

  // ---- bookings ----
  const [bookings, setBookings] = useState<SavedBooking[]>(() => readJSON<SavedBooking[]>("cc_bookings", []));
  const [target, setTarget] = useState<BookingTarget | null>(null);
  const onBooked = (b: SavedBooking) => {
    setBookings((all) => {
      const next = [b, ...all];
      writeJSON("cc_bookings", next);
      return next;
    });
    showToast(t(lang, "toastBooked"));
  };

  // ---- layout ----
  const latestCase = [...messages].reverse().find((m) => m.kind === "decision" || m.kind === "question") as
    | Extract<Msg, { kind: "decision" | "question" }>
    | undefined;
  const hasPanel = view === "check" && !!latestCase;
  const answering = messages[messages.length - 1]?.kind === "question";

  return (
    <>
      <div className={hasPanel ? "shell has-panel" : "shell"}>
        <Sidebar view={view} lang={lang} onView={setView} onLang={setLang} backend={backend} bookingsCount={bookings.length} />
        <div className="workspace">
          <TopBar lang={lang} onLang={setLang} onView={setView} />
          {view === "check" && (
            <>
              <main className="view view--check" id="main">
                <div className="chathead" ref={chatHeadRef}>
                  <ChatBar
                    lang={lang}
                    count={chats.length}
                    threadOpen={messages.length > 0}
                    incognito={incognito}
                    onHistory={() => setHistoryOpen(true)}
                    onIncognito={goIncognito}
                    onNewChat={newChat}
                    historyRef={historyBtnRef}
                  />
                  {incognito && <IncognitoBanner lang={lang} onClose={newChat} />}
                </div>
                {messages.length === 0 ? (
                  <Start
                    lang={lang}
                    onSeed={(s) => {
                      setDraft(s);
                      window.setTimeout(() => {
                        const el = inputRef.current;
                        if (el) {
                          el.focus();
                          el.setSelectionRange(s.length, s.length);
                        }
                      }, 30);
                    }}
                    onExample={(s) => void send(s, false)}
                    onMic={() => window.dispatchEvent(new Event("cc:mic"))}
                    micSupported={micSupported}
                  />
                ) : (
                  <Thread
                    messages={messages}
                    busy={busy}
                    lang={lang}
                    onAnswer={(s) => void send(s, false)}
                    onBook={(cg: TraceCaregiver, res: TriageResponse) => setTarget({ caregiver: cg, res })}
                    onRetry={retry}
                    onOpenEmergency={(m) => setSos(m)}
                    onNewCheck={newChat}
                    onAddMore={addMore}
                    adding={adding}
                  />
                )}
                <div ref={endRef} />
              </main>
              <Composer
                lang={lang}
                value={draft}
                onChange={setDraft}
                onSend={(s, v) => void send(s, v)}
                busy={busy}
                answering={answering}
                adding={adding}
                locationLabel={locationLabel}
                locating={locating}
                onUseLocation={useMyLocation}
                inputRef={inputRef}
              />
            </>
          )}
          {view === "bookings" && <BookingsView lang={lang} bookings={bookings} onStart={newChat} />}
          {view === "sos" && <SosView lang={lang} />}
          {view === "how" && <HowView lang={lang} last={last} />}
          {view === "settings" && (
            <SettingsView
              lang={lang}
              onLang={setLang}
              large={large}
              onLarge={setLarge}
              autoRead={autoRead}
              onAutoRead={setAutoRead}
              theme={theme}
              onTheme={setTheme}
              locationLabel={locationLabel}
              locating={locating}
              onUseLocation={useMyLocation}
            />
          )}
        </div>
        {hasPanel && latestCase && (
          <aside className="case-panel" aria-label={t(lang, "whyThis")}>
            <h2 className="case-panel__title">{t(lang, "whyThis")}</h2>
            <CaseDetails res={latestCase.res} lang={lang} />
          </aside>
        )}
      </div>
      <BottomNav view={view} lang={lang} onView={setView} />

      {target && (
        <BookingSheet
          target={target}
          lang={lang}
          locationLabel={locationLabel}
          onClose={() => setTarget(null)}
          onBooked={onBooked}
          onSeeBookings={() => {
            setTarget(null);
            setView("bookings");
          }}
        />
      )}
      {historyOpen && (
        <HistorySheet
          lang={lang}
          chats={chats}
          openId={incognito ? null : chatId}
          onOpen={openChat}
          onDelete={deleteChat}
          onDeleteAll={deleteAllChats}
          onClose={closeHistory}
        />
      )}
      {sos && (
        <EmergencyTakeover res={sos.res} userText={sos.userText} lang={lang} onBack={() => setSos(null)} onNewCheck={newChat} />
      )}
      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
    </>
  );
}
