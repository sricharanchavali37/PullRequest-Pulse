import { ConnectionStatus, PR } from "../types";

interface Props {
  status:   ConnectionStatus;
  prs:      PR[];
}

export function StatusBar({ status, prs }: Props) {
  const total  = prs.length;
  const high   = prs.filter((p) => p.risk_level === "HIGH").length;
  const medium = prs.filter((p) => p.risk_level === "MEDIUM").length;
  const low    = prs.filter((p) => p.risk_level === "LOW").length;

  const dot =
    status === "connected"    ? "dot dot-green"   :
    status === "connecting"   ? "dot dot-yellow"  :
                                "dot dot-red";

  const label =
    status === "connected"    ? "Live"         :
    status === "connecting"   ? "Connecting…"  :
                                "Disconnected";

  return (
    <div className="status-bar">
      <div className="status-left">
        <span className={dot}></span>
        <span className="status-label">{label}</span>
      </div>

      <div className="status-stats">
        <span className="stat-pill stat-total">{total} PRs</span>
        {high   > 0 && <span className="stat-pill stat-high">{high} High</span>}
        {medium > 0 && <span className="stat-pill stat-medium">{medium} Medium</span>}
        {low    > 0 && <span className="stat-pill stat-low">{low} Low</span>}
      </div>
    </div>
  );
}
