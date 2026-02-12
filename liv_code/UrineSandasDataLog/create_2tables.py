import sqlite3

# Create / connect to database file
conn = sqlite3.connect("activities.db")
cur = conn.cursor()

# 1. Create Urine table
cur.execute("""
CREATE TABLE IF NOT EXISTS Urine (
    SerialNumber INTEGER PRIMARY KEY AUTOINCREMENT,
    Activity TEXT DEFAULT 'Urine',
    DateTime DATETIME DEFAULT (datetime('now', 'localtime'))
)
""")

# 2. Create Sandas table
cur.execute("""
CREATE TABLE IF NOT EXISTS Sandas (
    SerialNumber INTEGER PRIMARY KEY AUTOINCREMENT,
    Activity TEXT DEFAULT 'Sandas',
    DateTime DATETIME DEFAULT (datetime('now', 'localtime'))
)
""")

conn.commit()
conn.close()

print("Tables created successfully.")
