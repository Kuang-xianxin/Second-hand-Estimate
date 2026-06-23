import sqlite3
conn = sqlite3.connect('guessr.db')
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print('Tables:', sorted([t[0] for t in tables]))

conn.execute("""
CREATE TABLE IF NOT EXISTS crawl_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id VARCHAR(64) UNIQUE NOT NULL,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    total_keywords INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    total_items INTEGER DEFAULT 0,
    bargains_found INTEGER DEFAULT 0,
    status VARCHAR(32) DEFAULT 'running',
    error_message TEXT
)
""")
conn.commit()
print("crawl_status table created")
conn.close()
