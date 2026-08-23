import sqlite3

DB_PATH = "/home/dkvlko/live_code/BLOBS/CalAndHolidays/CalAndHolidays.db"

START_YEAR = 1926
END_YEAR = 2126

HOLIDAYS = [
    ("01", "26", "Republic Day"),
    ("04", "14", "Dr Ambedkar Jayanti"),
    ("08", "15", "Independence Day"),
    ("10", "02", "Gandhi Jayanti"),
    ("12", "25", "Christmas Day"),
]

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

rows = []

for year in range(START_YEAR, END_YEAR + 1):
    for month, day, name in HOLIDAYS:
        rows.append((
            f"{year:04d}",
            month,
            day,
            name,
            "National Holiday"
        ))

cursor.executemany("""
    INSERT INTO Static_Holidays
        (Year, Month, Day, Name, Descr)
    VALUES (?, ?, ?, ?, ?)
""", rows)

conn.commit()

# Verify the number of rows inserted
cursor.execute("""
    SELECT COUNT(*)
    FROM Static_Holidays
""")

count = cursor.fetchone()[0]

conn.close()

print(f"Years populated : {START_YEAR} - {END_YEAR}")
print(f"Holidays/year   : {len(HOLIDAYS)}")
print(f"Rows inserted    : {len(rows)}")
print(f"Total table rows : {count}")
print("Static_Holidays populated successfully.")
