import { PR } from "../types";

interface Props {
  pr: PR;
  isNew?: boolean;
}

function RiskBadge({ level }: { level: string }) {
  const styles: Record<string, string> = {
    HIGH:   "badge badge-high",
    MEDIUM: "badge badge-medium",
    LOW:    "badge badge-low",
  };
  return (
    <span className={styles[level] ?? "badge badge-low"}>
      {level}
    </span>
  );
}

export function PRCard({ pr, isNew = false }: Props) {
  const totalLines = pr.lines_added + pr.lines_removed;

  return (
    <div className={`pr-card ${isNew ? "pr-card-new" : ""}`}>
      <div className="pr-card-header">
        <span className="pr-number">#{pr.pr_number}</span>
        <RiskBadge level={pr.risk_level} />
      </div>

      <div className="pr-meta">
        <span className="pr-author">@{pr.author}</span>
        <span className="pr-repo">{pr.repo_owner}/{pr.repo_name}</span>
      </div>

      <div className="pr-stats">
        <span className="stat">
          <span className="stat-label">Files</span>
          <span className="stat-value">{pr.files_changed}</span>
        </span>
        <span className="stat">
          <span className="stat-label">Lines</span>
          <span className="stat-value">{totalLines}</span>
        </span>
        <span className="stat">
          <span className="stat-label">+Added</span>
          <span className="stat-value stat-green">+{pr.lines_added}</span>
        </span>
        <span className="stat">
          <span className="stat-label">−Removed</span>
          <span className="stat-value stat-red">−{pr.lines_removed}</span>
        </span>
        <span className="stat">
          <span className="stat-label">Score</span>
          <span className="stat-value">{pr.risk_score}</span>
        </span>
      </div>
    </div>
  );
}
