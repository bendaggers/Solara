"""
query_trades.py
---------------
Shows all logged trades with their model score and threshold.

Usage:
    python query_trades.py              # all trades
    python query_trades.py --filled     # only FILLED trades
    python query_trades.py --signals    # signal_log only (includes rejected)
    python query_trades.py --today      # today's trades only
"""

import sqlite3
import os
import sys
import argparse
from datetime import date

DB = 'state/solara_aq.db'

# Threshold map — lowest min_confidence from confidence_tiers in model_registry.yaml
# Add new models here as you register them.
THRESHOLDS = {
    'UBB Rejection': 0.40,
}

def get_threshold(model_name):
    t = THRESHOLDS.get(model_name)
    return f'{t:.2f}' if t is not None else 'n/a'

def margin(score_val, model_name):
    try:
        score = float(score_val)
        t = THRESHOLDS.get(model_name)
        if t is None:
            return 'n/a'
        m = score - t
        return ('+' if m >= 0 else '') + f'{m:.4f}'
    except (ValueError, TypeError):
        return 'n/a'

def print_table(rows, col_names, col_widths):
    header = '  '.join(f'{c:<{w}}' for c, w in zip(col_names, col_widths))
    print(header)
    print('-' * len(header))
    for row in rows:
        line = '  '.join(f'{str(row.get(c) or ""):<{w}}' for c, w in zip(col_names, col_widths))
        print(line)
    print(f'\n  {len(rows)} row(s)')

def query_trades(filled_only=False, today_only=False):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    where = []
    if filled_only:
        where.append("t.status = 'FILLED'")
    if today_only:
        where.append(f"DATE(t.requested_at) = '{date.today()}'")
    where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

    cur = conn.cursor()
    cur.execute(f"""
        SELECT
            t.requested_at  AS time,
            t.symbol,
            t.direction     AS dir,
            t.status,
            t.ticket,
            s.confidence    AS score,
            t.model_name    AS model,
            t.volume        AS lot,
            t.entry_price   AS entry,
            t.sl_price      AS sl,
            t.tp_price      AS tp
        FROM trade_log t
        LEFT JOIN signal_log s ON s.trade_ticket = t.ticket
        {where_sql}
        ORDER BY t.requested_at DESC
    """)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print('No trades found.')
        return

    col_names  = ['time','symbol','dir','status','ticket','score','threshold','margin','lot','entry','sl','tp']
    col_widths = [26,    10,      6,    8,        12,      8,      10,        10,      5,   10,    10,  10]

    display = []
    for r in rows:
        d = dict(r)
        model = d.get('model') or ''
        d['threshold'] = get_threshold(model)
        d['margin']    = margin(d.get('score'), model)
        if d.get('score') is not None:
            d['score'] = f"{float(d['score']):.4f}"
        display.append(d)

    print_table(display, col_names, col_widths)

def query_signals():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT
            created_at      AS time,
            symbol,
            direction       AS dir,
            confidence      AS score,
            model_name      AS model,
            aggregation_status  AS agg,
            risk_status         AS risk,
            trade_ticket        AS ticket
        FROM signal_log
        ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print('No signals found.')
        return

    col_names  = ['time','symbol','dir','score','threshold','margin','agg','risk','ticket']
    col_widths = [26,    10,      6,    8,       10,         10,      10,   10,    12]

    display = []
    for r in rows:
        d = dict(r)
        model = d.get('model') or ''
        d['threshold'] = get_threshold(model)
        d['margin']    = margin(d.get('score'), model)
        if d.get('score') is not None:
            d['score'] = f"{float(d['score']):.4f}"
        display.append(d)

    print_table(display, col_names, col_widths)


if __name__ == '__main__':
    if not os.path.exists(DB):
        print(f'Database not found: {os.path.abspath(DB)}')
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument('--filled',  action='store_true', help='FILLED trades only')
    parser.add_argument('--signals', action='store_true', help='Show signal_log instead')
    parser.add_argument('--today',   action='store_true', help="Today only")
    args = parser.parse_args()

    if args.signals:
        query_signals()
    else:
        query_trades(filled_only=args.filled, today_only=args.today)
