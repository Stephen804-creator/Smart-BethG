#!/usr/bin/env python3
"""Trusted-operator CLI for creating or promoting a Smart BethG administrator."""
import getpass
import sys

from database import get_connection, initialize_database
from services.auth_service import create_user


def create_admin():
    username = input("Administrator username: ").strip()
    password = getpass.getpass("Administrator password (min 8 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise ValueError("Passwords do not match.")
    initialize_database()
    user = create_user(username, password)
    if not user:
        raise ValueError("That username already exists. Use promote-admin only if you verified ownership.")
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET role='admin' WHERE id=?", (user["id"],))
        conn.commit()
    finally:
        conn.close()
    print(f"Administrator account created for {username!r} (user id {user['id']}).")


def promote_admin(username):
    initialize_database()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, status FROM users WHERE username=? LIMIT 1",
            (username,),
        ).fetchone()
        if not row:
            raise ValueError("User not found.")
        if row["status"] != "active":
            raise ValueError("Inactive users cannot be promoted.")
        conn.execute("UPDATE users SET role='admin' WHERE id=?", (row["id"],))
        conn.commit()
    finally:
        conn.close()
    print(f"Administrator role granted to existing account {username!r} (user id {row['id']}).")


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "create-admin":
        create_admin()
    elif len(sys.argv) == 3 and sys.argv[1] == "promote-admin":
        if input(f"Type the exact username {sys.argv[2]!r} to confirm promotion: ").strip() != sys.argv[2]:
            raise SystemExit("Username confirmation did not match.")
        promote_admin(sys.argv[2])
    else:
        raise SystemExit(
            "Usage: python scripts/manage_user.py create-admin | "
            "python scripts/manage_user.py promote-admin USERNAME"
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Administrator operation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
