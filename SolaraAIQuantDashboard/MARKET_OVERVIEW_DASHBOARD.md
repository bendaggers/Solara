# Market Overview Dashboard — Build Spec

**Status:** Parked — resume when Pull Back Long live validation is complete.  
**Goal:** A live grid of all 28 pairs showing trend state and model scores per cycle —
so you can see what every pair scored on every model, not just the ones that fired.

---

## Context (read before starting)

SAQ is a Python trading system connecting MetaTrader 5 to ML models.
Key files relevant to this feature:

| File | Role |
|------|------|
| `state/models.py` | SQLAlchemy ORM — all DB tables go here |
| `features/pull_back_features.py` | Pull Back 3-stage FE — runs W1/D1/H4 trend models for all 28 pairs every H1 cycle |
| `engine/execution_engine.py` | Runs models in parallel; has predictor and FE caches |
| `file_watcher/pipeline_runner.py` | 8-stage pipeline; Stage 5 runs models, digest written after |
| `dashboard/trade_server.py` | Existing Flask HTTP server on port 8765 |
| `predictors/pull_back_entry.py` | Pull Back entry predictor — `_last_cycle_results` dict holds per-pair gate data |
| `utils/cycle_digest.py` | Writes `logs/cycle_digest.log` — already reads `_last_cycle_results` |

Database: SQLite at `state/solara_aq.db`. WAL mode, StaticPool, thread-local sessions.
Existing tables: `position_state`, `model_run`, `signal_log`, `trade_log`, `model_health`, `daily_stats`.

Active models as of April 2026:
- **Pull Back Entry Long** (magic 500301, H1 trigger) — ✅ enabled and live
- **Pull Back Entry Short** (magic 500302, H1 trigger) — disabled (enable after Long validation)
- TI V2 Long/Short — disabled (trend identifier only, not entry models)
- Punk Hazard Long/Short — disabled (awaiting model files)

---

## What to Build — 5 Phases

### Phase 1 — Two new DB tables (`state/models.py`)

#### Table 1: `prediction_log`
One row per symbol × model × cycle. Append-only.

```python
class PredictionLog(Base):
    __tablename__ = 'prediction_log'
    id            = Column(Integer, primary_key=True, autoincrement=True)
    symbol        = Column(String(10), nullable=False)
    model_name    = Column(String(64), nullable=False)
    bar_time      = Column(DateTime, nullable=False)   # cycle start time
    timeframe     = Column(String(8), nullable=False)  # 'H1', 'H4', etc.
    direction     = Column(String(8))                  # 'LONG', 'SHORT', None
    confidence    = Column(Float)                      # entry_prob (0–1)
    gate_reached  = Column(Integer)                    # 0=signal, 1-4=gate fail, 99=error
    signal_fired  = Column(Boolean, default=False)
    features_json = Column(Text)                       # JSON blob of key features
    created_at    = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_pred_log_symbol_model', 'symbol', 'model_name'),
        Index('ix_pred_log_bar_time', 'bar_time'),
    )
```

`gate_reached` encoding (matches `pull_back_entry.py`):
- `0` = all gates passed, signal fired
- `1` = G1 trend not aligned
- `2` = G2 wrong direction
- `3` = G3 exhaust prob too low
- `4` = G4 entry prob too low
- `99` = feature error / model error

#### Table 2: `pair_trend_state`
Latest trend snapshot per symbol × timeframe. Upsert pattern — not append.

```python
class PairTrendState(Base):
    __tablename__ = 'pair_trend_state'
    id         = Column(Integer, primary_key=True, autoincrement=True)
    symbol     = Column(String(10), nullable=False)
    timeframe  = Column(String(8), nullable=False)     # 'H4', 'D1', 'W1'
    trend_dir  = Column(String(16))                    # 'uptrend', 'downtrend', 'sideways'
    prob_up    = Column(Float)
    prob_down  = Column(Float)
    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('symbol', 'timeframe', name='uq_pair_tf'),
    )
```

