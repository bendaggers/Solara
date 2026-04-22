// FE/src/api/trades.js
// Drop this file into your FE/src/api/ folder.
// Replace the static `import { TRADES } from "../data/trades"` in Trades.jsx
// with the hooks/functions below.

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";

// ── Raw fetch helpers ─────────────────────────────────────────────────────────

export async function fetchOpenTrades() {
  const res = await fetch(`${BASE_URL}/trades/?status=open`);
  if (!res.ok) throw new Error(`Trades API error: ${res.status}`);
  const data = await res.json();
  // DRF returns { count, next, previous, results } when pagination is on
  return Array.isArray(data) ? data : data.results ?? [];
}

export async function fetchTradeSummary() {
  const res = await fetch(`${BASE_URL}/trades/summary/`);
  if (!res.ok) throw new Error(`Summary API error: ${res.status}`);
  return res.json();
}

export async function fetchAllTrades(status = null, symbol = null) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (symbol) params.set("symbol", symbol);
  const res = await fetch(`${BASE_URL}/trades/?${params}`);
  if (!res.ok) throw new Error(`Trades API error: ${res.status}`);
  const data = await res.json();
  return Array.isArray(data) ? data : data.results ?? [];
}

// ── React hook (optional) ─────────────────────────────────────────────────────
// Usage in Trades.jsx:
//   import { useTrades } from "../api/trades";
//   const { trades, summary, loading, error } = useTrades();

import { useState, useEffect } from "react";

export function useTrades(pollIntervalMs = 0) {
  const [trades,  setTrades]  = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  async function load() {
    try {
      const [t, s] = await Promise.all([fetchOpenTrades(), fetchTradeSummary()]);
      setTrades(t);
      setSummary(s);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    if (pollIntervalMs > 0) {
      const id = setInterval(load, pollIntervalMs);
      return () => clearInterval(id);
    }
  }, [pollIntervalMs]);

  return { trades, summary, loading, error, refetch: load };
}
