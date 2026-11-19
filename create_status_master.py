
import sqlite3
from database import DB_PATH

def create_status_master():

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create Asset Status Master table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS asset_statuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status_name TEXT NOT NULL UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1
        )
    """)

    # Default asset statuses
    statuses = [
        "Active",
        "In Stock",
        "Under Repair",
        "Transferred",
        "Condemned",
        "Disposed"
    ]

    for status in statuses:
        cursor.execute("""
            INSERT OR IGNORE INTO asset_statuses
            (status_name, is_active)
            VALUES (?, 1)
        """, (status,))

    conn.commit()

    print("Asset Status Master Created Successfully!")

    # Display saved statuses
    cursor.execute("""
        SELECT id, status_name, is_active
        FROM asset_statuses
        ORDER BY id
    """)

    for row in cursor.fetchall():
        print(row)

    conn.close()


if __name__ == "__main__":
    create_status_master()
