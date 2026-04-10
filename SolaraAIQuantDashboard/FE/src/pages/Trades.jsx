import { useState, useMemo, useRef, useEffect } from "react";
import StatCard from "../components/StatCard";
import TypeBadge from "../components/TypeBadge";
import { TRADES, SYMBOL_COLORS } from "../data/trades";
import "./Trades.css";

/* ── Helpers ── */
const pipValue = (trade) => {
  const diff = trade.type === "buy"
    ? trade.currentPrice - trade.entry
    : trade.entry - trade.currentPrice;
  const isJpy = trade.symbol.includes("JPY");
  const isXau = trade.symbol.includes("XAU");
  const multiplier = isJpy ? 100 : isXau ? 10 : 10000;
  return (diff * multiplier).toFixed(1);
};

const fmtProfit = (v) => v >= 0 ? `+$${v.toFixed(2)}` : `-$${Math.abs(v).toFixed(2)}`;
const fmtPips   = (v) => parseFloat(v) >= 0 ? `+${v}` : `${v}`;

/* ── Column definitions ──
   defaultVisible: true  → shown on first load
   defaultVisible: false → hidden, user can enable via panel
*/
const COLUMNS = [
  { key: "symbol",       label: "Symbol",         defaultVisible: true,  noSort: false },
  { key: "type",         label: "Type",            defaultVisible: true,  noSort: false },
  { key: "volume",       label: "Volume",          defaultVisible: true,  noSort: false },
  { key: "entry",        label: "Entry Price",     defaultVisible: true,  noSort: false },
  { key: "profit",       label: "Profit",          defaultVisible: true,  noSort: false },
  { key: "_pips",        label: "Profit in Pips",  defaultVisible: true,  noSort: true  },
  { key: "currentPrice", label: "Market Price",    defaultVisible: true,  noSort: false },
  // hidden by default
  { key: "ticket",       label: "Ticket",          defaultVisible: false, noSort: false },
  { key: "time",         label: "Open Time",       defaultVisible: false, noSort: false },
  { key: "sl",           label: "SL",              defaultVisible: false, noSort: false },
  { key: "tp",           label: "TP",              defaultVisible: false, noSort: false },
  { key: "magic",        label: "Magic",           defaultVisible: false, noSort: false },
  { key: "comment",      label: "Comment",         defaultVisible: false, noSort: true  },
];

const DEFAULT_VISIBILITY = Object.fromEntries(
  COLUMNS.map((c) => [c.key, c.defaultVisible])
);

