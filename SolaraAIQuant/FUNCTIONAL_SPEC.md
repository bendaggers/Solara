# Solara AI Quant (SAQ) — Functional Specification

**Version:** 1.0.0  
**Last Updated:** 2026-04-08  
**Status:** Active Development

---

## 1. System Overview

Solara AI Quant (SAQ) is a Python-based automated algorithmic trading system that bridges **MetaTrader 5 (MT5)** with machine learning models. It monitors CSV files written by an MT5 Expert Advisor (EA), runs ML inference on each new bar, and places or logs market orders.

### 1.1 Modes of Operation

| Mode | Command | Behavior |
|------|---------|----------|
| Development | `python main.py` | No MT5 connection; signals logged but not placed; Survivor Engine skipped |
| Production | `python main.py --production` | Full MT5 connection; real orders placed; Survivor Engine runs |
| Dry Run | `python main.py --production --dry-run` | MT5 connected but orders logged only |
| Status | `python main.py --status` | Print configuration and model registry summary |
| Tests | `python main.py --test` | Run pytest suite |

---

## 2. System Architecture

### 2.1 High-Level Data Flow

```
MT5 Expert Advisor (MQL5)
  │  Writes OHLCV + pre-computed indicators to CSV (28 symbols)
  │  Filename: marketdata_PERIOD_<TF>.csv  (in MQL5/Files/)
  ▼
OS file-change event (watchdog library)
  │  Debounce 2s → wait 10s for EA to finish writing all symbols
  ▼
FileObserver → CycleLock (prevents concurrent runs per TF)
  ▼
PipelineRunner.run(file_path, timeframe)
  ├── Stage 1: Ingest        — CSV → DataFrame
  ├── Stage 2: Validate      — OHLC sanity checks, remove bad rows
  ├── Stage 3: Merge         — join additional TF DataFrames (merge_asof)
  ├── Stage 4: Features      — SKIPPED when all models have custom FEs
  ├── Stage 5: Models        — parallel ML inference (ThreadPoolExecutor)
  ├── Stage 6: Signals       — conflict checker → AggregatedSignals
  ├── Stage 7: Risk          — cooldown guard, position limits, lot sizing
  └── Stage 8: Execute       — MT5 market orders + DB logging

Independent 60-second loop (production only):
SurvivorEngine → 22-stage progressive trailing stop ratchet
```

### 2.2 Module Map

