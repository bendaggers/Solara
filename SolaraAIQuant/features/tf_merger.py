"""
Solara AI Quant - Multi-Timeframe Merger

Handles merging of additional timeframe data into a base DataFrame
for models that require multi-timeframe context.

Rules:
- The trigger TF data is always the BASE DataFrame
- Each merge_timeframe is loaded from its CSV and merged in
- Merged columns are prefixed with the TF name in lowercase (d1_, h4_, m15_, etc.)
- Merging is always backward-looking (no data leakage):
    For each base row at time T, use the most recent completed bar
    from the secondary TF where bar_close_time <= T
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict, Tuple
import logging

from config import MQL5_FILES_DIR, TIMEFRAMES

logger = logging.getLogger(__name__)


# Maps each TF to its CSV filename config key
TF_TO_CONFIG_KEY = {
    'M5':  'M5',
    'M15': 'M15',
    'H1':  'H1',
    'H4':  'H4',
    'D1':  'D1',
    'W1':  'W1',
}


class MultiTimeframeMerger:
    """
    Merges one or more secondary timeframe CSVs into a base DataFrame.

    Usage:
        merger = MultiTimeframeMerger()
        df = merger.merge(base_df, base_tf="M5", merge_tfs=["H4", "D1"])
        # df now has h4_ and d1_ prefixed columns
    """

    def __init__(self):
        # Cache: tf_string → DataFrame (refreshed every cycle)
        self._cache: Dict[str, pd.DataFrame] = {}

    def merge(
        self,
        base_df: pd.DataFrame,
        base_tf: str,
        merge_tfs: List[str],
    ) -> pd.DataFrame:
        """
        Merge secondary TF data into base DataFrame.

        Args:
            base_df:   Base DataFrame (from trigger TF CSV)
            base_tf:   String name of the base TF (e.g. "M5")
            merge_tfs: List of TF strings to merge in (e.g. ["H4", "D1"])

        Returns:
            base_df with additional columns prefixed by TF name
        """
        if not merge_tfs:
            return base_df

        df = base_df.copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        for tf in merge_tfs:
            tf_upper = tf.upper()

            if tf_upper == base_tf.upper():
                logger.warning(
                    f"Skipping merge of {tf} into itself ({base_tf})"
                )
                continue

            secondary_df = self._load_tf(tf_upper)
            if secondary_df is None:
                logger.warning(
                    f"Could not load {tf_upper} data — skipping merge"
                )
                continue

            df = self._merge_single(df, secondary_df, tf_upper)
            logger.info(
                f"Merged {tf_upper} into {base_tf} — "
                f"added {sum(1 for c in df.columns if c.startswith(tf_upper.lower() + '_'))} columns"
            )

        return df

    def _load_tf(self, tf: str) -> Optional[pd.DataFrame]:
        """Load a TF CSV with caching."""
        if tf in self._cache:
            return self._cache[tf]

        config_key = TF_TO_CONFIG_KEY.get(tf)
        if not config_key:
            logger.error(f"Unknown timeframe: {tf}")
            return None

        tf_config = TIMEFRAMES.get(config_key)
        if not tf_config:
            logger.error(f"No TIMEFRAMES config entry for: {tf}")
            return None

        csv_path = MQL5_FILES_DIR / tf_config.csv_filename

        if not csv_path.exists():
            logger.warning(f"{tf} CSV not found: {csv_path}")
            return None

        try:
            df = pd.read_csv(csv_path, parse_dates=['timestamp'])

            # Normalise pair → symbol
            if 'pair' in df.columns and 'symbol' not in df.columns:
                df = df.rename(columns={'pair': 'symbol'})

            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp').reset_index(drop=True)

            self._cache[tf] = df
            logger.debug(f"Loaded {tf} CSV: {len(df)} rows")
            return df

        except Exception as e:
            logger.error(f"Error loading {tf} CSV: {e}")
            return None

    def _merge_single(
        self,
        base_df: pd.DataFrame,
        secondary_df: pd.DataFrame,
        secondary_tf: str,
    ) -> pd.DataFrame:
        """
        Merge one secondary TF into base_df using backward merge_asof.

        For each row in base_df at time T, we find the most recent row
        in secondary_df whose timestamp <= T. This guarantees no leakage.

        Secondary columns are prefixed with lowercase TF name + underscore.
        e.g. D1 → d1_close, d1_rsi_value, etc.
        """
        prefix = secondary_tf.lower() + '_'

        # Rename secondary columns with prefix (keep timestamp as join key)
        rename_map = {
            col: f"{prefix}{col}"
            for col in secondary_df.columns
            if col != 'timestamp'
        }
        sec = secondary_df.rename(columns=rename_map).copy()
        sec = sec.sort_values('timestamp').reset_index(drop=True)

        # merge_asof: for each base row, find most recent secondary row
        # where secondary.timestamp <= base.timestamp
        merged = pd.merge_asof(
            base_df.sort_values('timestamp'),
            sec,
            on='timestamp',
            direction='backward',
        )

        missing = merged[f'{prefix}close'].isna().sum() if f'{prefix}close' in merged.columns else 0
        if missing > 0:
            logger.debug(
                f"  {missing} base rows have no {secondary_tf} data "
                f"(before first {secondary_tf} bar)"
            )

        return merged

    def clear_cache(self):
        """Clear the TF data cache. Call between pipeline cycles if needed."""
        self._cache.clear()
        logger.debug("MultiTimeframeMerger cache cleared")


# ── Convenience function for pipeline_runner ─────────────────────────────────

def merge_timeframes_for_models(
    base_df: pd.DataFrame,
    base_tf: str,
    models,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Determine the union of merge_timeframes across all triggered models,
    then merge them all into base_df.

    Args:
        base_df:  Base DataFrame (already validated)
        base_tf:  Trigger TF string (e.g. "M5")
        models:   List of ModelConfig objects triggered this cycle

    Returns:
        (merged_df, list_of_tfs_merged)
    """
    # Collect all unique TFs needed across all triggered models
    needed_tfs: List[str] = []
    for model in models:
        for tf in model.get_merge_timeframe_strings():
            if tf not in needed_tfs and tf.upper() != base_tf.upper():
                needed_tfs.append(tf)

    if not needed_tfs:
        return base_df, []

    logger.info(
        f"Merging additional TFs {needed_tfs} into {base_tf} "
        f"(required by {[m.name for m in models]})"
    )

    merger = MultiTimeframeMerger()
    merged_df = merger.merge(base_df, base_tf=base_tf, merge_tfs=needed_tfs)

    return merged_df, needed_tfs
