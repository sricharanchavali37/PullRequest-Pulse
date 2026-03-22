import { RiskDist } from "../types";

interface DonutProps {
  dist: RiskDist | null;
}

function DonutSegment({
  pct, offset, color, radius = 40, stroke = 10,
}: {
  pct: number; offset: number; color: string;
  radius?: number; stroke?: number;
}) {
  const circ = 2 * Math.PI * radius;
  const dash  = (pct / 100) * circ;
  const gap   = circ - dash;
  // SVG starts at 3 o'clock — rotate to 12 o'clock then advance by offset
  const rotate = -90 + (offset / 100) * 360;
  return (
    <circle
      cx="50" cy="50" r={radius}
      fill="none"
      stroke={color}
      strokeWidth={stroke}
      strokeDasharray={`${dash} ${gap}`}
      strokeDashoffset={0}
      strokeLinecap="butt"
      transform={`rotate(${rotate} 50 50)`}
    />
  );
}

export function RiskChart({ dist }: DonutProps) {
  const total = dist
    ? dist.low + dist.medium + dist.high + dist.unknown
    : 0;

  const pctLow    = total > 0 ? (dist!.low    / total) * 100 : 0;
  const pctMed    = total > 0 ? (dist!.medium / total) * 100 : 0;
  const pctHigh   = total > 0 ? (dist!.high   / total) * 100 : 0;
  const pctUnk    = total > 0 ? (dist!.unknown / total) * 100 : 0;

  const segments = [
    { pct: pctHigh, color: "#f85149", label: "High",    count: dist?.high    ?? 0 },
    { pct: pctMed,  color: "#d29922", label: "Medium",  count: dist?.medium  ?? 0 },
    { pct: pctLow,  color: "#3fb950", label: "Low",     count: dist?.low     ?? 0 },
    { pct: pctUnk,  color: "#484f58", label: "Unknown", count: dist?.unknown ?? 0 },
  ];

  // Compute offsets
  let cursor = 0;
  const drawn = segments.map((s) => {
    const off = cursor;
    cursor += s.pct;
    return { ...s, offset: off };
  });

  return (
    <div className="risk-chart-card">
      <div className="chart-card-title">Risk Distribution</div>

      {total === 0 ? (
        <div className="chart-empty">No data yet</div>
      ) : (
        <div className="donut-layout">
          <svg viewBox="0 0 100 100" className="donut-svg">
            {/* track */}
            <circle cx="50" cy="50" r="40" fill="none"
              stroke="#21262d" strokeWidth="10" />
            {drawn.filter(s => s.pct > 0).map((s) => (
              <DonutSegment
                key={s.label}
                pct={s.pct}
                offset={s.offset}
                color={s.color}
              />
            ))}
            <text x="50" y="46" textAnchor="middle"
              fill="#e6edf3" fontSize="14" fontWeight="700">
              {total}
            </text>
            <text x="50" y="58" textAnchor="middle"
              fill="#8b949e" fontSize="7">
              total PRs
            </text>
          </svg>

          <div className="donut-legend">
            {drawn.filter(s => s.label !== "Unknown" || s.count > 0).map((s) => (
              <div key={s.label} className="legend-row">
                <span className="legend-dot" style={{ background: s.color }} />
                <span className="legend-label">{s.label}</span>
                <span className="legend-count">{s.count}</span>
                <span className="legend-pct">
                  {total > 0 ? `${s.pct.toFixed(0)}%` : "–"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
