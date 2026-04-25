import type { PellProration as PellProrationData } from "../types";

interface Props {
  data: PellProrationData;
}

const TIER_WIDTHS: Record<string, number> = {
  "full-time": 100,
  "three-quarter-time": 75,
  "half-time": 50,
  "less-than-half-time": 25,
};

const TIER_COLORS: Record<string, string> = {
  "full-time": "var(--color-success)",
  "three-quarter-time": "var(--color-warning)",
  "half-time": "var(--color-warning)",
  "less-than-half-time": "var(--color-danger)",
};

export default function PellProration({ data }: Props) {
  const barWidth = TIER_WIDTHS[data.enrollment_tier] ?? 0;
  const barColor = TIER_COLORS[data.enrollment_tier] ?? "var(--color-danger)";

  return (
    <div className="pell-banner">
      <div className="pell-banner__header">
        <span>🎓 Pell Grant Award Estimate</span>
        <span className="pell-banner__pct">{data.percentage_display}</span>
      </div>

      <div className="pell-bar-track">
        <div
          className="pell-bar-fill"
          style={{ width: `${barWidth}%`, background: barColor }}
        />
        {[25, 50, 75, 100].map((mark) => (
          <span key={mark} className="pell-bar-mark" style={{ left: `${mark}%` }}>
            {mark}%
          </span>
        ))}
      </div>

      <p className="pell-banner__note">{data.note}</p>
    </div>
  );
}
