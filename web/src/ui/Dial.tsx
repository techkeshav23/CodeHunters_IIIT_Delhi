import { useEffect, useState } from "react";
import type { Lang } from "../types";
import { t } from "../i18n";

// The compass dial: one needle, three bands (in a few days / today / now).
// The needle swings from the left once when a decision arrives.
const CX = 110;
const CY = 112;
const R = 86;

function pt(deg: number, r = R): [number, number] {
  const a = (deg * Math.PI) / 180;
  return [CX + r * Math.cos(a), CY - r * Math.sin(a)];
}

function arc(from: number, to: number): string {
  const [x1, y1] = pt(from);
  const [x2, y2] = pt(to);
  return `M ${x1.toFixed(1)} ${y1.toFixed(1)} A ${R} ${R} 0 0 1 ${x2.toFixed(1)} ${y2.toFixed(1)}`;
}

const BANDS = [
  { from: 178, to: 122, color: "var(--brand)" },
  { from: 118, to: 62, color: "var(--haldi)" },
  { from: 58, to: 2, color: "var(--sindoor)" },
];
const ANGLE = [-60, 0, 60];

export default function Dial({ level, lang }: { level: 0 | 1 | 2; lang: Lang }) {
  const [angle, setAngle] = useState(-90);
  useEffect(() => {
    const id = requestAnimationFrame(() => setAngle(ANGLE[level]));
    return () => cancelAnimationFrame(id);
  }, [level]);
  const labels = [t(lang, "urgRoutine"), t(lang, "urgSameDay"), t(lang, "urgNow")];

  return (
    <svg className="dial" viewBox="0 0 220 150" role="img" aria-label={labels[level]}>
      {BANDS.map((b, i) => (
        <path
          key={i}
          d={arc(b.from, b.to)}
          fill="none"
          stroke={b.color}
          strokeWidth={i === level ? 16 : 10}
          strokeLinecap="round"
          opacity={i === level ? 1 : 0.28}
        />
      ))}
      {Array.from({ length: 13 }, (_, i) => {
        const d = 180 - i * 15;
        const [x1, y1] = pt(d, R - 18);
        const [x2, y2] = pt(d, R - (i % 2 ? 22 : 26));
        return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--ink-3)" strokeWidth="1.5" opacity="0.5" />;
      })}
      <g className="dial__needle" style={{ transform: `rotate(${angle}deg)` }}>
        <path d={`M ${CX} ${CY - 70} L ${CX + 7} ${CY} L ${CX - 7} ${CY} Z`} fill="var(--ink)" />
        <path d={`M ${CX} ${CY - 70} L ${CX + 4} ${CY - 40} L ${CX - 4} ${CY - 40} Z`} fill="var(--haldi)" />
      </g>
      <circle cx={CX} cy={CY} r="10" fill="var(--surface)" stroke="var(--ink)" strokeWidth="3" />
      <text x={pt(180)[0] - 2} y={CY + 26} fontSize="11.5" textAnchor="start">
        {labels[0]}
      </text>
      <text x={CX} y="14" fontSize="11.5" textAnchor="middle">
        {labels[1]}
      </text>
      <text x={pt(0)[0] + 2} y={CY + 26} fontSize="11.5" textAnchor="end">
        {labels[2]}
      </text>
    </svg>
  );
}
