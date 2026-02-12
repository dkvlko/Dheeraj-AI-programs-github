import sqlite3
from datetime import datetime

DB_PATH = "activities.db"


def get_table_names(conn):
    """
    Return a list of all user tables in the SQLite database.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    rows = cur.fetchall()
    return [r[0] for r in rows]


def choose_table(tables):
    """
    Ask the user to pick a table from the list.
    """
    print("Available tables in database 'activities':")
    for idx, name in enumerate(tables, start=1):
        print(f"{idx}. {name}")

    while True:
        choice = input("Enter the number of the table you want to view: ").strip()
        if not choice.isdigit():
            print("Please enter a valid number.")
            continue

        idx = int(choice)
        if 1 <= idx <= len(tables):
            return tables[idx - 1]
        else:
            print("Number out of range. Try again.")


def ask_limit():
    """
    Ask how many entries the user wishes to see.
    """
    while True:
        text = input("How many entries do you wish to see? ").strip()
        if not text.isdigit():
            print("Please enter a positive integer.")
            continue

        n = int(text)
        if n <= 0:
            print("Number must be greater than 0.")
            continue
        return n


def show_entries(conn, table_name, limit):
    """
    Query and display entries from the chosen table.
    Sorted by DateTime DESC, limited by 'limit'.
    """
    cur = conn.cursor()

    query = f"""
        SELECT SerialNumber, Activity, DateTime
        FROM {table_name}
        ORDER BY DateTime DESC
        LIMIT ?
    """

    try:
        cur.execute(query, (limit,))
        rows = cur.fetchall()
    except sqlite3.Error as e:
        print(f"Error querying table '{table_name}': {e}")
        return

    if not rows:
        print(f"\nNo entries found in table '{table_name}'.\n")
        return

    print(f"\nShowing up to {limit} entries from '{table_name}' "
          f"sorted by DateTime (descending):\n")

    # Simple table-like output
    print(f"{'SerialNumber':>11}  {'Activity':<10}  {'DateTime'}")
    print("-" * 50)
    for serial, activity, dt in rows:
        print(f"{serial:>11}  {activity:<10}  {dt}")
    print()


def main():
    try:
        conn = sqlite3.connect(DB_PATH)
    except sqlite3.Error as e:
        print(f"Could not connect to database '{DB_PATH}': {e}")
        return

    with conn:
        tables = get_table_names(conn)
        if not tables:
            print("No user tables found in this database.")
            return

        table_name = choose_table(tables)
        limit = ask_limit()
        show_entries(conn, table_name, limit)


if __name__ == "__main__":
    main()
