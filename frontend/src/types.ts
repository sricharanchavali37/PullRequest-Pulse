export interface PR {
  pr_number:     number;
  author:        string;
  risk_score:    number;
  risk_level:    "LOW" | "MEDIUM" | "HIGH" | string;
  files_changed: number;
  lines_added:   number;
  lines_removed: number;
  repo_owner:    string;
  repo_name:     string;
  created_at?:   string;
}

export interface Repo {
  id:         string;
  name:       string;
  owner:      string;
  created_at: string;
}

export interface Metrics {
  repository_id:       string;
  total_pull_requests: number;
  average_pr_size:     number;
  average_risk_score:  number;
  high_risk_pr_count:  number;
  merged_pr_count:     number;
}

export interface RiskDist {
  low:     number;
  medium:  number;
  high:    number;
  unknown: number;
}

export interface RiskDistResponse {
  repository_id: string;
  distribution:  RiskDist;
}

export type RiskFilter       = "ALL" | "HIGH" | "MEDIUM" | "LOW";
export type ConnectionStatus = "connecting" | "connected" | "disconnected";