| Module | Path | Responsibility |
|--------|------|----------------|
| Entry point | `main.py` | Startup orchestration, signal handling, graceful shutdown |
| Configuration | `config.py` | All dataclasses + env var loading |
| Logger | `logger.py` | Rich colorized terminal output; in-place pipeline block rendering |
| Model Registry | `model_registry.yaml` | Single source of truth for all ML models |
| Registry loader | `engine/registry.py` | Parses YAML → `ModelConfig` dataclasses; validates magic numbers |
| Execution engine | `engine/execution_engine.py` | `ThreadPoolExecutor`; per-model FE + prediction; caches instances |
| Model health | `engine/model_health.py` | Auto-disable after 3 consecutive failures |
| File observer | `file_watcher/file_observer.py` | OS-native file watching via watchdog |
| Cycle lock | `file_watcher/cycle_lock.py` | Per-TF mutex prevents pipeline overlap |
| Pipeline runner | `file_watcher/pipeline_runner.py` | Orchestrates all 8 stages; renders terminal block |
| CSV reader | `ingestion/csv_reader.py` | Parses EA CSV; normalises column names |
| Data validator | `ingestion/data_validator.py` | Schema + OHLC integrity checks |
| TF merger | `features/tf_merger.py` | `merge_asof` merge of secondary TF CSVs |
| H4/D1 merger | `features/h4_d1_merger.py` | Legacy H4+D1 merge helper |
| Base FE | `features/base_feature_engineer.py` | Abstract base with `safe_compute()` validation wrapper |
| Global FE | `features/feature_engineer.py` | Legacy global feature engineer (used only for models without custom FE) |
| PH features | `features/punk_hazard_features.py` | Punk Hazard H4 feature set (43 features + 2 regime columns) |
| UBB features | `features/ubb_features.py` | UBB Rejection A/B/C triplet feature set |
| TI V2 features | `features/trend_id_v2_features.py` | TI V2 QUANT_V2_CORE 41-feature set (external dependency) |
| Stella features | `features/stella_alpha_features.py` | Discontinued (legacy) |
| Base predictor | `predictors/base_predictor.py` | Abstract base; pickle loading; symbol filter; `create_signal()` |
| PH Long | `predictors/punk_hazard_long.py` | EURUSD H4 BB lower-band reversal LONG |
| PH Short | `predictors/punk_hazard_short.py` | EURUSD H4 BB upper-band reversal SHORT |
| UBB Rejection | `predictors/ubb_rejection.py` | 10-pair H4 upper-BB 3-candle rejection SHORT |
| TI V2 | `predictors/trend_identifier_v2.py` | 28-pair H4 trend classifier (shared by LONG and SHORT entries) |
| Stella Alpha | `predictors/stella_alpha_long.py` | Discontinued |
| Signal models | `signals/signal_models.py` | `RawSignal` → `AggregatedSignal` → `ApprovedSignal` → `ExecutedSignal` |
| Aggregator | `signals/aggregator.py` | Converts predictions to signals; calls conflict checker |
| Conflict checker | `signals/conflict_checker.py` | Suppresses opposing signals from same model |
| MT5 manager | `mt5/mt5_manager.py` | Thread-safe singleton; connect/disconnect; `place_order()`, `modify_position()` |
| Symbol helper | `mt5/symbol_helper.py` | Symbol info utilities |
| Database | `state/database.py` | `DatabaseManager` singleton; WAL mode; session scope |
| ORM models | `state/models.py` | SQLAlchemy tables: positions, transitions, runs, signals, trades, health, stats |
| DB extensions | `state/database_extensions.py` | Additional DB query helpers |
| Survivor engine | `survivor/survivor_engine.py` | 22-stage trailing stop logic |
| Survivor runner | `survivor/survivor_runner.py` | 60-second polling loop thread |
| Stage definitions | `survivor/stage_definitions.yaml` | Stage trigger pips + protection percentages |
| Survivor reporter | `survivor/survivor_reporter.py` | Survivor analytics |
| Dashboard server | `dashboard/trade_server.py` | Standalone HTTP server (port 8765) |
| Query trades | `query_trades.py` | CLI query tool for `trade_log` |

---

## 3. Configuration

All configuration is loaded from environment variables (via `.env`) into dataclasses in `config.py`.

### 3.1 Key Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MT5_LOGIN` | 0 | MT5 account login number |
| `MT5_PASSWORD` | — | MT5 account password |
| `MT5_SERVER` | — | MT5 broker server name |
| `MT5_TERMINAL_PATH` | system default | Path to MT5 terminal folder |
| `SAQ_ENV` | `development` | `development` or `production` |
| `WATCHDOG_DEBOUNCE_SECONDS` | `2` | Debounce delay before re-processing same file |
| `WATCHDOG_PROCESSING_DELAY_SECONDS` | `10` | Wait for EA to finish writing all 28 symbol rows |
| `SURVIVOR_CHECK_INTERVAL_SECONDS` | `60` | How often Survivor Engine checks positions |
| `MAX_DAILY_DRAWDOWN_PCT` | `0.05` | 5% daily drawdown limit |
| `MAX_DAILY_TRADES` | `20` | Maximum trades per day |
| `MAX_RISK_PER_TRADE` | `0.02` | 2% risk per trade |
| `MAX_SLIPPAGE_POINTS` | `30` | Maximum slippage in points |

### 3.2 Watched Timeframes

| TF | CSV Filename |
|----|-------------|
| M5 | `marketdata_PERIOD_M5.csv` |
| M15 | `marketdata_PERIOD_M15.csv` |
| H1 | `marketdata_PERIOD_H1.csv` |
| H4 | `marketdata_PERIOD_H4.csv` |
| D1 | `marketdata_PERIOD_D1.csv` |

---

## 4. Pipeline Stages (Detail)

### Stage 1: Ingest

