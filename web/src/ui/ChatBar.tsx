import { useLayoutEffect, useRef, useState, type RefObject } from "react";
import { EyeOff, History, Plus, X } from "lucide-react";
import type { Lang } from "../types";
import { t } from "../i18n";

interface Props {
  lang: Lang;
  count: number;
  threadOpen: boolean;
  incognito: boolean;
  onHistory: () => void;
  onIncognito: () => void;
  onNewChat: () => void;
  historyRef?: RefObject<HTMLButtonElement>;
}

// One action of the bar. `keep` orders which labels fold first when the row is
// too narrow (lowest first); the icon (History: with its count) always stays.
interface Item {
  id: "history" | "incognito" | "new";
  icon: typeof History;
  label: string;
  badge?: string;
  primary?: boolean;
  keep: number;
  onClick: () => void;
}

const GAP = 8; // px between buttons, and the least room between the two sides

// History on the left; Incognito and New chat on the right (same as the Android
// app). Labels fold into icons (with a tooltip) when the row would not fit: a
// narrow phone, large text or a longer language.
export function ChatBar(p: Props) {
  const history: Item = {
    id: "history",
    icon: History,
    label: t(p.lang, "history"),
    badge: p.count > 0 ? String(p.count) : undefined,
    keep: 0,
    onClick: p.onHistory,
  };
  const right: Item[] = [];
  if (!p.incognito) {
    right.push({
      id: "incognito",
      icon: EyeOff,
      label: t(p.lang, p.threadOpen ? "incognitoShort" : "incognito"),
      keep: 1,
      onClick: p.onIncognito,
    });
  }
  if (p.threadOpen) {
    right.push({ id: "new", icon: Plus, label: t(p.lang, "newChat"), primary: true, keep: 2, onClick: p.onNewChat });
  }
  const items = [history, ...right];

  const barRef = useRef<HTMLDivElement>(null);
  const measureRef = useRef<HTMLDivElement>(null);
  // ids whose label is folded, e.g. "history,incognito"
  const [folded, setFolded] = useState("");
  const sig = items.map((it) => `${it.id}:${it.label}:${it.badge ?? ""}`).join("|");

  useLayoutEffect(() => {
    const bar = barRef.current;
    const m = measureRef.current;
    if (!bar || !m) return;
    const fit = () => {
      const width = (sel: string) => Array.from(m.querySelectorAll<HTMLElement>(sel), (el) => el.getBoundingClientRect().width);
      const full = width("[data-full]");
      const bare = width("[data-bare]");
      const show = items.map(() => true);
      const total = () => items.reduce((sum, _, i) => sum + (show[i] ? full[i] : bare[i]) + GAP, 0);
      const order = items.map((_, i) => i).sort((a, b) => items[a].keep - items[b].keep);
      for (const i of order) {
        if (total() <= bar.clientWidth) break;
        show[i] = false;
      }
      const next = items.filter((_, i) => !show[i]).map((it) => it.id).join(",");
      setFolded((prev) => (prev === next ? prev : next));
    };
    fit();
    let alive = true;
    // again once the web fonts are in (Devanagari labels are wider than the fallback)
    document.fonts?.ready.then(() => alive && fit());
    window.addEventListener("resize", fit);
    // the bar's width, and the labels' own width
    const ro = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(fit);
    ro?.observe(bar);
    ro?.observe(m);
    return () => {
      alive = false;
      window.removeEventListener("resize", fit);
      ro?.disconnect();
    };
  }, [sig]); // the items only change when their labels or count do; text size is set in
  // Settings, where this bar is not shown, so it is measured afresh on the way back

  const isFolded = (it: Item) => folded.split(",").includes(it.id);

  return (
    <div className="chatbar" ref={barRef}>
      {/* the same buttons with and without labels, unseen, to measure what fits */}
      <div className="chatbar__measure" aria-hidden="true">
        <div ref={measureRef}>
          {items.map((it) => (
            <span key={it.id} className="chatbar__measure-pair">
              <span data-full className={btnClass(it)}>
                <it.icon size={16} />
                <span className="chatbar__label">{it.label}</span>
                {it.badge && <span className="chatbar__badge">{it.badge}</span>}
              </span>
              <span data-bare className={btnClass(it)}>
                <it.icon size={16} />
                {it.badge && <span className="chatbar__badge">{it.badge}</span>}
              </span>
            </span>
          ))}
        </div>
      </div>
      <BarButton item={history} folded={isFolded(history)} btnRef={p.historyRef} />
      {right.length > 0 && (
        <div className="chatbar__right">
          {right.map((it) => (
            <BarButton key={it.id} item={it} folded={isFolded(it)} />
          ))}
        </div>
      )}
    </div>
  );
}

function btnClass(it: Item): string {
  return it.primary ? "chatbar__btn chatbar__btn--primary" : "chatbar__btn";
}

function BarButton({ item, folded, btnRef }: { item: Item; folded: boolean; btnRef?: RefObject<HTMLButtonElement> }) {
  const name = item.badge ? `${item.label} (${item.badge})` : item.label;
  return (
    <button
      ref={btnRef}
      type="button"
      className={btnClass(item)}
      data-action={item.id}
      onClick={item.onClick}
      aria-label={name}
      title={folded ? name : undefined}
    >
      <item.icon size={16} aria-hidden="true" />
      {!folded && <span className="chatbar__label">{item.label}</span>}
      {item.badge && (
        <span className="chatbar__badge" aria-hidden="true">
          {item.badge}
        </span>
      )}
    </button>
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
