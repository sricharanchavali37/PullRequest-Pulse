import { useEffect, useState, useRef } from "react";
import { PR, ConnectionStatus } from "./types";
import { PRCard } from "./components/PRCard";
import { StatusBar } from "./components/StatusBar";

// In development, Vite proxies /api → http://localhost:8001
// In Docker, frontend container talks directly to api container
const API_BASE =
  import.meta.env.VITE_API_URL ?? "http://localhost:8001";

export default function App() {
  const [prs, setPRs]           = useState<PR[]>([]);
  const [status, setStatus]     = useState<ConnectionStatus>("connecting");
  const [newIds, setNewIds]     = useState<Set<number>>(new Set());
  const [repoId, setRepoId]     = useState<string | null>(null);
  const esRef                   = useRef<EventSource | null>(null);

  // ── Step 1: Load existing PRs from REST API on mount ──────────────────────
  useEffect(() => {
    async function loadInitialData() {
      try {
        // Get repos list
        const repoRes = await fetch(`${API_BASE}/repos`);
        if (!repoRes.ok) return;
        const repos = await repoRes.json();
        if (!repos || repos.length === 0) return;

        // Use the first repo
        const repo = repos[0];
        setRepoId(repo.id);

        // Get PRs for that repo
        const prRes = await fetch(`${API_BASE}/repos/${repo.id}/prs?limit=50`);
        if (!prRes.ok) return;
        const data = await prRes.json();

        // Map DB response shape to our PR type
        const loaded: PR[] = (data.items ?? []).map((item: any) => ({
          pr_number:     item.pr_number,
          author:        item.author ?? "unknown",
          risk_score:    item.risk_score ?? 0,
          risk_level:    item.risk_level ?? "LOW",
          files_changed: item.files_changed ?? 0,
          lines_added:   item.lines_added ?? 0,
          lines_removed: item.lines_removed ?? 0,
          repo_owner:    repo.owner,
          repo_name:     repo.name,
        }));

        // Newest first
        setPRs(loaded.reverse());
      } catch (err) {
        console.error("Failed to load initial PRs:", err);
      }
    }

    loadInitialData();
  }, []);

  // ── Step 2: Open SSE connection for live updates ───────────────────────────
  useEffect(() => {
    const url = `${API_BASE}/events/stream`;
    const es  = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      setStatus("connected");
    };

    es.onerror = () => {
      setStatus("disconnected");
      // EventSource reconnects automatically — status updates when it does
    };

    es.onmessage = (event) => {
      try {
        const pr: PR = JSON.parse(event.data);

        // Mark this PR as "new" for 3 seconds (triggers highlight animation)
        setNewIds((prev) => new Set(prev).add(pr.pr_number));
        setTimeout(() => {
          setNewIds((prev) => {
            const next = new Set(prev);
            next.delete(pr.pr_number);
            return next;
          });
        }, 3000);

        // Prepend new PR — if it already exists, replace it
        setPRs((prev) => {
          const without = prev.filter((p) => p.pr_number !== pr.pr_number);
          return [pr, ...without];
        });
      } catch (err) {
        console.error("Failed to parse SSE event:", err);
      }
    };

    return () => {
      es.close();
    };
  }, []);

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="header-title">
            <span className="logo">PRPulse</span>
            <span className="logo-sub">Pull Request Intelligence</span>
          </div>
          <StatusBar status={status} prs={prs} />
        </div>
      </header>

      <main className="main">
        {prs.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📭</div>
            <div className="empty-title">No pull requests yet</div>
            <div className="empty-sub">
              Open a pull request on your GitHub repo.<br />
              It will appear here within a few seconds.
            </div>
          </div>
        ) : (
          <div className="pr-grid">
            {prs.map((pr) => (
              <PRCard
                key={pr.pr_number}
                pr={pr}
                isNew={newIds.has(pr.pr_number)}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