Add both tables to the existing `Base.metadata.create_all(engine)` call.
Run Alembic migration OR just let `create_all` handle it on next startup (SAQ uses `checkfirst=True`).

---

### Phase 2 — Write `pair_trend_state` from Feature Engineers

#### In `features/pull_back_features.py`

After the trend models run (after `_run_trend_models()`), write H4/D1/W1 trend state for
all 28 pairs. This is the only FE that covers all 28 pairs × 3 timeframes every H1 cycle.

The trend data is already computed in `_run_trend_models()` — just persist it.

```python
# In PullBackFeatureEngineer._run_trend_models() or at end of compute():
from state.db import get_session
from state.models import PairTrendState
from datetime import datetime

def _persist_trend_state(self, trend_results: dict) -> None:
    """
    Upsert trend state for all symbols × timeframes.
    trend_results: { symbol: { 'H4': {dir, prob_up, prob_down}, 'D1': {...}, 'W1': {...} } }
    """
    try:
        with get_session() as session:
            for sym, tf_data in trend_results.items():
                for tf, data in tf_data.items():
                    row = session.query(PairTrendState).filter_by(
                        symbol=sym, timeframe=tf
                    ).first()
                    if row is None:
                        row = PairTrendState(symbol=sym, timeframe=tf)
                        session.add(row)
                    row.trend_dir  = data.get('direction', 'sideways')
                    row.prob_up    = float(data.get('prob_up', 0.0))
                    row.prob_down  = float(data.get('prob_down', 0.0))
                    row.updated_at = datetime.utcnow()
            session.commit()
    except Exception as exc:
        logger.warning(f"[PullBackFE] pair_trend_state write failed: {exc}")
```

The trend data structure to collect from `_run_trend_models()` already has direction and
probabilities per timeframe per symbol — check `_h4_trend_results`, `_d1_trend_results`,
`_w1_trend_results` dicts in the FE.

---

### Phase 3 — Write `prediction_log` from Execution Engine

#### In `engine/execution_engine.py`

After each model run, write a row to `prediction_log` for EVERY symbol (including those
that failed gates early). The per-symbol gate data is available in
`predictor._last_cycle_results` after `predict()` returns.

```python
# After predictor.predict() returns in _run_model():
from state.db import get_session
from state.models import PredictionLog
import json

def _persist_prediction_log(
    self,
    model_name: str,
    timeframe: str,
    bar_time: datetime,
    predictor,           # has ._last_cycle_results after predict()
    signals: list,
) -> None:
    """Write per-symbol prediction rows for this model run."""
    last_results = getattr(predictor, '_last_cycle_results', {})
    if not last_results:
        return

    signal_symbols = {s.get('symbol') for s in signals}

    try:
        rows = []
        for sym, result in last_results.items():
            rows.append(PredictionLog(
                symbol       = sym,
                model_name   = model_name,
                bar_time     = bar_time,
                timeframe    = timeframe,
                direction    = result.get('direction'),
                confidence   = result.get('entry_prob'),
                gate_reached = result.get('gate', 99),
                signal_fired = sym in signal_symbols,
                features_json = json.dumps({
                    'exhaust_prob': result.get('exhaust_prob'),
                    'entry_prob':   result.get('entry_prob'),
                    'aligned':      result.get('aligned'),
                }),
            ))
        with get_session() as session:
            session.bulk_save_objects(rows)
            session.commit()
    except Exception as exc:
        logger.warning(f"[ExecutionEngine] prediction_log write failed: {exc}")
```

**Important:** Only `PullBackEntryPredictor` currently implements `_last_cycle_results`.
When Punk Hazard or other models are added, implement the same pattern in their predictors.

---

### Phase 4 — New API Endpoints (`dashboard/trade_server.py`)

Add two new routes to the existing Flask app:

