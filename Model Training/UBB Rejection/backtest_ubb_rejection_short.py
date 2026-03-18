#!/usr/bin/env python3
"""
Backtest: EURUSD H4 Short Strategy using Upper Bollinger Band Rejection

Rules
-----
Signal uses 3 candles:
- Candle A = i-2
- Candle B = i-1
- Candle C = i   (entry candle)

Entry conditions for SHORT:
1) Candle A must have reached the upper Bollinger Band:
   - high_A >= upper_bb_A
   OR
   - c_pos_A >= 85

2) Candle B must show rejection / move down versus Candle A.
   Current implementation defines this as:
   - close_B < close_A
   - high_B <= high_A

3) Enter SHORT at the OPEN of Candle C.

Trade management:
- TP = 40 pips
- Initial SL = 30 pips
- If profit reaches +15 pips, move SL to breakeven
- If profit reaches +20 pips, move SL to lock +10 pips
- If profit reaches +30 pips, move SL to lock +20 pips

Important backtest assumption
-----------------------------
Because OHLC data does not reveal the exact intrabar price path, this script uses
a conservative rule:

For each candle after entry:
1) Check whether the CURRENT SL or TP was hit during the candle.
2) Only if neither was hit, evaluate whether profit thresholds were reached
   and update the SL for the NEXT candle.

This avoids overstating performance from intrabar stop adjustments.

CSV requirements
----------------
Expected columns (case-insensitive supported):
- datetime
- open
- high
- low
- close

Usage
-----
python backtest_ubb_rejection_short.py --data EURUSD_H4.csv

Optional:
python backtest_ubb_rejection_short.py --data EURUSD_H4.csv --bb-period 20 --bb-std 2.0 --output trades.csv
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd


# =========================
# CONFIG
# =========================
DEFAULT_BB_PERIOD = 20
DEFAULT_BB_STD = 2.0
PIP_SIZE = 0.0001  # EURUSD
TP_PIPS = 40
SL_PIPS = 30

# Threshold -> locked profit in pips
TRAILING_RULES = [
    (15, 0),   # move to breakeven
    (20, 10),  # lock +10
    (30, 20),  # lock +20
]


# =========================
# DATA STRUCTURES
# =========================
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
    threshold_15_reached: bool
    threshold_20_reached: bool
    threshold_30_reached: bool


# =========================
# HELPERS
# =========================
def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    for col in df.columns:
        c = col.strip().lower()
        if c in {"date", "time", "timestamp", "datetime"}:
            rename_map[col] = "datetime"
        elif c == "open":
            rename_map[col] = "open"
        elif c == "high":
            rename_map[col] = "high"
        elif c == "low":
            rename_map[col] = "low"
        elif c == "close":
            rename_map[col] = "close"
    df = df.rename(columns=rename_map)

    required = ["datetime", "open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Found: {list(df.columns)}")

    df = df[required].copy()
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=required).sort_values("datetime").reset_index(drop=True)
    return df


def add_bollinger_features(df: pd.DataFrame, period: int, std_mult: float) -> pd.DataFrame:
    ma = df["close"].rolling(period).mean()
    sd = df["close"].rolling(period).std(ddof=0)

    df["bb_mid"] = ma
    df["bb_std"] = sd
    df["ubb"] = ma + std_mult * sd
    df["lbb"] = ma - std_mult * sd

    width = df["ubb"] - df["lbb"]
    df["c_pos"] = np.where(width > 0, ((df["close"] - df["lbb"]) / width) * 100.0, np.nan)
    return df


def pips_from_price_diff(diff: float, pip_size: float = PIP_SIZE) -> float:
    return diff / pip_size


def price_from_pips(pips: float, pip_size: float = PIP_SIZE) -> float:
    return pips * pip_size


def short_signal(df: pd.DataFrame, i: int) -> bool:
    """
    Signal at candle i means entry at open of candle i using:
    A = i-2
    B = i-1
    """
    if i < 2:
        return False

    a = df.iloc[i - 2]
    b = df.iloc[i - 1]

    needed = ["ubb", "lbb", "c_pos"]
    if any(pd.isna(a[x]) for x in needed) or any(pd.isna(b[x]) for x in needed):
        return False

    cond_a = (a["high"] >= a["ubb"]) or (a["c_pos"] >= 85.0)

    # Current interpretation of "fully rejected / went down compared to candle A"
    cond_b = (b["close"] < a["close"]) and (b["high"] <= a["high"])

    return bool(cond_a and cond_b)


def compute_next_stop(entry_price: float, lowest_price_seen: float, current_stop: float) -> float:
    """
    For a SHORT:
    favorable movement = entry_price - lowest_price_seen

    Conservative implementation:
    stop updates are computed after a candle closes and apply from next candle onward.
    """
    profit_pips = pips_from_price_diff(entry_price - lowest_price_seen)

    desired_stop = current_stop
    for trigger_pips, lock_pips in TRAILING_RULES:
        if profit_pips >= trigger_pips:
            new_stop = entry_price - price_from_pips(lock_pips)
            desired_stop = min(desired_stop, new_stop)  # for shorts, lower stop price is tighter
    return desired_stop


def backtest(df: pd.DataFrame) -> List[Trade]:
    trades: List[Trade] = []
    in_trade = False

    entry_index: Optional[int] = None
    entry_price = None
    initial_stop = None
    current_stop = None
    take_profit = None
    lowest_price_seen = None

    hit_15 = False
    hit_20 = False
    hit_30 = False

    i = 0
    n = len(df)

    while i < n:
        row = df.iloc[i]

        if not in_trade:
            if short_signal(df, i):
                entry_index = i
                entry_price = float(row["open"])
                initial_stop = entry_price + price_from_pips(SL_PIPS)
                current_stop = initial_stop
                take_profit = entry_price - price_from_pips(TP_PIPS)
                lowest_price_seen = entry_price

                hit_15 = False
                hit_20 = False
                hit_30 = False
                in_trade = True
            i += 1
            continue

        # Manage active trade on candle i
        high_i = float(row["high"])
        low_i = float(row["low"])

        # 1) Check existing SL / TP first
        # For SHORT:
        # - SL hits if high >= current_stop
        # - TP hits if low <= take_profit
        sl_hit = high_i >= current_stop
        tp_hit = low_i <= take_profit

        exit_price = None
        outcome = None

        if sl_hit and tp_hit:
            # Conservative tie-breaker: assume SL is hit first
            exit_price = current_stop
            outcome = "SL_and_TP_same_bar_assume_SL_first"
        elif sl_hit:
            exit_price = current_stop
            outcome = "SL"
        elif tp_hit:
            exit_price = take_profit
            outcome = "TP"

        if exit_price is not None:
            pnl_pips = pips_from_price_diff(entry_price - exit_price)
            trades.append(
                Trade(
                    entry_index=entry_index,
                    entry_time=str(df.iloc[entry_index]["datetime"]),
                    exit_index=i,
                    exit_time=str(row["datetime"]),
                    side="SHORT",
                    entry_price=entry_price,
                    exit_price=exit_price,
                    stop_price_initial=initial_stop,
                    stop_price_final=current_stop,
                    take_profit_price=take_profit,
                    pnl_pips=round(pnl_pips, 2),
                    outcome=outcome,
                    bars_held=i - entry_index + 1,
                    threshold_15_reached=hit_15,
                    threshold_20_reached=hit_20,
                    threshold_30_reached=hit_30,
                )
            )
            in_trade = False
            entry_index = None
            entry_price = None
            initial_stop = None
            current_stop = None
            take_profit = None
            lowest_price_seen = None
            i += 1
            continue

        # 2) No exit on this bar -> update excursion and stop for next bar
        lowest_price_seen = min(lowest_price_seen, low_i)
        profit_pips_now = pips_from_price_diff(entry_price - lowest_price_seen)

        if profit_pips_now >= 15:
            hit_15 = True
        if profit_pips_now >= 20:
            hit_20 = True
        if profit_pips_now >= 30:
            hit_30 = True

        current_stop = compute_next_stop(
            entry_price=entry_price,
            lowest_price_seen=lowest_price_seen,
            current_stop=current_stop,
        )

        i += 1

    # Force-close any open trade at last close
    if in_trade and entry_index is not None:
        last_row = df.iloc[-1]
        exit_price = float(last_row["close"])
        pnl_pips = pips_from_price_diff(entry_price - exit_price)
        trades.append(
            Trade(
                entry_index=entry_index,
                entry_time=str(df.iloc[entry_index]["datetime"]),
                exit_index=n - 1,
                exit_time=str(last_row["datetime"]),
                side="SHORT",
                entry_price=entry_price,
                exit_price=exit_price,
                stop_price_initial=initial_stop,
                stop_price_final=current_stop,
                take_profit_price=take_profit,
                pnl_pips=round(pnl_pips, 2),
                outcome="FORCED_EXIT_LAST_CLOSE",
                bars_held=(n - 1) - entry_index + 1,
                threshold_15_reached=hit_15,
                threshold_20_reached=hit_20,
                threshold_30_reached=hit_30,
            )
        )

    return trades


def summarize_trades(trades: List[Trade]) -> pd.DataFrame:
    return pd.DataFrame([asdict(t) for t in trades])


def compute_performance(trades_df: pd.DataFrame) -> dict:
    if trades_df.empty:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate_pct": 0.0,
            "net_pips": 0.0,
            "avg_pips_per_trade": 0.0,
            "profit_factor": np.nan,
            "max_drawdown_pips": 0.0,
            "expectancy_pips": 0.0,
        }

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


def print_report(metrics: dict) -> None:
    print("\n===== BACKTEST RESULTS =====")
    for k, v in metrics.items():
        print(f"{k}: {v}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest EURUSD H4 Upper BB rejection short strategy.")
    parser.add_argument("--data", required=True, help="Path to CSV file")
    parser.add_argument("--bb-period", type=int, default=DEFAULT_BB_PERIOD, help="Bollinger period (default: 20)")
    parser.add_argument("--bb-std", type=float, default=DEFAULT_BB_STD, help="Bollinger std multiplier (default: 2.0)")
    parser.add_argument("--output", type=str, default="", help="Optional path to save trade log CSV")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        raise FileNotFoundError(f"CSV file not found: {data_path}")

    df = pd.read_csv(data_path)
    df = standardize_columns(df)
    df = add_bollinger_features(df, period=args.bb_period, std_mult=args.bb_std)

    trades = backtest(df)
    trades_df = summarize_trades(trades)
    metrics = compute_performance(trades_df)

    print_report(metrics)

    if not trades_df.empty:
        print("\nSample trades:")
        print(trades_df.head(10).to_string(index=False))
    else:
        print("\nNo trades were found based on the current rules.")

    if args.output:
        out_path = Path(args.output)
        trades_df.to_csv(out_path, index=False)
        print(f"\nTrade log saved to: {out_path}")


if __name__ == "__main__":
    main()
