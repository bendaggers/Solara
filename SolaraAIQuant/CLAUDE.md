# CLAUDE.md — Solara AI Quant (SAQ)

This file provides context for Claude Code when working in this repository.

---

## Project Overview

SAQ is a Python trading system that connects MetaTrader 5 to ML models. It watches for CSV files written by an MT5 Expert Advisor, runs ML inference per bar, and places market orders. Full architecture details are in `FUNCTIONAL_SPEC.md`.

---

## How to Run

```bash
python main.py                         # Development mode (no MT5, signals logged only)
python main.py --production            # Production mode (real MT5 connection + orders)
python main.py --production --dry-run  # MT5 connected but no real orders
python main.py --status                # Show configuration and model summary
python main.py --test                  # Run pytest suite
python main.py --log-level DEBUG       # Verbose output (goes to log file, not terminal)
```

Environment variables are loaded from a `.env` file in the project root. See `config.py` for all variables.

### Monitoring logs in real time (PowerShell)

```powershell
# All Pull Back prediction scores per symbol per cycle
Get-Content .\logs\saq.log -Wait -Tail 50 -Encoding UTF8 | Select-String "PullBack|pull_back"

# All errors
Get-Content .\logs\saq.log -Wait -Tail 50 -Encoding UTF8 | Select-String "ERROR"
```

Always use `-Encoding UTF8` — the log is UTF-8 but PowerShell defaults to Windows-1252.

### Model health management

```bash
python reset_model_health.py               # show current health for all models
python reset_model_health.py --reset-all   # re-enable all auto-disabled models
python reset_model_health.py "Pull Back Entry Long"  # reset a specific model
```

Models are auto-disabled after 3 consecutive failures. After fixing a bug, run
`reset_model_health.py` before restarting SAQ or the model will stay skipped.

---

## Key Files

| File | What it does |
|------|-------------|
| `main.py` | Entry point. `SolaraAIQuant` class initializes all components in order. |
| `config.py` | All configuration dataclasses. Read this before changing any paths or settings. |
| `model_registry.yaml` | **Single source of truth** for all ML models. Enable/disable models here. |
| `engine/registry.py` | Parses `model_registry.yaml`. `ModelConfig.get_fixed_lot()` drives lot sizing. |
| `file_watcher/pipeline_runner.py` | The 8-stage pipeline. Stage 4 skip logic is here. `_execution_engine` is created once in `__init__()` and reused across cycles. |
| `engine/execution_engine.py` | Parallel model execution. Predictor and FE caches live on the instance — must be reused across cycles for caching to work. |
| `engine/model_health.py` | Auto-disable logic. 3 consecutive failures → model skipped until manually reset. |
| `features/pull_back_features.py` | Pull Back 3-stage feature engineer. Loads H4/D1/W1 CSVs directly. Runs trend models + pullback model internally. |
| `predictors/pull_back_entry.py` | Pull Back entry predictor. 4 gates: trend aligned → direction match → exhaust ≥ 0.65 → entry prob ≥ 0.80. |
| `reset_model_health.py` | CLI utility to view and reset auto-disabled model health records in SQLite. |
| `survivor/stage_definitions.yaml` | Trailing stop stage definitions. |
| `state/models.py` | SQLAlchemy ORM. All database tables defined here. |
| `logger.py` | Terminal output. Uses ANSI cursor tricks for in-place pipeline block rendering. |

---

## Module Structure

```
SolaraAIQuant/
├── main.py                  Entry point
├── config.py                All config dataclasses + env loading
├── logger.py                Terminal logger (colorama, in-place rendering)
├── model_registry.yaml      Model definitions (YAML)
├── reset_model_health.py    Model health reset CLI utility
├── engine/                  Model registry, parallel execution, health tracking
├── file_watcher/            OS file watching, pipeline orchestration, cycle lock
├── ingestion/               CSV parsing + validation
├── features/                Per-model feature engineering classes
├── predictors/              ML model wrappers
├── signals/                 Signal aggregation + conflict resolution
├── mt5/                     Thread-safe MT5 singleton
├── state/                   SQLite persistence (SQLAlchemy ORM)
├── survivor/                Independent trailing stop engine
├── dashboard/               Standalone HTTP server (port 8765)
├── tests/                   Pytest test suite
├── utils/                   Logging utilities
└── Models/                  .joblib / .pkl model files
```

