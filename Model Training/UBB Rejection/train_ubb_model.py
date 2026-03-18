#!/usr/bin/env python3
"""
train_ubb_model.py

Train an ML model on the UBB signal dataset with:
- time-based train/validation/test split
- validation threshold search
- test evaluation
- walk-forward validation
- trade frequency realism checks
- feature importance inspection
- optional permutation-based feature pruning (RFE-like, leakage-safe on validation)
- conditional .pkl save only if thresholds are met

Examples
--------
Basic:
python train_ubb_model.py --data ubb_signal_dataset.csv --model-output ubb_model.pkl

With walk-forward and pruning:
python train_ubb_model.py --data ubb_signal_dataset.csv --model-output ubb_model.pkl --enable-pruning
"""

from __future__ import annotations

import argparse
import pickle
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


def load_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    needed = {"signal_time", "is_profitable", "final_pnl_pips"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"Dataset missing columns: {missing}")
    df["signal_time"] = pd.to_datetime(df["signal_time"], errors="coerce")
    df = df.dropna(subset=["signal_time"]).sort_values("signal_time").reset_index(drop=True)
    return df


def time_split(df: pd.DataFrame, train_frac: float = 0.6, valid_frac: float = 0.2) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    n = len(df)
    train_end = int(n * train_frac)
    valid_end = int(n * (train_frac + valid_frac))
    return df.iloc[:train_end].copy(), df.iloc[train_end:valid_end].copy(), df.iloc[valid_end:].copy()


def select_feature_columns(df: pd.DataFrame, target_col: str) -> List[str]:
    drop_cols = {
        "signal_index", "signal_time", "entry_price",
        "exit_index", "final_pnl_pips", "hit_tp_first", "hit_sl_first",
        target_col,
    }
    return [c for c in df.columns if c not in drop_cols]


def build_pipeline_from_features(df: pd.DataFrame, feature_cols: List[str]) -> Pipeline:
    categorical_cols = [c for c in feature_cols if df[c].dtype == "object"]
    numeric_cols = [c for c in feature_cols if c not in categorical_cols]

    numeric_pipe = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
    ])
    categorical_pipe = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_pipe, numeric_cols),
            ("cat", categorical_pipe, categorical_cols),
        ]
    )

    model = RandomForestClassifier(
        n_estimators=400,
        max_depth=8,
        min_samples_leaf=10,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced_subsample",
    )

    return Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("model", model),
    ])


def threshold_search(y_true: np.ndarray, proba: np.ndarray, pnl: np.ndarray) -> Dict[str, float]:
    best = {
        "threshold": 0.50,
        "precision": 0.0,
        "selected_trades": 0,
        "selected_pf": 0.0,
        "selected_expectancy": -1e9,
        "selected_net_pips": -1e9,
    }

    for thr in np.arange(0.50, 0.86, 0.02):
        mask = proba >= thr
        selected = int(mask.sum())
        if selected < 20:
            continue

        pnl_sel = pnl[mask]
        y_sel = y_true[mask]

        wins = pnl_sel[pnl_sel > 0]
        losses = pnl_sel[pnl_sel <= 0]
        gross_profit = wins.sum()
        gross_loss_abs = abs(losses.sum())
        pf = gross_profit / gross_loss_abs if gross_loss_abs > 0 else np.nan
        expectancy = pnl_sel.mean()
        net_pips = pnl_sel.sum()
        precision = precision_score(y_sel, np.ones_like(y_sel), zero_division=0)

        cand = (
            0 if np.isnan(pf) else pf,
            expectancy,
            net_pips,
            selected,
            precision,
        )
        prev = (
            best["selected_pf"],
            best["selected_expectancy"],
            best["selected_net_pips"],
            best["selected_trades"],
            best["precision"],
        )
        if cand > prev:
            best = {
                "threshold": float(thr),
                "precision": float(precision),
                "selected_trades": selected,
                "selected_pf": float(pf) if not np.isnan(pf) else 0.0,
                "selected_expectancy": float(expectancy),
                "selected_net_pips": float(net_pips),
            }

    return best