- `CSVReader.read_and_parse(file_path)` reads the EA CSV.
- Expected columns: `timestamp`, `symbol`, `open`, `high`, `low`, `close`, `volume`.
- Timestamp format: `%Y.%m.%d %H:%M:%S`.
- Returns a `pd.DataFrame` with one row per bar per symbol (multi-symbol, flat format).

### Stage 2: Validate

- `DataValidator.validate(df)` performs:
  - Schema check: required columns present.
  - OHLC integrity: `high >= low`, no zero prices.
  - Drops rows with null symbol.
  - Returns `ValidationResult` with `is_valid`, `rows_before`, `rows_after`, `symbols_found`, `errors`.

### Stage 3: Multi-TF Merge

- `merge_timeframes_for_models()` collects the union of `merge_timeframes` from all triggered models.
- Uses `pd.merge_asof` (backward direction) — no lookahead bias.
- Secondary TF columns are prefixed with lowercase TF name (e.g. `d1_close`, `h4_rsi_value`).
- If a secondary TF CSV is not found on disk, the merge is skipped with a warning.
- Currently, all active models set `merge_timeframes: []` — this stage effectively passes through.

### Stage 4: Global Feature Engineering

- **SKIPPED** when ALL triggered models have a `feature_engineering_class` set.
- **RUNS** only for legacy models (e.g. Stella Alpha) that have no custom FE class.
- Skipping is intentional: it preserves pre-computed indicator values (RSI, BB, etc.) from the EA CSV that per-model FEs need as raw inputs. Re-computing these from only 3 rows of history would produce garbage.

### Stage 5: Model Execution

`ExecutionEngine.execute_for_timeframe()` runs all enabled, healthy models in parallel:

1. For each model, in a thread:
   - **Load predictor** (cached after first load via `_predictor_cache`).
   - **Load feature engineer** (cached after first load via `_feature_engineer_cache`).
   - **`feature_engineer.safe_compute(df_merged)`** — validates input columns → calls `compute()` → validates output features.
   - **Trim DataFrame** to `[symbol, timestamp] + required_features` (exact column order from training).
   - **`predictor.predict(df_featured, model_config)`** — applies entry gates, runs model, returns `List[Dict]`.
2. Health is recorded per model (`ModelHealthTracker`). After 3 consecutive failures/timeouts, the model is auto-disabled.
3. Returns `ModelResultSet` (all predictions across all models).

### Stage 6: Signal Aggregation

- `SignalAggregator.aggregate(result_set)`:
  1. Converts prediction dicts to `RawSignal` objects.
  2. Runs `ConflictChecker.check_conflicts()` — suppresses opposing signals from the **same model**.
  3. Returns only validated `AggregatedSignal` objects.
- Strategy is `INDEPENDENT_PASSTHROUGH`: each model's signals are independent; no multi-model voting required.

### Stage 7: Risk

For each `AggregatedSignal`:

1. **Cooldown check** (5 minutes): queries `trade_log` for FILLED trades on same `(symbol, magic)` within 300 seconds. Prevents duplicate fills from rapid EA CSV writes within the same bar.
2. **Position limit check** (production only): calls `mt5_manager.get_position_count(magic)`. If at `max_positions`, signal is skipped.
3. **Lot size resolution**: `model_config.get_fixed_lot(confidence)` looks up the confidence tier. Returns `None` if below all tiers → signal rejected.
4. Returns `List[ApprovedSignal]` with resolved `lot_size`.

### Stage 8: Trade Execution

For each `ApprovedSignal`:

1. Resolves TP/SL prices using **timeframe-aware** `model_config.get_tp_pips(tf)` / `get_sl_pips(tf)`.
2. Fetches current tick via `mt5.symbol_info_tick(symbol)`.
3. Calculates `sl_price` and `tp_price` with `pip_size = 0.01 if 'JPY' in symbol else 0.0001`.
4. Rounds to symbol's `digits` precision.
5. Calls `mt5_manager.place_order()` → `mt5.order_send()`.
6. Logs result to both `signal_log` and `trade_log` tables (even on failure).
7. In dev mode (MT5 not connected): signals are logged and dropped silently.

**Order comment format:** `"{model.comment} {timeframe}"` (max 31 chars, visible in MT5 terminal).

---

## 5. Model Registry

