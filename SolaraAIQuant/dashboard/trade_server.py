"""
trade_server.py
---------------
Lightweight HTTP server that serves the trade dashboard.
Reads trade log from state/solara_aq.db and enriches with live
MT5 data (open position comment, closed trade exit price / exit time / profit).

Usage:
    python dashboard/trade_server.py
    python dashboard/trade_server.py --port 9000
    python dashboard/trade_server.py --tz-offset 3

--tz-offset
    Hours to add to the UTC timestamps stored in the database so they
    match what you see in the MT5 terminal (broker local time).
    Example: DB shows 13:35, MT5 shows 16:35  →  offset = +3  (default)
"""

import sqlite3
import json
import argparse
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

# ── Paths ──────────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
DB    = os.path.join(_ROOT, 'state', 'solara_aq.db')
PORT  = 8765

# ── Config ─────────────────────────────────────────────────────────────────────
THRESHOLDS = {
    'UBB Rejection': 0.55,
}

# Magic numbers for ALL SAQ models — used to filter positions/deals from MT5
SAQ_MAGIC_NUMBERS = {200001}

# Populated at startup via --tz-offset (default 3 = UTC+3 broker time)
TZ_OFFSET_HOURS = 3


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_threshold(model_name: str) -> float:
    return THRESHOLDS.get(model_name or '', 0.40)


def utc_to_broker(utc_str: str) -> str:
    """
    Add TZ_OFFSET_HOURS to a UTC datetime string from the database.
    Handles both 'YYYY-MM-DD HH:MM:SS' and 'YYYY-MM-DD HH:MM:SS.ffffff'.
    Returns the broker-local string 'YYYY-MM-DD HH:MM:SS'.
    """
    if not utc_str:
        return ''
    try:
        clean = utc_str.split('.')[0].strip()
        dt = datetime.strptime(clean, '%Y-%m-%d %H:%M:%S')
        dt += timedelta(hours=TZ_OFFSET_HOURS)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return utc_str  # fall back to raw value


def fmt_price(val) -> str:
    if val is None:
        return ''
    try:
        return f"{float(val):.5f}"
    except (ValueError, TypeError):
        return str(val)


def fmt_profit(val) -> str:
    if val is None:
        return ''
    try:
        v = float(val)
        return f"{v:+.2f}"
    except (ValueError, TypeError):
        return str(val)


# ── MT5 enrichment ─────────────────────────────────────────────────────────────

def get_mt5_enrichment():
    """
    Query the MT5 Python API and return two dicts keyed by integer ticket:

        open_map   { ticket -> {'comment': str} }
        closed_map { ticket -> {'exit_time': str, 'exit_price': float,
                                'profit': float,  'comment':    str} }

    Falls back to empty dicts when MT5 is unavailable (dev machine).

    HOW MT5 HISTORY WORKS
    ─────────────────────
    mt5.positions_get()          -> currently open positions
    mt5.history_deals_get(f, t)  -> all deals in a time window

    Each position generates two deals:
      DEAL_ENTRY_IN  (entry)  -> d.order       = ticket stored in trade_log
                                  d.position_id = links to exit deal
      DEAL_ENTRY_OUT (exit)   -> d.position_id = same position id
                                  d.price / d.profit / d.time = exit details

    Build closed_map:
      1. Collect all OUT deals  -> position_exits { position_id -> exit info }
      2. For each IN deal       -> closed_map[d.order] = position_exits[d.position_id]
    """
    open_map   = {}
    closed_map = {}

    try:
        import MetaTrader5 as mt5

        if not mt5.initialize():
            return open_map, closed_map

        # ── Open positions ─────────────────────────────────────────────────────
        positions = mt5.positions_get() or []
        for p in positions:
            if p.magic in SAQ_MAGIC_NUMBERS:
                open_map[p.ticket] = {'comment': p.comment or ''}

        # ── Closed deals ──────────────────────────────────────────────────────
        from_date = datetime(2020, 1, 1)
        to_date   = datetime.utcnow() + timedelta(days=1)
        deals     = mt5.history_deals_get(from_date, to_date) or []

        # Step 1 — index all EXIT deals by position_id
        # EXIT deal comment = MT5 close reason e.g. "[tp 1.92101]" or "[sl 1.66042]"
        position_exits = {}
        for d in deals:
            if d.magic not in SAQ_MAGIC_NUMBERS:
                continue
            if d.entry == mt5.DEAL_ENTRY_OUT:
                exit_dt  = datetime.utcfromtimestamp(d.time)
                exit_dt += timedelta(hours=TZ_OFFSET_HOURS)
                position_exits[d.position_id] = {
                    'exit_time':    exit_dt.strftime('%Y-%m-%d %H:%M:%S'),
                    'exit_price':   d.price,
                    'profit':       d.profit,
                    'close_reason': d.comment or '',   # e.g. "[tp 1.92101]"
                }

        # Step 2 — map entry order ticket -> exit info + entry deal comment
        # ENTRY deal comment = order comment we set e.g. "UBB Rejection M5"
        for d in deals:
            if d.magic not in SAQ_MAGIC_NUMBERS:
                continue
            if d.entry == mt5.DEAL_ENTRY_IN:
                if d.position_id in position_exits:
                    closed_map[d.order] = {
                        **position_exits[d.position_id],
                        'comment': d.comment or '',    # "UBB Rejection M5"
                    }

        mt5.shutdown()

    except ImportError:
        pass   # MT5 not installed — dev mode, silently skip
    except Exception as e:
        print(f"  [trade_server] MT5 query error: {e}")

    return open_map, closed_map


