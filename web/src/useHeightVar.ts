import { useCallback, useRef } from "react";

// Callback ref that keeps a CSS variable on <html> equal to the element's height
// (0px once it is gone), so sticky bars and scroll margins can stack under it.
export function useHeightVar(name: string) {
  const ro = useRef<ResizeObserver | null>(null);
  return useCallback(
    (el: HTMLElement | null) => {
      ro.current?.disconnect();
      ro.current = null;
      const root = document.documentElement.style;
      if (!el) {
        root.setProperty(name, "0px");
        return;
      }
      const set = () => root.setProperty(name, `${el.offsetHeight}px`);
      set();
      if (typeof ResizeObserver === "undefined") return;
      ro.current = new ResizeObserver(set);
      ro.current.observe(el);
    },
    [name],
  );
}