Defined in `model_registry.yaml`. Loaded by `ModelRegistry` into `ModelConfig` dataclasses.

### 5.1 Registry Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Unique model name |
| `class_path` | str | Python import path for the predictor class |
| `model_file` | str | `.pkl` filename in `Models/` directory |
| `feature_version` | str | Feature set version identifier |
| `model_type` | `LONG` / `SHORT` | Direction of signals this entry emits |
| `timeframe` | str | TF the model was trained on |
| `trigger_timeframes` | list[str] | Which CSV changes fire this model |
| `merge_timeframes` | list[str] | Additional TF CSVs to merge before FE |
| `feature_engineering_class` | str | Python import path for the FE class |
| `confidence_tiers` | list | `min_confidence` / `max_confidence` / `fixed_lot` mappings |
| `timeframe_overrides` | dict | Per-TF overrides for `tp_pips`, `sl_pips`, `max_holding_bars`, `max_positions` |
| `symbols` | list[str] | Allowed symbols (empty = all) |
| `magic` | int | MT5 magic number (must be unique) |
| `max_positions` | int | Maximum concurrent open positions for this model |
| `tp_pips` | int | Default take profit in pips |
| `sl_pips` | int | Default stop loss in pips |
| `max_holding_bars` | int | Maximum bars to hold (used by Survivor timeout) |
| `enabled` | bool | Whether the model is active |

### 5.2 Magic Number Convention

Format: `XXYYZZ`  
- `XX` = Strategy ID (10=Stella, 20=UBB, 30=PunkHazard, 40=TrendID)  
- `YY` = Timeframe (01=M5, 02=M15, 03=H1, 04=H4, 05=D1)  
- `ZZ` = Variant number

### 5.3 Confidence Tiers

First matching tier wins. If confidence falls below the lowest tier's `min_confidence`, `get_fixed_lot()` returns `None` and the signal is rejected at Stage 7.

---

## 6. Registered Models

### 6.1 Punk Hazard Long (enabled)

| Field | Value |
|-------|-------|
| Magic | 300401 |
| Direction | LONG |
| Timeframe | H4 |
| Trigger TFs | M15, H1, H4 |
| Algorithm | `CalibratedClassifierCV` (sigmoid, LightGBM base) |
| Probability threshold | 0.50 |
| Features | 43 (`ph1` feature version) |
| Symbols | 28 major + minor forex pairs |
| Max positions | 1 |
| Training | Run 29, 303 walk-forward folds, 2000–2025, EURUSD H4 |
| EV (mean) | +5.19 pips/trade |
| EV 2020–2025 | +3.97 pips |
| Calibration ECE | 0.179 (sigmoid) |

**Entry gates (all must pass):**
1. `bb_touch_strength_long > 0.997` — price at or below BB lower band.
2. Regime NOT in `{(HighVol+Down), (LowVol+Up)}` — blocks falling knife + trend conflict.
3. `P(win) >= 0.50`.

**TP/SL:** Loaded from `.pkl` export at model load time. Registry values are fallbacks only.

---

### 6.2 Punk Hazard Short (enabled)

| Field | Value |
|-------|-------|
| Magic | 300402 |
| Direction | SHORT |
| Timeframe | H4 |
| Trigger TFs | M15, H1, H4 |
| Algorithm | `CalibratedClassifierCV` (sigmoid) |
| Probability threshold | 0.48 |
| Max positions | 1 |

**Entry gates:**
1. `bb_touch_strength > 0.997` — price at or above BB upper band.
2. Regime NOT in `{(LowVol+Up)}` — HighVol+Range is **active** (restored in Run 19; removing it caused EV+% to drop 45.8% → 42.5%).
3. `P(win) >= 0.48`.

**Important:** Do NOT raise short threshold to 0.52 in combined mode. Run 21 confirmed that this causes negative interaction — short entries removed from HighVol+Range get replaced by long entries which are negative in 2020–2025.

---

### 6.3 UBB Rejection (disabled)

