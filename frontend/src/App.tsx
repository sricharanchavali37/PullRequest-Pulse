import { useEffect, useState, useCallback } from "react";
import {
  PR, Repo, Metrics, RiskDistResponse, RiskDist,
  RiskFilter, ConnectionStatus,
} from "./types";
import { KPIBar }     from "./components/KPIBar";
import { RiskChart }  from "./components/RiskChart";
import { ScoreGauge } from "./components/ScoreGauge";
import { FilterBar }  from "./components/FilterBar";
import { PRCard }     from "./components/PRCard";
import { LiveFeed }   from "./components/LiveFeed";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8001";

export default function App() {
  // ── Data state ──────────────────────────────────────────────────────────────
  const [prs,      setPRs]      = useState<PR[]>([]);
  const [repo,     setRepo]     = useState<Repo | null>(null);
  const [metrics,  setMetrics]  = useState<Metrics | null>(null);
  const [dist,     setDist]     = useState<RiskDist | null>(null);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState<string | null>(null);

  // ── SSE state ───────────────────────────────────────────────────────────────
  const [status,    setStatus]    = useState<ConnectionStatus>("connecting");
  const [newIds,    setNewIds]    = useState<Set<number>>(new Set());
  const [lastEvent, setLastEvent] = useState<string | null>(null);

  // ── UI state ────────────────────────────────────────────────────────────────
  const [filter, setFilter] = useState<RiskFilter>("ALL");
  const [search, setSearch] = useState("");

  // ── Load all initial data from REST API ────────────────────────────────────
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // 1. Repos
      const reposRes = await fetch(`${API}/repos`);
      if (!reposRes.ok) throw new Error("Failed to load repositories");
      const repos: Repo[] = await reposRes.json();
      if (!repos.length) { setLoading(false); return; }
      const r = repos[0];
      setRepo(r);

      // 2. PRs, metrics, risk-distribution — all in parallel
      const [prRes, metRes, distRes] = await Promise.all([
        fetch(`${API}/repos/${r.id}/prs?limit=100`),
        fetch(`${API}/repos/${r.id}/metrics`),
        fetch(`${API}/repos/${r.id}/risk-distribution`),
      ]);

      if (prRes.ok) {
        const data = await prRes.json();
        const loaded: PR[] = (data.items ?? []).map((item: any) => ({
          pr_number:     item.pr_number,
          author:        item.author        ?? "unknown",
          risk_score:    item.risk_score    ?? 0,
          risk_level:    (item.risk_level   ?? "LOW").toUpperCase(),
          files_changed: item.files_changed ?? 0,
          lines_added:   item.lines_added   ?? 0,
          lines_removed: item.lines_removed ?? 0,
          repo_owner:    r.owner,
          repo_name:     r.name,
          created_at:    item.created_at,
        }));
        setPRs(loaded);
      }

      if (metRes.ok) {
        const m: Metrics = await metRes.json();
        setMetrics(m);
      }

      if (distRes.ok) {
        const d: RiskDistResponse = await distRes.json();
        setDist(d.distribution);
      }

    } catch (err: any) {
      setError(err.message ?? "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // ── SSE — live PR feed ─────────────────────────────────────────────────────
  useEffect(() => {
    const es = new EventSource(`${API}/events/stream`);

    es.onopen = () => setStatus("connected");

    es.onerror = () => {
      setStatus("disconnected");
      // EventSource auto-reconnects; status will update on next onopen
    };

    es.onmessage = (event) => {
      try {
        const pr: PR = {
          ...JSON.parse(event.data),
          risk_level: (JSON.parse(event.data).risk_level ?? "LOW").toUpperCase(),
        };

        // Flash "new" highlight for 4 seconds
        setNewIds((prev) => new Set(prev).add(pr.pr_number));
        setTimeout(() => {
          setNewIds((prev) => {
            const next = new Set(prev);
            next.delete(pr.pr_number);
            return next;
          });
        }, 4000);

        // Prepend, dedup by pr_number
        setPRs((prev) => [pr, ...prev.filter((p) => p.pr_number !== pr.pr_number)]);

        // Update last-event strip
        setLastEvent(`PR #${pr.pr_number} · ${pr.risk_level} · @${pr.author}`);

        // Refresh metrics and dist counts
        if (repo) {
          Promise.all([
            fetch(`${API}/repos/${repo.id}/metrics`),
            fetch(`${API}/repos/${repo.id}/risk-distribution`),
          ]).then(async ([mr, dr]) => {
            if (mr.ok) setMetrics(await mr.json());
            if (dr.ok) {
              const d: RiskDistResponse = await dr.json();
              setDist(d.distribution);
            }
          });
        }
      } catch { /* malformed event — ignore */ }
    };

    return () => es.close();
  }, [repo]);

  // ── Filter + search ────────────────────────────────────────────────────────
  const visible = prs.filter((pr) => {
    const levelMatch =
      filter === "ALL" || pr.risk_level === filter;
    const searchMatch =
      !search || pr.author.toLowerCase().includes(search.toLowerCase());
    return levelMatch && searchMatch;
  });

  const counts: Record<RiskFilter, number> = {
    ALL:    prs.length,
    HIGH:   prs.filter((p) => p.risk_level === "HIGH").length,
    MEDIUM: prs.filter((p) => p.risk_level === "MEDIUM").length,
    LOW:    prs.filter((p) => p.risk_level === "LOW").length,
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="app">

      {/* ── Navbar ────────────────────────────────────────────────────────── */}
      <nav className="navbar">
        <div className="navbar-inner">
          <div className="navbar-brand">
            <span className="brand-logo">PRPulse</span>
            <span className="brand-tag">Pull Request Intelligence</span>
          </div>
          {repo && (
            <div className="navbar-repo">
              <svg viewBox="0 0 16 16" className="repo-icon" fill="#8b949e">
                <path d="M2 2.5A2.5 2.5 0 014.5 0h8.75a.75.75 0 01.75.75v12.5a.75.75 0 01-.75.75h-2.5a.75.75 0 010-1.5h1.75v-2h-8a1 1 0 00-.714 1.7.75.75 0 01-1.072 1.05A2.495 2.495 0 012 11.5v-9zm10.5-1V9h-8c-.356 0-.694.074-1 .208V2.5a1 1 0 011-1h8zM5 12.25v3.25a.25.25 0 00.4.2l1.45-1.087a.25.25 0 01.3 0L8.6 15.7a.25.25 0 00.4-.2v-3.25a.25.25 0 00-.25-.25h-3.5a.25.25 0 00-.25.25z"/>
              </svg>
              <span className="repo-name">{repo.owner}/{repo.name}</span>
            </div>
          )}
        </div>
      </nav>

      {/* ── Live feed strip ───────────────────────────────────────────────── */}
      <LiveFeed status={status} lastEvent={lastEvent} />

      <main className="main">

        {/* ── Error state ─────────────────────────────────────────────────── */}
        {error && (
          <div className="error-banner">
            <strong>Could not load data:</strong> {error}
            <button onClick={loadData} className="retry-btn">Retry</button>
          </div>
        )}

        {/* ── KPI bar ─────────────────────────────────────────────────────── */}
        <KPIBar metrics={metrics} dist={dist} />

        {/* ── Charts row ──────────────────────────────────────────────────── */}
        <div className="charts-row">
          <RiskChart  dist={dist} />
          <ScoreGauge score={metrics?.average_risk_score ?? 0} />
        </div>

        {/* ── Filter + search ─────────────────────────────────────────────── */}
        <FilterBar
          active={filter}
          search={search}
          counts={counts}
          onChange={setFilter}
          onSearch={setSearch}
        />

        {/* ── PR grid ─────────────────────────────────────────────────────── */}
        {loading ? (
          <div className="skeleton-grid">
            {[0,1,2,3].map((i) => (
              <div key={i} className="pr-card-skeleton" />
            ))}
          </div>
        ) : visible.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">
              {prs.length === 0 ? "📭" : "🔍"}
            </div>
            <div className="empty-title">
              {prs.length === 0
                ? "No pull requests yet"
                : "No PRs match this filter"}
            </div>
            <div className="empty-sub">
              {prs.length === 0
                ? "Open a pull request on your GitHub repo.\nIt will appear here within seconds."
                : "Try a different risk level or clear the author search."}
            </div>
            {prs.length > 0 && (
              <button className="clear-btn"
                onClick={() => { setFilter("ALL"); setSearch(""); }}>
                Clear filters
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="results-count">
              Showing {visible.length} of {prs.length} pull requests
            </div>
            <div className="pr-grid">
              {visible.map((pr) => (
                <PRCard
                  key={pr.pr_number}
                  pr={pr}
                  isNew={newIds.has(pr.pr_number)}
                />
              ))}
            </div>
          </>
        )}

      </main>
    </div>
  );
}
