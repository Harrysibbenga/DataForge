# check_user_data.py
import sqlite3
import sys
import os

# Connect to the SQLite database
conn = sqlite3.connect('dataforge.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get the email to search for
email = input("Enter user email to check: ")

# Query user data
cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
user = cursor.fetchone()

if not user:
    print(f"No user found with email: {email}")
    sys.exit(1)

print("\n=== USER INFO ===")
print(f"ID: {user['id']}")
print(f"Email: {user['email']}")
print(f"Full Name: {user['full_name']}")
print(f"Is Active: {user['is_active']}")
print(f"Is Verified: {user['is_verified']}")
print(f"Created At: {user['created_at']}")

# Query subscription data
cursor.execute("SELECT * FROM subscriptions WHERE user_id = ?", (user['id'],))
subscription = cursor.fetchone()

if not subscription:
    print("\nNo subscription found for this user!")
else:
    print("\n=== SUBSCRIPTION INFO ===")
    print(f"Plan: {subscription['plan']}")
    print(f"Is Active: {subscription['is_active']}")
    print(f"Conversion Count: {subscription['conversion_count']}")
    print(f"Conversion Limit: {subscription['conversion_limit']}")
    print(f"File Size Limit: {subscription['file_size_limit_mb']} MB")

conn.close()