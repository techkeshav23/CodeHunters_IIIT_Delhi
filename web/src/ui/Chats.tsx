import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { EllipsisVertical, EyeOff, Plus, Trash2, X } from "lucide-react";
import type { Lang } from "../types";
import { t, type Key } from "../i18n";
import { chatTime, isUnclear, type SavedChat } from "../lib";
import { BrandMark } from "./Brand";

interface Props {
  lang: Lang;
  chats: SavedChat[];
  // the chat open in the thread (null in incognito or on an empty thread)
  openId: string | null;
  incognito: boolean;
  onNewChat: () => void;
  onIncognito: () => void;
  onOpen: (c: SavedChat) => void;
  onDelete: (id: string) => void;
  onDeleteAll: () => void;
}

const DEVANAGARI = /[ऀ-ॿ]/;
const GROUPS: Key[] = ["chatsToday", "chatsYesterday", "chatsEarlier"];

// The chat sidebar (desktop) and drawer (phone, tablet): New chat, Incognito chat,
// then the chats saved in this browser, newest first, grouped Aaj / Kal / Pehle.
// Clicking one opens it in the Jaanch thread; each can be deleted from its menu,
// or all of them after a confirm step.
export function ChatsPanel({ lang, chats, openId, incognito, onNewChat, onIncognito, onOpen, onDelete, onDeleteAll }: Props) {
  const rootRef = useRef<HTMLElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const clearRef = useRef<HTMLButtonElement>(null);
  const [confirming, setConfirming] = useState(false);
  const wasConfirming = useRef(false);
  const [menuId, setMenuId] = useState<string | null>(null);
  const confirmTitleId = useId();
  const now = new Date();

  // focus to "Wapas" when the confirm step opens, back to "Saari history mitayein" if it is cancelled
  useEffect(() => {
    if (confirming) cancelRef.current?.focus();
    else if (wasConfirming.current) clearRef.current?.focus();
    wasConfirming.current = confirming;
  }, [confirming]);

  const groups = GROUPS.map((key) => ({ key, chats: [] as SavedChat[] }));
  for (const c of chats) groups[dayGroup(c.updated_at, now)].chats.push(c);

  return (
    <section className="chats-panel" aria-label={t(lang, "historyTitle")} tabIndex={-1} ref={rootRef}>
      <div className="chats-panel__actions">
        <button type="button" className="btn btn--primary btn--block chats-panel__new" onClick={onNewChat}>
          <Plus size={19} aria-hidden="true" />
          {t(lang, "newChat")}
        </button>
        <button type="button" className="chats-panel__incog" aria-pressed={incognito} onClick={onIncognito}>
          <EyeOff size={18} aria-hidden="true" />
          {t(lang, "incognito")}
        </button>
      </div>

      <div className="chats-panel__list">
        {chats.length === 0 && <p className="chats-panel__empty">{t(lang, "historyEmpty")}</p>}
        {groups
          .filter((g) => g.chats.length > 0)
          .map((g) => (
            <div key={g.key} className="chat-group">
              <h3 className="chat-group__title">{t(lang, g.key)}</h3>
              <ul className="chats">
                {g.chats.map((c) => {
                  const open = c.id === openId;
                  const look = lookOf(c, lang);
                  const title = c.title || "…";
                  return (
                    <li
                      key={c.id}
                      className={open ? "chat-row chat-row--open" : "chat-row"}
                      // right click, or a long press on Android, opens the same menu as ⋮
                      onContextMenu={(e) => {
                        e.preventDefault();
                        setMenuId(c.id);
                      }}
                    >
                      <button
                        type="button"
                        className="chat-row__open"
                        aria-current={open ? "true" : undefined}
                        title={chatTime(c.updated_at, lang, now)}
                        onClick={() => onOpen(c)}
                      >
                        <span className="chat-row__title" lang={DEVANAGARI.test(title) ? "hi" : undefined}>
                          {title}
                        </span>
                        {look.outcome && (
                          <span className={`chat-row__outcome chat-row__outcome--${look.tone}`} lang={DEVANAGARI.test(look.outcome) ? "hi" : undefined}>
                            {look.outcome}
                          </span>
                        )}
                      </button>
                      <RowMenu
                        lang={lang}
                        title={title}
                        open={menuId === c.id}
                        onToggle={(on) => setMenuId(on ? c.id : null)}
                        onDelete={() => {
                          setMenuId(null);
                          onDelete(c.id);
                          rootRef.current?.focus();
                        }}
                      />
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}

        {chats.length > 0 && (
          <div className="history__foot">
            {confirming ? (
              <div
                className="history__confirm"
                role="group"
                aria-labelledby={confirmTitleId}
                onKeyDown={(e) => {
                  if (e.key !== "Escape") return;
                  e.stopPropagation(); // only the confirm step closes, not the drawer
                  setConfirming(false);
                }}
              >
                <strong id={confirmTitleId}>{t(lang, "deleteAllTitle")}</strong>
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
                      rootRef.current?.focus();
                    }}
                  >
                    <Trash2 size={17} aria-hidden="true" />
                    {t(lang, "deleteYes")}
                  </button>
                </div>
              </div>
            ) : (
              <button ref={clearRef} type="button" className="btn btn--quiet history__clear" onClick={() => setConfirming(true)}>
                <Trash2 size={17} aria-hidden="true" />
                {t(lang, "deleteAll")}
              </button>
            )}
          </div>
        )}
        <p className="chats-panel__note">{t(lang, "historySub")}</p>
      </div>
    </section>
  );
}

// ⋮ on a chat row and its one-item menu ("Mitayein"). Escape, a click outside or
// moving focus away closes it.
function RowMenu({
  lang,
  title,
  open,
  onToggle,
  onDelete,
}: {
  lang: Lang;
  title: string;
  open: boolean;
  onToggle: (on: boolean) => void;
  onDelete: () => void;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const itemRef = useRef<HTMLButtonElement>(null);
  // the latest onToggle, so re-renders while open do not re-run the effect (and refocus)
  const toggleRef = useRef(onToggle);
  toggleRef.current = onToggle;

  useEffect(() => {
    if (!open) return;
    itemRef.current?.focus({ preventScroll: true });
    itemRef.current?.scrollIntoView({ block: "nearest" });
    const away = (e: PointerEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) toggleRef.current(false);
    };
    document.addEventListener("pointerdown", away);
    return () => document.removeEventListener("pointerdown", away);
  }, [open]);

  return (
    <div
      className="chat-row__menu"
      ref={wrapRef}
      onBlur={(e) => {
        if (open && e.relatedTarget && !e.currentTarget.contains(e.relatedTarget as Node)) onToggle(false);
      }}
      onKeyDown={(e) => {
        if (e.key !== "Escape" || !open) return;
        e.stopPropagation(); // only the menu closes, not the drawer
        onToggle(false);
        btnRef.current?.focus();
      }}
    >
      <button
        ref={btnRef}
        type="button"
        className="chat-row__more"
        aria-label={`${t(lang, "chatMenu")}: ${title}`}
        title={t(lang, "chatMenu")}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => onToggle(!open)}
      >
        <EllipsisVertical size={18} aria-hidden="true" />
      </button>
      {open && (
        <div className="chat-menu" role="menu" aria-label={title}>
          <button ref={itemRef} type="button" role="menuitem" className="chat-menu__item" onClick={onDelete}>
            <Trash2 size={17} aria-hidden="true" />
            {t(lang, "chatDelete")}
          </button>
        </div>
      )}
    </div>
  );
}

// The chats on phones and tablets: the same panel, sliding in from the left over a
// backdrop. Escape, the backdrop or the cross closes it (focus goes back to ☰ in App).
export function ChatDrawer({ lang, onClose, children }: { lang: Lang; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="drawer-scrim" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="drawer" role="dialog" aria-modal="true" aria-label={t(lang, "historyTitle")} tabIndex={-1} ref={ref}>
        <div className="drawer__head">
          <span className="brand">
            <BrandMark size={30} />
            <span className="brand__name">
              <span>Raahat</span>
            </span>
          </span>
          <button type="button" className="icon-btn" aria-label={t(lang, "close")} title={t(lang, "close")} onClick={onClose}>
            <X size={20} aria-hidden="true" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

// Shown the whole time incognito is on; the cross leaves it (and drops the
// incognito chat), like "Nayi chat". Inverted colours so it reads as a different
// mode in both themes.
export function IncognitoBanner({ lang, onClose }: { lang: Lang; onClose: () => void }) {
  return (
    <div className="incog" role="status">
      <EyeOff size={18} aria-hidden="true" className="incog__icon" />
      <span className="incog__text">{t(lang, "incognitoBanner")}</span>
      <button type="button" className="incog__close" onClick={onClose} aria-label={t(lang, "incognitoOff")} title={t(lang, "incognitoOff")}>
        <X size={18} aria-hidden="true" />
      </button>
    </div>
  );
}

// 0 today, 1 yesterday, 2 earlier (calendar days, like chatTime)
function dayGroup(iso: string, now: Date): 0 | 1 | 2 {
  const w = new Date(iso);
  if (Number.isNaN(w.getTime())) return 2;
  const day = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((day(now) - day(w)) / 86400000);
  return days <= 0 ? 0 : days === 1 ? 1 : 2;
}

// What a chat came to: the line under its title, in its colour.
function lookOf(c: SavedChat, lang: Lang): { outcome: string; tone: "danger" | "brand" | "plain" | "muted" } {
  switch (c.outcome.kind) {
    case "emergency":
      return { outcome: c.outcome.label ?? t(lang, "sosPageTitle"), tone: "danger" };
    case "decision": {
      // the doctor call after nothing was understood is not an outcome to show as care
      const last = [...c.messages].reverse().find((m) => m.type !== "user");
      if (last?.type === "decision" && isUnclear(last.res)) return { outcome: t(lang, "chatUnclear"), tone: "plain" };
      return { outcome: c.outcome.label ?? "", tone: c.outcome.level === 2 ? "danger" : "brand" };
    }
    case "question":
      return { outcome: t(lang, "chatPending"), tone: "plain" };
    default:
      return { outcome: t(lang, "chatNoReply"), tone: "muted" };
  }
}