#### `GET /api/market-overview`
Returns the latest trend state for all pairs + most recent prediction per model.

```python
@app.route('/api/market-overview')
def market_overview():
    with get_session() as session:
        # Latest trend state per symbol
        trend_rows = session.query(PairTrendState).all()
        trend_map = {}  # { symbol: { tf: {dir, prob_up, prob_down} } }
        for r in trend_rows:
            trend_map.setdefault(r.symbol, {})[r.timeframe] = {
                'dir': r.trend_dir,
                'prob_up': r.prob_up,
                'prob_down': r.prob_down,
                'updated_at': r.updated_at.isoformat() if r.updated_at else None,
            }

        # Latest prediction per symbol × model (subquery: max bar_time per group)
        from sqlalchemy import func
        latest_subq = (
            session.query(
                PredictionLog.symbol,
                PredictionLog.model_name,
                func.max(PredictionLog.bar_time).label('max_bt'),
            )
            .group_by(PredictionLog.symbol, PredictionLog.model_name)
            .subquery()
        )
        pred_rows = (
            session.query(PredictionLog)
            .join(latest_subq, (PredictionLog.symbol == latest_subq.c.symbol) &
                               (PredictionLog.model_name == latest_subq.c.model_name) &
                               (PredictionLog.bar_time == latest_subq.c.max_bt))
            .all()
        )
        pred_map = {}  # { symbol: { model_name: {...} } }
        for r in pred_rows:
            pred_map.setdefault(r.symbol, {})[r.model_name] = {
                'gate':         r.gate_reached,
                'confidence':   r.confidence,
                'signal_fired': r.signal_fired,
                'direction':    r.direction,
                'bar_time':     r.bar_time.isoformat() if r.bar_time else None,
            }

    return jsonify({'trend': trend_map, 'predictions': pred_map})
```

#### `GET /api/prediction-history?symbol=GBPCHF&model=Pull+Back+Entry+Short`
Returns the last 48 rows for one symbol × model (for the history chart popup).

```python
@app.route('/api/prediction-history')
def prediction_history():
    symbol = request.args.get('symbol', '')
    model  = request.args.get('model', '')
    with get_session() as session:
        rows = (
            session.query(PredictionLog)
            .filter_by(symbol=symbol, model_name=model)
            .order_by(PredictionLog.bar_time.desc())
            .limit(48)
            .all()
        )
    return jsonify([{
        'bar_time':     r.bar_time.isoformat(),
        'gate':         r.gate_reached,
        'confidence':   r.confidence,
        'signal_fired': r.signal_fired,
    } for r in rows])
```

---

### Phase 5 — "Market Overview" Tab in Dashboard HTML

#### Location
Add a new tab to `dashboard/templates/` (or inline HTML in `trade_server.py` if that's how
the existing dashboard is structured). Check how the existing dashboard tab structure works
before starting.

#### Layout — 28-row grid

```
PAIR    | H4 trend  | D1 trend | W1 trend | PB Long          | PB Short
--------|-----------|----------|----------|------------------|------------------
GBPCHF  | ▼ DOWN    | ▼ DOWN   | ▼ DOWN   | ✗ G2 0.00        | ✔ 0.66 ●
AUDUSD  | ▲ UP      | ▲ UP     | mixed    | ✗ G3 0.55        | ✗ G2 0.00
...
```

#### Cell design rules

**Trend cells (H4/D1/W1):**
- Green background + "▲ UP" if uptrend
- Red background + "▼ DOWN" if downtrend
- Grey background + "~ mixed" if sideways or misaligned
- Faded if `updated_at` > 2 hours old (stale)

