import sqlite3
from datetime import date, timedelta

DB_PATH = "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/CalAndHolidays/CalAndHolidays.db"

# Current year
current_year = date.today().year

# 100 previous years + current year + 100 future years
start_year = current_year - 100
end_year = current_year + 100

WEEKDAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday"
]

# Connect to SQLite database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Make sure the table exists
cursor.execute("""
CREATE TABLE IF NOT EXISTS GregorianCalendar (
    Year TEXT NOT NULL CHECK (
        length(Year) = 4 AND
        Year GLOB '[0-9][0-9][0-9][0-9]' AND
        Year != '0000'
    ),
    Month TEXT NOT NULL CHECK (
        Month IN (
            '01','02','03','04','05','06',
            '07','08','09','10','11','12'
        )
    ),
    Day TEXT NOT NULL CHECK (
        Day IN (
            '01','02','03','04','05','06','07','08','09','10',
            '11','12','13','14','15','16','17','18','19','20',
            '21','22','23','24','25','26','27','28','29','30','31'
        )
    ),
    "Weekday Name" TEXT NOT NULL CHECK (
        "Weekday Name" IN (
            'Sunday',
            'Monday',
            'Tuesday',
            'Wednesday',
            'Thursday',
            'Friday',
            'Saturday'
        )
    )
)
""")

# Create unique index so the same date cannot be inserted twice
cursor.execute("""
CREATE UNIQUE INDEX IF NOT EXISTS idx_GregorianCalendar_date
ON GregorianCalendar(Year, Month, Day)
""")

# Start and end dates
start_date = date(start_year, 1, 1)
end_date = date(end_year, 12, 31)

# Prepare all rows
rows = []

current_date = start_date

while current_date <= end_date:

    year = f"{current_date.year:04d}"
    month = f"{current_date.month:02d}"
    day = f"{current_date.day:02d}"
    weekday = WEEKDAYS[current_date.weekday()]

    rows.append((
        year,
        month,
        day,
        weekday
    ))

    current_date += timedelta(days=1)

# Insert all rows
cursor.executemany("""
INSERT OR IGNORE INTO GregorianCalendar
(Year, Month, Day, "Weekday Name")
VALUES (?, ?, ?, ?)
""", rows)

conn.commit()

# Count rows
cursor.execute("SELECT COUNT(*) FROM GregorianCalendar")
total_rows = cursor.fetchone()[0]

conn.close()

print(f"Calendar range : {start_date} to {end_date}")
print(f"Rows generated : {len(rows):,}")
print(f"Rows in table  : {total_rows:,}")
print("Gregorian calendar population completed successfully.")