def evaluate_split(name: str, y_true: np.ndarray, proba: np.ndarray, pnl: np.ndarray, threshold: float) -> Dict[str, float]:
    mask = proba >= threshold
    selected = int(mask.sum())

    if selected > 0:
        pnl_sel = pnl[mask]
        wins = pnl_sel[pnl_sel > 0]
        losses = pnl_sel[pnl_sel <= 0]
        gross_profit = wins.sum()
        gross_loss_abs = abs(losses.sum())
        pf = gross_profit / gross_loss_abs if gross_loss_abs > 0 else np.nan
        expectancy = pnl_sel.mean()
        net_pips = pnl_sel.sum()
        precision = precision_score(y_true[mask], np.ones(mask.sum(), dtype=int), zero_division=0)
    else:
        pf = np.nan
        expectancy = 0.0
        net_pips = 0.0
        precision = 0.0

    auc = roc_auc_score(y_true, proba) if len(np.unique(y_true)) > 1 else np.nan

    return {
        f"{name}_auc": round(float(auc), 4) if not np.isnan(auc) else np.nan,
        f"{name}_threshold": round(float(threshold), 4),
        f"{name}_selected_trades": selected,
        f"{name}_selected_pf": round(float(pf), 4) if not np.isnan(pf) else np.nan,
        f"{name}_selected_expectancy": round(float(expectancy), 4),
        f"{name}_selected_net_pips": round(float(net_pips), 2),
        f"{name}_precision": round(float(precision), 4),
    }


def get_feature_importance_table(
    pipe: Pipeline,
    X_valid: pd.DataFrame,
    y_valid: np.ndarray,
    feature_cols: List[str],
    random_state: int = 42,
) -> pd.DataFrame:
    result = permutation_importance(
        pipe,
        X_valid,
        y_valid,
        n_repeats=8,
        random_state=random_state,
        scoring="roc_auc",
        n_jobs=1,
    )
    imp_df = pd.DataFrame({
        "feature": feature_cols,
        "importance_mean": result.importances_mean,
        "importance_std": result.importances_std,
    }).sort_values("importance_mean", ascending=False).reset_index(drop=True)
    return imp_df


def maybe_prune_features(
    df_train: pd.DataFrame,
    df_valid: pd.DataFrame,
    feature_cols: List[str],
    target_col: str,
    enable_pruning: bool,
    max_drop: int,
) -> Tuple[List[str], pd.DataFrame]:
    if not enable_pruning:
        return feature_cols, pd.DataFrame(columns=["feature", "importance_mean", "importance_std"])

    pipe = build_pipeline_from_features(df_train, feature_cols)
    pipe.fit(df_train[feature_cols], df_train[target_col].astype(int).to_numpy())

    imp_df = get_feature_importance_table(
        pipe=pipe,
        X_valid=df_valid[feature_cols],
        y_valid=df_valid[target_col].astype(int).to_numpy(),
        feature_cols=feature_cols,
    )

    removable = imp_df[imp_df["importance_mean"] <= 0]["feature"].tolist()
    removable = removable[:max_drop]

    pruned = [c for c in feature_cols if c not in removable]

    if len(pruned) < max(10, int(len(feature_cols) * 0.4)):
        pruned = feature_cols

    return pruned, imp_df


def trade_frequency_realism(df: pd.DataFrame, proba: np.ndarray, threshold: float) -> Dict[str, float]:
    mask = proba >= threshold
    sel = df.loc[mask, ["signal_time"]].copy()

    if sel.empty:
        return {
            "selected_trades_per_year": 0.0,
            "selected_trades_per_month": 0.0,
            "max_gap_days_between_selected_trades": np.nan,
            "median_gap_days_between_selected_trades": np.nan,
        }

    sel = sel.sort_values("signal_time").reset_index(drop=True)

    total_days = max(1.0, (sel["signal_time"].max() - sel["signal_time"].min()).days + 1)
    total_years = total_days / 365.25
    total_months = total_days / 30.44

    gaps = sel["signal_time"].diff().dt.total_seconds().div(86400).dropna()

    return {
        "selected_trades_per_year": round(len(sel) / total_years, 2),
        "selected_trades_per_month": round(len(sel) / total_months, 2),
        "max_gap_days_between_selected_trades": round(float(gaps.max()), 2) if not gaps.empty else 0.0,
        "median_gap_days_between_selected_trades": round(float(gaps.median()), 2) if not gaps.empty else 0.0,
    }


