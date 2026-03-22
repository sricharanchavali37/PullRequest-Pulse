interface Props {
  score: number;   // 0–100
  label?: string;
}

export function ScoreGauge({ score, label = "Avg Risk Score" }: Props) {
  // Arc from 210° to 330° (210° sweep) — left to right
  const SWEEP = 210;
  const START = 210; // degrees from positive x-axis

  const R  = 38;
  const CX = 50;
  const CY = 54;

  function polarToXY(angleDeg: number) {
    const rad = (angleDeg * Math.PI) / 180;
    return {
      x: CX + R * Math.cos(rad),
      y: CY + R * Math.sin(rad),
    };
  }

  const startAngle = START;
  const endAngle   = START + SWEEP;
  const fillAngle  = START + (score / 100) * SWEEP;

  const trackStart = polarToXY(startAngle);
  const trackEnd   = polarToXY(endAngle);
  const fillEnd    = polarToXY(fillAngle);

  const trackLarge = SWEEP > 180 ? 1 : 0;
  const fillLarge  = (score / 100) * SWEEP > 180 ? 1 : 0;

  const trackPath = [
    `M ${trackStart.x} ${trackStart.y}`,
    `A ${R} ${R} 0 ${trackLarge} 1 ${trackEnd.x} ${trackEnd.y}`,
  ].join(" ");

  const fillPath = score > 0 ? [
    `M ${trackStart.x} ${trackStart.y}`,
    `A ${R} ${R} 0 ${fillLarge} 1 ${fillEnd.x} ${fillEnd.y}`,
  ].join(" ") : "";

  const color =
    score >= 61 ? "#f85149" :
    score >= 31 ? "#d29922" :
    "#3fb950";

  const level =
    score >= 61 ? "HIGH" :
    score >= 31 ? "MEDIUM" :
    "LOW";

  return (
    <div className="gauge-card">
      <div className="chart-card-title">{label}</div>
      <svg viewBox="0 0 100 80" className="gauge-svg">
        {/* Track */}
        <path d={trackPath} fill="none" stroke="#21262d"
          strokeWidth="9" strokeLinecap="round" />
        {/* Fill */}
        {fillPath && (
          <path d={fillPath} fill="none" stroke={color}
            strokeWidth="9" strokeLinecap="round" />
        )}
        {/* Score number */}
        <text x={CX} y={CY - 4} textAnchor="middle"
          fill="#e6edf3" fontSize="18" fontWeight="700">
          {score.toFixed(0)}
        </text>
        {/* Level label */}
        <text x={CX} y={CY + 10} textAnchor="middle"
          fill={color} fontSize="7" fontWeight="700" letterSpacing="1">
          {level}
        </text>
        {/* Min / Max */}
        <text x={trackStart.x - 2} y={trackStart.y + 4}
          textAnchor="middle" fill="#484f58" fontSize="6">0</text>
        <text x={trackEnd.x + 2} y={trackEnd.y + 4}
          textAnchor="middle" fill="#484f58" fontSize="6">100</text>
      </svg>
      <div className="gauge-sub">
        Risk scoring: files × size × breaking changes × config edits
      </div>
    </div>
  );
}
