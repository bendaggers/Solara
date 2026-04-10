#!/usr/bin/env python3
"""
build_ubb_signal_dataset.py

Build an ML-ready signal dataset for the UBB rejection short idea.

Important concept
-----------------
Each row in the output is NOT every H4 candle.
Each row is a candidate signal event.

This script now supports multiple candidate modes so you can move from
strict rule-based generation toward a broader ML candidate universe.

Candidate modes
---------------
1) strict
   Original baseline:
   - Candle A close > upper_band
   - Candle A high >= upper_band OR bb_position >= 85
   - Candle B close < close_A
   - Candle B high <= high_A
   - Candle A RSI >= 55

2) broad_v1
   Broader ML candidate pool:
   - Candle A high >= upper_band OR bb_position >= 85
   - Candle B close < close_A
   - Candle B high <= high_A
   - Candle A RSI >= 50

3) broad_v2
   Even broader ML candidate pool:
   - Candle A high >= upper_band OR bb_position >= 85
   - Candle B close < close_A
   - Candle A RSI >= 50
   - no strict Candle B high <= high_A requirement

Usage
-----
Strict:
python build_ubb_signal_dataset.py --data eurusd_h4.csv --output ubb_signal_dataset_strict.csv --candidate-mode strict

Broad v1:
python build_ubb_signal_dataset.py --data eurusd_h4.csv --output ubb_signal_dataset_broad_v1.csv --candidate-mode broad_v1

Broad v2:
python build_ubb_signal_dataset.py --data eurusd_h4.csv --output ubb_signal_dataset_broad_v2.csv --candidate-mode broad_v2
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

import pandas as pd


PIP_SIZE = 0.0001
TP_PIPS = 40
SL_PIPS = 30

TRAILING_RULES = [
    (15, 0),
    (20, 10),
    (30, 20),
]


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    for col in df.columns:
        c = col.strip().lower()
        rename_map[col] = "timestamp" if c in {"timestamp", "datetime", "date", "time"} else c
    df = df.rename(columns=rename_map)

    required = [
        "timestamp", "open", "high", "low", "close",
        "upper_band", "lower_band", "middle_band",
        "bb_touch_strength", "bb_position", "bb_width_pct", "rsi_value",
        "rsi_divergence", "volume_ratio", "candle_rejection", "candle_body_pct",
        "atr_pct", "trend_strength", "prev_candle_body_pct", "prev_volume_ratio",
        "gap_from_prev_close", "price_momentum", "prev_was_selloff",
        "previous_touches", "time_since_last_touch", "support_distance_pct", "session",
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


def price_from_pips(pips: float) -> float:
    return pips * PIP_SIZE


def pips_from_price_diff(diff: float) -> float:
    return diff / PIP_SIZE


def candidate_signal(df: pd.DataFrame, i: int, mode: str) -> bool:
    if i < 2:
        return False

    a = df.iloc[i - 2]
    b = df.iloc[i - 1]

    a_overextended = (a["high"] >= a["upper_band"]) or (a["bb_position"] >= 85.0)

    if mode == "strict":
        cond_a = a_overextended and (a["close"] > a["upper_band"]) and (a["rsi_value"] >= 55.0)
        cond_b = (b["close"] < a["close"]) and (b["high"] <= a["high"])
        return bool(cond_a and cond_b)

    if mode == "broad_v1":
        cond_a = a_overextended and (a["rsi_value"] >= 50.0)
        cond_b = (b["close"] < a["close"]) and (b["high"] <= a["high"])
        return bool(cond_a and cond_b)

    if mode == "broad_v2":
        cond_a = a_overextended and (a["rsi_value"] >= 50.0)
        cond_b = (b["close"] < a["close"])
        return bool(cond_a and cond_b)

    raise ValueError(f"Unknown candidate mode: {mode}")


def simulate_trade(df: pd.DataFrame, entry_index: int) -> Dict[str, float]:
    row = df.iloc[entry_index]
    entry_price = float(row["open"])
    current_stop = entry_price + price_from_pips(SL_PIPS)
    take_profit = entry_price - price_from_pips(TP_PIPS)
    lowest_price_seen = entry_price

    hit_tp_first = 0
    hit_sl_first = 0

    for i in range(entry_index, min(len(df), entry_index + 1000)):
        r = df.iloc[i]
        high_i = float(r["high"])
        low_i = float(r["low"])

        sl_hit = high_i >= current_stop
        tp_hit = low_i <= take_profit

        if sl_hit and tp_hit:
            hit_sl_first = 1
            return {
                "exit_index": i,
                "final_pnl_pips": round(pips_from_price_diff(entry_price - current_stop), 2),
                "hit_tp_first": hit_tp_first,
                "hit_sl_first": hit_sl_first,
            }

        if sl_hit:
            hit_sl_first = 1
            return {
                "exit_index": i,
                "final_pnl_pips": round(pips_from_price_diff(entry_price - current_stop), 2),
                "hit_tp_first": hit_tp_first,
                "hit_sl_first": hit_sl_first,
            }

        if tp_hit:
            hit_tp_first = 1
            return {
                "exit_index": i,
                "final_pnl_pips": round(pips_from_price_diff(entry_price - take_profit), 2),
                "hit_tp_first": hit_tp_first,
                "hit_sl_first": hit_sl_first,
            }

        lowest_price_seen = min(lowest_price_seen, low_i)
        profit_pips_now = pips_from_price_diff(entry_price - lowest_price_seen)
        bars_held_now = i - entry_index + 1

        if bars_held_now >= 2 and profit_pips_now < 3.0:
            exit_price = float(r["close"])
            return {
                "exit_index": i,
                "final_pnl_pips": round(pips_from_price_diff(entry_price - exit_price), 2),
                "hit_tp_first": hit_tp_first,
                "hit_sl_first": hit_sl_first,
            }

        if bars_held_now >= 10:
            exit_price = float(r["close"])
            return {
                "exit_index": i,
                "final_pnl_pips": round(pips_from_price_diff(entry_price - exit_price), 2),
                "hit_tp_first": hit_tp_first,
                "hit_sl_first": hit_sl_first,
            }

        for trigger_pips, lock_pips in TRAILING_RULES:
            if profit_pips_now >= trigger_pips:
                current_stop = min(current_stop, entry_price - price_from_pips(lock_pips))

    exit_price = float(df.iloc[-1]["close"])
    return {
        "exit_index": len(df) - 1,
        "final_pnl_pips": round(pips_from_price_diff(entry_price - exit_price), 2),
        "hit_tp_first": hit_tp_first,
        "hit_sl_first": hit_sl_first,
    }


def build_dataset(df: pd.DataFrame, candidate_mode: str) -> pd.DataFrame:
    rows: List[Dict] = []

    for i in range(len(df)):
        if not candidate_signal(df, i, candidate_mode):
            continue

        a = df.iloc[i - 2]
        b = df.iloc[i - 1]
        c = df.iloc[i]
        outcome = simulate_trade(df, i)

        row = {
            "candidate_mode": candidate_mode,
            "signal_index": i,
            "signal_time": c["timestamp"],
            "entry_price": c["open"],
            "session": c["session"],
        }

        for prefix, src in [("a", a), ("b", b), ("c", c)]:
            for col in [
                "open", "high", "low", "close",
                "bb_touch_strength", "bb_position", "bb_width_pct", "rsi_value",
                "rsi_divergence", "volume_ratio", "candle_rejection", "candle_body_pct",
                "atr_pct", "trend_strength", "prev_candle_body_pct", "prev_volume_ratio",
                "gap_from_prev_close", "price_momentum", "prev_was_selloff",
                "previous_touches", "time_since_last_touch", "support_distance_pct",
            ]:
                if col in src.index:
                    row[f"{prefix}_{col}"] = src[col]

        row.update(outcome)
        row["is_profitable"] = 1 if outcome["final_pnl_pips"] > 0 else 0
        rows.append(row)

    return pd.DataFrame(rows)


def print_summary(df: pd.DataFrame, signal_df: pd.DataFrame, candidate_mode: str) -> None:
    total_candles = len(df)
    total_signals = len(signal_df)
    signal_rate_pct = (total_signals / total_candles * 100.0) if total_candles > 0 else 0.0

    start = df["timestamp"].min()
    end = df["timestamp"].max()
    total_days = max(1.0, (end - start).days + 1)
    total_years = total_days / 365.25

    signals_per_year = total_signals / total_years if total_years > 0 else 0.0

    print("===== DATASET BUILD SUMMARY =====")
    print(f"candidate_mode: {candidate_mode}")
    print(f"total_candles: {total_candles}")
    print(f"total_signals: {total_signals}")
    print(f"signal_rate_pct: {signal_rate_pct:.4f}")
    print(f"signals_per_year: {signals_per_year:.2f}")
    print(f"date_start: {start}")
    print(f"date_end: {end}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ML-ready signal dataset from UBB rejection candidate events.")
    parser.add_argument("--data", required=True, help="Path to H4 CSV")
    parser.add_argument("--output", required=True, help="Output CSV path")
    parser.add_argument(
        "--candidate-mode",
        default="strict",
        choices=["strict", "broad_v1", "broad_v2"],
        help="Signal generator strictness for ML candidate rows",
    )
    args = parser.parse_args()

    df = standardize_columns(pd.read_csv(Path(args.data)))
    signal_df = build_dataset(df, candidate_mode=args.candidate_mode)
    signal_df.to_csv(Path(args.output), index=False)

    print_summary(df, signal_df, args.candidate_mode)
    print(f"Dataset saved to: {args.output}")

    if not signal_df.empty:
        print("\nSample rows:")
        print(signal_df.head(5).to_string(index=False))


if __name__ == "__main__":
    main()