def walk_forward_validate(
    df: pd.DataFrame,
    feature_cols: List[str],
    target_col: str,
    n_splits: int = 4,
    train_frac: float = 0.6,
    valid_frac: float = 0.2,
) -> pd.DataFrame:
    n = len(df)
    rows = []
    min_test_size = max(40, int(n * 0.10))

    for split_idx in range(n_splits):
        start = int(split_idx * (n - min_test_size) / max(1, n_splits))
        df_sub = df.iloc[start:].reset_index(drop=True)
        if len(df_sub) < 200:
            continue

        train_df, valid_df, test_df = time_split(df_sub, train_frac=train_frac, valid_frac=valid_frac)
        if len(train_df) < 100 or len(valid_df) < 40 or len(test_df) < 40:
            continue

        pipe = build_pipeline_from_features(train_df, feature_cols)
        pipe.fit(train_df[feature_cols], train_df[target_col].astype(int).to_numpy())

        valid_proba = pipe.predict_proba(valid_df[feature_cols])[:, 1]
        best = threshold_search(
            valid_df[target_col].astype(int).to_numpy(),
            valid_proba,
            valid_df["final_pnl_pips"].astype(float).to_numpy(),
        )
        threshold = best["threshold"]

        test_proba = pipe.predict_proba(test_df[feature_cols])[:, 1]
        metrics = evaluate_split(
            f"wf{split_idx+1}",
            test_df[target_col].astype(int).to_numpy(),
            test_proba,
            test_df["final_pnl_pips"].astype(float).to_numpy(),
            threshold,
        )

        rows.append({
            "split": split_idx + 1,
            "rows_total": len(df_sub),
            "train_rows": len(train_df),
            "valid_rows": len(valid_df),
            "test_rows": len(test_df),
            **metrics,
        })

    return pd.DataFrame(rows)


