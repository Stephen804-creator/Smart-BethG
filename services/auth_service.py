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
        if not row or row["status"] != "active" or not row["password_hash"] or not check_password_hash(row["password_hash"], password):
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
    if len(username) > 254 or len(password) > 1024:
        raise ValueError("Username or password exceeds the configured length limit.")

    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO users(username, password_hash, status, role) "
            "VALUES (?, ?, 'active', 'user') ON CONFLICT(username) DO NOTHING RETURNING id",
            (username, generate_password_hash(password)),
        )
        created = cur.fetchone()
        if not created:
            conn.rollback()
            return None
        conn.commit()
        return {"id": created["id"], "username": username, "role": "user"}
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
    email = (email or "").strip().lower()
    if not email:
        raise ValueError("Google did not return an email address for this account.")

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, status, role FROM users WHERE oauth_provider=? AND oauth_subject=? AND status='active' LIMIT 1",
            (provider, subject),
        ).fetchone()
        if row:
            return {"id": row["id"], "username": row["username"], "role": row["role"]}

        row = conn.execute(
            "SELECT id, username, status, role, oauth_provider, oauth_subject "
            "FROM users WHERE LOWER(username)=? LIMIT 1",
            (email,),
        ).fetchone()
        if row:
            if row["status"] != "active":
                raise PermissionError("This account is inactive.")
            if row["oauth_provider"] and (
                row["oauth_provider"] != provider or row["oauth_subject"] != subject
            ):
                raise PermissionError("This account is already linked to a different external identity.")
            if not row["oauth_provider"]:
                linked = conn.execute(
                    "UPDATE users SET oauth_provider=?, oauth_subject=? "
                    "WHERE id=? AND oauth_provider IS NULL AND oauth_subject IS NULL",
                    (provider, subject, row["id"]),
                )
                if linked.rowcount == 1:
                    conn.commit()
                    return {"id": row["id"], "username": row["username"], "role": row["role"]}
                conn.rollback()
                # Another callback may have linked this account concurrently.
                refreshed = conn.execute(
                    "SELECT id, username, status, role, oauth_provider, oauth_subject "
                    "FROM users WHERE id=? LIMIT 1",
                    (row["id"],),
                ).fetchone()
                if (
                    not refreshed or refreshed["status"] != "active"
                    or refreshed["oauth_provider"] != provider
                    or refreshed["oauth_subject"] != subject
                ):
                    raise PermissionError("This account was linked to a different external identity.")
                return {"id": refreshed["id"], "username": refreshed["username"], "role": refreshed["role"]}
            return {"id": row["id"], "username": row["username"], "role": row["role"]}

        if not allow_create:
            raise PermissionError("Registration is closed. Sign in with an existing linked account or use password login.")

        placeholder_hash = generate_password_hash(secrets.token_urlsafe(32))
        cur = conn.execute(
            "INSERT INTO users(username, password_hash, status, role, oauth_provider, oauth_subject) "
            "VALUES (?, ?, 'active', 'user', ?, ?) "
            "ON CONFLICT DO NOTHING RETURNING id",
            (email, placeholder_hash, provider, subject),
        )
        created = cur.fetchone()
        if created:
            conn.commit()
            return {"id": created["id"], "username": email, "role": "user"}
        conn.rollback()
        # A concurrent callback may have created or linked this identity.
        row = conn.execute(
            "SELECT id, username, status, role FROM users "
            "WHERE oauth_provider=? AND oauth_subject=? AND status='active' LIMIT 1",
            (provider, subject),
        ).fetchone()
        if row:
            return {"id": row["id"], "username": row["username"], "role": row["role"]}
        raise PermissionError("An account with this email already exists. Sign in and link the account first.")
    finally:
        conn.close()
