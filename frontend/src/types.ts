// Types that match exactly what the API returns

export interface PR {
  pr_number:    number;
  author:       string;
  risk_score:   number;
  risk_level:   "LOW" | "MEDIUM" | "HIGH" | string;
  files_changed: number;
  lines_added:   number;
  lines_removed: number;
  repo_owner:   string;
  repo_name:    string;
}

export interface Repo {
  id:         string;
  name:       string;
  owner:      string;
  created_at: string;
}

export type ConnectionStatus = "connecting" | "connected" | "disconnected";
