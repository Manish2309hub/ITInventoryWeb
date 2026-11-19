
import sqlite3
from database import DB_PATH

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON")

# Sample branches
branches = [
    ("Head Office", "HO"),
    ("Branch 01", "BR01"),
    ("Branch 02", "BR02")
]

# IT device categories
categories = [
    ("Desktop",),
    ("Laptop",),
    ("Printer",),
    ("Scanner",),
    ("Server",),
    ("Network Switch",),
    ("Router",),
    ("Firewall",),
    ("UPS",)
]

conn.executemany("""
    INSERT OR IGNORE INTO branches
    (branch_name, branch_code)
    VALUES (?, ?)
""", branches)

conn.executemany("""
    INSERT OR IGNORE INTO asset_categories
    (category_name)
    VALUES (?)
""", categories)

conn.commit()
conn.close()

print("Branch and Category Masters Created Successfully!")