export default function Trades() {
  const [search,     setSearch]     = useState("");
  const [filter,     setFilter]     = useState("all");
  const [sortCol,    setSortCol]    = useState("symbol");
  const [sortDir,    setSortDir]    = useState("asc");
  const [visibility, setVisibility] = useState(DEFAULT_VISIBILITY);
  const [panelOpen,  setPanelOpen]  = useState(false);

  const panelRef = useRef(null);
  const btnRef   = useRef(null);

  // Close panel on outside click
  useEffect(() => {
    function onOutside(e) {
      if (
        panelOpen &&
        panelRef.current && !panelRef.current.contains(e.target) &&
        btnRef.current  && !btnRef.current.contains(e.target)
      ) {
        setPanelOpen(false);
      }
    }
    document.addEventListener("mousedown", onOutside);
    return () => document.removeEventListener("mousedown", onOutside);
  }, [panelOpen]);

  const toggleCol   = (key) => setVisibility(v => ({ ...v, [key]: !v[key] }));
  const resetCols   = ()    => setVisibility(DEFAULT_VISIBILITY);

  const visibleCols = COLUMNS.filter(c => visibility[c.key]);
  const hiddenCount = COLUMNS.filter(c => !visibility[c.key]).length;

  /* ── Stats ── */
  const totalProfit = TRADES.reduce((a, t) => a + t.profit, 0);
  const winners     = TRADES.filter(t => t.profit > 0).length;
  const losers      = TRADES.filter(t => t.profit < 0).length;
  const winRate     = ((winners / TRADES.length) * 100).toFixed(1);
  const totalVol    = TRADES.reduce((a, t) => a + t.volume, 0).toFixed(2);

  /* ── Filtered + sorted rows ── */
  const rows = useMemo(() => {
    let d = [...TRADES];
    if (search) d = d.filter(r =>
      r.symbol.toLowerCase().includes(search.toLowerCase()) ||
      String(r.ticket).includes(search) ||
      r.comment.toLowerCase().includes(search.toLowerCase())
    );
    if (filter !== "all") d = d.filter(r => r.type === filter);
    d.sort((a, b) => {
      let av = a[sortCol], bv = b[sortCol];
      if (av === undefined || bv === undefined) return 0;
      if (typeof av === "string") { av = av.toLowerCase(); bv = bv.toLowerCase(); }
      return sortDir === "asc" ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1);
    });
    return d;
  }, [search, filter, sortCol, sortDir]);

  const handleSort = (key) => {
    if (sortCol === key) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortCol(key); setSortDir("asc"); }
  };

  /* ── Cell renderer ── */
  const renderCell = (col, t, bg) => {
    const pips    = pipValue(t);
    const pipsNum = parseFloat(pips);

    switch (col.key) {
      case "symbol":
        return (
          <td key="symbol" style={{ background: bg }}>
            <div className="cell-symbol">
              <span className="symbol-dot" style={{ background: SYMBOL_COLORS[t.symbol] || "#94a3b8" }} />
              {t.symbol}
            </div>
          </td>
        );
      case "type":
        return <td key="type" style={{ background: bg }}><TypeBadge type={t.type} /></td>;
      case "volume":
        return <td key="volume" style={{ background: bg }}>{t.volume.toFixed(2)}</td>;
      case "entry":
        return <td key="entry" style={{ background: bg }}>{t.entry.toFixed(5)}</td>;
      case "profit":
        return (
          <td key="profit" style={{ background: bg }} className={t.profit >= 0 ? "cell-profit-pos" : "cell-profit-neg"}>
            {fmtProfit(t.profit)}
          </td>
        );
      case "_pips":
        return (
          <td key="_pips" style={{ background: bg }} className={pipsNum >= 0 ? "cell-pips-pos" : "cell-pips-neg"}>
            {fmtPips(pips)} pips
          </td>
        );
      case "currentPrice":
        return <td key="currentPrice" style={{ background: bg }}>{t.currentPrice.toFixed(5)}</td>;
      case "ticket":
        return <td key="ticket" style={{ background: bg }} className="cell-muted">#{t.ticket}</td>;
      case "time":
        return <td key="time" style={{ background: bg }} className="cell-time">{t.time}</td>;
      case "sl":
        return <td key="sl" style={{ background: bg }} className="cell-sl">{t.sl.toFixed(5)}</td>;
      case "tp":
        return <td key="tp" style={{ background: bg }} className="cell-tp">{t.tp.toFixed(5)}</td>;
      case "magic":
        return <td key="magic" style={{ background: bg }} className="cell-muted">{t.magic}</td>;
      case "comment":
        return (
          <td key="comment" style={{ background: bg }}>
            <span className="comment-tag">{t.comment}</span>
          </td>
        );
      default:
        return <td key={col.key} style={{ background: bg }}>—</td>;
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="trades-header">
        <div>
          <h1 className="trades-title">Open Trades</h1>
          <p className="trades-subtitle">Real-time monitoring · {TRADES.length} active positions</p>
        </div>
        <div className="live-badge">🟢 Live · Updated just now</div>
      </div>

      {/* Stat Cards */}
      <div className="stats-row">
        <StatCard icon="📂" label="Total Trades"  value={TRADES.length}          sub={`${winners} win · ${losers} loss`}       accent="#3b82f6" />
        <StatCard icon="💰" label="Floating P&L"  value={fmtProfit(totalProfit)}  sub="USD net profit"                          accent={totalProfit >= 0 ? "#16a34a" : "#dc2626"} />
        <StatCard icon="🎯" label="Win Rate"       value={`${winRate}%`}           sub={`${winners} of ${TRADES.length} trades`} accent="#8b5cf6" />
        <StatCard icon="📦" label="Total Volume"   value={`${totalVol} lots`}      sub="across all positions"                   accent="#f59e0b" />
      </div>

      {/* Table Card */}
      <div className="table-card">

        {/* Toolbar */}
        <div className="table-toolbar">
          <div className="search-box">
            <span className="search-icon">🔍</span>
            <input
              className="search-input"
              placeholder="Search symbol, ticket, comment…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>

          <div className="filter-group">
            {[["all","All"],["buy","▲ Buy"],["sell","▼ Sell"]].map(([v, lbl]) => (
              <button
                key={v}
                className={`filter-btn ${filter === v ? "active" : "inactive"}`}
                onClick={() => setFilter(v)}
              >
                {lbl}
              </button>
            ))}
          </div>

          <span className="row-count">{rows.length} of {TRADES.length} rows</span>

          {/* Column toggle button */}
          <div className="col-toggle-wrapper">
            <button
              ref={btnRef}
              className={`col-toggle-btn ${panelOpen ? "col-toggle-btn--open" : ""}`}
              onClick={() => setPanelOpen(v => !v)}
              title="Show / hide columns"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
                <rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
              </svg>
              Columns
              {hiddenCount > 0 && (
                <span className="col-hidden-badge">{hiddenCount}</span>
              )}
            </button>

            {panelOpen && (
              <div className="col-panel" ref={panelRef}>
                <div className="col-panel-header">
                  <span>Manage Columns</span>
                  <button className="col-reset-btn" onClick={resetCols}>Reset</button>
                </div>

                <div className="col-section-label">Default columns</div>
                {COLUMNS.filter(c => c.defaultVisible).map(col => (
                  <label key={col.key} className="col-row">
                    <span className="col-checkbox-wrap">
                      <input type="checkbox" checked={!!visibility[col.key]} onChange={() => toggleCol(col.key)} />
                      <span className="col-checkmark">
                        {visibility[col.key] && (
                          <svg width="9" height="9" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="2,6 5,9 10,3"/>
                          </svg>
                        )}
                      </span>
                    </span>
                    <span className="col-row-label">{col.label}</span>
                  </label>
                ))}

                <div className="col-panel-divider" />

                <div className="col-section-label">Optional columns</div>
                {COLUMNS.filter(c => !c.defaultVisible).map(col => (
                  <label key={col.key} className="col-row">
                    <span className="col-checkbox-wrap">
                      <input type="checkbox" checked={!!visibility[col.key]} onChange={() => toggleCol(col.key)} />
                      <span className="col-checkmark">
                        {visibility[col.key] && (
                          <svg width="9" height="9" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="2,6 5,9 10,3"/>
                          </svg>
                        )}
                      </span>
                    </span>
                    <span className="col-row-label">{col.label}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Table */}
        <div className="table-wrap">
          <table className="trades-table">
            <thead>
              <tr>
                {visibleCols.map(col => (
                  <th
                    key={col.key}
                    onClick={() => !col.noSort && handleSort(col.key)}
                    style={{ cursor: col.noSort ? "default" : "pointer" }}
                  >
                    {col.label}
                    {!col.noSort && (
                      <span className="sort-icon" style={{ opacity: sortCol === col.key ? 0.8 : 0.25 }}>
                        {sortCol === col.key ? (sortDir === "asc" ? "↑" : "↓") : "↕"}
                      </span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((t, i) => {
                const bg = i % 2 === 0 ? "#fff" : "#fafbfd";
                return (
                  <tr key={t.ticket}>
                    {visibleCols.map(col => renderCell(col, t, bg))}
                  </tr>
                );
              })}
              {rows.length === 0 && (
                <tr className="no-results">
                  <td colSpan={visibleCols.length}>No trades match your filter.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Footer */}
        <div className="table-footer">
          <span className="footer-text">Showing {rows.length} trades</span>
          <div className="footer-pnl">
            <span className="footer-text">Net Floating P&L:</span>
            <span className={`pnl-value ${totalProfit >= 0 ? "pnl-pos" : "pnl-neg"}`}>
              {fmtProfit(totalProfit)}
            </span>
          </div>
        </div>

      </div>
    </div>
  );
}
