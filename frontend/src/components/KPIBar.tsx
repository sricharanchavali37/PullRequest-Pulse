import { Metrics, RiskDist } from "../types";

interface Props {
  metrics: Metrics | null;
  dist:    RiskDist | null;
}

interface KPICardProps {
  label:    string;
  value:    string | number;
  sub?:     string;
  accent?:  "red" | "yellow" | "green" | "blue" | "default";
}

function KPICard({ label, value, sub, accent = "default" }: KPICardProps) {
  return (
    <div className={`kpi-card kpi-${accent}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

export function KPIBar({ metrics, dist }: Props) {
  if (!metrics && !dist) {
    return (
      <div className="kpi-bar">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="kpi-card kpi-skeleton" />
        ))}
      </div>
    );
  }

  const total     = metrics?.total_pull_requests ?? 0;
  const highCount = dist?.high ?? 0;
  const avgRisk   = metrics?.average_risk_score ?? 0;
  const avgSize   = metrics?.average_pr_size ?? 0;
  const highPct   = total > 0 ? Math.round((highCount / total) * 100) : 0;

  const riskAccent =
    avgRisk >= 61 ? "red" :
    avgRisk >= 31 ? "yellow" :
    "green";

  return (
    <div className="kpi-bar">
      <KPICard
        label="Total PRs Analysed"
        value={total}
        sub={`${dist?.low ?? 0} low · ${dist?.medium ?? 0} medium · ${dist?.high ?? 0} high`}
        accent="default"
      />
      <KPICard
        label="High Risk PRs"
        value={highCount}
        sub={`${highPct}% of all PRs`}
        accent={highCount > 0 ? "red" : "default"}
      />
      <KPICard
        label="Avg Risk Score"
        value={avgRisk.toFixed(1)}
        sub="0 = safe · 100 = critical"
        accent={riskAccent}
      />
      <KPICard
        label="Avg PR Size"
        value={Math.round(avgSize)}
        sub="lines changed per PR"
        accent="blue"
      />
    </div>
  );
}
