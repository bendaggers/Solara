# check_ids.py
import sqlite3
conn = sqlite3.connect('checkpoints/fast.db')

rows = conn.execute('''
    SELECT config_id, bb_threshold, rsi_threshold, timestamp 
    FROM completed 
    WHERE config_id LIKE 'CFG_0000%'
    ORDER BY timestamp DESC
    LIMIT 20
''').fetchall()

print('Recent Config IDs (CFG_0000x):')
for r in rows:
    print(f'  {r[0]}: BB={r[1]}, RSI={r[2]}, Time={r[3]}')

conn.close()