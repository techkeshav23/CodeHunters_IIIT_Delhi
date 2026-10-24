// Logo: a compass needle inside a rounded tile. The haldi tip points the way.
export function BrandMark({ size = 34 }: { size?: number }) {
  return (
    <svg className="brand__mark" width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <rect width="40" height="40" rx="12" fill="var(--brand)" />
      <circle cx="20" cy="20" r="12.5" fill="none" stroke="var(--brand-ink)" strokeOpacity="0.35" strokeWidth="1.5" />
      <path d="M20 7.5 L24.2 20 L20 18.6 L15.8 20 Z" fill="var(--haldi)" />
      <path d="M20 32.5 L15.8 20 L20 21.4 L24.2 20 Z" fill="var(--brand-ink)" />
      <circle cx="20" cy="20" r="1.8" fill="var(--brand)" />
    </svg>
  );
}

export function Brand({ onClick }: { onClick?: () => void }) {
  return (
    <button type="button" className="brand" onClick={onClick} style={{ border: 0, background: "none" }}>
      <BrandMark />
      <span className="brand__name">
        Care<span>Compass</span>
      </span>
    </button>
  );
}
