"""
Solara AI Quant - Pipeline Runner

Orchestrates the full processing pipeline when a CSV file changes.
Uses saq_log.render_pipeline_block() so each timeframe's status
updates IN PLACE — no repeated scrolling output.

Stage 4 (global feature engineer) behaviour:
    SKIPPED  — when ALL triggered models have a feature_engineering_class.
               Each model's own FE runs inside Stage 5 instead.
               This preserves pre-computed EA CSV values (RSI, BB, etc.)
               which would otherwise be overwritten with wrong values
               computed from only 3 rows of history.

    RUNS     — when at least one triggered model has NO
               feature_engineering_class (legacy models like Stella Alpha
               that rely on the global FeatureEngineer).

Stage 7 (risk):
    Converts AggregatedSignal → ApprovedSignal.
    Applies position-limit check per model: if a model already has
    max_positions open (filtered by magic number), the signal is skipped.
    All other signals are approved with lot size resolved via confidence tiers.

Stage 8 (execute):
    Places market orders via MT5Manager.
    Skipped silently if MT5 is not connected (dev mode).
    Each filled order is logged to the trade_log database table.
    The triggered timeframe is passed through so get_tp_pips(tf) /
    get_sl_pips(tf) timeframe overrides are applied correctly.
"""

from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime
import logging

