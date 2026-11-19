
import sqlite3
from getpass import getpass
from werkzeug.security import generate_password_hash
from database import DB_PATH

username = input("Administrator username: ").strip()
full_name = input("Administrator full name: ").strip()
password = getpass("Administrator password: ")

if not username or not full_name or len(password) < 12:
    print("Username and full name are required.")
    print("Password must contain at least 12 characters.")
    raise SystemExit(1)

conn = sqlite3.connect(DB_PATH)

try:
    conn.execute("""
        INSERT INTO users
        (username, password_hash, full_name, role)
        VALUES (?, ?, ?, ?)
    """, (
        username,
        generate_password_hash(password),
        full_name,
        "Admin"
    ))
    conn.commit()
    print("Administrator account created successfully!")
except sqlite3.IntegrityError:
    print("Username already exists.")
finally:
    conn.close()
