import type { Lang } from "../types";
import { t } from "../i18n";

export default function Footer({ lang }: { lang: Lang }) {
  return (
    <footer className="footer" lang={lang === "hi" ? "hi" : undefined}>
      {t(lang, "footer")}
    </footer>
  );
}