---

## Active Models (as of April 2026)

| Model | Magic | Trigger | Status | Notes |
|-------|-------|---------|--------|-------|
| TI V2 Long | 400401 | H4 | ❌ disabled | Trend identifier only — not an entry model. Disabled intentionally. |
| TI V2 Short | 400402 | H4 | ❌ disabled | Trend identifier only — not an entry model. Disabled intentionally. |
| Pull Back Entry Long | 500301 | H1 | ✅ enabled | 3-stage pullback entry — fires every hour. Pipeline confirmed working. |
| Pull Back Entry Short | 500302 | H1 | ❌ disabled | Enable after Pull Back Long validation |
| Punk Hazard Long | 200401 | M15/H1/H4 | ❌ disabled | Awaiting model file generation |
| Punk Hazard Short | 200402 | M15/H1/H4 | ❌ disabled | Awaiting model file generation |
| UBB Rejection | — | H4/M15/H1 | ❌ disabled | Superseded |

---

## Adding a New Model

1. **Train the model** in the research codebase; export a `.joblib` dict artifact with keys `model`, `feature_names` (or `feature_cols`), `tp_pips`, `sl_pips`, `metadata`.
2. **Place the `.joblib`** in `Models/`.
3. **Create a predictor class** in `predictors/` inheriting `BasePredictor`. Implement `get_required_features()` and `predict()`.
4. **Create a feature engineer class** in `features/` inheriting `BaseFeatureEngineer`. Implement `get_required_input_columns()`, `compute()`, `get_output_features()`.
5. **Register in `model_registry.yaml`** with a unique name, unique magic number, `class_path`, `model_file`, `feature_engineering_class`, `confidence_tiers`, etc.
6. **Enable** by setting `enabled: true` in the registry.

Magic number format: `XXYYZZ` (XX=strategy, YY=timeframe, ZZ=variant). No duplicate magic numbers are allowed — `ModelRegistry` validates this on load.

---

## Important Gotchas

### Stage 4 is intentionally skipped for all current models
All active models have `feature_engineering_class` set. This causes Stage 4 (global feature engineer) to be **skipped**. The global FE recomputes RSI/BB/ATR from OHLCV history — but the EA CSV already contains these values and each per-model FE reads them directly. If you add a model without a custom FE, Stage 4 will run for that cycle.

### ExecutionEngine must be reused across cycles
`PipelineRunner.__init__()` creates a single `ExecutionEngine` instance stored as `self._execution_engine`. This instance holds the predictor and feature engineer caches. If you create a new `ExecutionEngine` inside `_stage_models()` (as it used to do), the caches are thrown away every cycle and every model reloads from disk on each bar.

### PunkHazardFeatureEngineer does not inherit BaseFeatureEngineer
It implements `transform()` not `compute()`. The execution engine calls `safe_compute()` which calls `compute()`. `PunkHazardFeatureEngineer` must implement `compute()` to be compatible — this is a **latent bug**. Fix before enabling Punk Hazard.

### TI V2 and Pull Back share the same external path
Both `features/trend_id_v2_features.py` and `features/pull_back_features.py` import from:
```
C:\Users\Ben Michael Oracion\Documents\Solara\Model Training\Trend Identifier
```
Neither model can run without this path. **On VPS deployment, update both files.**

### Pull Back trend models have a separate hard-coded path
`features/pull_back_features.py` also loads trend models from:
```
C:\Users\Ben Michael Oracion\Documents\Solara\Model Training\Pull Back Strategy\models\
```
Files needed: `Trend_Identifier_H4.joblib`, `Trend_Identifier_D1.joblib`, `Trend_Identifier_W1.joblib`.
**On VPS deployment, copy these files and update `_PB_STRATEGY_ROOT` in `pull_back_features.py`.**

### TI V2 predictor must add sys.path before loading the model file
`predictors/trend_identifier_v2.py` adds the Trend Identifier path to `sys.path` inside `load_model()` before calling `joblib.load()`. This is intentional. The model `.joblib` file contains serialized `forex_trend_model` objects — if the path isn't set before deserialization, you get `ModuleNotFoundError: No module named 'forex_trend_model'`.

