#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

import pandas as pd

PIP_SIZE = 0.0001
TP_PIPS = 40
SL_PIPS = 30
TRAILING_RULES = [(15, 0), (20, 10), (30, 20)]


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    for col in df.columns:
        c = col.strip().lower()
        rename_map[col] = "timestamp" if c in {"timestamp", "datetime", "date", "time"} else c
    df = df.rename(columns=rename_map)

    required = [
        "timestamp", "pair", "open", "high", "low", "close", "volume",
        "lower_band", "middle_band", "upper_band",
        "bb_touch_strength", "bb_position", "bb_width_pct",
        "rsi_value", "rsi_divergence", "volume_ratio", "candle_rejection",
        "candle_body_pct", "atr_pct", "trend_strength",
        "prev_candle_body_pct", "prev_volume_ratio", "gap_from_prev_close",
        "price_momentum", "prev_was_selloff", "previous_touches",
        "time_since_last_touch", "support_distance_pct", "session",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    numeric_cols = [c for c in required if c not in {"timestamp", "pair", "session"}]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["pair"] = df["pair"].astype(str)
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


def price_from_pips(pips: float) -> float:
    return pips * PIP_SIZE


def pips_from_price_diff(diff: float) -> float:
    return diff / PIP_SIZE


def upper_wick_size(row: pd.Series) -> float:
    return float(row["high"] - max(row["open"], row["close"]))


def candle_range(row: pd.Series) -> float:
    return float(max(row["high"] - row["low"], 1e-10))


def no_upper_wick_bearish_rejection(a: pd.Series, near_bb_threshold: float, max_upper_wick_pct: float) -> bool:
    wick_pct = upper_wick_size(a) / candle_range(a)
    return bool((a["bb_position"] >= near_bb_threshold) and (a["close"] < a["open"]) and (wick_pct <= max_upper_wick_pct))


def bb_event_type(a: pd.Series, near_bb_threshold: float, max_upper_wick_pct: float) -> str:
    if a["close"] > a["upper_band"]:
        return "close_above_ubb"
    if a["high"] >= a["upper_band"]:
        return "high_touch_ubb"
    if no_upper_wick_bearish_rejection(a, near_bb_threshold, max_upper_wick_pct):
        return "no_upper_wick_bear_reject_near_ubb"
    if a["bb_position"] >= near_bb_threshold:
        return "near_upper_bb_fail_break"
    return "none"


def bb_event_strength(event_type: str) -> float:
    return {"close_above_ubb": 1.0, "high_touch_ubb": 0.8, "no_upper_wick_bear_reject_near_ubb": 0.75, "near_upper_bb_fail_break": 0.6, "none": 0.0}.get(event_type, 0.0)


def add_candle_a_engineered_features(row: Dict, a: pd.Series, near_bb_threshold: float, max_upper_wick_pct: float) -> None:
    event_type = bb_event_type(a, near_bb_threshold, max_upper_wick_pct)
    row["a_bb_event_type"] = event_type
    row["a_bb_event_strength"] = bb_event_strength(event_type)
    row["a_close_above_ubb"] = 1 if a["close"] > a["upper_band"] else 0
    row["a_high_touch_ubb"] = 1 if a["high"] >= a["upper_band"] else 0
    row["a_near_upper_bb"] = 1 if a["bb_position"] >= near_bb_threshold else 0
    row["a_no_upper_wick_bear_reject"] = 1 if no_upper_wick_bearish_rejection(a, near_bb_threshold, max_upper_wick_pct) else 0
    row["a_failed_break_ubb"] = 1 if ((a["high"] >= a["upper_band"]) and (a["close"] <= a["upper_band"])) else 0
    row["a_ubb_distance_close"] = float(a["upper_band"] - a["close"])
    row["a_ubb_distance_high"] = float(a["upper_band"] - a["high"])
    row["a_upper_wick_size"] = upper_wick_size(a)
    row["a_upper_wick_pct"] = upper_wick_size(a) / candle_range(a)


def candidate_signal(df: pd.DataFrame, i: int, mode: str, near_bb_threshold: float, max_upper_wick_pct: float, expected_step: pd.Timedelta) -> bool:
    if not are_consecutive_triplet(df, i, expected_step):
        return False

    a = df.iloc[i - 2]
    b = df.iloc[i - 1]
    a_bb_event = bb_event_type(a, near_bb_threshold, max_upper_wick_pct) != "none"

    if mode == "strict":
        cond_a = (((a["high"] >= a["upper_band"]) or (a["bb_position"] >= 0.85)) and (a["close"] > a["upper_band"]) and (a["rsi_value"] >= 55.0))
        cond_b = (b["close"] < a["close"]) and (b["high"] <= a["high"])
        return bool(cond_a and cond_b)
    if mode == "broad_v1":
        cond_a = a_bb_event and (a["rsi_value"] >= 50.0)
        cond_b = (b["close"] < a["close"]) and (b["high"] <= a["high"])
        return bool(cond_a and cond_b)
    if mode == "broad_v2":
        cond_a = a_bb_event and (a["rsi_value"] >= 50.0)
        cond_b = (b["close"] < a["close"])
        return bool(cond_a and cond_b)
    if mode == "broad_v3":
        cond_a = a_bb_event and (a["rsi_value"] >= 45.0)
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
            return {"exit_index": i, "final_pnl_pips": round(pips_from_price_diff(entry_price - current_stop), 2), "hit_tp_first": hit_tp_first, "hit_sl_first": hit_sl_first}
        if sl_hit:
            hit_sl_first = 1
            return {"exit_index": i, "final_pnl_pips": round(pips_from_price_diff(entry_price - current_stop), 2), "hit_tp_first": hit_tp_first, "hit_sl_first": hit_sl_first}
        if tp_hit:
            hit_tp_first = 1
            return {"exit_index": i, "final_pnl_pips": round(pips_from_price_diff(entry_price - take_profit), 2), "hit_tp_first": hit_tp_first, "hit_sl_first": hit_sl_first}

        lowest_price_seen = min(lowest_price_seen, low_i)
        profit_pips_now = pips_from_price_diff(entry_price - lowest_price_seen)
        bars_held_now = i - entry_index + 1

        if bars_held_now >= 2 and profit_pips_now < 3.0:
            exit_price = float(r["close"])
            return {"exit_index": i, "final_pnl_pips": round(pips_from_price_diff(entry_price - exit_price), 2), "hit_tp_first": hit_tp_first, "hit_sl_first": hit_sl_first}

        if bars_held_now >= 10:
            exit_price = float(r["close"])
            return {"exit_index": i, "final_pnl_pips": round(pips_from_price_diff(entry_price - exit_price), 2), "hit_tp_first": hit_tp_first, "hit_sl_first": hit_sl_first}

        for trigger_pips, lock_pips in TRAILING_RULES:
            if profit_pips_now >= trigger_pips:
                current_stop = min(current_stop, entry_price - price_from_pips(lock_pips))

    exit_price = float(df.iloc[-1]["close"])
    return {"exit_index": len(df) - 1, "final_pnl_pips": round(pips_from_price_diff(entry_price - exit_price), 2), "hit_tp_first": hit_tp_first, "hit_sl_first": hit_sl_first}


def build_dataset(df: pd.DataFrame, candidate_mode: str, near_bb_threshold: float, max_upper_wick_pct: float, expected_step: pd.Timedelta) -> pd.DataFrame:
    rows: List[Dict] = []
    for i in range(len(df)):
        if not candidate_signal(df, i, candidate_mode, near_bb_threshold, max_upper_wick_pct, expected_step):
            continue

        a = df.iloc[i - 2]
        b = df.iloc[i - 1]
        c = df.iloc[i]
        outcome = simulate_trade(df, i)

        row = {"candidate_mode": candidate_mode, "signal_index": i, "signal_time": c["timestamp"], "entry_price": c["open"], "a_timestamp": a["timestamp"], "b_timestamp": b["timestamp"], "c_timestamp": c["timestamp"], "session": c["session"], "pair": c["pair"]}

        for prefix, src in [("a", a), ("b", b), ("c", c)]:
            for col in ["open", "high", "low", "close", "volume", "bb_touch_strength", "bb_position", "bb_width_pct", "rsi_value", "rsi_divergence", "volume_ratio", "candle_rejection", "candle_body_pct", "atr_pct", "trend_strength", "prev_candle_body_pct", "prev_volume_ratio", "gap_from_prev_close", "price_momentum", "prev_was_selloff", "previous_touches", "time_since_last_touch", "support_distance_pct"]:
                if col in src.index:
                    row[f"{prefix}_{col}"] = src[col]

        add_candle_a_engineered_features(row, a, near_bb_threshold, max_upper_wick_pct)
        row.update(outcome)
        row["is_profitable"] = 1 if outcome["final_pnl_pips"] > 0 else 0
        rows.append(row)

    return pd.DataFrame(rows)


def count_invalid_triplets(df: pd.DataFrame, expected_step: pd.Timedelta) -> int:
    return sum(1 for i in range(2, len(df)) if not are_consecutive_triplet(df, i, expected_step))


def print_summary(df: pd.DataFrame, signal_df: pd.DataFrame, candidate_mode: str, near_bb_threshold: float, max_upper_wick_pct: float, expected_step: pd.Timedelta) -> None:
    total_candles = len(df)
    total_signals = len(signal_df)
    signal_rate_pct = (total_signals / total_candles * 100.0) if total_candles > 0 else 0.0
    start = df["timestamp"].min()
    end = df["timestamp"].max()
    total_days = max(1.0, (end - start).days + 1)
    total_years = total_days / 365.25
    signals_per_year = total_signals / total_years if total_years > 0 else 0.0
    invalid_triplets = count_invalid_triplets(df, expected_step)

    print("===== DATASET BUILD SUMMARY =====")
    print(f"candidate_mode: {candidate_mode}")
    print(f"inferred_time_step: {expected_step}")
    print(f"invalid_nonconsecutive_triplets_skipped: {invalid_triplets}")
    print(f"candle_a_logic: close>upper_band OR high>=upper_band OR bb_position>={near_bb_threshold} OR no-upper-wick-bear-reject-near-UBB (wick_pct<={max_upper_wick_pct})")
    print(f"total_candles: {total_candles}")
    print(f"total_signals: {total_signals}")
    print(f"signal_rate_pct: {signal_rate_pct:.4f}")
    print(f"signals_per_year: {signals_per_year:.2f}")
    print(f"date_start: {start}")
    print(f"date_end: {end}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--near-bb-threshold", type=float, default=0.95)
    parser.add_argument("--max-upper-wick-pct", type=float, default=0.10)
    parser.add_argument("--candidate-mode", default="strict", choices=["strict", "broad_v1", "broad_v2", "broad_v3"])
    args = parser.parse_args()

    df = standardize_columns(pd.read_csv(Path(args.data)))
    expected_step = validate_time_order_and_infer_step(df)

    signal_df = build_dataset(df, args.candidate_mode, args.near_bb_threshold, args.max_upper_wick_pct, expected_step)
    out = Path(args.output)
    signal_df.to_csv(out, index=False)

    print_summary(df, signal_df, args.candidate_mode, args.near_bb_threshold, args.max_upper_wick_pct, expected_step)
    print(f"Dataset saved to: {args.output}")
    if not signal_df.empty:
        print("\nSample rows:")
        print(signal_df.head(5).to_string(index=False))


if __name__ == "__main__":
    main()