| Field | Value |
|-------|-------|
| Magic | 200001 |
| Direction | SHORT |
| Timeframe | H4 |
| Trigger TFs | H4, M5, M15, H1 |
| Algorithm | sklearn Pipeline (LightGBM) |
| Threshold | 0.84 |
| Features | ~57 (A/B/C candle triplet) |
| Symbols | 10 trained pairs (AUDCAD, AUDNZD, AUDUSD, EURUSD, GBPAUD, NZDCAD, NZDCHF, NZDJPY, USDCAD, USDCHF) |
| Training | 22,853 rows, test precision 95.55%, AUC 0.8113, 4/4 positive walk-forward splits |

**Entry gates:**
1. `a_bb_event_type > 0` — candle A must have a BB event.
2. `a_rsi_value >= 45` — RSI filter.
3. `b_candle_body_pct < 0` — candle B must be bearish.
4. `P(SHORT) >= threshold` from model.

**Timeframe overrides for TP/SL:**

| TF | TP | SL | Max Bars |
|----|----|----|----------|
| M5 | 15 pips | 10 pips | 24 |
| M15 | 20 pips | 10 pips | 99 |
| H1 | 30 pips | 15 pips | 99 |
| H4 | 40 pips | 30 pips | 10 |

---

### 6.4 Trend Identifier V2 Long (disabled)

| Field | Value |
|-------|-------|
| Magic | 400401 |
| Direction | LONG |
| Timeframe | H4 |
| Trigger TFs | H4 |
| Algorithm | LightGBM + XGBoost + CatBoost soft-voting ensemble + Platt scaling |
| Threshold | 0.55 |
| Features | 41 (QUANT_V2_CORE) |
| Symbols | All 28 pairs |
| Max positions | 3 |
| Balanced accuracy | 92.59% |
| Calibration ECE | 1.53% |
| Version | 20260402_230006 |

**Signal logic:** `p(uptrend) >= 0.55` → LONG signal.

**Important:** CatBoost requires `pair_encoded`, `base_ccy_encoded`, `quote_ccy_encoded` to be **integer dtype** at inference. The predictor enforces this with explicit `.astype(int)` in `_prepare_features()`.

**External dependency:** `trend_id_v2_features.py` imports `compute_quant_v2_features` from:
```
C:\Users\Ben Michael Oracion\Documents\Solara\Model Training\Trend Identifier
```
This path is hard-coded and must exist for TI V2 to function.

---

### 6.5 Trend Identifier V2 Short (disabled)

| Field | Value |
|-------|-------|
| Magic | 400402 |
| Direction | SHORT |

Same model file as TI V2 Long. Uses `p(downtrend)` instead of `p(uptrend)`. Two registry entries share one `.pkl` — the predictor checks `config.model_type` to determine which probability to emit.

---

### 6.6 Stella Alpha Long (disabled — discontinued)

Superseded by UBB Rejection as of March 2026.

---

## 7. Feature Engineering

### 7.1 Per-Model Feature Engineers

Each model has its own `BaseFeatureEngineer` subclass. The execution engine dynamically imports and caches the class from `feature_engineering_class` in the registry.

`BaseFeatureEngineer` enforces a 3-method contract:
- `get_required_input_columns()` — input validation (before `compute()`).
- `compute(df)` — transforms merged base DataFrame into featured DataFrame.
- `get_output_features()` — output validation (after `compute()`).

`safe_compute()` wraps `compute()` with input/output validation and error handling. Returns `None` on any failure (which causes the model to be skipped for that cycle).

### 7.2 Punk Hazard Feature Set (`ph1`)

43 features + 2 regime columns computed from OHLCV + EA CSV indicators:

- **Direction-neutral CSV features (10):** `rsi_value`, `bb_position`, `bb_width_pct`, `atr_pct`, `candle_body_pct`, `trend_strength`, `volume_ratio`, `prev_candle_body_pct`, `prev_volume_ratio`, `gap_from_prev_close`.
- **Long-specific CSV features (6):** `bb_touch_strength_long`, `candle_rejection_long`, `price_momentum_long`, `previous_touches_long`, `time_since_last_touch_long`, `support_distance_pct`.
- **Supplementary computed features (17):** SMA distances (50/100/200), `atr_ratio`, `stoch_k`, `macd_hist`, `dist_extreme`, candle structure metrics, RSI slopes, BB width Z-score, `dist_52w_low`, `atr_percentile`, `atr_longterm_zscore`, `price_accel`, `vol_divergence`.
- **Lag features (5):** `trend_strength_lag1`, `bb_width_pct_lag3`, `atr_pct_lag3`, `atr_ratio_lag2`, `bb_width_zscore_lag2`.
- **Regime features (2):** `regime_volatility` (0=Low, 1=High), `regime_trend` (-1/0/+1).