### CatBoost sklearn compatibility fix in ensemble.py
`forex_trend_model/models/ensemble.py` — `CatBoostTrendModel.predict_proba()` has a fallback to CatBoost's native `predict(prediction_type='Probability')` API. This handles a CatBoost + sklearn version mismatch where `super().get_params()` raises `AttributeError` after several prediction cycles. Do not remove this fallback.

### LightGBM TypeError after joblib.load() — fixed in ensemble.py
`LightGBMTrendModel.predict_proba()` catches **both** `AttributeError` and `TypeError`. After `joblib.load()`, LightGBM's internal predict function pointer can be `None`, which raises `TypeError: 'NoneType' object is not callable` (not just AttributeError). The fallback uses `model.booster_.predict()` directly, which survives deserialization correctly. A shape guard ensures single-row input is reshaped to `(1, n_classes)`. Do not revert this to catching `AttributeError` only.

File edited: `C:\Users\Ben Michael Oracion\Documents\Solara\Model Training\Trend Identifier\forex_trend_model\models\ensemble.py` (outside SAQ git repo — must be re-applied after any reinstall of the Trend Identifier package).

### TrendIDV2FeatureEngineer does not inherit BaseFeatureEngineer
`features/trend_id_v2_features.py` has a manually added `safe_compute()` method (wraps `compute()`). The execution engine always calls `safe_compute()`. If you remove this method, TI V2 will crash every cycle with `AttributeError: 'TrendIDV2FeatureEngineer' object has no attribute 'safe_compute'`.

### W1 timeframe is in TIMEFRAMES config but not in the Timeframe enum
`config.py` has `W1` in the `TIMEFRAMES` dict (needed so Pull Back FE can find the W1 CSV path). But `Timeframe` in `cycle_lock.py` and `TimeframeEnum` in `registry.py` do NOT include W1. On startup, `FileObserver` logs a warning: `Unknown timeframe: W1`. This is expected — Pull Back loads the W1 CSV directly and W1 does not need to be watched. Do not add W1 to these enums unless you want SAQ to trigger a full pipeline cycle on every W1 bar.

### Dead code in registry.py
`engine/registry.py:228` has `return 0.01` after `return None` in `get_fixed_lot()`. It is unreachable. Do not treat it as meaningful.

### TP/SL for Punk Hazard models come from the .pkl file
The values in `model_registry.yaml` (`tp_pips`, `sl_pips`) are **fallbacks only**. The actual values are read from the exported model dict at load time in `PunkHazardLongPredictor._load_ph_metadata()`.

### MT5 is Windows-only
`mt5_manager.py` has an `IS_WINDOWS` guard. The system runs in development mode on non-Windows platforms. For live trading you need a **Windows VPS** with MT5 installed.

### Processing delay (10 seconds by default)
The file observer waits `WATCHDOG_PROCESSING_DELAY_SECONDS` (default 10s) after a file change before reading. This is intentional — the EA writes 28 symbols row by row and the wait ensures it finishes. Do not remove this delay. Total latency per cycle: ~10s wait + ~10s Pull Back FE computation = ~20s end-to-end.

### Cooldown guard is SQL-based, not in-memory
The 5-minute cooldown check at Stage 7 queries `trade_log` via SQLite. It works in both dev and prod modes. This means cooldown state survives restarts.

### CatBoost requires integer cat features
`TrendIdentifierV2Predictor._prepare_features()` casts `pair_encoded`, `base_ccy_encoded`, `quote_ccy_encoded` to `int`. CatBoost will raise an error if these arrive as float. This is enforced in the predictor, not in the feature engineer.

### Pull Back Entry Long-side BB features are computed in Python
The production EA CSV does not export long-side BB features (`bb_touch_strength_long`, `candle_rejection_long`, etc.). These are computed in `PullBackFeatureEngineer._compute_h1_features()` using the same formulas as the EA's short-side counterparts. Do not expect these columns in the raw H1 CSV.

### model_type in predictors must use .value
`config.model_type` from the registry is a `ModelType` enum, not a plain string. Any predictor accessing it must call `.value` before string operations: `config.model_type.value.upper()` not `config.model_type.upper()`.

### Gate columns must be declared in BOTH get_output_features() AND get_required_features()
`execution_engine.py` Step 3b trims the DataFrame to exactly `(symbol, timestamp) + predictor.get_required_features()` before calling `predict()`. Any column the predictor needs for gating logic (e.g. `_pb_trend_aligned`, `_pb_direction`, `_pb_exhaust_prob`, `_pb_h4_label`, `close`) must appear in **both**:
- `PullBackFeatureEngineer.get_output_features()` — so `safe_compute()` validation passes
- `PullBackEntryPredictor.get_required_features()` — so Step 3b does not strip them

