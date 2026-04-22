// FE/src/api/trades.js

import { useState, useEffect } from "react";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";

// Converts API decimal strings → JS numbers so all components work unchanged
function normalizeTrade(t) {
  return {
    ...t,
    entry:        Number(t.entry),
    currentPrice: Number(t.currentPrice),
    sl:           Number(t.sl),
    tp:           Number(t.tp),
    profit:       Number(t.profit),
    volume:       Number(t.volume),
  };
}

export async function fetchOpenTrades() {
  const res = await fetch(`${BASE_URL}/trades/?status=open`);
  if (!res.ok) throw new Error(`Trades API error: ${res.status}`);
  const data = await res.json();
  const raw = Array.isArray(data) ? data : data.results ?? [];
  return raw.map(normalizeTrade);   // ← normalize here
}

export async function fetchTradeSummary() {
  const res = await fetch(`${BASE_URL}/trades/summary/`);
  if (!res.ok) throw new Error(`Summary API error: ${res.status}`);
  return res.json();
}

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