def summarize_walk_forward(wf_df: pd.DataFrame) -> Dict[str, float]:
    if wf_df.empty:
        return {
            "wf_splits": 0,
            "wf_mean_pf": np.nan,
            "wf_median_pf": np.nan,
            "wf_mean_expectancy": np.nan,
            "wf_mean_selected_trades": np.nan,
            "wf_positive_pf_splits": 0,
        }

    pf_cols = [c for c in wf_df.columns if c.endswith("_selected_pf")]
    exp_cols = [c for c in wf_df.columns if c.endswith("_selected_expectancy")]
    tr_cols = [c for c in wf_df.columns if c.endswith("_selected_trades")]

    pf = wf_df[pf_cols[0]].astype(float)
    exp = wf_df[exp_cols[0]].astype(float)
    tr = wf_df[tr_cols[0]].astype(float)

    return {
        "wf_splits": int(len(wf_df)),
        "wf_mean_pf": round(float(pf.mean()), 4),
        "wf_median_pf": round(float(pf.median()), 4),
        "wf_mean_expectancy": round(float(exp.mean()), 4),
        "wf_mean_selected_trades": round(float(tr.mean()), 2),
        "wf_positive_pf_splits": int((pf > 1.0).sum()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train ML model on UBB signal dataset and save .pkl if quality thresholds are met.")
    parser.add_argument("--data", required=True, help="Path to signal dataset CSV")
    parser.add_argument("--model-output", required=True, help="Path to save model .pkl")
    parser.add_argument("--min-test-pf", type=float, default=1.15)
    parser.add_argument("--min-test-trades", type=int, default=30)
    parser.add_argument("--min-test-precision", type=float, default=0.50)
    parser.add_argument("--enable-pruning", action="store_true", help="Drop weak features based on validation permutation importance")
    parser.add_argument("--max-pruned-features", type=int, default=20)
    parser.add_argument("--walk-forward-splits", type=int, default=4)
    args = parser.parse_args()

    df = load_dataset(Path(args.data))
    if len(df) < 200:
        raise ValueError(f"Dataset too small for robust ML training: {len(df)} rows")

    target_col = "is_profitable"
    raw_feature_cols = select_feature_columns(df, target_col=target_col)

    train_df, valid_df, test_df = time_split(df)

    feature_cols, importance_df = maybe_prune_features(
        df_train=train_df,
        df_valid=valid_df,
        feature_cols=raw_feature_cols,
        target_col=target_col,
        enable_pruning=args.enable_pruning,
        max_drop=args.max_pruned_features,
    )

    pipe = build_pipeline_from_features(df, feature_cols)

    X_train = train_df[feature_cols]
    y_train = train_df[target_col].astype(int).to_numpy()

    X_valid = valid_df[feature_cols]
    y_valid = valid_df[target_col].astype(int).to_numpy()
    pnl_valid = valid_df["final_pnl_pips"].astype(float).to_numpy()

    X_test = test_df[feature_cols]
    y_test = test_df[target_col].astype(int).to_numpy()
    pnl_test = test_df["final_pnl_pips"].astype(float).to_numpy()

    pipe.fit(X_train, y_train)

    valid_proba = pipe.predict_proba(X_valid)[:, 1]
    best = threshold_search(y_valid, valid_proba, pnl_valid)
    selected_threshold = best["threshold"]

    test_proba = pipe.predict_proba(X_test)[:, 1]

    valid_metrics = evaluate_split("valid", y_valid, valid_proba, pnl_valid, selected_threshold)
    test_metrics = evaluate_split("test", y_test, test_proba, pnl_test, selected_threshold)

    freq_metrics = trade_frequency_realism(test_df, test_proba, selected_threshold)

    final_importance_df = get_feature_importance_table(
        pipe=pipe,
        X_valid=X_valid,
        y_valid=y_valid,
        feature_cols=feature_cols,
    )

    wf_df = walk_forward_validate(
        df=df,
        feature_cols=feature_cols,
        target_col=target_col,
        n_splits=max(1, args.walk_forward_splits),
    )
    wf_summary = summarize_walk_forward(wf_df)

    print("===== TRAINING SUMMARY =====")
    print(f"dataset_rows: {len(df)}")
    print(f"train_rows: {len(train_df)}")
    print(f"valid_rows: {len(valid_df)}")
    print(f"test_rows: {len(test_df)}")
    print(f"raw_feature_count: {len(raw_feature_cols)}")
    print(f"final_feature_count: {len(feature_cols)}")
    print(f"selected_threshold_from_validation: {selected_threshold:.4f}")

    for k, v in {**valid_metrics, **test_metrics, **freq_metrics, **wf_summary}.items():
        print(f"{k}: {v}")

    print("\n===== TOP FEATURE IMPORTANCE (validation permutation AUC impact) =====")
    print(final_importance_df.head(20).to_string(index=False))

    if args.enable_pruning and not importance_df.empty:
        print("\n===== INITIAL PRUNING IMPORTANCE SNAPSHOT =====")
        print(importance_df.head(20).to_string(index=False))

    if not wf_df.empty:
        print("\n===== WALK-FORWARD RESULTS =====")
        print(wf_df.to_string(index=False))

    save_ok = (
        (test_metrics["test_selected_trades"] >= args.min_test_trades)
        and (0 if np.isnan(test_metrics["test_selected_pf"]) else test_metrics["test_selected_pf"]) >= args.min_test_pf
        and test_metrics["test_precision"] >= args.min_test_precision
    )

    if save_ok:
        payload = {
            "pipeline": pipe,
            "threshold": selected_threshold,
            "feature_cols": feature_cols,
            "metadata": {
                "min_test_pf": args.min_test_pf,
                "min_test_trades": args.min_test_trades,
                "min_test_precision": args.min_test_precision,
                "valid_metrics": valid_metrics,
                "test_metrics": test_metrics,
                "trade_frequency": freq_metrics,
                "walk_forward_summary": wf_summary,
                "walk_forward_rows": wf_df.to_dict(orient="records"),
                "top_feature_importance": final_importance_df.head(50).to_dict(orient="records"),
                "pruning_enabled": args.enable_pruning,
            },
        }
        with open(Path(args.model_output), "wb") as f:
            pickle.dump(payload, f)
        print(f"\nModel saved to: {args.model_output}")
    else:
        print("\nModel NOT saved because thresholds were not met.")


if __name__ == "__main__":
    main()
