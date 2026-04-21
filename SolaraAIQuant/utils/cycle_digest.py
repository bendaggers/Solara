"""
Cycle Digest Writer
===================
Writes a clean, human-readable per-cycle summary to logs/cycle_digest.log.

Each cycle produces one block showing every symbol's gate result for both
Pull Back Long and Pull Back Short models. Example:

    ════════════════════════════════════════════════════════════════════════
      CYCLE  2026-04-16 20:00:33  │  H1  │  0 signals  │  11.1s
    ════════════════════════════════════════════════════════════════════════
      PAIR      TREND      │  LONG                    │  SHORT
      ────────  ─────────  │  ────────────────────── │  ─────────────────
      CADCHF    DOWN ↓     │  ✗ G2 wrong dir          │  ✗ G4 entry=0.43
      CHFJPY    UP   ↑     │  ✗ G3 exhaust=0.47       │  ✗ G2 wrong dir
      EURUSD    mixed      │  ✗ G1 not aligned        │  ✗ G1 not aligned
      ─────────────────────────────────────────────────────────────────────
      No signals this cycle.
    ════════════════════════════════════════════════════════════════════════

Real-time monitoring (PowerShell):
    Get-Content .\\logs\\cycle_digest.log -Wait -Tail 80 -Encoding UTF8

Called from pipeline_runner._write_cycle_digest() after Stage 5 completes.
Data source: PullBackEntryPredictor._last_cycle_results (per-symbol gate dict).
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)

# ── Column widths ─────────────────────────────────────────────────────────────
_W_PAIR  = 8
_W_TREND = 9
_W_GATE  = 24

# Total block width
_W_TOTAL = 2 + _W_PAIR + 2 + _W_TREND + 4 + _W_GATE + 4 + _W_GATE + 2  # ~80

_SEP  = '═' * _W_TOTAL
_DASH = '─' * _W_TOTAL

# ── Trend display ─────────────────────────────────────────────────────────────
_TREND_FMT = {
    'uptrend':   'UP   ↑',
    'downtrend': 'DOWN ↓',
    'sideways':  'mixed ',
}


def _fmt_trend(direction: str, aligned: bool) -> str:
    if aligned:
        return _TREND_FMT.get(direction, 'mixed ')
    return 'mixed '


def _fmt_gate(result: dict) -> str:
    """Format a gate result dict into a padded display string."""
    if not result:
        return '—'
    g = result.get('gate', 99)
    if g == 0:
        ep = result.get('entry_prob', 0.0)
        return f'✔ SIGNAL  entry={ep:.2f}'
    if g == 1:
        return '✗ G1 not aligned'
    if g == 2:
        return '✗ G2 wrong dir'
    if g == 3:
        ep = result.get('exhaust_prob', 0.0)
        return f'✗ G3 exhaust={ep:.2f}'
    if g == 4:
        ep = result.get('entry_prob', 0.0)
        return f'✗ G4 entry={ep:.2f}'
    return '✗ error'


def _build_digest_lines(
    cycle_time: datetime,
    timeframe: str,
    long_pred:  Any,
    short_pred: Any,
    signals:    list,
    elapsed:    float,
) -> list:
    """Build all lines for one cycle block."""

    n_sig     = len(signals)
    sig_label = f"{n_sig} signal{'s' if n_sig != 1 else ''}" if n_sig else "0 signals"
    header    = (
        f"  CYCLE  {cycle_time.strftime('%Y-%m-%d %H:%M:%S')}"
        f"  │  {timeframe}"
        f"  │  {sig_label}"
        f"  │  {elapsed:.1f}s"
    )
    col_header = (
        f"  {'PAIR':<{_W_PAIR}}  {'TREND':<{_W_TREND}}"
        f"  │  {'LONG':<{_W_GATE}}"
        f"  │  {'SHORT':<{_W_GATE}}"
    )
    col_sep = (
        f"  {'─'*_W_PAIR}  {'─'*_W_TREND}"
        f"  │  {'─'*_W_GATE}"
        f"  │  {'─'*_W_GATE}"
    )

    lines = [_SEP, header, _SEP, col_header, col_sep]

    long_data  = getattr(long_pred,  '_last_cycle_results', {}) or {}
    short_data = getattr(short_pred, '_last_cycle_results', {}) or {}

    all_symbols = sorted(set(long_data) | set(short_data))

    for sym in all_symbols:
        long_result  = long_data.get(sym, {})
        short_result = short_data.get(sym, {})

        # Trend direction from whichever predictor has data
        res      = long_result or short_result
        trend    = _fmt_trend(res.get('direction', 'sideways'), res.get('aligned', False))
        long_str  = _fmt_gate(long_result)
        short_str = _fmt_gate(short_result)

        lines.append(
            f"  {sym:<{_W_PAIR}}  {trend:<{_W_TREND}}"
            f"  │  {long_str:<{_W_GATE}}"
            f"  │  {short_str:<{_W_GATE}}"
        )

    lines.append(f"  {_DASH}")

    if signals:
        for sig in signals:
            sym  = sig.get('symbol', '?')
            dirn = sig.get('direction', '?')
            conf = sig.get('confidence', 0.0)
            lines.append(f"  ✔ SIGNAL  {sym}  {dirn}  confidence={conf:.3f}")
    else:
        lines.append("  No signals this cycle.")

    lines.append(_SEP)
    return lines


def ensure_digest_log_exists(log_path: Optional[Path] = None) -> None:
    """
    Touch cycle_digest.log so PowerShell's Get-Content -Wait can start
    monitoring immediately on SAQ startup, before the first H1 cycle fires.
    Safe to call multiple times — does nothing if the file already exists.
    """
    if log_path is None:
        try:
            from config import LOGS_DIR
            log_path = LOGS_DIR / 'cycle_digest.log'
        except Exception:
            log_path = Path('logs/cycle_digest.log')
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if not log_path.exists():
            log_path.touch()
            logger.debug(f"CycleDigest: created empty log at {log_path}")
    except Exception as exc:
        logger.warning(f"CycleDigest: could not pre-create log: {exc}")


def write_cycle_digest(
    cycle_time: datetime,
    timeframe:  str,
    long_pred:  Optional[Any]  = None,
    short_pred: Optional[Any]  = None,
    signals:    Optional[list] = None,
    elapsed:    float          = 0.0,
    log_path:   Optional[Path] = None,
) -> None:
    """
    Write one cycle block to cycle_digest.log.

    Parameters
    ----------
    cycle_time  : When this cycle ran.
    timeframe   : Timeframe string (e.g. 'H1').
    long_pred   : PullBackEntryPredictor instance for Long model.
    short_pred  : PullBackEntryPredictor instance for Short model.
    signals     : List of signal dicts from result_set.get_all_predictions().
    elapsed     : Cycle elapsed seconds.
    log_path    : Override default log path (logs/cycle_digest.log).
    """
    if log_path is None:
        try:
            from config import LOGS_DIR
            log_path = LOGS_DIR / 'cycle_digest.log'
        except Exception:
            log_path = Path('logs/cycle_digest.log')

    try:
        lines = _build_digest_lines(
            cycle_time, timeframe,
            long_pred, short_pred,
            signals or [], elapsed,
        )
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n\n')

    except Exception as exc:
        logger.warning(f"CycleDigest: failed to write digest: {exc}")
