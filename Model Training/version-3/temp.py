import sqlite3
conn = sqlite3.connect('checkpoints/fast.db')
cursor = conn.cursor()
cursor.execute("SELECT config_id, status, ev_mean FROM completed WHERE status='PASSED' ORDER BY ev_mean DESC LIMIT 10")
for row in cursor.fetchall():
    print(f'{row[0]}: EV={row[2]:.2f}')
conn.close()
