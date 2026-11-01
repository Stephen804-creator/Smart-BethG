from werkzeug.security import check_password_hash, generate_password_hash
import secrets

import config
from database import get_connection


def authenticate_user(username, password):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, password_hash, status, role, session_version FROM users WHERE username=? LIMIT 1",
            (username,),
        ).fetchone()
        if not row or row["status"] != "active" or not row["password_hash"] or not check_password_hash(row["password_hash"], password):
            return None
        return {"id": row["id"], "username": row["username"], "role": row["role"], "session_version": row["session_version"]}
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, status, role, session_version FROM users WHERE id=? LIMIT 1", (user_id,)
        ).fetchone()
        return {"id": row["id"], "username": row["username"], "role": row["role"], "session_version": row["session_version"]} if row and row["status"] == "active" else None
    finally:
        conn.close()


def revoke_user_sessions(user_id):
    """Invalidate all previously issued signed cookies for this user."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "UPDATE users SET session_version=session_version+1 WHERE id=? AND status='active'",
            (user_id,),
        )
        conn.commit()
        return cursor.rowcount == 1
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def record_policy_acceptance(
    user_id,
    *,
    accepted_terms,
    accepted_privacy,
    age_verified,
    terms_version=None,
    privacy_version=None,
):
    """Persist the current accepted policy versions and age confirmation for a user."""
    if user_id is None:
        raise ValueError("A user id is required.")
    if not accepted_terms or not accepted_privacy or not age_verified:
        raise ValueError("All required consent options must be accepted.")

    terms_version = (terms_version or config.TERMS_OF_SERVICE_VERSION).strip()
    privacy_version = (privacy_version or config.PRIVACY_POLICY_VERSION).strip()
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO user_policy_acceptance(
                user_id,
                accepted_terms_version,
                accepted_privacy_version,
                age_verified,
                accepted_at
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                accepted_terms_version = EXCLUDED.accepted_terms_version,
                accepted_privacy_version = EXCLUDED.accepted_privacy_version,
                age_verified = EXCLUDED.age_verified,
                accepted_at = CURRENT_TIMESTAMP
            """,
            (user_id, terms_version, privacy_version, bool(age_verified)),
        )
        conn.commit()
        return {
            "user_id": user_id,
            "accepted_terms_version": terms_version,
            "accepted_privacy_version": privacy_version,
            "age_verified": bool(age_verified),
        }
    finally:
        conn.close()


def user_policy_is_current(
    user_id,
    *,
    terms_version=None,
    privacy_version=None,
    minimum_age=None,
):
    """Return True only when the user has accepted the current policy versions and age check."""
    if user_id is None:
        return False

    terms_version = (terms_version or config.TERMS_OF_SERVICE_VERSION).strip()
    privacy_version = (privacy_version or config.PRIVACY_POLICY_VERSION).strip()
    minimum_age = config.MINIMUM_ACCOUNT_AGE if minimum_age is None else int(minimum_age)

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT accepted_terms_version, accepted_privacy_version, age_verified FROM user_policy_acceptance WHERE user_id=? LIMIT 1",
            (user_id,),
        ).fetchone()
        if not row:
            return False
        if row["accepted_terms_version"] != terms_version:
            return False
        if row["accepted_privacy_version"] != privacy_version:
            return False
        if not bool(row["age_verified"]):
            return False
        return minimum_age <= config.MINIMUM_ACCOUNT_AGE
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


__all__ = [
    "authenticate_user",
    "get_user_by_id",
    "revoke_user_sessions",
    "create_user",
    "find_or_create_oauth_user",
    "record_policy_acceptance",
    "user_policy_is_current",
]

