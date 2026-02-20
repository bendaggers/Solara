# 🌅 Solara AI Quant (SAQ)

**Multi-Model AI Trading System — Functional Specification v1.2**

> Event-driven • Multi-timeframe • 5–100 ML models • 8 concurrent workers

Solara AI Quant is an automated trading system that watches the market using multiple machine learning models simultaneously, decides when to place trades, manages all open positions automatically, and protects profits using a built-in 22-stage trailing stop system. A human operator configures the models and risk settings — then the system runs on its own.

---

## 📋 Table of Contents

- [Overview](#-1-system-overview--scope)
- [Quick Start](#-quick-start)
- [Architecture](#-2-event-driven-architecture-flow)
- [File Watchdog](#-3-file-watchdog)
- [Model Registry](#-4-model-registry)
- [Pipeline & Features](#-5-per-timeframe-pipeline--feature-engineering)
- [Execution Engine](#-6-model-execution-engine)
- [Signal Aggregation](#-7-signal-aggregation-rules)
- [Risk Manager](#-8-risk-manager-rules)
- [Survivor Engine](#-9-survivor-engine--position-management)
- [Database](#-10-database-schema)
- [File Architecture](#-11-file-architecture)
- [Adding a New Model](#-adding-a-new-model)
- [Glossary](#-12-glossary)

---

## 📘 1. System Overview & Scope

### Purpose

**Solara AI Quant (SAQ)** is an event-driven, multi-timeframe, multi-model algorithmic trading system built on top of **MetaTrader 5**. It:

- Receives market data from an MT5 Expert Advisor (EA) via CSV exports
- Runs a fleet of machine learning models against that data
- Aggregates signals, applies risk controls, and executes trades
- Manages open positions with a 22-stage Survivor trailing-stop engine

The system is designed to scale from **2 to 100 models** without architectural changes. Adding a new model requires editing a single configuration file and dropping a model file into a folder — **no code changes** elsewhere.

### In Scope ✅

| Area | Description |
|------|-------------|
| 📥 **Data ingestion** | Event-driven ingestion from MT5 EA CSV exports |
| 🤖 **Model execution** | 5–100 ML models per timeframe event, concurrent execution |
| 📊 **Signal aggregation** | Conflict detection across models |
| 🛡️ **Risk management** | Pre-trade enforcement before every order |
| 📤 **Trade execution** | Via MT5 Python API |
| 📈 **Survivor Engine** | 22-stage trailing stop position management |
| 💾 **Persistence** | SQLite for positions and model run history |
| 📝 **Audit** | Structured logging for every system event |

### Out of Scope ❌

- Model training and ML model development
- MT5 EA development (EA is pre-existing)
- Broker connectivity configuration
- Manual trade intervention tooling

### System Boundaries

| Component | Owned by SAQ | External |
|----------|--------------|----------|
| Market data | File Watchdog + CSV reader | MT5 EA writes CSV to MQL5/Files/ |
| ML models | Execution Engine runs them | .pkl files trained externally |
| Trade execution | TradeExecutor + retry + confirm | MT5 Python API |
| Position tracking | Survivor Engine + SQLite | MT5 position feed |
| Credentials | Loaded from OS env vars | Broker account (external) |

---

## 🚀 Quick Start

### Requirements

- **Python** 3.10+
- **MetaTrader 5** terminal (for live/demo trading)
- MT5 Expert Advisor that exports CSV to `MQL5/Files/`

### Install

```bash
pip install -r requirements.txt
# Dev: pip install -r requirements-dev.txt
```

### Configure

1. Copy `.env.example` to `.env`
2. Set MT5 credentials and terminal path:

```env
MT5_LOGIN=12345678
MT5_PASSWORD=your_password
MT5_SERVER=YourBroker-Server
MT5_TERMINAL_PATH=C:\Users\YourName\AppData\Roaming\MetaQuotes\Terminal\<TerminalHash>
SAQ_ENV=development
```

3. Ensure `model_registry.yaml` exists and `Models/` contains your `.pkl` files.

### Run

```bash
python main.py
```

The process will validate config, connect to MT5, initialize the database, load the model registry, start the Survivor Engine (background timer), and then start the File Watchdog (blocks until SIGTERM/SIGINT).

---

## 🔄 2. Event-Driven Architecture Flow

SAQ does **not** use cron jobs or fixed-interval polling. The **only** trigger for a model execution cycle is a **filesystem modification event** on one of the four watched CSV files. The market tells SAQ when to act.

### End-to-End Flow (Single Timeframe Event)

| Step | Component | What happens |
|------|-----------|--------------|
| **1** | MT5 EA | Bar closes (e.g. H4) → EA writes `marketdata_PERIOD_H4.csv` |
| **2** | File Watchdog | Detects file modification → checks cycle lock → if free, acquires lock and starts pipeline |
| **3** | Data ingestion | Read CSV → validate (columns, nulls, OHLC, min bars) → fail = release lock, abort |
| **4** | Feature engineering | Compute BB, RSI, momentum, lags (8 stages) → one featured DataFrame |
| **5** | Execution engine | Get enabled models for timeframe → validate feature version → dispatch to worker pool (max 8) → collect `ModelResultSet` |
| **6** | Signal aggregation | Apply conflict rules → output `list[AggregatedSignal]` |
| **7** | Risk manager | For each signal: drawdown, daily trades, position limit, margin, lot size → pass or reject |
| **8** | Trade execution | Lot size → place order via MT5 → retry on retryable errors → log result |
| **9** | Survivor Engine | Independent loop every 60s: fetch positions → compute stage → update SL/TP |
| **10** | Cycle complete | Release cycle lock → log summary |

### Four Independent Timeframe Pipelines

| Timeframe | CSV file | Cycle frequency | Models triggered |
|-----------|----------|-----------------|-------------------|
| **M5** | `marketdata_PERIOD_M5.csv` | Every 5 min | All with `timeframe: M5` |
| **M15** | `marketdata_PERIOD_M15.csv` | Every 15 min | All with `timeframe: M15` |
| **H1** | `marketdata_PERIOD_H1.csv` | Every 1 hour | All with `timeframe: H1` |
| **H4** | `marketdata_PERIOD_H4.csv` | Every 4 hours | All with `timeframe: H4` |

When all four timeframes align (every 4 hours), **all four pipelines can run simultaneously** — up to 32 models at once (4 × 8 workers).

### ⚠️ Cycle Overlap

If a new file event fires for a timeframe whose cycle is **still running**, the new event is **skipped** (not queued). A WARNING is logged. The lock is released only when the active cycle completes. If this appears often, reduce model count or increase worker allocation for that timeframe.

### ✅ Cross-Timeframe Symbol Trading

Different timeframes may hold positions on the **same symbol** at the same time. Each model has a **unique magic number**. Survivor and Risk Manager operate **per magic**, not per symbol globally.

---

## 👁️ 3. File Watchdog

The watchdog monitors four CSV paths (one per timeframe) using the **watchdog** library (OS-native: inotify / ReadDirectoryChangesW). Only **FILE_MODIFIED** is used; CREATE/DELETE/MOVED are ignored.

### Event rules

| Condition | Action | Log |
|-----------|--------|-----|
| File modified, no active cycle | Acquire lock, start pipeline | INFO: cycle started |
| File modified, cycle already active | Skip event | WARNING: cycle overlap — skipping |
| File empty (0 bytes) | Skip, do not start | WARNING: CSV is empty |
| File fails validation | Release lock, abort | ERROR: validation failed |
| Non-watched file modified | Ignore | (none) |

### Cycle locks

- One `threading.Event` per timeframe (M5, M15, H1, H4).
- **Set** = locked (cycle running), **Clear** = idle.
- **Critical:** Every `acquire` must have a `release` in a `try/finally` block so a crash never leaves a timeframe permanently locked.

---

## 📜 4. Model Registry

The **only** file you edit to add, remove, or toggle a model is **`model_registry.yaml`**. It is Pydantic-validated at startup.

### Location & format

- **File:** `<SAQ_ROOT>/model_registry.yaml`
- **Format:** YAML
- **Loaded:** At startup, before watchdog starts

### Example entry (annotated)

```yaml
models:
  - name: "BB Long Reversal v2"                    # unique
    class_path: "predictors.bb_reversal_long.BBReversalLongPredictor"
    model_file: "BB_LONG_v2.pkl"                    # in Models/
    feature_version: "v3"                           # must match feature_versions.yaml
    model_type: "LONG"                              # LONG | SHORT
    timeframe: "H4"                                 # M5 | M15 | H1 | H4
    min_confidence: 0.65                             # 0.01–1.00
    weight: 1.0                                      # 0.1–2.0, aggregation
    priority: 1                                      # 1–100, lower = first
    timeout: 30                                      # seconds, 5–300
    magic: 201000                                    # unique MT5 magic
    comment: "SAQ_BBLong"
    enabled: true
    max_positions: 3                                 # 1–20
    symbols: []                                      # [] = all; or ["EURUSD", ...]
```

### Magic number convention

| Strategy ID | Timeframe (3rd digit) |
|-------------|------------------------|
| 20xxxx = BB Reversal | x0xxxx = H4 |
| 30xxxx = RSI | x1xxxx = H1 |
| 40xxxx = MACD | x2xxxx = M15 |
| 50xxxx = Custom | x3xxxx = M5 |

Example: `201000` = BB Reversal, H4, model #1 (Long).

### Validation

- Duplicate names or magic → **startup FATAL**
- Missing/invalid `class_path` or missing `model_file` (when enabled) → **startup FATAL**
- Invalid `feature_version`, `model_type`, `timeframe`, or out-of-range numbers → **startup FATAL**

---

## 📊 5. Per-Timeframe Pipeline & Feature Engineering

### Pipeline independence

Each timeframe has its own pipeline: ingest → features → engine → signals → risk → execute. Pipelines run in **parallel** (separate threads). They share only:

- MT5 connection (thread-safe)
- SQLite database (atomic writes)

### Data ingestion

**MT5 EA CSV schema (required columns):**

- `timestamp`, `symbol`, `open`, `high`, `low`, `close`, `tick_volume`, `spread`, `price`

**Validation rules:**

1. File not empty.
2. All 9 required columns present.
3. No nulls in OHLC + symbol (drop bad rows; if all null → abort).
4. `high >= low` (drop violated rows).
5. Timestamps parseable as datetime.
6. Minimum **30 bars per symbol**; exclude symbols with fewer.
7. Sort by `timestamp` ascending per symbol before features.

### Feature engineering (8 stages)

Features are computed **once** per cycle and shared (read-only) by all models. Order is fixed (later stages depend on earlier ones):

| Stage | Features |
|-------|----------|
| 1 | `body_size`, `candle_body_pct` |
| 2 | `ret`, `ret_lag1`, `ret_lag2`, `ret_lag3` |
| 3 | `price_momentum` |
| 4 | RSI(14) Wilder → `rsi_value` |
| 5 | `rsi_slope`, lags, `RSI_slope_3` |
| 6 | Bollinger (20, 2) → `dist_bb_upper`, `dist_bb_lower` |
| 7 | `dist_bb_upper_lag1/2/3` |
| 8 | Trim to **latest bar per symbol** (1 row per symbol) |

Feature versions (e.g. v1, v2, v3) are defined in **`features/feature_versions.yaml`**. The engine checks each model’s `feature_version` against the computed columns **before** dispatching; models with missing features are **skipped** that cycle.

---

## ⚙️ 6. Model Execution Engine

- **Level 1:** Each timeframe pipeline runs in its own OS thread (up to 4 threads when all fire).
- **Level 2:** Within each pipeline, models run in a **ThreadPoolExecutor** with **max 8 workers**. Batches of up to 8 run concurrently; next batch starts when the current one finishes.

**Why threads (not processes):** Shared memory (no DataFrame serialization), single model load per pipeline, GIL released during sklearn/numpy inference, simpler debugging.

### Batch algorithm

1. Priority queue of enabled models (by `priority`).
2. Fill batch (up to `MAX_CONCURRENT_MODELS`).
3. Submit batch to executor; wait for all with per-model `timeout`.
4. Collect results; on timeout → mark TIMEOUT and continue.
5. Repeat until queue empty.

### Fault isolation

| Failure type | Effect on others | System behavior |
|-------------|------------------|-----------------|
| Model exception | None | Result FAILED, traceback logged, health updated |
| Model timeout | None | Result TIMEOUT, WARNING |
| Empty predictions | None | Result EMPTY |
| Missing features | Model skipped | ERROR by Feature Validator |
| All models fail | Survivor unaffected | CRITICAL, no trades this cycle |
| One pipeline crash | Other pipelines unaffected | Lock released, others continue |

### Model health & auto-disable

- **ModelHealth** (SQLite): `last_run_at`, `last_run_status`, `consecutive_failures`, `total_runs`, etc.
- **Auto-disable:** When `consecutive_failures >= 3`, the model is set `enabled = False` **in memory** (YAML not modified). Re-enable by editing YAML and restarting SAQ.
- **EMPTY** does **not** count as a failure; only **FAILED** and **TIMEOUT** increment the counter.

---

## 📡 7. Signal Aggregation Rules

- Each model emits **RawSignal** (symbol, direction, confidence, model_name, magic, price, comment, …).
- **Default strategy:** INDEPENDENT_PASSTHROUGH — each model’s signal is evaluated alone; no cross-model voting.
- Signals with `confidence >= model.min_confidence` go to the **Conflict Checker**.

### Conflict suppression

| Scenario | Rule |
|---------|------|
| Same model, same symbol, LONG + SHORT | **Suppress both.** WARNING. |
| Different models, same symbol, LONG + SHORT | **Allow both.** |
| Same model, same symbol, same direction (duplicate) | **Keep highest confidence.** DEBUG. |
| Symbol not in model’s `symbols` whitelist | **Discard.** WARNING. |

Output is **AggregatedSignal** list → passed to Risk Manager.

---

## 🛡️ 8. Risk Manager Rules

Five checks, in order. First failure → reject signal (no trade).

| # | Check | Rule | On failure |
|---|--------|------|------------|
| 1 | **Drawdown** | Equity >= initial_equity × (1 - MAX_DAILY_DRAWDOWN_PCT) | REJECT, ERROR, **halt all trading** for session |
| 2 | **Daily trade count** | Trades today (per magic) < MAX_DAILY_TRADES | REJECT, WARNING |
| 3 | **Position limit** | Open positions (this magic) < model.max_positions | REJECT, INFO |
| 4 | **Margin** | Free margin >= required margin for trade | REJECT, WARNING |
| 5 | **Lot size** | Lot > 0 and <= broker max | REJECT, ERROR |

### Config (e.g. config.py)

- `MAX_DAILY_DRAWDOWN_PCT` = 0.05 (5%)
- `MAX_DAILY_TRADES` = 20 per magic per day
- `MAX_RISK_PER_TRADE` = 0.02 (2%)
- Default SL/TP in pips; `MAX_SLIPPAGE_POINTS` for orders

### Lot size formula

```
risk_amount = equity × MAX_RISK_PER_TRADE
pip_value   = from SymbolHelper (JPY, XAU aware)
lot_size   = risk_amount / (sl_pips × pip_value)
lot_size   = clamp(lot_size, MIN_LOT, MAX_LOT)
```

---

## 📈 9. Survivor Engine — Position Management

The Survivor Engine runs on an **independent timer** (e.g. every 60 seconds). It does **not** depend on CSV events.

### Cycle

1. Fetch all open positions from MT5.
2. For each position: compute pips in profit → determine **stage** (0–22).
3. If stage advanced: compute new SL (and TP if applicable) → send modify to MT5.
4. Persist stage transition (e.g. SQLite, audit log).

### 22 stages (summary)

- **STAGE_0:** Entry (0 pips, 0% protection, TP active).
- **STAGE_1–13:** Thresholds from 8 to 65 pips; protection from 10% to 70%; **TP active**.
- **STAGE_14–22:** From 70 to 200 pips; protection 72% to 90%; **TP removed** (pure trailing).

Stages only move **forward**. SL is never moved backward. From Stage 14 onward, TP is set to 0 and not reinstated.

### SL formula

- **Long:** `new_sl = entry_price + (protected_pips × pip_size)` where `protected_pips = max_profit_pips × stage.protection_pct`.
- **Short:** `new_sl = entry_price - (protected_pips × pip_size)`.

`max_profit_pips` uses highest price (long) or lowest price (short) since entry.

---

## 💾 10. Database Schema

**File:** `<SAQ_ROOT>/state/solara_aq.db` (SQLite, WAL mode). Application-only; do not edit by hand.

| Table | Purpose |
|-------|---------|
| **PositionState** | Current Survivor stage, SL/TP, highest/lowest price per open position |
| **StageTransitionLog** | Append-only log of every stage change |
| **ModelRun** | Every model run (SUCCESS/FAILED/TIMEOUT/EMPTY), timing, batch |
| **SignalLog** | Every signal (model, symbol, direction, confidence, aggregation/risk outcome, trade ticket) |
| **TradeLog** | Every trade attempt (lot, SL/TP, ticket, MT5 code, status) |
| **ModelHealth** | One row per model; updated after each cycle (counts, auto-disable, etc.) |

---

## 📁 11. File Architecture

```
SolaraAIQuant/
├── main.py                 # Entry: config, MT5, DB, registry, Survivor, watchdog
├── config.py               # Constants, paths, env vars
├── model_registry.yaml     # Only file to edit to add/remove/toggle models
├── .env.example
├── requirements.txt
├── requirements-dev.txt
├── .gitignore
├── ingestion/              # CSV read, validate, clean DataFrame
├── features/               # 8-stage feature engineering, feature_versions.yaml
├── watchdog/               # File observer, cycle locks, pipeline_runner
├── engine/                 # Registry, execution_engine, worker_pool, model_health, result_collector
├── predictors/             # BasePredictor, bb_reversal_long, bb_reversal_short, …
├── signals/                # signal_models, signal_aggregator, conflict_checker
├── execution/              # risk_manager, position_sizer, trade_executor, execution_models
├── mt5/                    # mt5_manager, symbol_helper
├── survivor/               # survivor_engine, survivor_runner, stage_definitions.yaml, survivor_reporter
├── state/                  # database.py, models.py (ORM), solara_aq.db (git-ignored)
├── tests/                  # conftest, test_ingestion, test_features, test_engine, …
├── logs/                   # JSON logs (git-ignored)
├── reports/                # archive, exports (git-ignored)
└── Models/                 # .pkl files (git-ignored)
```

---

## ➕ Adding a New Model

1. **Train** the model → save to `Models/<name>_vN.pkl`.
2. **Add predictor class** in `predictors/<strategy>.py` (inherit `BasePredictor`, implement `predict()`, `get_feature_list()`, `get_metadata()`).
3. **Register** in `model_registry.yaml` (all required fields, unique `magic`, `enabled: true`).
4. **Restart SAQ** (or rely on hot-reload when implemented).
5. **Verify** in logs and ModelHealth after the next cycle for that timeframe.

No changes to `main.py`, `config.py`, execution_engine, risk_manager, survivor_engine, or trade_executor are required.

---

## 📖 12. Glossary

| Term | Definition |
|------|------------|
| **SAQ** | Solara AI Quant |
| **EA** | Expert Advisor — MT5 script that exports CSV |
| **Bar/Candle** | One time unit of OHLCV (e.g. one H4 bar) |
| **Timeframe** | M5, M15, H1, H4 |
| **Cycle** | One full pipeline run for one timeframe (read → features → models → signals → risk → execute) |
| **Cycle lock** | In-memory flag preventing overlapping cycles for the same timeframe |
| **Worker pool** | Up to 8 concurrent model threads per pipeline |
| **Batch** | Up to 8 models dispatched together |
| **Aggregated signal** | Signal that passed conflict checker, ready for risk check |
| **Survivor Engine** | 22-stage trailing stop position management |
| **Stage** | One of 22 profit milestones with a protection % |
| **Feature version** | Label (e.g. v3) for the feature set a model was trained on |
| **Auto-disable** | Model excluded after 3 consecutive failures (in-memory only) |

---

## 📄 Specification

This README is derived from **Solara AI Quant — Functional Specification v1.2** (February 2026). For the authoritative document, see **SolaraAIQuant Functional Specification.docx**.

---

*Confidential | February 2026 | Office of Technology Strategy*
