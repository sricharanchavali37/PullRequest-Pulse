import { RiskFilter } from "../types";

interface Props {
  active:   RiskFilter;
  search:   string;
  counts:   Record<RiskFilter, number>;
  onChange: (f: RiskFilter) => void;
  onSearch: (s: string) => void;
}

const FILTERS: { key: RiskFilter; label: string }[] = [
  { key: "ALL",    label: "All"    },
  { key: "HIGH",   label: "High"   },
  { key: "MEDIUM", label: "Medium" },
  { key: "LOW",    label: "Low"    },
];

export function FilterBar({ active, search, counts, onChange, onSearch }: Props) {
  return (
    <div className="filter-bar">
      <div className="filter-buttons">
        {FILTERS.map(({ key, label }) => (
          <button
            key={key}
            className={`filter-btn filter-btn-${key.toLowerCase()} ${active === key ? "active" : ""}`}
            onClick={() => onChange(key)}
          >
            {label}
            <span className="filter-count">{counts[key]}</span>
          </button>
        ))}
      </div>

      <div className="filter-search">
        <svg className="search-icon" viewBox="0 0 16 16" fill="none">
          <circle cx="6.5" cy="6.5" r="4.5" stroke="#8b949e" strokeWidth="1.5"/>
          <path d="M10 10l3 3" stroke="#8b949e" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
        <input
          type="text"
          placeholder="Filter by author…"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          className="search-input"
        />
        {search && (
          <button className="search-clear" onClick={() => onSearch("")}>✕</button>
        )}
      </div>
    </div>
  );
}
