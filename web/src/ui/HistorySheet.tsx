import { useEffect, useRef, useState } from "react";
import { History, MessageCircleQuestion, MessageSquare, Stethoscope, Trash2, TriangleAlert, X } from "lucide-react";
import type { Lang } from "../types";
import { t } from "../i18n";
import { chatTime, type SavedChat } from "../lib";

interface Props {
  lang: Lang;
  chats: SavedChat[];
  // the chat open in the thread (null in incognito or on an empty thread)
  openId: string | null;
  onOpen: (c: SavedChat) => void;
  onDelete: (id: string) => void;
  onDeleteAll: () => void;
  onClose: () => void;
}

const DEVANAGARI = /[ऀ-ॿ]/;

// Chats saved in this browser, newest first. Clicking one opens it in the
// Jaanch thread; each can be deleted, or all of them after a confirm step.
export default function HistorySheet({ lang, chats, openId, onOpen, onDelete, onDeleteAll, onClose }: Props) {
  const sheetRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const [confirming, setConfirming] = useState(false);
  const now = new Date();

  useEffect(() => {
    sheetRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (confirming) setConfirming(false);
      else onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [confirming, onClose]);

  useEffect(() => {
    if (confirming) cancelRef.current?.focus();
  }, [confirming]);

  return (
    <div className="scrim" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet sheet--history" role="dialog" aria-modal="true" aria-labelledby="history-title" tabIndex={-1} ref={sheetRef}>
        <div className="history__head">
          <div className="history__titles">
            <h2 id="history-title">{t(lang, "historyTitle")}</h2>
            <p>{t(lang, "historySub")}</p>
          </div>
          <button type="button" className="icon-btn" aria-label={t(lang, "close")} title={t(lang, "close")} onClick={onClose}>
            <X size={20} aria-hidden="true" />
          </button>
        </div>

        <div className="history__list">
          {chats.length === 0 ? (
            <div className="history__empty">
              <span className="history__empty-ico" aria-hidden="true">
                <History size={26} />
              </span>
              <p>{t(lang, "historyEmpty")}</p>
            </div>
          ) : (
            <ul className="chats">
              {chats.map((c) => {
                const open = c.id === openId;
                const look = lookOf(c, lang);
                const when = chatTime(c.updated_at, lang, now);
                const title = c.title || "…";
                return (
                  <li key={c.id} className={open ? "chat-row chat-row--open" : "chat-row"}>
                    <button type="button" className="chat-row__open" aria-current={open ? "true" : undefined} onClick={() => onOpen(c)}>
                      <span className={`chat-row__ico chat-row__ico--${c.outcome.kind}`} aria-hidden="true">
                        <look.icon size={19} />
                      </span>
                      <span className="chat-row__text">
                        <span className="chat-row__title" lang={DEVANAGARI.test(title) ? "hi" : undefined}>
                          {title}
                        </span>
                        {look.outcome && (
                          <span className={`chat-row__outcome chat-row__outcome--${look.tone}`} lang={DEVANAGARI.test(look.outcome) ? "hi" : undefined}>
                            {look.outcome}
                          </span>
                        )}
                        <span className="chat-row__when">{when}</span>
                      </span>
                    </button>
                    <button
                      type="button"
                      className="chat-row__del"
                      aria-label={`${t(lang, "chatDelete")}: ${title}`}
                      title={t(lang, "chatDelete")}
                      onClick={() => {
                        onDelete(c.id);
                        sheetRef.current?.focus();
                      }}
                    >
                      <Trash2 size={18} aria-hidden="true" />
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {chats.length > 0 && (
          <div className="history__foot">
            {confirming ? (
              <div className="history__confirm" role="group" aria-labelledby="delete-all-title">
                <strong id="delete-all-title">{t(lang, "deleteAllTitle")}</strong>
                <p>{chats.length === 1 ? t(lang, "deleteAllTextOne") : t(lang, "deleteAllText", { n: chats.length })}</p>
                <div className="sheet__actions">
                  <button ref={cancelRef} type="button" className="btn btn--ghost" onClick={() => setConfirming(false)}>
                    {t(lang, "back")}
                  </button>
                  <button
                    type="button"
                    className="btn btn--danger"
                    onClick={() => {
                      onDeleteAll();
                      setConfirming(false);
                      sheetRef.current?.focus();
                    }}
                  >
                    <Trash2 size={17} aria-hidden="true" />
                    {t(lang, "deleteYes")}
                  </button>
                </div>
              </div>
            ) : (
              <button type="button" className="btn btn--quiet history__clear" onClick={() => setConfirming(true)}>
                <Trash2 size={17} aria-hidden="true" />
                {t(lang, "deleteAll")}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// What a chat came to: an icon, and the line under its title in its colour.
function lookOf(c: SavedChat, lang: Lang): { icon: typeof History; outcome: string; tone: "danger" | "brand" | "plain" | "muted" } {
  switch (c.outcome.kind) {
    case "emergency":
      return { icon: TriangleAlert, outcome: c.outcome.label ?? t(lang, "sosPageTitle"), tone: "danger" };
    case "decision":
      return { icon: Stethoscope, outcome: c.outcome.label ?? "", tone: c.outcome.level === 2 ? "danger" : "brand" };
    case "question":
      return { icon: MessageCircleQuestion, outcome: t(lang, "chatPending"), tone: "plain" };
    default:
      return { icon: MessageSquare, outcome: t(lang, "chatNoReply"), tone: "muted" };
  }
}
