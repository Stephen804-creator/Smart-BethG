"""Encrypted per-installation provider credentials stored in PostgreSQL.
Use a stable, deployment-managed SMART_BETHG_SECRET_KEY; rotating it requires
an explicit credential re-encryption migration rather than silent data loss.
"""
import base64
import hashlib
import json
from cryptography.fernet import Fernet, InvalidToken
import config
from database import get_connection

def _fernet():
    key = base64.urlsafe_b64encode(hashlib.sha256(config.SECRET_KEY.encode("utf-8")).digest())
    return Fernet(key)

class ConnectorSecretStore:
    def put(self, installation_id, credentials, provider_account=None, scopes=None, expires_at=None):
        if not isinstance(credentials, dict) or not credentials.get("access_token"):
            raise ValueError("A provider access token is required.")
        encrypted = _fernet().encrypt(json.dumps(credentials, separators=(",", ":")).encode()).decode()
        conn = get_connection()
        try:
            conn.execute("""INSERT INTO connector_credentials
                (installation_id, encrypted_payload, provider_account, scopes_json, expires_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(installation_id) DO UPDATE SET encrypted_payload=excluded.encrypted_payload,
                provider_account=excluded.provider_account, scopes_json=excluded.scopes_json,
                expires_at=excluded.expires_at, updated_at=CURRENT_TIMESTAMP""",
                (installation_id, encrypted, (provider_account or "")[:255], json.dumps(scopes or []), expires_at))
            conn.commit()
        finally:
            conn.close()

    def get(self, installation_id):
        conn = get_connection()
        try:
            row = conn.execute("SELECT encrypted_payload, provider_account, scopes_json, expires_at FROM connector_credentials WHERE installation_id=?",
                               (installation_id,)).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        try:
            credentials = json.loads(_fernet().decrypt(row["encrypted_payload"].encode()).decode())
            scopes = json.loads(row["scopes_json"] or "[]")
        except (InvalidToken, ValueError, TypeError, json.JSONDecodeError):
            raise RuntimeError("Connector credentials cannot be decrypted; check SMART_BETHG_SECRET_KEY.")
        return {"credentials": credentials, "provider_account": row["provider_account"],
                "scopes": scopes, "expires_at": row["expires_at"]}

    def delete(self, installation_id):
        conn = get_connection()
        try:
            conn.execute("DELETE FROM connector_credentials WHERE installation_id=?", (installation_id,))
            conn.commit()
        finally:
            conn.close()
