from werkzeug.security import check_password_hash, generate_password_hash
import secrets

from database import get_connection


def authenticate_user(username, password):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, password_hash, status, role FROM users WHERE username=? LIMIT 1",
            (username,),
        ).fetchone()
        if not row or row["status"] != "active" or not check_password_hash(row["password_hash"], password):
            return None
        return {"id": row["id"], "username": row["username"], "role": row["role"]}
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, status, role FROM users WHERE id=? LIMIT 1", (user_id,)
        ).fetchone()
        return {"id": row["id"], "username": row["username"], "role": row["role"]} if row and row["status"] == "active" else None
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
            "INSERT INTO users(username, password_hash, status, role) VALUES (?, ?, 'active', 'user')",
            (username, generate_password_hash(password)),
        )
        conn.commit()
        return {"id": cur.lastrowid, "username": username, "role": "user"}
    finally:
        conn.close()


def find_or_create_oauth_user(email, provider, subject, allow_create=False):
    """
    Look up a user by (oauth_provider, oauth_subject) first - the stable
    identifier Google gives us - and fall back to matching by email for
    an account that already exists. If neither matches, create a new
    account. OAuth-created accounts still get a real (random, unusable)
    password hash so the schema's NOT NULL constraint is satisfied even
    on a database created before oauth support existed; that password is
    never generated to be shared with the user and password login for
    that account will simply always fail, which is correct since they
    signed up via Google.
    """
    email = (email or "").strip()
    if not email:
        raise ValueError("Google did not return an email address for this account.")

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, status, role FROM users WHERE oauth_provider=? AND oauth_subject=? LIMIT 1",
            (provider, subject),
        ).fetchone()
        if row:
            return {"id": row["id"], "username": row["username"], "role": row["role"]}

        row = conn.execute(
            "SELECT id, username, status, role, oauth_provider FROM users WHERE username=? LIMIT 1",
            (email,),
        ).fetchone()
        if row:
            if not row["oauth_provider"]:
                conn.execute(
                    "UPDATE users SET oauth_provider=?, oauth_subject=? WHERE id=?",
                    (provider, subject, row["id"]),
                )
                conn.commit()
            return {"id": row["id"], "username": row["username"], "role": row["role"]}

        if not allow_create:
            raise PermissionError("Registration is closed. Sign in with an existing linked account or use password login.")

        placeholder_hash = generate_password_hash(secrets.token_urlsafe(32))
        cur = conn.execute(
            "INSERT INTO users(username, password_hash, status, role, oauth_provider, oauth_subject) "
            "VALUES (?, ?, 'active', 'user', ?, ?)",
            (email, placeholder_hash, provider, subject),
        )
        conn.commit()
        return {"id": cur.lastrowid, "username": email, "role": "user"}
    finally:
        conn.close()
