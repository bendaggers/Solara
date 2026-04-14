import { useEffect } from "react";
import TypeBadge from "./TypeBadge";
import { SYMBOL_COLORS } from "../data/trades";
import "./TradeModal.css";

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

const fmtProfit = (v) =>
  v >= 0 ? `+$${v.toFixed(2)}` : `-$${Math.abs(v).toFixed(2)}`;
const fmtPips = (v) =>
  parseFloat(v) >= 0 ? `+${v} pips` : `${v} pips`;

export default function TradeModal({ trade, onClose }) {
  if (!trade) return null;

  const pips     = pipValue(trade);
  const pipsNum  = parseFloat(pips);
  const color    = SYMBOL_COLORS[trade.symbol] || "#94a3b8";

  /* Close on Escape key */
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  /* Prevent body scroll while open */
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, []);

  return (
    <div className="tm-backdrop" onClick={onClose}>
      <div className="tm-modal" onClick={(e) => e.stopPropagation()}>

        {/* ── Header ── */}
        <div className="tm-header" style={{ borderTopColor: color }}>
          <div className="tm-header-left">
            <span
              className="tm-symbol-badge"
              style={{ background: `${color}18`, color, borderColor: `${color}40` }}
            >
              {trade.symbol}
            </span>
            <div>
              <div className="tm-ticket">Ticket #{trade.ticket}</div>
              <div className="tm-opened">Opened {trade.time}</div>
            </div>
          </div>
          <div className="tm-header-right">
            <TypeBadge type={trade.type} />
            <button className="tm-close" onClick={onClose} aria-label="Close">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
        </div>

        {/* ── P&L Hero ── */}
        <div className="tm-pnl-hero">
          <div className="tm-pnl-block">
            <span className="tm-pnl-label">Floating P&L</span>
            <span className={`tm-pnl-value ${trade.profit >= 0 ? "pos" : "neg"}`}>
              {fmtProfit(trade.profit)}
            </span>
          </div>
          <div className="tm-pnl-divider" />
          <div className="tm-pnl-block">
            <span className="tm-pnl-label">Profit in Pips</span>
            <span className={`tm-pnl-value ${pipsNum >= 0 ? "pos" : "neg"}`}>
              {fmtPips(pips)}
            </span>
          </div>
        </div>

        {/* ── Detail grid ── */}
        <div className="tm-body">

          <div className="tm-section-label">Position</div>
          <div className="tm-grid">
            <div className="tm-field">
              <span className="tm-field-key">Volume</span>
              <span className="tm-field-val mono">{trade.volume.toFixed(2)} lots</span>
            </div>
            <div className="tm-field">
              <span className="tm-field-key">Entry Price</span>
              <span className="tm-field-val mono">{trade.entry.toFixed(5)}</span>
            </div>
            <div className="tm-field">
              <span className="tm-field-key">Market Price</span>
              <span className="tm-field-val mono">{trade.currentPrice.toFixed(5)}</span>
            </div>
          </div>

          <div className="tm-section-label">Risk Levels</div>
          <div className="tm-grid">
            <div className="tm-field">
              <span className="tm-field-key">Stop Loss</span>
              <span className="tm-field-val mono sl">{trade.sl.toFixed(5)}</span>
            </div>
            <div className="tm-field">
              <span className="tm-field-key">Take Profit</span>
              <span className="tm-field-val mono tp">{trade.tp.toFixed(5)}</span>
            </div>
          </div>

          <div className="tm-section-label">Metadata</div>
          <div className="tm-grid">
            <div className="tm-field">
              <span className="tm-field-key">Magic Number</span>
              <span className="tm-field-val mono muted">{trade.magic}</span>
            </div>
            <div className="tm-field tm-field--full">
              <span className="tm-field-key">Comment</span>
              <span className="tm-field-val">
                <span className="comment-tag">{trade.comment}</span>
              </span>
            </div>
          </div>

        </div>

        {/* ── Footer ── */}
        <div className="tm-footer">
          <span className="tm-footer-hint">Press <kbd>Esc</kbd> or click outside to close</span>
        </div>

      </div>
    </div>
  );
}
