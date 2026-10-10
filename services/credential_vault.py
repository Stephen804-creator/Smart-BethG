"""Encrypted database-backed credential vault for third-party connector tokens.

The database stores ciphertext only. Keep SMART_BETHG_TOKEN_ENCRYPTION_KEY in
a deployment secret manager or workload environment, never in source control.
The vault reference, not the token, is stored on connector-account records.
"""
import json
import os
import uuid

from cryptography.fernet import Fernet, InvalidToken

from database import get_connection


class CredentialVaultError(RuntimeError):
    pass


class CredentialVault:
    def __init__(self, key=None):
        raw = key or os.getenv("SMART_BETHG_TOKEN_ENCRYPTION_KEY", "")
        if not raw:
            raise CredentialVaultError("Connector token encryption key is not configured.")
        try:
            self._fernet = Fernet(raw.encode("ascii") if isinstance(raw, str) else raw)
        except (ValueError, TypeError, UnicodeEncodeError) as exc:
            raise CredentialVaultError("Connector token encryption key must be a valid Fernet key.") from exc

    def store(self, user_id, provider, access_token, *, scopes=None, expires_at=None, connection=None):
        if not isinstance(access_token, str) or not access_token.strip():
            raise ValueError("Cannot store an empty connector token.")
        provider = (provider or "").strip().lower()
        if not provider or len(provider) > 80:
            raise ValueError("Invalid connector provider.")
        credential_id = uuid.uuid4().hex
        encrypted = self._fernet.encrypt(access_token.encode("utf-8")).decode("ascii")
        owns_connection = connection is None
        conn = connection or get_connection()
        try:
            conn.execute(
                "INSERT INTO connector_credentials(id, user_id, provider, encrypted_access_token, "
                "scopes_json, expires_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (credential_id, user_id, provider, encrypted, json.dumps(scopes or []), expires_at),
            )
            if owns_connection:
                conn.commit()
        finally:
            if owns_connection:
                conn.close()
        return "vault:" + credential_id

    def resolve(self, reference, user_id, provider):
        if not isinstance(reference, str) or not reference.startswith("vault:"):
            raise CredentialVaultError("Invalid credential reference.")
        credential_id = reference[6:]
        if not credential_id or len(credential_id) > 80:
            raise CredentialVaultError("Invalid credential reference.")
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT encrypted_access_token FROM connector_credentials "
                "WHERE id=? AND user_id=? AND provider=? AND revoked_at IS NULL LIMIT 1",
                (credential_id, user_id, (provider or "").strip().lower()),
            ).fetchone()
        finally:
            conn.close()
        if not row or not row["encrypted_access_token"]:
            raise CredentialVaultError("Connector credential is unavailable or revoked.")
        try:
            return self._fernet.decrypt(row["encrypted_access_token"].encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as exc:
            raise CredentialVaultError("Connector credential could not be decrypted.") from exc

    def revoke(self, reference, user_id, provider):
        if not isinstance(reference, str) or not reference.startswith("vault:"):
            return False
        conn = get_connection()
        try:
            cursor = conn.execute(
                "UPDATE connector_credentials SET revoked_at=CURRENT_TIMESTAMP, "
                "encrypted_access_token='', updated_at=CURRENT_TIMESTAMP "
                "WHERE id=? AND user_id=? AND provider=? AND revoked_at IS NULL",
                (reference[6:], user_id, (provider or "").strip().lower()),
            )
            conn.commit()
            return cursor.rowcount == 1
        finally:
            conn.close()