### 7.3 Trend Identifier V2 Feature Set (`ti_v2`)

41 QUANT_V2_CORE features: ADX system (2), EMA alignment (7), Momentum (6), MACD (2), Volatility (6), Price structure (9), Market structure (4), Volume (1), Encoding (4: `tf_log_minutes`, `pair_encoded`, `base_ccy_encoded`, `quote_ccy_encoded`).

### 7.4 UBB Feature Set (`v3`)

~57 features derived from a 3-candle A/B/C rejection pattern: per-candle OHLCV, BB metrics, RSI, ATR, volume, momentum, and BB event type/strength columns.

---

## 8. Signal System

### 8.1 Signal Data Flow

```
predictor.predict() → List[Dict]
  ↓ SignalAggregator.aggregate()
RawSignal (from_prediction)
  ↓ ConflictChecker.check_conflicts()
AggregatedSignal (status=VALIDATED or CONFLICT)
  ↓ get_valid_signals()
List[AggregatedSignal] (validated only)
  ↓ Stage 7: Risk
ApprovedSignal (lot_size resolved)
  ↓ Stage 8: Execute
ExecutedSignal (ticket, entry_price)
```

### 8.2 Signal Model Fields

**`RawSignal`:** `signal_id`, `model_name`, `magic`, `symbol`, `direction`, `confidence`, `entry_price`, `tp_pips`, `sl_pips`, `comment`, `timestamp`, `features`.

**`AggregatedSignal`:** adds `combined_confidence`, `contributing_models`, `total_weight`, `status`, `rejection_reason`.

**`ApprovedSignal`:** adds `lot_size`, `sl_price`, `tp_price`, `risk_amount`, `risk_percent`.

**`ExecutedSignal`:** adds `ticket`, `actual_entry_price`, `slippage_pips`, `executed_at`.

### 8.3 Conflict Checker

Suppresses opposing signals (LONG vs SHORT) from the **same model** on the **same symbol**. Since Punk Hazard Long and Short share no model identity (separate names), they can both emit for the same symbol in theory.

---

## 9. Survivor Engine

### 9.1 Overview

The Survivor Engine is a **22-stage progressive trailing stop system** that runs on an independent 60-second polling loop (production only). It is completely decoupled from the signal pipeline.

### 9.2 Stage Definitions

Defined in `survivor/stage_definitions.yaml`. Stages only advance forward — never backward.

| Stages | Category | Trigger Range | Protection |
|--------|----------|---------------|------------|
| 0 | None | 0 pips | 0% |
| 1–5 | Early | 10–30 pips | 20–40% |
| 6–10 | Building | 35–55 pips | 45–58% |
| 11–15 | Strong | 60–80 pips | 60–70% |
| 16–19 | Aggressive | 90–140 pips | 72–80% |
| 20–22 | Maximum | 160–200 pips | 82–88% |

**Settings:** `min_profit_to_start = 10 pips`, `pip_buffer = 2 pips`.

### 9.3 SL Calculation

```
sl_offset_pips = max(0, profit_pips * protection_pct - pip_buffer)
new_sl = entry_price ± (sl_offset_pips * pip_value)
```

For LONG: SL moves up (ratchet). For SHORT: SL moves down.  
SL is based on **max profit reached** (high-water mark), not current profit — prevents stage regression during pullbacks.

### 9.4 State Persistence

Position state is stored in `position_state` table. Every stage transition is logged to `stage_transition_log` (append-only). State survives crashes and restarts.

---

## 10. State Management (Database)

SQLite database at `state/solara_aq.db`. WAL mode enabled for concurrent access. Singleton `DatabaseManager` with thread-local sessions.

### 10.1 Tables

