import { CheckCircle2, RotateCcw } from "lucide-react";
import type { Lang, BookingResponse } from "../types";
import { t } from "../i18n";

interface Props {
  lang: Lang;
  booking: BookingResponse;
  slotLabel: string | null;
  onRestart: () => void;
}

function formatSlot(slot: string | null, fallback: string | null): string {
  if (fallback) return fallback;
  if (!slot) return "";
  try {
    const d = new Date(slot);
    return d.toLocaleString();
  } catch {
    return slot;
  }
}

export default function Booking({ lang, booking, slotLabel, onRestart }: Props) {
  const dev = lang === "hi" ? "hi" : undefined;
  return (
    <div className="stack" aria-live="polite">
      <div className="done-check">
        <CheckCircle2 size={48} aria-hidden="true" />
      </div>
      <h1 className="tagline" lang={dev}>
        {t(lang, "booked")}
      </h1>
      <p className="muted" style={{ textAlign: "center" }} lang={dev}>
        {t(lang, "bookedConfirm")}
      </p>

      <section className="card">
        <div className="done-row">
          <span className="muted">{t(lang, "withCaregiver")}</span>
          <strong>{booking.caregiver_name}</strong>
        </div>
        <div className="done-row">
          <span className="muted">{t(lang, "nextFree")}</span>
          <strong>{formatSlot(booking.slot, slotLabel)}</strong>
        </div>
        <div className="done-row">
          <span className="muted">{t(lang, "bookingId")}</span>
          <strong>{booking.booking_id}</strong>
        </div>
      </section>

      <button type="button" className="btn btn--primary" onClick={onRestart}>
        <RotateCcw size={20} aria-hidden="true" />
        {t(lang, "restart")}
      </button>
    </div>
  );
}