# ── Data fetch ─────────────────────────────────────────────────────────────────

def fetch_trades() -> list:
    if not os.path.exists(DB):
        return []

    open_map, closed_map = get_mt5_enrichment()

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()
    cur.execute("""
        SELECT
            t.requested_at   AS time,
            t.symbol,
            t.direction      AS dir,
            t.status,
            t.ticket,
            t.model_name     AS model,
            t.volume         AS lot,
            t.entry_price    AS entry,
            t.sl_price       AS sl,
            t.tp_price       AS tp,
            COALESCE(s1.confidence, s2.confidence) AS score
        FROM trade_log t
        LEFT JOIN signal_log s1
            ON s1.trade_ticket = t.ticket
        LEFT JOIN signal_log s2
            ON  s2.trade_ticket IS NULL
            AND s2.symbol     = t.symbol
            AND s2.direction  = t.direction
            AND s2.model_name = t.model_name
            AND ABS((JULIANDAY(s2.created_at) - JULIANDAY(t.requested_at)) * 86400) <= 10
        WHERE t.status = 'FILLED'
        ORDER BY t.requested_at DESC
        LIMIT 500
    """)
    rows = cur.fetchall()
    conn.close()

    result = []
    for r in rows:
        d         = dict(r)
        model     = d.get('model') or ''
        threshold = get_threshold(model)
        score     = d.get('score')
        ticket    = d.get('ticket')   # integer or None

        # ── Time: shift UTC → broker local ────────────────────────────────────
        d['time'] = utc_to_broker(d.get('time', ''))

        # ── Score ─────────────────────────────────────────────────────────────
        d['threshold'] = f"{threshold:.2f}"
        if score is not None:
            score_f     = float(score)
            margin      = score_f - threshold
            d['score']  = f"{score_f:.4f}"
            d['margin'] = ('+' if margin >= 0 else '') + f"{margin:.4f}"
            d['passed'] = score_f >= threshold
        else:
            d['score']  = ''
            d['margin'] = 'n/a'
            d['passed'] = None

        # ── Round prices ──────────────────────────────────────────────────────
        for col in ('entry', 'sl', 'tp'):
            d[col] = fmt_price(d.get(col))

        # ── MT5 enrichment ────────────────────────────────────────────────────
        mt5_open   = open_map.get(ticket)   if ticket is not None else None
        mt5_closed = closed_map.get(ticket) if ticket is not None else None

        if mt5_open:
            d['pos_status']   = 'OPEN'
            d['comment']      = mt5_open.get('comment', '')   # "UBB Rejection M5"
            d['close_reason'] = ''
            d['exit_time']    = ''
            d['exit_price']   = ''
            d['profit']       = ''

        elif mt5_closed:
            d['pos_status']   = 'CLOSED'
            d['comment']      = mt5_closed.get('comment', '')        # "UBB Rejection M5"
            d['close_reason'] = mt5_closed.get('close_reason', '')   # "[tp 1.92101]"
            d['exit_time']    = mt5_closed.get('exit_time', '')
            d['exit_price']   = fmt_price(mt5_closed.get('exit_price'))
            d['profit']       = fmt_profit(mt5_closed.get('profit'))

        else:
            # MT5 unavailable or ticket not found yet
            d['pos_status']   = ''
            d['comment']      = ''
            d['close_reason'] = ''
            d['exit_time']    = ''
            d['exit_price']   = ''
            d['profit']       = ''

        result.append(d)

    return result


# ── HTTP server ────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence default request log

    def do_GET(self):
        if self.path == '/data':
            self._serve_json()
        else:
            self._serve_html()

    def _serve_json(self):
        data = json.dumps(fetch_trades())
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(data.encode())

    def _serve_html(self):
        html_path = os.path.join(_HERE, 'trade_dashboard.html')
        html = open(html_path, encoding='utf-8').read()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode())


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SAQ Trade Dashboard Server')
    parser.add_argument('--port',      type=int, default=PORT,
                        help='HTTP port (default: 8765)')
    parser.add_argument('--tz-offset', type=int, default=3,
                        help='Hours to add to UTC for broker display time (default: 3)')
    args = parser.parse_args()

    TZ_OFFSET_HOURS = args.tz_offset

    if not os.path.exists(DB):
        print(f"  Warning: database not found at {DB}")
        print("  Server will start but show no data until SAQ runs.")

    print(f"  SAQ Trade Dashboard  →  http://localhost:{args.port}")
    print(f"  Time display         →  UTC+{TZ_OFFSET_HOURS} (broker time)")
    print(f"  Ctrl+C to stop\n")

    HTTPServer(('', args.port), Handler).serve_forever()