**Model cells (PB Long / PB Short):**
- `gate=0` (signal): bright green, bold, bell icon `✔ 0.66 🔔`, shows confidence
- `gate=1`: grey, "G1 —" (not aligned)
- `gate=2`: grey, "G2 —" (wrong dir)
- `gate=3`: yellow-ish, "G3 0.XX" (shows exhaust prob — close to threshold is interesting)
- `gate=4`: orange, "G4 0.XX" (shows entry prob — near miss)
- `gate=99`: red, "ERR"
- Faded if `bar_time` > 2 hours old

**Click behaviour:**
- Click any model cell → opens history popup chart (calls `/api/prediction-history`)
- Chart shows last 48 bars: confidence line + gate reached per bar + signal markers

#### Auto-refresh
Poll `/api/market-overview` every 30 seconds. Highlight cells that changed since last
refresh with a brief flash animation.

#### Implementation notes
- Sort rows: pairs with gate=0 (signals) first, then by gate number ascending, then alpha
- For the history popup, use Chart.js (already likely in the existing dashboard) or a
  simple table if Chart.js is not present
- The grid should show "Last updated: HH:MM:SS" header so the user knows how fresh the data is

---

## Startup Sequence Changes

In `state/db.py` (or wherever `create_all` is called):
```python
# Both new tables are auto-created on startup via create_all(checkfirst=True)
# No manual migration needed for SQLite
```

In `features/pull_back_features.py` — `_persist_trend_state()` is called inside `compute()`,
wrapped in try/except so FE failures never propagate.

In `engine/execution_engine.py` — `_persist_prediction_log()` is called after each
`predictor.predict()` returns, also wrapped in try/except.

---

## Key Design Decisions (already settled)

1. **Data source for prediction_log:** `predictor._last_cycle_results` (already populated
   by `PullBackEntryPredictor` after every cycle). No FE changes needed for model scores.

2. **Data source for pair_trend_state:** `PullBackFeatureEngineer` writes all 28 × 3 TFs
   every H1 cycle. When Reversal FEs are re-enabled, they also upsert their pairs/TFs.
   Latest writer wins — upsert not append.

3. **Dashboard polling vs WebSocket:** Polling every 30s is fine. H1 cycles fire every
   hour; 30s polling means the grid updates within 30s of a cycle completing.

4. **History chart depth:** 48 bars = 2 days of H1 data. Sufficient to see patterns
   without overloading the DB query.

5. **prediction_log is append-only:** Never update or delete rows. Add a cleanup job
   later (e.g. delete rows > 30 days old) if the table grows large.

---

## Files to Create / Modify

| Action | File | What |
|--------|------|------|
| MODIFY | `state/models.py` | Add `PredictionLog` and `PairTrendState` classes |
| MODIFY | `features/pull_back_features.py` | Add `_persist_trend_state()`, call from `compute()` |
| MODIFY | `engine/execution_engine.py` | Add `_persist_prediction_log()`, call after `predict()` |
| MODIFY | `dashboard/trade_server.py` | Add `/api/market-overview` and `/api/prediction-history` routes |
| CREATE/MODIFY | `dashboard/templates/` | Add Market Overview tab HTML + JS |

---

## Testing Checklist

- [ ] Both new tables created on fresh `create_all()` (no error on restart)
- [ ] After one H1 cycle: `prediction_log` has 28 rows (one per symbol) for Pull Back Long
- [ ] After one H1 cycle: `pair_trend_state` has 84 rows (28 symbols × 3 TFs) or fewer if
      some TFs had no data
- [ ] `/api/market-overview` returns data for all 28 pairs
- [ ] Grid renders correctly with colour coding
- [ ] Clicking a cell opens the history chart
- [ ] Auto-refresh updates the grid after the next H1 cycle
- [ ] FE / execution engine failures are caught and do NOT block trade execution

---

## Prerequisite: Pull Back Short must be enabled

The Market Overview dashboard is most useful when both Long and Short are active —
otherwise the SHORT column is always empty. Enable Pull Back Short in `model_registry.yaml`
before starting this feature, or accept that the SHORT column will show no data until
it is enabled.