| Table | Purpose |
|-------|---------|
| `position_state` | Survivor Engine state for each open position |
| `stage_transition_log` | Append-only log of SL stage changes |
| `model_run` | Per-model execution analytics (status, duration, signals) |
| `signal_log` | Every signal with confidence score, aggregation/risk status, trade ticket |
| `trade_log` | Every order attempt with ticket, entry price, SL, TP, status |
| `model_health` | Auto-disable counters, consecutive failures, total runs |
| `daily_stats` | Aggregated daily trading statistics |

---

## 11. MT5 Connection Manager

`MT5Manager` is a thread-safe singleton. Features:
- Double-checked locking singleton.
- `is_connected` checks `mt5.terminal_info()` at each call (not just a flag).
- `ensure_connected()` attempts reconnection if lost.
- `place_order()`: builds market order request with `TRADE_ACTION_DEAL`, `ORDER_TIME_GTC`, `ORDER_FILLING_IOC`. Max slippage: 30 points.
- `modify_position()`: `TRADE_ACTION_SLTP` to update SL/TP.
- Symbol info is cached (`_symbol_cache`).
- Only available on Windows (`IS_WINDOWS` guard).

---

## 12. Terminal Logger

`SAQLogger` in `logger.py` provides rich colorized terminal output using `colorama`:

- **In-place pipeline block:** each timeframe's pipeline block renders at the same terminal position on every cycle (overwritten using ANSI cursor-up + line-clear sequences). No scrolling output during normal operation.
- **Startup banner:** shows version, all component statuses, and watched files.
- **Standalone messages:** `ok()`, `info()`, `warn()`, `error()`.
- File logging via `RotatingFileHandler` (10 MB, 5 backups) at `logs/saq.log`.

---

## 13. Dashboard

`dashboard/trade_server.py` is a standalone HTTP server (port 8765) serving `trade_dashboard.html`.

- Not started by `main.py` — run separately.
- Reads from `state/solara_aq.db` via SQLite.
- Enriches data with live MT5 position info.
- Accepts `--tz-offset` flag to convert UTC timestamps to broker local time.

---

## 14. Known Issues and Notes

### 14.1 Dead Code

`engine/registry.py:228` has an unreachable `return 0.01` statement immediately after `return None` in `get_fixed_lot()`. This is a vestige of a previous implementation and has no effect.

### 14.2 External Dependency (TI V2)

`features/trend_id_v2_features.py` imports `compute_quant_v2_features` from a hard-coded path:
```
C:\Users\Ben Michael Oracion\Documents\Solara\Model Training\Trend Identifier
```
TI V2 models cannot be enabled without this sibling research project on disk at exactly this path.

### 14.3 PunkHazardFeatureEngineer vs BaseFeatureEngineer

`PunkHazardFeatureEngineer` does not inherit from `BaseFeatureEngineer`. It implements `transform()` instead of `compute()`. This works because the execution engine calls `safe_compute()` which calls `compute()` — meaning `PunkHazardFeatureEngineer` must implement `compute()` to be compatible. Currently it only implements `transform()`. **This is a latent bug** if `PunkHazardFeatureEngineer` is used via `safe_compute()`.

### 14.4 Stage 7 Dev Mode Behavior

In development mode, position-limit checks are skipped (MT5 not connected). All signals that pass the cooldown check and confidence tier are approved and forwarded to Stage 8, where they are silently dropped with a dev-mode log message.

### 14.5 `.pkl` Export Format

Punk Hazard models use a dict artifact format:
```python
{
    'model':         CalibratedClassifierCV,
    'feature_names': List[str],
    'tp_pips':       float,
    'sl_pips':       float,
    'timeout':       int,
    'metadata':      dict,
}
```
TI V2 models use `joblib` (not `pickle`) and the same dict format with keys `model`, `feature_cols`, `pair_map`.  
UBB Rejection uses: `pipeline` (sklearn Pipeline), `threshold`, `feature_cols`, `metadata`.

---

## 15. Testing

Test suite at `tests/`:

| File | Coverage |
|------|---------|
| `test_phases_1_3.py` | Ingest, validate, merge |
| `test_phases_4_6.py` | Features, models, signals |
| `test_phases_7_8.py` | Risk, execution |
| `test_phase_8_main.py` | Main startup integration |

Run: `python main.py --test` or `pytest tests/`