If a gate column is missing from either list, it is silently stripped and the gate always fails (e.g. `_pb_trend_aligned` missing → defaults to `False` → all pairs fail Gate 1).

### Pull Back multi-timeframe architecture
The Pull Back pipeline uses W1, D1, and H4 trend models — but their scope is limited:
- **Gate 1 (trend alignment)**: all 3 TFs (H4 + D1 + W1) must have ≥ 2/3 agreement
- **Pullback model features**: H4 trend context only (`trend_dir_encoded`, `trend_prob_up`, `trend_prob_down`)
- **Entry model features**: H4 trend context only (`h4_trend_dir`, `h4_trend_prob_up`, `h4_trend_prob_down`)

D1 and W1 act only as a pre-filter gate. The trained models themselves are blind to D1/W1 probabilities.

---

## VPS Deployment Checklist

Before deploying to a Windows VPS for paper trading:

- [ ] Copy entire `SolaraAIQuant/` directory to VPS
- [ ] Copy `Models/` directory (`.joblib` files)
- [ ] Copy Pull Back trend model files to the same path or update `_PB_STRATEGY_ROOT` in `pull_back_features.py`
- [ ] Copy or clone the `Trend Identifier` package to VPS; update `_TI_ROOT` in both `trend_id_v2_features.py` and `pull_back_features.py`; update the path in `trend_identifier_v2.py` `load_model()`
- [ ] Re-apply the LightGBM `TypeError` fix to `forex_trend_model/models/ensemble.py` (catch `TypeError` in addition to `AttributeError` in `LightGBMTrendModel.predict_proba`)
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Install MT5 on VPS and configure broker connection in `.env`
- [ ] Configure EA to export CSVs to the correct `MQL5/Files/` path; update `MQL5_FILES_DIR` in `.env` if needed
- [ ] Verify EA `KeepLastNCandles = 350` in `MarketDataExporter.mq5` (H4 trend model needs ≥ 260 bars warmup; 350 provides safe buffer)
- [ ] Run `python main.py --status` to verify all models load and paths resolve
- [ ] Run `python reset_model_health.py` to clear any stale auto-disable records from dev machine

---

## Database

SQLite at `state/solara_aq.db`. WAL mode, `StaticPool`, thread-local sessions.

Key tables: `position_state`, `stage_transition_log`, `model_run`, `signal_log`, `trade_log`, `model_health`, `daily_stats`.

To query trades from CLI:
```bash
python query_trades.py
```

---

## Dashboard

Run separately from main system:
```bash
python dashboard/trade_server.py
python dashboard/trade_server.py --tz-offset 8  # UTC+8
```
Opens at http://localhost:8765

---

## Dependencies

See `requirements.txt`. Key packages:
- `MetaTrader5` — MT5 Python API (Windows only)
- `pandas`, `numpy` — data processing
- `scikit-learn` — LogisticRegression calibration layer + utilities
- `lightgbm`, `xgboost`, `catboost` — ensemble ML inference (TI V2 + Pull Back trend models)
- `joblib` — `.joblib` model file loading
- `watchdog` — OS-native file monitoring
- `sqlalchemy` — SQLite ORM
- `colorama` — terminal colors
- `python-dotenv` — env var loading
- `pydantic` — used in `engine/model_registry.py`

---

## MT5 Expert Advisor — MarketDataExporter

**File:** `MQL5/Production/MarketDataExporter.mq5` (v6.6+)

The EA writes one CSV per enabled timeframe to `MQL5/Files/`. Each CSV contains OHLCV + all pre-computed indicators for every symbol.

### Key parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| `KeepLastNCandles` | **350** | H4 trend model needs ≥ 260 bars warmup; 350 = safe buffer. Never set below 300. |
| `WaitSecondsAfterCandleClose` | 5 | Seconds to wait after bar close before processing |
| `TF_H4` / `TF_H1` / `TF_D1` / `TF_W1` | true/false | Enable timeframes consumed by SAQ |

