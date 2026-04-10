#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

PIP_SIZE = 0.0001
TP_PIPS = 40
SL_PIPS = 30
TRAILING_RULES = [(15, 0), (20, 10), (30, 20)]


@dataclass
class Trade:
    entry_index: int
    entry_time: str
    exit_index: int
    exit_time: str
    side: str
    entry_price: float
    exit_price: float
    stop_price_initial: float
    stop_price_final: float
    take_profit_price: float
    pnl_pips: float
    outcome: str
    bars_held: int
    max_favorable_excursion_pips: float
    threshold_15_reached: bool
    threshold_20_reached: bool
    threshold_30_reached: bool


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    for col in df.columns:
        c = col.strip().lower()
        rename_map[col] = "timestamp" if c in {"timestamp", "datetime", "date", "time"} else c
    df = df.rename(columns=rename_map)

    required = [
        "timestamp", "open", "high", "low", "close",
        "upper_band", "lower_band", "middle_band",
        "bb_position", "rsi_value",
        "previous_touches", "time_since_last_touch",
        "price_momentum", "support_distance_pct", "session",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    numeric_cols = [c for c in required if c not in {"timestamp", "session"}]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["session"] = df["session"].astype(str).str.strip().str.lower()

    return (
        df.dropna(subset=["timestamp"] + numeric_cols)
          .sort_values("timestamp")
          .reset_index(drop=True)
    )


def validate_time_order_and_infer_step(df: pd.DataFrame) -> pd.Timedelta:
    ts = df["timestamp"]
    if not ts.is_monotonic_increasing:
        raise ValueError("Timestamps are not strictly increasing after preprocessing.")
    diffs = ts.diff().dropna()
    if diffs.empty:
        raise ValueError("Not enough rows to infer timeframe.")
    if (diffs <= pd.Timedelta(0)).any():
        raise ValueError("Duplicate or non-increasing timestamps detected.")
    return diffs.mode().iloc[0]


def are_consecutive_triplet(df: pd.DataFrame, i: int, expected_step: pd.Timedelta) -> bool:
    if i < 2:
        return False
    t_a = df.iloc[i - 2]["timestamp"]
    t_b = df.iloc[i - 1]["timestamp"]
    t_c = df.iloc[i]["timestamp"]
    return bool((t_b - t_a == expected_step) and (t_c - t_b == expected_step))


def upper_wick_size(row: pd.Series) -> float:
    return float(row["high"] - max(row["open"], row["close"]))


def candle_range(row: pd.Series) -> float:
    return float(max(row["high"] - row["low"], 1e-10))


def no_upper_wick_bearish_rejection(a: pd.Series, near_bb_threshold: float, max_upper_wick_pct: float) -> bool:
    wick_pct = upper_wick_size(a) / candle_range(a)
    return bool((a["bb_position"] >= near_bb_threshold) and (a["close"] < a["open"]) and (wick_pct <= max_upper_wick_pct))


def candle_a_event_type(a: pd.Series, near_bb_threshold: float, max_upper_wick_pct: float) -> str:
    if a["close"] > a["upper_band"]:
        return "close_above_ubb"
    if a["high"] >= a["upper_band"]:
        return "high_touch_ubb"
    if no_upper_wick_bearish_rejection(a, near_bb_threshold, max_upper_wick_pct):
        return "no_upper_wick_bear_reject_near_ubb"
    if a["bb_position"] >= near_bb_threshold:
        return "near_upper_bb_fail_break"
    return "none"


def overextension_pass(a: pd.Series, mode: str, min_bb_position_a: float, near_bb_threshold: float, max_upper_wick_pct: float) -> bool:
    event_type = candle_a_event_type(a, near_bb_threshold, max_upper_wick_pct)
    if mode == "strict_close_above_ubb":
        return bool((a["close"] > a["upper_band"]) and ((a["high"] >= a["upper_band"]) or (a["bb_position"] >= min_bb_position_a)))
    if mode == "broad_bb_event":
        return bool(event_type != "none")
    if mode == "touch_only":
        return bool((a["high"] >= a["upper_band"]) or (a["bb_position"] >= min_bb_position_a))
    raise ValueError(f"Unknown overextension_mode: {mode}")


def context_filters_pass(c: pd.Series, params: Dict[str, Any]) -> bool:
    if params["allowed_sessions"] and c["session"] not in params["allowed_sessions"]:
        return False
    if c["previous_touches"] < params["min_previous_touches"]:
        return False
    if c["time_since_last_touch"] < params["min_time_since_last_touch"]:
        return False
    if c["price_momentum"] < params["min_price_momentum"]:
        return False
    if c["price_momentum"] > params["max_price_momentum"]:
        return False
    if c["support_distance_pct"] < params["min_support_distance_pct"]:
        return False
    if c["support_distance_pct"] > params["max_support_distance_pct"]:
        return False
    return True


def short_signal(df: pd.DataFrame, i: int, params: Dict[str, Any], expected_step: pd.Timedelta) -> bool:
    if not are_consecutive_triplet(df, i, expected_step):
        return False
    a = df.iloc[i - 2]
    b = df.iloc[i - 1]
    c = df.iloc[i]
    cond_overext = overextension_pass(a, params["h4_overextension_mode"], params["h4_min_bb_position_a"], params["near_bb_threshold"], params["max_upper_wick_pct"])
    cond_b = (b["close"] < a["close"]) and ((not params["require_b_high_not_break"]) or (b["high"] <= a["high"]))
    cond_rsi = a["rsi_value"] >= params["h4_min_rsi_a"]
    cond_context = context_filters_pass(c, params)
    return bool(cond_overext and cond_b and cond_rsi and cond_context)


def pips_from_price_diff(diff: float) -> float:
    return diff / PIP_SIZE


def price_from_pips(pips: float) -> float:
    return pips * PIP_SIZE


def compute_next_stop(entry_price: float, lowest_price_seen: float, current_stop: float) -> float:
    profit_pips = pips_from_price_diff(entry_price - lowest_price_seen)
    desired_stop = current_stop
    for trigger_pips, lock_pips in TRAILING_RULES:
        if profit_pips >= trigger_pips:
            desired_stop = min(desired_stop, entry_price - price_from_pips(lock_pips))
    return desired_stop


def backtest(df: pd.DataFrame, params: Dict[str, Any], expected_step: pd.Timedelta) -> List[Trade]:
    trades: List[Trade] = []
    in_trade = False
    entry_index: Optional[int] = None
    entry_price = initial_stop = current_stop = take_profit = lowest_price_seen = None
    hit_15 = hit_20 = hit_30 = False
    i = 0
    n = len(df)

    while i < n:
        row = df.iloc[i]
        if not in_trade:
            if short_signal(df, i, params, expected_step):
                entry_index = i
                entry_price = float(row["open"])
                initial_stop = entry_price + price_from_pips(SL_PIPS)
                current_stop = initial_stop
                take_profit = entry_price - price_from_pips(TP_PIPS)
                lowest_price_seen = entry_price
                hit_15 = hit_20 = hit_30 = False
                in_trade = True
            i += 1
            continue

        high_i = float(row["high"])
        low_i = float(row["low"])
        sl_hit = high_i >= current_stop
        tp_hit = low_i <= take_profit
        exit_price = None
        outcome = None

        if sl_hit and tp_hit:
            exit_price, outcome = current_stop, "SL_and_TP_same_bar_assume_SL_first"
        elif sl_hit:
            exit_price, outcome = current_stop, "SL"
        elif tp_hit:
            exit_price, outcome = take_profit, "TP"

        if exit_price is not None:
            pnl_pips = pips_from_price_diff(entry_price - exit_price)
            mfe_pips = pips_from_price_diff(entry_price - lowest_price_seen)
            trades.append(Trade(entry_index, str(df.iloc[entry_index]["timestamp"]), i, str(row["timestamp"]), "SHORT", entry_price, exit_price, initial_stop, current_stop, take_profit, round(pnl_pips, 2), outcome, i - entry_index + 1, round(mfe_pips, 2), hit_15, hit_20, hit_30))
            in_trade = False
            entry_index = entry_price = initial_stop = current_stop = take_profit = lowest_price_seen = None
            i += 1
            continue

        lowest_price_seen = min(lowest_price_seen, low_i)
        profit_pips_now = pips_from_price_diff(entry_price - lowest_price_seen)
        bars_held_now = i - entry_index + 1

        if profit_pips_now >= 15:
            hit_15 = True
        if profit_pips_now >= 20:
            hit_20 = True
        if profit_pips_now >= 30:
            hit_30 = True

        if bars_held_now >= params["follow_through_bars"] and profit_pips_now < params["min_follow_through_pips"]:
            exit_price = float(row["close"])
            pnl_pips = pips_from_price_diff(entry_price - exit_price)
            trades.append(Trade(entry_index, str(df.iloc[entry_index]["timestamp"]), i, str(row["timestamp"]), "SHORT", entry_price, exit_price, initial_stop, current_stop, take_profit, round(pnl_pips, 2), "EARLY_EXIT_WEAK_FOLLOW_THROUGH", bars_held_now, round(profit_pips_now, 2), hit_15, hit_20, hit_30))
            in_trade = False
            entry_index = entry_price = initial_stop = current_stop = take_profit = lowest_price_seen = None
            i += 1
            continue

        if bars_held_now >= params["max_bars_in_trade"]:
            exit_price = float(row["close"])
            pnl_pips = pips_from_price_diff(entry_price - exit_price)
            trades.append(Trade(entry_index, str(df.iloc[entry_index]["timestamp"]), i, str(row["timestamp"]), "SHORT", entry_price, exit_price, initial_stop, current_stop, take_profit, round(pnl_pips, 2), "TIME_EXIT_MAX_BARS", bars_held_now, round(profit_pips_now, 2), hit_15, hit_20, hit_30))
            in_trade = False
            entry_index = entry_price = initial_stop = current_stop = take_profit = lowest_price_seen = None
            i += 1
            continue

        current_stop = compute_next_stop(entry_price, lowest_price_seen, current_stop)
        i += 1

    return trades


def summarize_trades(trades: List[Trade]) -> pd.DataFrame:
    return pd.DataFrame([asdict(t) for t in trades])


def compute_performance(trades_df: pd.DataFrame) -> dict:
    if trades_df.empty:
        return {"total_trades": 0, "wins": 0, "losses": 0, "win_rate_pct": 0.0, "net_pips": 0.0, "avg_pips_per_trade": 0.0, "profit_factor": np.nan, "max_drawdown_pips": 0.0, "expectancy_pips": 0.0}
    pnl = trades_df["pnl_pips"].astype(float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    equity = pnl.cumsum()
    running_peak = equity.cummax()
    drawdown = equity - running_peak
    gross_profit = wins.sum()
    gross_loss_abs = abs(losses.sum())
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


def count_invalid_triplets(df: pd.DataFrame, expected_step: pd.Timedelta) -> int:
    return sum(1 for i in range(2, len(df)) if not are_consecutive_triplet(df, i, expected_step))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--min-rsi-a", type=float, default=50.0)
    parser.add_argument("--near-bb-threshold", type=float, default=0.95)
    parser.add_argument("--max-upper-wick-pct", type=float, default=0.10)
    parser.add_argument("--strict-close-above-ubb", action="store_true")
    parser.add_argument("--require-b-high-not-break", action="store_true")
    parser.add_argument("--output", type=str, default="")
    args = parser.parse_args()

    df = standardize_columns(pd.read_csv(Path(args.data)))
    expected_step = validate_time_order_and_infer_step(df)

    params = {
        "h4_min_rsi_a": args.min_rsi_a,
        "h4_overextension_mode": "strict_close_above_ubb" if args.strict_close_above_ubb else "broad_bb_event",
        "h4_min_bb_position_a": 85.0,
        "near_bb_threshold": args.near_bb_threshold,
        "max_upper_wick_pct": args.max_upper_wick_pct,
        "require_b_high_not_break": args.require_b_high_not_break,
        "max_bars_in_trade": 10,
        "follow_through_bars": 2,
        "min_follow_through_pips": 3.0,
        "allowed_sessions": set(),
        "min_previous_touches": 0.0,
        "min_time_since_last_touch": 0.0,
        "min_price_momentum": -1e9,
        "max_price_momentum": 1e9,
        "min_support_distance_pct": 0.0,
        "max_support_distance_pct": 1e9,
    }

    trades_df = summarize_trades(backtest(df, params, expected_step))
    metrics = compute_performance(trades_df)
    invalid_triplets = count_invalid_triplets(df, expected_step)

    print("\n===== BACKTEST RESULTS =====")
    print(f"inferred_time_step: {expected_step}")
    print(f"invalid_nonconsecutive_triplets_skipped: {invalid_triplets}")
    print(f"candle_a_logic: close>upper_band OR high>=upper_band OR bb_position>={args.near_bb_threshold} OR no-upper-wick-bear-reject-near-UBB (wick_pct<={args.max_upper_wick_pct}) (unless --strict-close-above-ubb)")
    for k, v in params.items():
        if k != "allowed_sessions":
            print(f"params.{k}: {v}")
    for k, v in metrics.items():
        print(f"{k}: {v}")
    if not trades_df.empty:
        print("\nSample trades:\n" + trades_df.head(10).to_string(index=False))
    if args.output:
        trades_df.to_csv(Path(args.output), index=False)
        print(f"\nTrade log saved to: {args.output}")


if __name__ == "__main__":
    main()