from config import feature_config
from ingestion import CSVReader, DataValidator
from features import feature_engineer
from .cycle_lock import Timeframe
from logger import saq_log

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of a pipeline execution."""
    timeframe: str
    success: bool
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    rows_processed: int
    symbols_found: List[str]
    models_run: int
    signals_generated: int
    trades_executed: int
    error_message: Optional[str] = None


class PipelineRunner:
    """
    Runs the full processing pipeline for a timeframe.

    Only fires if at least one model is registered for the trigger TF.
    Multi-TF merging is driven by each model's merge_timeframes field.
    """

    def __init__(self):
        self.csv_reader = CSVReader()
        self.data_validator = DataValidator()

        # ExecutionEngine is created once and reused across cycles so that its
        # predictor and feature-engineer caches survive between H1/H4 triggers.
        # Creating a new engine each cycle (the old behaviour) discarded all
        # caches, causing joblib model files to reload from disk every cycle.
        from engine.execution_engine import ExecutionEngine
        from engine.registry import model_registry
        self._execution_engine = ExecutionEngine(registry=model_registry)

    def run(self, file_path: Path, timeframe: Timeframe) -> PipelineResult:
        start_time = datetime.now()

        # Early exit — no models for this TF
        from engine.registry import model_registry
        models_for_tf = model_registry.get_models_for_timeframe(timeframe.value)
        if not models_for_tf:
            logger.debug(f"No enabled models for {timeframe.value} — skipping")
            return PipelineResult(
                timeframe=timeframe.value, success=True,
                start_time=start_time, end_time=datetime.now(),
                duration_seconds=0, rows_processed=0,
                symbols_found=[], models_run=0,
                signals_generated=0, trades_executed=0,
            )

        # Stage state accumulator
        stages  = []
        signals = []

        result = PipelineResult(
            timeframe=timeframe.value, success=False,
            start_time=start_time, end_time=start_time,
            duration_seconds=0, rows_processed=0,
            symbols_found=[], models_run=0,
            signals_generated=0, trades_executed=0,
        )

        try:
            # ── Stage 1: INGEST ───────────────────────────────────────────────
            df, error = self._stage_ingest(file_path)
            if error:
                stages.append(dict(step=1, name="ingest", status="error", detail=error))
                result.error_message = f"Ingest failed: {error}"
                return self._finalize(result, stages, signals, start_time)

            # ── Stage 2: VALIDATE ─────────────────────────────────────────────
            validation = self._stage_validate(df)
            if not validation.is_valid:
                stages.append(dict(step=1, name="ingest",   status="ok",
                    detail=f"{len(df)} rows"))
                stages.append(dict(step=2, name="validate", status="error",
                    detail=" · ".join(str(e) for e in validation.errors)))
                result.error_message = f"Validation failed: {validation.errors}"
                return self._finalize(result, stages, signals, start_time)

            df = validation.df
            result.rows_processed = len(df)
            result.symbols_found  = validation.symbols_found

            stages.append(dict(step=1, name="ingest",   status="ok",
                detail=f"{len(df)} rows · {len(validation.symbols_found)} symbols"))
            stages.append(dict(step=2, name="validate", status="ok",
                detail=f"{validation.rows_before} → {validation.rows_after} rows · all clean"))

            # ── Stage 3: MULTI-TF MERGE ───────────────────────────────────────
            df, merge_detail, merge_status = self._stage_merge(
                df, timeframe, models_for_tf
            )
            stages.append(dict(step=3, name="merge", status=merge_status,
                detail=merge_detail))

            # ── Stage 4: FEATURES ─────────────────────────────────────────────
            # Skip global feature engineering when every triggered model has
            # its own feature_engineering_class — those models compute their
            # own features inside Stage 5 using the raw EA CSV values.
            # Run it only for legacy models that have no custom FE class.
            all_have_custom_fe = all(
                bool(m.feature_engineering_class) for m in models_for_tf
            )

            if all_have_custom_fe:
                stages.append(dict(step=4, name="features", status="skip",
                    detail="per-model FE — global stage skipped"))
                logger.debug(
                    f"Stage 4 skipped for {timeframe.value} — "
                    f"all models use per-model feature engineering"
                )
            else:
                has_secondary = any(
                    c.endswith("_close")
                    for c in df.columns
                    if "_" in c and not c.startswith("prev")
                )
                df = feature_engineer.compute_all_features(
                    df, include_d1=has_secondary
                )
                stages.append(dict(step=4, name="features", status="ok",
                    detail=f"{len(df.columns)} columns computed"))

            # ── Stage 5: MODELS ───────────────────────────────────────────────
            result_set = self._stage_models(df, timeframe)
            result.models_run = result_set.total_models if result_set else 0

            if result_set and result_set.failed_models > 0:
                # At least one model actually crashed or timed out
                model_status = "error"
                model_detail = (
                    f"{result_set.failed_models} failed · "
                    f"{result_set.successful_models} ok · "
                    f"{result_set.duration_seconds:.2f}s"
                )
            elif result_set and result_set.total_models > 0:
                # All models ran (may be EMPTY = no setups, but no crash)
                model_status = "ok"
                model_detail = (
                    f"{result_set.total_models}/{result_set.total_models} ran · "
                    f"{result_set.total_predictions} predictions · "
                    f"{result_set.duration_seconds:.2f}s"
                )
            else:
                model_status = "skip"
                model_detail = "no models"

            stages.append(dict(step=5, name="models",
                status=model_status, detail=model_detail))

            # ── Stage 6: SIGNALS ──────────────────────────────────────────────
            valid_signals = self._stage_signals(result_set)
            result.signals_generated = len(valid_signals)

            if valid_signals:
                stages.append(dict(step=6, name="signals", status="ok",
                    detail=f"{len(valid_signals)} valid from "
                           f"{result_set.total_predictions if result_set else 0} predictions"))
                for sig in valid_signals:
                    features = sig.raw_signal.features or {}
                    score    = features.get("model_score", sig.combined_confidence)
                    a_rsi    = features.get("a_rsi_value", 0)
                    signals.append(dict(
                        symbol=sig.symbol,
                        direction=sig.direction.value,
                        confidence=sig.combined_confidence,
                        detail=f"score {score:.3f} · a_rsi {a_rsi:.1f}" if a_rsi else "",
                    ))
            else:
                no_pred = (result_set.total_predictions == 0) if result_set else True
                stages.append(dict(step=6, name="signals", status="skip",
                    detail="no setups found" if no_pred
                    else "none passed conflict check"))

            # ── Stage 7: RISK ─────────────────────────────────────────────────
            approved, risk_skip_reason = self._stage_risk(valid_signals, timeframe)
            if approved:
                stages.append(dict(step=7, name="risk", status="ok",
                    detail=f"{len(approved)}/{len(valid_signals)} approved"))
            elif valid_signals:
                stages.append(dict(step=7, name="risk", status="skip",
                    detail=f"0/{len(valid_signals)} approved — {risk_skip_reason}"))
            else:
                stages.append(dict(step=7, name="risk", status="skip",
                    detail="no signals to check"))

            # ── Stage 8: EXECUTE ──────────────────────────────────────────────
            trades = self._stage_execute(approved, timeframe)
            result.trades_executed = len(trades)
            if trades:
                stages.append(dict(step=8, name="execute", status="ok",
                    detail=f"{len(trades)} order{'s' if len(trades) > 1 else ''} placed"))
            elif approved:
                stages.append(dict(step=8, name="execute", status="skip",
                    detail="MT5 not connected (dev mode)"))
            else:
                stages.append(dict(step=8, name="execute", status="skip",
                    detail="nothing to execute"))

            result.success = True

        except Exception as e:
            logger.exception(f"Pipeline crashed in {timeframe.value}: {e}")
            stages.append(dict(step=0, name="crash", status="error",
                detail=str(e)[:80]))
            result.error_message = str(e)

        return self._finalize(result, stages, signals, start_time)

    def _finalize(
        self,
        result: PipelineResult,
        stages: list,
        signals: list,
        start_time: datetime,
    ) -> PipelineResult:
        result.end_time = datetime.now()
        result.duration_seconds = (
            result.end_time - result.start_time
        ).total_seconds()

        if not result.success:
            outcome = "failed"
            detail  = (result.error_message or "")[:60]
        elif result.signals_generated > 0:
            n       = result.signals_generated
            outcome = f"{n} signal{'s' if n > 1 else ''}"
            syms    = " · ".join(s['symbol'] for s in signals[:4])
            detail  = syms
        else:
            outcome = "no signal"
            detail  = "no setups found"

        saq_log.render_pipeline_block(
            timeframe=result.timeframe,
            stages=stages,
            signals=signals,
            outcome=outcome,
            elapsed=result.duration_seconds,
            footer_detail=detail,
        )
        saq_log.watching()
        return result

    # =========================================================================
    # Stage implementations
    # =========================================================================

    def _stage_ingest(self, file_path: Path):
        df, error = self.csv_reader.read_and_parse(file_path)
        if error:
            logger.error(f"Ingest failed: {error}")
            return None, error
        return df, None

    def _stage_validate(self, df):
        return self.data_validator.validate(df)

    def _stage_merge(self, df, timeframe: Timeframe, models) -> tuple:
        from features.tf_merger import merge_timeframes_for_models

        merged_df, merged_tfs = merge_timeframes_for_models(
            base_df=df, base_tf=timeframe.value, models=models
        )

        if merged_tfs:
            added = len([c for c in merged_df.columns if c not in df.columns])
            return merged_df, f"+{added} {'/'.join(merged_tfs)} columns merged", "ok"

        needed = []
        for m in models:
            for tf in m.get_merge_timeframe_strings():
                if tf.upper() != timeframe.value.upper() and tf not in needed:
                    needed.append(tf)

        if needed:
            return merged_df, f"{'/'.join(needed)} CSV not found — skipped", "warn"
        return merged_df, "no extra TFs required", "ok"

    def _stage_models(self, df, timeframe: Timeframe):
        return self._execution_engine.execute_for_timeframe(
            timeframe=timeframe.value,
            df_merged=df,
            feature_columns=list(df.columns),
        )

    def _stage_signals(self, result_set) -> List:
        if result_set is None or result_set.total_predictions == 0:
            return []
        from signals.aggregator import SignalAggregator
        return SignalAggregator().aggregate(result_set)

    def _stage_risk(self, signals: List, timeframe: Timeframe):
        """
        Stage 7: Risk / position-limit check.

        Converts AggregatedSignal → ApprovedSignal.
        Checks (in order):
          1. Cooldown  — no re-entry within 5 min on same symbol+magic
          2. Position  — model has not exceeded max_positions (by magic)
          3. Confidence — signal confidence matches a lot-size tier

        No MT5 connection required — position check uses mt5_manager
        only if connected; if not connected, skips the check and
        approves everything (so dev-mode signals still reach Stage 8
        where they are logged and dropped cleanly).

        Returns:
            (approved: List[ApprovedSignal], skip_reason: str)
            skip_reason is a human-readable summary of why signals were
            rejected, used by the Stage 7 terminal display.
        """
        from signals.signal_models import ApprovedSignal, SignalStatus, RejectionReason
        from engine.registry import model_registry

        if not signals:
            return [], ""

        # Try to get live position counts (None = MT5 not connected)
        try:
            from mt5.mt5_manager import mt5_manager
            mt5_connected = mt5_manager.is_connected
        except Exception:
            mt5_connected = False

        # Cooldown window — blocks re-entry on the same symbol+model after a fill.
        # Prevents the EA writing the CSV multiple times per bar from placing
        # duplicate trades on the same setup seconds apart.
        COOLDOWN_SECONDS = 300  # 5 minutes

        # Rejection counters for the Stage 7 display summary
        n_cooldown   = 0
        n_pos_limit  = 0
        n_low_conf   = 0

        approved = []
        for agg_sig in signals:
            model_config = model_registry.get_model(agg_sig.raw_signal.model_name)
            if model_config is None:
                logger.warning(f"Risk: no config for {agg_sig.raw_signal.model_name}")
                continue

            # ── 1. Cooldown check ──────────────────────────────────────────
            # Skip if a FILLED trade for this symbol+magic was placed within
            # the last COOLDOWN_SECONDS. Works in both prod and dev mode.
            try:
                from state.database import db_manager
                from sqlalchemy import text as _text
                with db_manager.engine.connect() as _conn:
                    recent = _conn.execute(_text("""
                        SELECT COUNT(*) FROM trade_log
                        WHERE symbol = :sym
                          AND magic  = :magic
                          AND status = 'FILLED'
                          AND (JULIANDAY('now') - JULIANDAY(requested_at)) * 86400
                              <= :secs
                    """), {
                        'sym':   agg_sig.symbol,
                        'magic': model_config.magic,
                        'secs':  COOLDOWN_SECONDS,
                    }).scalar()
                if recent and recent > 0:
                    n_cooldown += 1
                    logger.info(
                        f"Risk: {agg_sig.symbol} skipped — cooldown active "
                        f"({COOLDOWN_SECONDS}s) [{agg_sig.raw_signal.model_name}]"
                    )
                    continue
            except Exception as _e:
                logger.warning(f"Risk: cooldown check failed for {agg_sig.symbol}: {_e}")

            # ── 2. Position-limit check (only when connected — dev mode skips)
            if mt5_connected:
                try:
                    from mt5.mt5_manager import mt5_manager
                    open_count = mt5_manager.get_position_count(
                        magic=model_config.magic
                    )
                    max_pos = model_config.get_max_positions(timeframe.value)
                    if open_count >= max_pos:
                        n_pos_limit += 1
                        logger.info(
                            f"Risk: {agg_sig.symbol} skipped — "
                            f"{agg_sig.raw_signal.model_name} at max positions "
                            f"({open_count}/{max_pos})"
                        )
                        continue
                except Exception as e:
                    logger.warning(f"Risk: position count check failed: {e}")

            # ── 3. Confidence-tier check ───────────────────────────────────
            # None means confidence is below the lowest tier — reject signal.
            lot_size = model_config.get_fixed_lot(agg_sig.combined_confidence)

            if lot_size is None:
                n_low_conf += 1
                logger.info(
                    f"Risk: {agg_sig.symbol} rejected — "
                    f"score {agg_sig.combined_confidence:.4f} below min tier "
                    f"for {agg_sig.raw_signal.model_name}"
                )
                continue

            approved.append(ApprovedSignal(
                aggregated_signal=agg_sig,
                lot_size=lot_size,
                status=SignalStatus.APPROVED,
            ))

        # Build a concise rejection reason string for the Stage 7 display
        parts = []
        if n_pos_limit:
            parts.append(f"pos limit ×{n_pos_limit}")
        if n_cooldown:
            parts.append(f"cooldown ×{n_cooldown}")
        if n_low_conf:
            parts.append(f"low conf ×{n_low_conf}")
        skip_reason = ", ".join(parts) if parts else "rejected"

        return approved, skip_reason

    def _stage_execute(self, approved: List, timeframe: Timeframe) -> List:
        """
        Stage 8: Trade execution via MT5.

        For each ApprovedSignal:
          1. Resolve TP/SL prices using timeframe-aware config getters.
          2. Place market order via mt5_manager.place_order().
          3. Log result to trade_log database table.

        If MT5 is not connected (dev mode) all signals are logged and
        dropped — no exception is raised.
        """
        from signals.signal_models import ExecutedSignal, SignalStatus, RejectionReason
        from engine.registry import model_registry

        if not approved:
            return []

        try:
            from mt5.mt5_manager import mt5_manager
            import MetaTrader5 as mt5
            MT5_AVAILABLE = True
        except ImportError:
            MT5_AVAILABLE = False
            mt5_manager = None
            mt5 = None

        executed = []

        for appr in approved:
            raw     = appr.raw_signal
            symbol  = raw.symbol
            model_config = model_registry.get_model(raw.model_name)

            if model_config is None:
                logger.warning(f"Execute: no config for {raw.model_name}")
                continue

            # ── Resolve TP / SL with timeframe override ────────────────────
            tp_pips = model_config.get_tp_pips(timeframe.value)
            sl_pips = model_config.get_sl_pips(timeframe.value)
            pip_size = 0.01 if 'JPY' in symbol.upper() else 0.0001

            # ── Check MT5 availability ─────────────────────────────────────
            if not MT5_AVAILABLE or not mt5_manager.is_connected:
                logger.info(
                    f"Execute (dev): {symbol} {raw.direction.value} "
                    f"lot={appr.lot_size} TP={tp_pips}pip SL={sl_pips}pip "
                    f"[MT5 not connected — order NOT placed]"
                )
                continue

            # ── Determine order type and prices ────────────────────────────
            try:
                tick = mt5.symbol_info_tick(symbol)
                if tick is None:
                    logger.error(f"Execute: no tick for {symbol}")
                    continue

                if raw.direction.value == "SHORT":
                    order_type  = mt5.ORDER_TYPE_SELL
                    entry_price = tick.bid
                    sl_price    = entry_price + (sl_pips * pip_size)
                    tp_price    = entry_price - (tp_pips * pip_size)
                else:
                    order_type  = mt5.ORDER_TYPE_BUY
                    entry_price = tick.ask
                    sl_price    = entry_price - (sl_pips * pip_size)
                    tp_price    = entry_price + (tp_pips * pip_size)

                # Round to symbol digits
                sym_info = mt5.symbol_info(symbol)
                if sym_info:
                    digits   = sym_info.digits
                    sl_price = round(sl_price, digits)
                    tp_price = round(tp_price, digits)

            except Exception as e:
                logger.error(f"Execute: price calculation failed for {symbol}: {e}")
                continue

            # ── Place order ────────────────────────────────────────────────
            try:
                result = mt5_manager.place_order(
                    symbol=symbol,
                    order_type=order_type,
                    volume=appr.lot_size,
                    price=entry_price,
                    sl=sl_price,
                    tp=tp_price,
                    magic=model_config.magic,
                    # e.g. "UBB Rejection H4" or "UBB Rejection M5" — visible in MT5
                    comment=f"{model_config.comment or model_config.name} {timeframe.value}"[:31],
                )
            except Exception as e:
                logger.error(f"Execute: place_order raised for {symbol}: {e}")
                result = None

            if result is not None:
                ticket = getattr(result, 'order', 0)
                score  = appr.aggregated_signal.combined_confidence
                logger.info(
                    f"Execute: {symbol} {raw.direction.value} "
                    f"ticket={ticket} score={score:.4f} lot={appr.lot_size} "
                    f"entry={entry_price} SL={sl_price} TP={tp_price}"
                )

                try:
                    from state.database import db_manager

                    # ── Log signal with score ──────────────────────────────
                    db_manager.log_signal(
                        model_name=raw.model_name,
                        symbol=symbol,
                        direction=raw.direction.value,
                        confidence=score,
                        weight=appr.aggregated_signal.total_weight or 1.0,
                        aggregation_status='PASSED',
                        risk_status='APPROVED',
                        trade_ticket=ticket,
                    )

                    # ── Log trade ──────────────────────────────────────────
                    db_manager.log_trade(
                        symbol=symbol,
                        direction=raw.direction.value,
                        magic=model_config.magic,
                        volume=appr.lot_size,
                        status='FILLED',
                        model_name=raw.model_name,
                        ticket=ticket,
                        entry_price=entry_price,
                        sl_price=sl_price,
                        tp_price=tp_price,
                    )
                except Exception as e:
                    logger.warning(f"Execute: db log failed for {symbol}: {e}")

                executed.append(result)
            else:
                logger.error(
                    f"Execute: order FAILED for {symbol} {raw.direction.value}"
                )
                try:
                    from state.database import db_manager

                    # ── Log signal even on failure so score is preserved ───
                    db_manager.log_signal(
                        model_name=raw.model_name,
                        symbol=symbol,
                        direction=raw.direction.value,
                        confidence=appr.aggregated_signal.combined_confidence,
                        aggregation_status='PASSED',
                        risk_status='APPROVED',
                        trade_ticket=None,
                    )

                    db_manager.log_trade(
                        symbol=symbol,
                        direction=raw.direction.value,
                        magic=model_config.magic,
                        volume=appr.lot_size,
                        status='FAILED',
                        model_name=raw.model_name,
                    )
                except Exception as e:
                    logger.warning(f"Execute: db log (failed) error: {e}")

        return executed


pipeline_runner = PipelineRunner()
