#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

PIP_SIZE = 0.0001
TP_PIPS = 40
SL_PIPS = 30
TRAILING_RULES = [(15, 0), (20, 10), (30, 20)]

@dataclass
class Trade:
    entry_index:int; entry_time:str; exit_index:int; exit_time:str; side:str
    entry_price:float; exit_price:float; stop_price_initial:float; stop_price_final:float
    take_profit_price:float; pnl_pips:float; outcome:str; bars_held:int
    max_favorable_excursion_pips:float; threshold_15_reached:bool
    threshold_20_reached:bool; threshold_30_reached:bool

def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    for col in df.columns:
        c = col.strip().lower()
        rename_map[col] = "timestamp" if c in {"timestamp","datetime","date","time"} else c
    df = df.rename(columns=rename_map)
    required = ["timestamp","open","high","low","close","upper_band","bb_position","rsi_value",
                "session","previous_touches","time_since_last_touch","price_momentum","support_distance_pct"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Found: {list(df.columns)}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    num_cols = ["open","high","low","close","upper_band","bb_position","rsi_value",
                "previous_touches","time_since_last_touch","price_momentum","support_distance_pct"]
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["session"] = df["session"].astype(str).str.strip().str.lower()
    return df.dropna(subset=["timestamp"] + num_cols).sort_values("timestamp").reset_index(drop=True)

def pips_from_price_diff(diff: float) -> float: return diff / PIP_SIZE

def price_from_pips(pips: float) -> float: return pips * PIP_SIZE

def overextension_pass(a: pd.Series, mode: str, min_bb_position_a: float) -> bool:
    base_touch = (a["high"] >= a["upper_band"]) or (a["bb_position"] >= min_bb_position_a)
    if mode == "touch_only": return bool(base_touch)
    if mode == "high_above_ubb": return bool((a["high"] > a["upper_band"]) and base_touch)
    if mode == "close_above_ubb": return bool((a["close"] > a["upper_band"]) and base_touch)
    raise ValueError(f"Unknown overextension_mode: {mode}")

def context_filters_pass(c: pd.Series, params: Dict[str, Any]) -> bool:
    if params["allowed_sessions"] and c["session"] not in params["allowed_sessions"]: return False
    if c["previous_touches"] < params["min_previous_touches"]: return False
    if c["time_since_last_touch"] < params["min_time_since_last_touch"]: return False
    if c["price_momentum"] < params["min_price_momentum"]: return False
    if c["price_momentum"] > params["max_price_momentum"]: return False
    if c["support_distance_pct"] < params["min_support_distance_pct"]: return False
    if c["support_distance_pct"] > params["max_support_distance_pct"]: return False
    return True

def short_signal(df: pd.DataFrame, i: int, params: Dict[str, Any]) -> bool:
    if i < 2: return False
    a = df.iloc[i - 2]; b = df.iloc[i - 1]; c = df.iloc[i]
    cond_overext = overextension_pass(a, params["h4_overextension_mode"], params["h4_min_bb_position_a"])
    cond_b = (b["close"] < a["close"]) and (b["high"] <= a["high"])
    cond_rsi = a["rsi_value"] >= params["h4_min_rsi_a"]
    cond_context = context_filters_pass(c, params)
    return bool(cond_overext and cond_b and cond_rsi and cond_context)

def compute_next_stop(entry_price: float, lowest_price_seen: float, current_stop: float) -> float:
    profit_pips = pips_from_price_diff(entry_price - lowest_price_seen)
    desired_stop = current_stop
    for trigger_pips, lock_pips in TRAILING_RULES:
        if profit_pips >= trigger_pips:
            desired_stop = min(desired_stop, entry_price - price_from_pips(lock_pips))
    return desired_stop

def backtest(df: pd.DataFrame, params: Dict[str, Any]) -> List[Trade]:
    trades: List[Trade] = []; in_trade = False
    entry_index: Optional[int] = None
    entry_price = initial_stop = current_stop = take_profit = lowest_price_seen = None
    hit_15 = hit_20 = hit_30 = False
    i = 0; n = len(df)
    while i < n:
        row = df.iloc[i]
        if not in_trade:
            if short_signal(df, i, params):
                entry_index = i
                entry_price = float(row["open"])
                initial_stop = entry_price + price_from_pips(SL_PIPS)
                current_stop = initial_stop
                take_profit = entry_price - price_from_pips(TP_PIPS)
                lowest_price_seen = entry_price
                hit_15 = hit_20 = hit_30 = False
                in_trade = True
            i += 1; continue
        high_i = float(row["high"]); low_i = float(row["low"])
        sl_hit = high_i >= current_stop; tp_hit = low_i <= take_profit
        exit_price = None; outcome = None
        if sl_hit and tp_hit: exit_price, outcome = current_stop, "SL_and_TP_same_bar_assume_SL_first"
        elif sl_hit: exit_price, outcome = current_stop, "SL"
        elif tp_hit: exit_price, outcome = take_profit, "TP"
        if exit_price is not None:
            pnl_pips = pips_from_price_diff(entry_price - exit_price)
            mfe_pips = pips_from_price_diff(entry_price - lowest_price_seen)
            trades.append(Trade(entry_index, str(df.iloc[entry_index]["timestamp"]), i, str(row["timestamp"]), "SHORT",
                                entry_price, exit_price, initial_stop, current_stop, take_profit,
                                round(pnl_pips,2), outcome, i-entry_index+1, round(mfe_pips,2),
                                hit_15, hit_20, hit_30))
            in_trade = False
            entry_index = entry_price = initial_stop = current_stop = take_profit = lowest_price_seen = None
            i += 1; continue
        lowest_price_seen = min(lowest_price_seen, low_i)
        profit_pips_now = pips_from_price_diff(entry_price - lowest_price_seen)
        bars_held_now = i - entry_index + 1
        if profit_pips_now >= 15: hit_15 = True
        if profit_pips_now >= 20: hit_20 = True
        if profit_pips_now >= 30: hit_30 = True
        if bars_held_now >= params["follow_through_bars"] and profit_pips_now < params["min_follow_through_pips"]:
            exit_price = float(row["close"])
            pnl_pips = pips_from_price_diff(entry_price - exit_price)
            trades.append(Trade(entry_index, str(df.iloc[entry_index]["timestamp"]), i, str(row["timestamp"]), "SHORT",
                                entry_price, exit_price, initial_stop, current_stop, take_profit,
                                round(pnl_pips,2), "EARLY_EXIT_WEAK_FOLLOW_THROUGH", bars_held_now, round(profit_pips_now,2),
                                hit_15, hit_20, hit_30))
            in_trade = False
            entry_index = entry_price = initial_stop = current_stop = take_profit = lowest_price_seen = None
            i += 1; continue
        if bars_held_now >= params["max_bars_in_trade"]:
            exit_price = float(row["close"])
            pnl_pips = pips_from_price_diff(entry_price - exit_price)
            trades.append(Trade(entry_index, str(df.iloc[entry_index]["timestamp"]), i, str(row["timestamp"]), "SHORT",
                                entry_price, exit_price, initial_stop, current_stop, take_profit,
                                round(pnl_pips,2), "TIME_EXIT_MAX_BARS", bars_held_now, round(profit_pips_now,2),
                                hit_15, hit_20, hit_30))
            in_trade = False
            entry_index = entry_price = initial_stop = current_stop = take_profit = lowest_price_seen = None
            i += 1; continue
        current_stop = compute_next_stop(entry_price, lowest_price_seen, current_stop)
        i += 1
    return trades

def summarize_trades(trades: List[Trade]) -> pd.DataFrame:
    return pd.DataFrame([asdict(t) for t in trades])

def compute_performance(trades_df: pd.DataFrame) -> dict:
    if trades_df.empty:
        return {"total_trades":0,"wins":0,"losses":0,"win_rate_pct":0.0,"net_pips":0.0,
                "avg_pips_per_trade":0.0,"profit_factor":np.nan,"max_drawdown_pips":0.0,"expectancy_pips":0.0}
    pnl = trades_df["pnl_pips"].astype(float)
    wins = pnl[pnl > 0]; losses = pnl[pnl <= 0]
    equity = pnl.cumsum(); running_peak = equity.cummax(); drawdown = equity - running_peak
    gross_profit = wins.sum(); gross_loss_abs = abs(losses.sum())
    return {
        "total_trades": int(len(trades_df)),
        "wins": int((pnl > 0).sum()),
        "losses": int((pnl <= 0).sum()),
        "win_rate_pct": round((pnl > 0).mean() * 100.0, 2),
        "net_pips": round(pnl.sum(), 2),
        "avg_pips_per_trade": round(pnl.mean(), 2),
        "profit_factor": round(gross_profit / gross_loss_abs, 3) if gross_loss_abs > 0 else np.nan,
        "max_drawdown_pips": round(abs(drawdown.min()), 2),
        "expectancy_pips": round(pnl.mean(), 2),
    }

def run_single(df: pd.DataFrame, params: Dict[str, Any]) -> Tuple[pd.DataFrame, dict]:
    trades_df = summarize_trades(backtest(df, params))
    return trades_df, compute_performance(trades_df)

def evaluate_combo(task: Tuple[pd.DataFrame, Dict[str, Any], int]) -> Dict[str, Any]:
    df, params, idx = task
    _, metrics = run_single(df, params)
    return {"combo_index": idx, "allowed_sessions": ",".join(sorted(params["allowed_sessions"])) if params["allowed_sessions"] else "all", **params, **metrics}

def optimize_parallel(df: pd.DataFrame, workers: int, log_every: int) -> pd.DataFrame:
    session_sets = [tuple(), ("london",), ("new york",), ("asia",), ("london","new york")]
    previous_touches_vals = [0.0, 1.0, 2.0]
    time_since_vals = [0.0, 1.0, 3.0]
    momentum_bands = [(-1e9,1e9), (-1e9,0.0), (0.0,1e9)]
    support_bands = [(0.0,1e9), (0.5,1e9), (1.0,1e9)]
    tasks = []
    for idx, (sess, prev_t, tslt, mom, sup) in enumerate(product(session_sets, previous_touches_vals, time_since_vals, momentum_bands, support_bands), start=1):
        params = {
            "h4_min_rsi_a":55.0, "h4_overextension_mode":"close_above_ubb", "h4_min_bb_position_a":85.0,
            "max_bars_in_trade":10, "follow_through_bars":2, "min_follow_through_pips":3.0,
            "allowed_sessions": set(sess), "min_previous_touches":prev_t, "min_time_since_last_touch":tslt,
            "min_price_momentum":mom[0], "max_price_momentum":mom[1],
            "min_support_distance_pct":sup[0], "max_support_distance_pct":sup[1],
        }
        tasks.append((df, params, idx))
    total = len(tasks)
    print(f"\nStarting H4 context optimizer with {workers} worker(s)")
    print(f"Total combinations: {total}")
    print(f"Progress log frequency: every {log_every} completed job(s)")
    rows = []; started = time.time()
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(evaluate_combo, task): task[2] for task in tasks}
        completed = 0
        for future in as_completed(futures):
            result = future.result(); rows.append(result); completed += 1
            if (completed % log_every == 0) or (completed == total):
                elapsed = time.time() - started; rate = completed / elapsed if elapsed > 0 else 0.0; eta = (total-completed)/rate if rate > 0 else float("nan")
                print(f"[{completed}/{total}] done | combo=#{result['combo_index']} | sessions={result['allowed_sessions']} | prev_touch>={result['min_previous_touches']} | time_since>={result['min_time_since_last_touch']} | momentum=({result['min_price_momentum']},{result['max_price_momentum']}) | support=({result['min_support_distance_pct']},{result['max_support_distance_pct']}) | PF={result['profit_factor']} | Exp={result['expectancy_pips']} | Trades={result['total_trades']} | Elapsed={elapsed:.1f}s | ETA={eta:.1f}s")
    res = pd.DataFrame(rows)
    return res.sort_values(by=["profit_factor","expectancy_pips","total_trades","max_drawdown_pips","net_pips"], ascending=[False,False,False,True,False]).reset_index(drop=True)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--sessions", type=str, default="")
    parser.add_argument("--min-previous-touches", type=float, default=0.0)
    parser.add_argument("--min-time-since-last-touch", type=float, default=0.0)
    parser.add_argument("--min-price-momentum", type=float, default=-1e9)
    parser.add_argument("--max-price-momentum", type=float, default=1e9)
    parser.add_argument("--min-support-distance-pct", type=float, default=0.0)
    parser.add_argument("--max-support-distance-pct", type=float, default=1e9)
    parser.add_argument("--optimize", action="store_true")
    parser.add_argument("--workers", type=int, default=max(1, min(6, os.cpu_count() or 1)))
    parser.add_argument("--log-every", type=int, default=5)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--output", type=str, default="")
    args = parser.parse_args()
    df = standardize_columns(pd.read_csv(Path(args.data)))
    if args.optimize:
        results = optimize_parallel(df, max(1, args.workers), max(1, args.log_every))
        print("\n===== H4 CONTEXT OPTIMIZER TOP RESULTS =====")
        print(results.head(args.top).to_string(index=False))
        if args.output:
            results.to_csv(Path(args.output), index=False)
            print(f"\nOptimization results saved to: {args.output}")
        return
    allowed_sessions = {s.strip().lower() for s in args.sessions.split(",") if s.strip()}
    params = {
        "h4_min_rsi_a":55.0, "h4_overextension_mode":"close_above_ubb", "h4_min_bb_position_a":85.0,
        "max_bars_in_trade":10, "follow_through_bars":2, "min_follow_through_pips":3.0,
        "allowed_sessions": allowed_sessions, "min_previous_touches":args.min_previous_touches,
        "min_time_since_last_touch":args.min_time_since_last_touch, "min_price_momentum":args.min_price_momentum,
        "max_price_momentum":args.max_price_momentum, "min_support_distance_pct":args.min_support_distance_pct,
        "max_support_distance_pct":args.max_support_distance_pct,
    }
    trades_df, metrics = run_single(df, params)
    print("\n===== BACKTEST RESULTS =====")
    print(f"params.allowed_sessions: {sorted(allowed_sessions) if allowed_sessions else 'all'}")
    for k, v in params.items():
        if k != "allowed_sessions": print(f"params.{k}: {v}")
    for k, v in metrics.items(): print(f"{k}: {v}")
    if not trades_df.empty: print("\nSample trades:\n" + trades_df.head(10).to_string(index=False))
    else: print("\nNo trades found.")
    if args.output:
        trades_df.to_csv(Path(args.output), index=False)
        print(f"\nTrade log saved to: {args.output}")

if __name__ == "__main__":
    main()
