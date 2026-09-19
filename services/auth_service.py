from werkzeug.security import check_password_hash, generate_password_hash

from database import get_connection


def authenticate_user(username, password):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, password_hash, status FROM users WHERE username=? LIMIT 1",
            (username,),
        ).fetchone()
        if not row or row["status"] != "active" or not check_password_hash(row["password_hash"], password):
            return None
        return {"id": row["id"], "username": row["username"]}
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, status FROM users WHERE id=? LIMIT 1", (user_id,)
        ).fetchone()
        return {"id": row["id"], "username": row["username"]} if row and row["status"] == "active" else None
    finally:
        conn.close()


def create_user(username, password):
    """Create a new user with a securely hashed password.

    Returns the created user dict, or None if the username is already taken.
    """
    username = (username or "").strip()
    if not username or not password or len(password) < 8:
        raise ValueError("Username is required and password must be at least 8 characters.")

    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE username=? LIMIT 1", (username,)
        ).fetchone()
        if existing:
            return None
        cur = conn.execute(
            "INSERT INTO users(username, password_hash, status) VALUES (?, ?, 'active')",
            (username, generate_password_hash(password)),
        )
        conn.commit()
        return {"id": cur.lastrowid, "username": username}
    finally:
        conn.close()
