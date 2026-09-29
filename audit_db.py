import sqlite3
import os

db_path = 'flashflood.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print('TABLES IN DB:')
    for table in tables:
        tname = table[0]
        cursor.execute(f"SELECT count(*) FROM {tname}")
        count = cursor.fetchone()[0]
        print(f'{tname}: {count} rows')
    conn.close()
else:
    print('DB not found')
