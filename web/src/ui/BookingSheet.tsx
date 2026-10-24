import { useEffect, useRef, useState } from "react";
import { CalendarCheck, CircleCheck, X } from "lucide-react";
import type { Lang } from "../types";
import { t } from "../i18n";
import { createBooking } from "../api";
import { careKey, isRemoteCarer, roleKey, type BookingTarget, type SavedBooking } from "../lib";

interface Props {
  target: BookingTarget;
  lang: Lang;
  locationLabel: string;
  onClose: () => void;
  onBooked: (b: SavedBooking) => void;
  onSeeBookings: () => void;
}

export default function BookingSheet({ target, lang, locationLabel, onClose, onBooked, onSeeBookings }: Props) {
  const { caregiver: cg, res } = target;
  const [note, setNote] = useState("");
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const [saved, setSaved] = useState<SavedBooking | null>(null);
  const sheetRef = useRef<HTMLDivElement>(null);
  const tele = isRemoteCarer(res.care_type, cg.role);
  const fallbackCare = careKey(res.care_type);
  const careLabel =
    res.trace.decision.care_label_local || res.trace.decision.care_label || (fallbackCare ? t(lang, fallbackCare) : null);

  useEffect(() => {
    sheetRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const confirm = async () => {
    setState("busy");
    try {
      const b = await createBooking({
        caregiver_id: cg.caregiver_id,
        slot: cg.next_slot,
        care_type: res.care_type,
        urgency: res.urgency,
        note,
      });
      const s: SavedBooking = {
        booking_id: b.booking_id,
        caregiver_id: cg.caregiver_id,
        caregiver_name: b.caregiver_name || cg.name || cg.caregiver_id,
        role: cg.role,
        slot_label: cg.next_slot_label_local,
        care_label: careLabel,
        urgency_label: res.trace.decision.urgency_label_local,
        created_at: b.created_at,
      };
      setSaved(s);
      onBooked(s);
      setState("done");
    } catch {
      setState("error");
    }
  };

  return (
    <div className="scrim" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title" tabIndex={-1} ref={sheetRef}>
        {state !== "done" ? (
          <>
            <div className="sheet__head">
              <h2 id="sheet-title">{t(lang, "confirmTitle")}</h2>
              <button type="button" className="icon-btn" aria-label={t(lang, "close")} onClick={onClose}>
                <X size={20} />
              </button>
            </div>
            <dl className="kv">
              <dt>{t(lang, "bWho")}</dt>
              <dd>
                {cg.name || cg.caregiver_id}
                {cg.role ? `, ${t(lang, roleKey(cg.role))}` : ""}
              </dd>
              <dt>{t(lang, "bWhen")}</dt>
              <dd>{cg.next_slot_label_local ?? "-"}</dd>
              <dt>{t(lang, "bWhere")}</dt>
              <dd>{tele ? t(lang, "videoCall") : locationLabel}</dd>
              <dt>{t(lang, "bWhat")}</dt>
              <dd>{careLabel ?? "-"}</dd>
            </dl>
            <div className="field">
              <label htmlFor="booking-note">{t(lang, "bNote")}</label>
              <textarea id="booking-note" value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />
            </div>
            {state === "error" && (
              <p className="error" role="alert">
                {t(lang, "bookFailed")}
              </p>
            )}
            <div className="sheet__actions">
              <button type="button" className="btn btn--ghost" onClick={onClose}>
                {t(lang, "back")}
              </button>
              <button type="button" className="btn btn--primary" onClick={confirm} disabled={state === "busy"}>
                <CalendarCheck size={18} aria-hidden="true" />
                {state === "busy" ? t(lang, "booking") : t(lang, "confirm")}
              </button>
            </div>
          </>
        ) : (
          <div className="done" aria-live="polite">
            <div className="done__badge" aria-hidden="true">
              <CircleCheck size={36} />
            </div>
            <h2 id="sheet-title" style={{ fontSize: "1.7rem", fontWeight: 800 }}>
              {t(lang, "booked")}
            </h2>
            <p>{t(lang, "bookedText", { name: cg.name, time: cg.next_slot_label_local ?? "" })}</p>
            <dl className="kv">
              <dt>{t(lang, "bookingId")}</dt>
              <dd className="done__id">{saved?.booking_id}</dd>
            </dl>
            <div className="sheet__actions" style={{ width: "100%" }}>
              <button type="button" className="btn btn--ghost" onClick={onSeeBookings}>
                {t(lang, "seeBookings")}
              </button>
              <button type="button" className="btn btn--primary" onClick={onClose}>
                {t(lang, "close")}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
