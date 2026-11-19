
import sqlite3
from pathlib import Path

# Database file location
DB_PATH = Path(__file__).resolve().parent / "inventory.db"

# Connect to SQLite database
conn = sqlite3.connect(DB_PATH)

# Enable foreign key support
conn.execute("PRAGMA foreign_keys = ON")

cursor = conn.cursor()

# Branch master table
cursor.execute("""
CREATE TABLE IF NOT EXISTS branches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_name TEXT NOT NULL UNIQUE,
    branch_code TEXT NOT NULL UNIQUE
)
""")

# Asset category master table
cursor.execute("""
CREATE TABLE IF NOT EXISTS asset_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name TEXT NOT NULL UNIQUE
)
""")

# Main IT asset register
cursor.execute("""
CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_code TEXT NOT NULL UNIQUE,
    asset_name TEXT NOT NULL,
    serial_number TEXT UNIQUE,
    brand TEXT,
    model TEXT,
    category_id INTEGER NOT NULL,
    branch_id INTEGER NOT NULL,
    purchase_date TEXT,
    warranty_expiry TEXT,
    status TEXT NOT NULL DEFAULT 'Active',
    FOREIGN KEY (category_id)
        REFERENCES asset_categories(id),
    FOREIGN KEY (branch_id)
        REFERENCES branches(id)
)
""")

# Users table
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL
        CHECK(role IN ('Admin', 'IT Staff')),
    is_active INTEGER NOT NULL DEFAULT 1
        CHECK(is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
""")

# Save database changes
conn.commit()

# Close database connection
conn.close()

print("IT Inventory Database Created Successfully!")
