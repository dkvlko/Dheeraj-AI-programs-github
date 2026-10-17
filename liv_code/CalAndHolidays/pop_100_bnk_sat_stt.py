import sqlite3
import calendar
from datetime import date

DB_PATH = "/home/dkvlko/live_code/BLOBS/CalAndHolidays/CalAndHolidays.db"

START_YEAR = 2016
END_YEAR = 2126

DESCRIPTION = "Bank Saturday Holiday"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

rows = []

for year in range(START_YEAR, END_YEAR + 1):

    for month in range(1, 13):

        # Get all Saturdays in this month
        saturdays = []

        for day in range(1, calendar.monthrange(year, month)[1] + 1):
            if date(year, month, day).weekday() == 5:  # Saturday
                saturdays.append(day)

        # Second Saturday
        second_saturday = saturdays[1]

        rows.append((
            f"{year:04d}",
            f"{month:02d}",
            f"{second_saturday:02d}",
            "Second Saturday",
            DESCRIPTION
        ))

        # Fourth Saturday
        fourth_saturday = saturdays[3]

        rows.append((
            f"{year:04d}",
            f"{month:02d}",
            f"{fourth_saturday:02d}",
            "Fourth Saturday",
            DESCRIPTION
        ))

cursor.executemany("""
    INSERT INTO Static_Holidays
        (Year, Month, Day, Name, Descr)
    VALUES (?, ?, ?, ?, ?)
""", rows)

conn.commit()

cursor.execute("""
    SELECT COUNT(*)
    FROM Static_Holidays
    WHERE Year BETWEEN ? AND ?
      AND Descr = ?
""", (str(START_YEAR), str(END_YEAR), DESCRIPTION))

count = cursor.fetchone()[0]

conn.close()

print(f"Years populated : {START_YEAR} - {END_YEAR}")
print(f"Rows generated  : {len(rows):,}")
print(f"Rows in database: {count:,}")
print("Bank Saturday holidays populated successfully.")
