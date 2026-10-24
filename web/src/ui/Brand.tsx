// Logo: a caring hand under a heartbeat, with a location pin (public/logo-mark.png),
// on a white rounded tile so it reads in light and dark themes.
export function BrandMark({ size = 34 }: { size?: number }) {
  return (
    <img
      className="brand__mark"
      src="/logo-mark.png"
      width={size}
      height={size}
      alt=""
      aria-hidden="true"
      style={{ borderRadius: Math.round(size * 0.28), background: "#fff", objectFit: "contain" }}
    />
  );
}

export function Brand({ onClick }: { onClick?: () => void }) {
  return (
    <button type="button" className="brand" onClick={onClick} style={{ border: 0, background: "none" }}>
      <BrandMark />
      <span className="brand__name">
        <span>Raahat</span>
      </span>
    </button>
  );
}
