# SolaraAIQuantDashboard — Backend (BE)

Django + PostgreSQL REST API serving trade data and historical OHLCV candles, with Celery for background task scheduling.

---

## Table of Contents

- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Django Admin](#django-admin)
- [Trades API](#trades-api)
- [OHLCV Historical System](#ohlcv-historical-system)
- [Celery Task System](#celery-task-system)
- [Launching All Servers](#launching-all-servers)
- [Frontend Integration](#frontend-integration)
- [CORS](#cors)
- [Coding Conventions](#coding-conventions)
- [ML Feature Creation](#ml-feature-creation)
- [Roadmap](#roadmap)

---

## Tech Stack

| Layer       | Technology                 | Version   |
|-------------|----------------------------|-----------|
| Framework   | Django                     | 4.2–5.1   |
| API         | Django REST Framework      | 3.14+     |
| Database    | PostgreSQL                 | 14+       |
| DB Driver   | psycopg2-binary            | 2.9+      |
| CORS        | django-cors-headers        | 4.0+      |
| Config      | python-dotenv              | 1.0+      |
| MT5 Bridge  | MetaTrader5 (Windows only) | latest    |
| Task Queue  | Celery                     | 5.3+      |
| Broker      | Redis                      | 5.0+      |
| Scheduler   | django-celery-beat         | 2.5+      |
| Results     | django-celery-results      | 2.5+      |
| Runtime     | Python                     | 3.11+     |

---

## Project Structure

```
BE/
├── core/
│   ├── settings.py              # All settings — reads from .env
│   ├── urls.py                  # Root URL dispatcher → /api/
│   ├── celery.py                # Celery app definition
│   └── __init__.py              # Loads Celery on Django startup
│
├── trades/                      # Open/closed trade positions
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   ├── migrations/
│   └── management/commands/
│       └── seed_trades.py
│
├── ohlcv/                       # Historical candle store
│   ├── models.py                # OHLCV + KnownClosure tables
│   ├── mt5_bridge.py            # ALL MT5 interaction lives here
│   ├── services.py              # Sync, gap detection, DB insert logic
│   ├── tasks.py                 # Celery tasks (event-driven, not polling)
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   └── migrations/
│       ├── 0001_initial.py
│       └── 0002_knownclosure.py
│   └── management/commands/
│       ├── backfill_ohlcv.py
│       ├── check_gaps.py        # Startup gap check — runs automatically via start-be.bat
│       └── sync_ohlcv.py        # Legacy — kept for manual testing only
│
├── .env
├── .env.example
├── requirements.txt
└── manage.py
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis (Windows installer: `https://github.com/microsoftarchive/redis/releases`)
- MetaTrader 5 terminal running on the same Windows machine

### Installation

```bash
cd SolaraAIQuantDashboard/BE

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
pip install MetaTrader5           # Windows only

# Edit .env — set DB credentials + MT5 credentials

psql -U postgres -c "CREATE DATABASE solara_quant;"

python manage.py migrate

python manage.py seed_trades      # dummy trade data
python manage.py createsuperuser  # Django admin account

# Run once — fills 500 candles of history per symbol/timeframe
python manage.py backfill_ohlcv

# Check and fix any gaps in historical data
python manage.py check_gaps

# Then launch everything via the bat scripts
# start-be.bat runs check_gaps automatically on every startup
```

---

## Environment Variables

> ⚠️ `.env` credentials are for PostgreSQL and MT5 only — NOT the Django admin login.
> When changes are needed, only the specific lines to add/change are shown.

| Variable               | Value                       | Description                                     |
|------------------------|-----------------------------|-------------------------------------------------|
| `DJANGO_SECRET_KEY`    | your-secret-key             | Change in production                            |
| `DEBUG`                | `True`                      | Set `False` in production                       |
| `ALLOWED_HOSTS`        | `localhost,127.0.0.1`       | Comma-separated                                 |
| `DB_NAME`              | `solara_quant`              | PostgreSQL database name                        |
| `DB_USER`              | `postgres`                  | PostgreSQL username                             |
| `DB_PASSWORD`          | your-db-password            | PostgreSQL password                             |
| `DB_HOST`              | `localhost`                 | PostgreSQL host                                 |
| `DB_PORT`              | `5432`                      | PostgreSQL port                                 |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,...` | Comma-separated FE origins                      |
| `MT5_LOGIN`            | your-account-number         | MT5 account number                              |
| `MT5_PASSWORD`         | your-mt5-password           | MT5 password                                    |
| `MT5_SERVER`           | e.g. `ICMarkets-Live`       | Broker server name                              |
| `OHLCV_TIMEFRAMES`     | `M15,H1,H4,D1,W1`          | Tracked timeframes                              |
| `OHLCV_BACKFILL_COUNT` | `500`                       | Candles to fetch on first run per symbol/TF     |
| `OHLCV_SYNC_INTERVAL`  | `60`                        | Legacy — no longer used by Celery               |
| `CELERY_BROKER_URL`    | `redis://localhost:6379/0`  | Redis broker URL                                |

---

## Django Admin

URL: `http://localhost:8000/admin/`

```bash
# Create admin account (separate from DB and MT5 credentials)
python manage.py createsuperuser

# Forgot password?
python manage.py changepassword <username>

# Forgot username?
python manage.py shell -c "from django.contrib.auth.models import User; print(list(User.objects.values_list('username', flat=True)))"
```

The OHLCV and KnownClosure tables are **read-only** in the admin panel.

---

## Trades API

Base URL: `http://localhost:8000/api/`

| Method | URL                          | Description                           |
|--------|------------------------------|---------------------------------------|
| GET    | `/api/trades/`               | List all trades (paginated)           |
| GET    | `/api/trades/?status=open`   | Filter by status                      |
| GET    | `/api/trades/?symbol=EURUSD` | Filter by symbol                      |
| GET    | `/api/trades/{ticket}/`      | Single trade detail                   |
| GET    | `/api/trades/summary/`       | Aggregated stats for StatCards        |

### Trade object

```json
{
  "ticket": 1040231,
  "symbol": "EURUSD",
  "time": "01/15/2025 08:32:14",
  "type": "buy",
  "volume": "0.10",
  "entry": "1.08320",
  "sl": "1.07800",
  "tp": "1.09100",
  "profit": "42.50",
  "currentPrice": "1.08745",
  "magic": 20240101,
  "comment": "TI V2 LONG",
  "status": "open"
}
```

> ⚠️ Decimal fields are strings from DRF. The FE `normalizeTrade()` converts them — do not remove it.

---

## OHLCV Historical System

### Design principles

- **Append-only** — insert once, never update, never delete
- **Closed candles only** — forming candle is always skipped
- **Duplicate-safe** — `ON CONFLICT DO NOTHING` + `RETURNING` for accurate count
- **Event-driven inserts** — candles inserted at close time, not by polling
- **KnownClosure table** — holidays and broker halts recorded permanently, never retried
- **Forex weekend aware** — Fri 22:00 UTC → Sun 22:00 UTC skipped for ALL timeframes (M15, H1, H4, D1, W1)

### Database tables

**`ohlcv`**
```sql
CREATE TABLE ohlcv (
    symbol    TEXT,
    timeframe TEXT,
    time      TIMESTAMP,
    open      FLOAT,
    high      FLOAT,
    low       FLOAT,
    close     FLOAT,
    volume    FLOAT,
    PRIMARY KEY (symbol, timeframe, time)
);
CREATE INDEX idx_symbol_tf_time ON ohlcv(symbol, timeframe, time DESC);
```

**`ohlcv_known_closure`**
```sql
CREATE TABLE ohlcv_known_closure (
    symbol      TEXT,
    timeframe   TEXT,
    time        TIMESTAMP,
    reason      TEXT DEFAULT 'no_data',
    recorded_at TIMESTAMP,
    UNIQUE (symbol, timeframe, time)
);
```

Slots in `KnownClosure` are **permanently skipped** by gap detection. Once a holiday or broker halt is confirmed by MT5 returning no data, it is never retried again.

### Tracked timeframes

`M15, H1, H4, D1, W1` (configured via `OHLCV_TIMEFRAMES` in `.env`)

### Tracked symbols

28 forex pairs + gold:
```
EURUSD GBPUSD USDJPY USDCHF AUDUSD USDCAD NZDUSD
EURGBP EURJPY EURCHF EURAUD EURCAD EURNZD
GBPJPY GBPCHF GBPAUD GBPCAD GBPNZD
AUDJPY AUDCHF AUDCAD AUDNZD
NZDJPY NZDCHF NZDCAD
CADJPY CADCHF CHFJPY
XAUUSD
```

### Price precision

All prices rounded to 5 decimal places and volume to 2 decimal places in `mt5_bridge.py` before DB insert — prevents floating point noise like `1.6562999999999999`.

### Forex market hours

The market is universally closed during:

| Window | Rule |
|---|---|
| Saturday | Always closed |
| Sunday before 22:00 UTC | Closed |
| Friday 22:00 UTC onwards | Closed |

Any candle slot falling in these windows is skipped by gap detection for **all timeframes** — not just D1/W1.

### Gap detection algorithm

`find_gaps()` walks **consecutive stored candle pairs** and checks if the time between them is larger than one step. This is efficient — it only examines actual data points, not a generated expected sequence.

For each gap found between candle A and candle B:
1. Generate the missing slots between A and B
2. Skip slots during forex weekend closure
3. Skip slots already in `KnownClosure`
4. Return remaining genuine gaps

`fix_gaps()` then:
1. Groups consecutive gaps into ranges (one MT5 fetch per range)
2. Fetches candles from MT5 for each range
3. Inserts what's found with `ON CONFLICT DO NOTHING RETURNING`
4. Records any unfillable slots into `KnownClosure` permanently

### Verifying gap checks worked

```bash
# Manually trigger gap check right now (don't wait for 23:00)
python manage.py shell -c "
from ohlcv.tasks import check_and_fix_gaps
result = check_and_fix_gaps()
print(result)
"

# See what was recorded as known closures (holidays/halts)
python manage.py shell -c "
from ohlcv.models import KnownClosure
print('Known closures recorded:', KnownClosure.objects.count())
for kc in KnownClosure.objects.order_by('symbol','timeframe','time')[:20]:
    print(' ', kc)
"

# Confirm zero genuine gaps remain
python manage.py shell -c "
from ohlcv.services import find_gaps
symbols = ['EURUSD', 'XAUUSD', 'GBPUSD']
tfs = ['H1', 'D1']
for s in symbols:
    for tf in tfs:
        gaps = find_gaps(s, tf)
        print(f'{s} {tf}: {len(gaps)} gap(s) remaining')
"
```

---

## Celery Task System

### Architecture overview

```
MT5 Terminal
    │
    ▼
mt5_bridge.py   — connect(), fetch_candles(), is_closed()
    │
    ▼
services.py     — sync_symbol_timeframe()
                — find_gaps() / fix_gaps()
                — bulk_insert (ON CONFLICT DO NOTHING RETURNING)
    │
    ▼
tasks.py        — Celery tasks (event-driven scheduling)
    │
    ▼
PostgreSQL      — ohlcv + ohlcv_known_closure tables
    │
    ▼
views.py        — REST API → React frontend
```

### Task schedule

Candle insert tasks fire **at close time** — not by polling. Each task fetches only 2 candles per symbol.

| Task | Schedule | What it does |
|---|---|---|
| `ohlcv.insert_m15` | :01 :16 :31 :46 | Insert just-closed M15 candle |
| `ohlcv.insert_h1` | :01 past every hour | Insert just-closed H1 candle |
| `ohlcv.insert_h4` | 00:01 04:01 08:01 12:01 16:01 20:01 UTC | Insert just-closed H4 candle |
| `ohlcv.insert_d1` | 22:01 UTC daily | Insert just-closed D1 candle |
| `ohlcv.insert_w1` | Friday 22:01 UTC | Insert just-closed W1 candle |
| `ohlcv.check_and_fix_gaps` | 23:00 UTC daily | Gap scan + KnownClosure recording |

> Gap check also runs automatically on every startup via `start-be.bat` → `python manage.py check_gaps`

### Why event-driven instead of polling

Old approach (polling every 60s):
- Fetches 50 candles × 29 symbols × 5 timeframes = wasteful every minute
- Most fetches return nothing new

New approach (event-driven):
- M15 fires 4× per hour, fetches 2 candles × 29 symbols — only when a candle actually closes
- H1 fires 1× per hour, H4 6× per day, D1 once daily, W1 once weekly
- Gap check runs once daily — after first run, KnownClosure makes it nearly instant

### On-demand task (for live charting)

```python
from ohlcv.tasks import sync_single_ohlcv

# Trigger fresh fetch for one symbol when user opens a chart
sync_single_ohlcv.delay("EURUSD", "H1")
```

### Managing stale Celery Beat schedules

If you update `settings.py` beat schedule, old tasks may still be in the DB. Clean them:

```bash
# Remove a specific old task
python manage.py shell -c "
from django_celery_beat.models import PeriodicTask
deleted, _ = PeriodicTask.objects.filter(task='ohlcv.sync_all').delete()
print(f'Deleted {deleted} old task(s)')
"

# List all currently registered tasks
python manage.py shell -c "
from django_celery_beat.models import PeriodicTask
for t in PeriodicTask.objects.all():
    print(t.name, '->', t.task)
"
```

### Running the system

**First startup (run once):**
```bash
python manage.py migrate
python manage.py backfill_ohlcv    # fills 500 candles of history
python manage.py check_gaps        # fix any gaps after backfill
```

**Every subsequent startup:**
```bash
# Just double-click start-solara.bat
# start-be.bat automatically runs check_gaps before Django starts
```

**Manual gap check anytime:**
```bash
python manage.py check_gaps           # check + fix
python manage.py check_gaps --dry-run # report only, no inserts
```

**Then launch via bat scripts — Celery handles everything automatically.**

---

## Launching All Servers

Place all `.bat` files in `SolaraAIQuantDashboard\`:

```
SolaraAIQuantDashboard\
├── start-solara.bat          ← double-click this
├── start-be.bat
├── start-celery-worker.bat
├── start-celery-beat.bat
├── start-fe.bat
├── BE\
└── FE\
```

Double-clicking `start-solara.bat` opens **4 terminal windows**:

| Window | Command | Purpose |
|---|---|---|
| Django backend | `manage.py runserver` | Serves API + admin |
| Celery worker | `python -m celery -A core worker --pool=solo` | Executes tasks |
| Celery beat | `python -m celery -A core beat` | Fires tasks on schedule |
| Vite frontend | `npm run dev` | React dev server |

> Redis must be running as a Windows service before launching.
> Verify with: `redis-cli ping` → should reply `PONG`

---

## Frontend Integration

### `FE/src/api/trades.js`

Must be created manually at `FE/src/api/trades.js`:

```js
import { useState, useEffect } from "react";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";

function normalizeTrade(t) {
  return {
    ...t,
    entry:        Number(t.entry),
    currentPrice: Number(t.currentPrice),
    sl:           Number(t.sl),
    tp:           Number(t.tp),
    profit:       Number(t.profit),
    volume:       Number(t.volume),
  };
}

export async function fetchOpenTrades() {
  const res = await fetch(`${BASE_URL}/trades/?status=open`);
  if (!res.ok) throw new Error(`Trades API error: ${res.status}`);
  const data = await res.json();
  const raw = Array.isArray(data) ? data : data.results ?? [];
  return raw.map(normalizeTrade);
}

export async function fetchTradeSummary() {
  const res = await fetch(`${BASE_URL}/trades/summary/`);
  if (!res.ok) throw new Error(`Summary API error: ${res.status}`);
  return res.json();
}

export function useTrades(pollIntervalMs = 0) {
  const [trades,  setTrades]  = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  async function load() {
    try {
      const [t, s] = await Promise.all([fetchOpenTrades(), fetchTradeSummary()]);
      setTrades(t);
      setSummary(s);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    if (pollIntervalMs > 0) {
      const id = setInterval(load, pollIntervalMs);
      return () => clearInterval(id);
    }
  }, [pollIntervalMs]);

  return { trades, summary, loading, error, refetch: load };
}
```

### `Trades.jsx` imports

```js
import { SYMBOL_COLORS } from "../data/trades";  // TRADES removed
import { useTrades } from "../api/trades";
```

### Vite env var

Add to `FE/.env`:
```
VITE_API_URL=http://localhost:8000/api
```

---

## CORS

To add a production domain:
```
CORS_ALLOWED_ORIGINS=http://localhost:5173,https://your-production-domain.com
```

---

## Coding Conventions

- **One app per domain** — `trades` for positions, `ohlcv` for candles
- **MT5 isolation** — only `mt5_bridge.py` imports MetaTrader5
- **Append-only OHLCV** — never add update/delete to the ohlcv app
- **Event-driven tasks** — no polling; tasks fire at actual candle close times
- **KnownClosure is permanent** — never delete from this table unless fixing a bug
- **Decimal fields** — add new decimals to `normalizeTrade()` in the FE
- **Price rounding** — 5dp prices, 2dp volume, done in `mt5_bridge.py`
- **`.env` changes** — only specific lines shown, no full file regeneration
- **Migrations committed** — never gitignore `migrations/` folders

---

## ML Feature Creation

### Data integrity

The `time` column is `timestamptz` (UTC). pgAdmin displays it as "4 a.m." / "midnight" — this is cosmetic only. All ORM queries return proper UTC `datetime` objects.

### Fetching 300 rows as a Pandas DataFrame

```python
import pandas as pd
from django.db import connection

def get_ml_dataframe(symbol: str, timeframe: str, count: int = 300) -> pd.DataFrame:
    sql = """
        SELECT time, open, high, low, close, volume
        FROM ohlcv
        WHERE symbol = %s AND timeframe = %s
        ORDER BY time DESC
        LIMIT %s
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [symbol, timeframe, count])
        rows = cursor.fetchall()

    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"])
    df = df.iloc[::-1].reset_index(drop=True)   # reverse to chronological
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df.set_index("time", inplace=True)
    return df
```

### Check data availability before ML runs

```python
from ohlcv.models import OHLCV

def has_enough_data(symbol: str, timeframe: str, min_count: int = 300) -> bool:
    return OHLCV.objects.filter(symbol=symbol, timeframe=timeframe).count() >= min_count
```

### Verify clean data via pgAdmin

```sql
SELECT
    symbol,
    timeframe,
    TO_CHAR(time AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS') AS time,
    open, high, low, close, volume
FROM ohlcv
WHERE symbol = 'EURUSD' AND timeframe = 'H1'
ORDER BY time DESC
LIMIT 10;
```

---

## Gap Check System

### How it works

On every startup, `start-be.bat` runs `python manage.py check_gaps` before Django starts.

| Symbol | What happens |
|--------|-------------|
| Gap found, MT5 has data | Candle inserted ✅ |
| Gap found, MT5 has no data | Recorded in `KnownClosure` permanently — never retried 📋 |
| Gap falls in Fri 22:00–Sun 22:00 UTC | Skipped — forex weekend closure |
| Gap already in `KnownClosure` | Skipped instantly |

### Output legend

```
[✓] EURUSD H1: 4 gap(s) — all fixed
[~] EURUSD H4: 6 gap(s) — 2 fixed, 4 recorded as KnownClosure (holiday/halt)
[K] XAUUSD M15: 116 gap(s) — MT5 has no data, all recorded as KnownClosure
✅  No gaps found — data is clean!
```

### Key functions

| File | Function | Purpose |
|------|----------|---------|
| `services.py` | `find_gaps()` | Detects missing candles, skips weekends + KnownClosure |
| `services.py` | `fix_gaps()` | Fills gaps via MT5, records unfillable slots as KnownClosure |
| `mt5_bridge.py` | `fetch_candles_range()` | Date-range fetch using `copy_rates_range` — used by gap fixer |
| `mt5_bridge.py` | `fetch_candles()` | Last-N fetch using `copy_rates_from_pos` — used by regular sync |

### Weekend skip logic

Applies to ALL timeframes (M15, H1, H4, D1, W1):
- Friday 22:00 UTC → closed
- All of Saturday → closed  
- Sunday 00:00–21:59 UTC → closed
- Sunday 22:00 UTC → open again

---

## Roadmap

- [ ] `POST /api/trades/` — write endpoint for MT5 EA to push live trade events
- [ ] `PATCH /api/trades/{ticket}/` — update price/profit from MT5
- [ ] `POST /api/trades/{ticket}/close/` — mark trade closed
- [ ] Live OHLCV streaming — WebSocket feed from MT5 to frontend (replaces `sync_single`)
- [ ] `GET /api/history/` — closed trade log with date range filters
- [ ] `GET /api/performance/` — equity curve, drawdown, win streak
- [ ] Token authentication for write endpoints
- [ ] Windows service wrapper for Celery (survives reboots without bat scripts)
- [ ] Docker Compose (Django + PostgreSQL + Redis + Nginx) for production