### Indicator fields exported per bar
The EA computes and exports all 28 indicator columns for every bar — not just OHLCV:
`lower_band`, `middle_band`, `upper_band`, `bb_position`, `bb_width_pct`, `rsi_value`, `volume_ratio`, `atr_pct`, `candle_body_pct`, `candle_rejection`, `trend_strength`, `prev_candle_body_pct`, `prev_volume_ratio`, `gap_from_prev_close`, `prev_was_rally`, `prev_was_selloff`, `price_momentum`, `previous_touches`, `bb_touch_strength`, `rsi_divergence`, `time_since_last_touch`, `resistance_distance_pct`, `support_distance_pct`, `close_above_ubb`, `high_touch_ubb`, `failed_break_ubb`, `no_upper_wick_bear_reject`, `bb_event_type`, `ubb_distance_close`, `session`.

### Known historical bugs (fixed)
1. **`KeepLastNCandles = 3` default** — EA only wrote 3 bars per symbol (84 rows total for 28 symbols). Trend model needs 260+ bars → all symbols returned "insufficient H4 bars". Fixed: default changed to 350.
2. **`tgt` search direction bug** — `CopyRates` returns `rates[0]` = oldest bar. The tgt-search loop ran `for(i=0; i<bars; i++)` which immediately matched `rates[0]` (oldest bar ≤ lcs is always true), giving `tgt=0`. The export loop then ran only once → `done=1` → "ERROR: Only 1/350". Fixed: search now runs `for(i=bars-1; i>=0; i--)` to find the most recent closed bar.
3. **Indicator fields all zeros** — The export loop only copied OHLCV into `buf[x]`; all 28 indicator fields were left at `0.0`. Fixed: all indicator fields are now computed and written per bar inside the export loop.

### After modifying the EA
1. Recompile in MetaEditor (F7)
2. Remove EA from chart and re-attach (clears stale global variable state)
3. Expected first-run log: `H4 export complete — candle: ... (28/28 symbols)` and `CSV written: marketdata_PERIOD_H4.csv — 9800 candles`

---

## Parked Feature — Market Overview Dashboard

**Status:** Planned, not started. Resume when Pull Back is validated live.

### Goal
A live grid of all 28 pairs showing trend state and model scores per cycle — so you can see what every pair scored on every model, not just the ones that fired.

### What needs to be built (5 phases)

**Phase 1 — Two new DB tables (`state/models.py`)**
- `prediction_log` — one row per symbol × model × cycle:
  `symbol | model_name | bar_time | confidence | direction | gate_reached | signal_fired | features_json`
  - `gate_reached` = 0–99 (which gate it got to before failing; 99 = all passed)
- `pair_trend_state` — latest trend snapshot per symbol × TF (upsert, not append):
  `symbol | timeframe | trend_dir | prob_up | prob_down | updated_at`

**Phase 2 — Write `pair_trend_state` from FEs**
- `PullBackFeatureEngineer.compute()` after trend models run → write H4/D1/W1 for all 28 pairs
- `ReversalShortFeatureEngineer` + `ReversalLongFeatureEngineer` → same upsert

**Phase 3 — Write `prediction_log` from execution engine**
- After each model run in `execution_engine.py`, write rows for ALL symbols (even filtered ones)
- Feature DataFrames already contain all probabilities — just persist them

**Phase 4 — New API endpoint in `dashboard/trade_server.py`**
- `GET /api/market-overview` → latest `pair_trend_state` + most recent `prediction_log` per model
- `GET /api/prediction-history?symbol=EURUSD&model=Pull+Back+Entry+Long` → time series

**Phase 5 — New "Market Overview" tab in dashboard HTML**
- 28 rows (pairs) × columns (H4/D1/W1 trend + one column per enabled model)
- Color coded: green = uptrend, red = downtrend, grey = sideways
- Each model cell shows: latest confidence score + gate reached (e.g. "0.43 G2")
- Bold + bell icon = signal fired this cycle
- Click cell → history chart popup

### Key design decision (settled)
`pair_trend_state` should be written by **whichever FE runs that cycle** (upsert pattern). Pull Back covers all 28 pairs × 3 TFs. Reversal FEs also update it. Latest writer wins.

---

## Tests

```bash
pytest tests/test_phases_1_3.py   # Ingest, validate, merge
pytest tests/test_phases_4_6.py   # Features, models, signals
pytest tests/test_phases_7_8.py   # Risk, execution
pytest tests/test_phase_8_main.py # Integration
```
