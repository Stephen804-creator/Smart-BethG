"""Owner-scoped artifact storage using the configured storage adapter."""
import hashlib
import re
import uuid

from database import get_connection
from storage.backend import get_storage_backend


class ArtifactService:
    MAX_CONTENT_BYTES = 1024 * 1024

    def __init__(self, storage=None):
        self.storage = storage or get_storage_backend()

    def create(self, user_id, name, content, artifact_type="text", mission_id=None, idempotency_key=None):
        name = (name or "").strip()
        if not name or len(name) > 160:
            raise ValueError("Artifact name must be between 1 and 160 characters.")
        if not isinstance(content, str):
            raise ValueError("Artifact content must be text.")
        encoded = content.encode("utf-8")
        if len(encoded) > self.MAX_CONTENT_BYTES:
            raise ValueError("Artifact content exceeds the 1 MiB limit.")
        artifact_type = (artifact_type or "text").strip().lower()
        if not re.fullmatch(r"[a-z0-9_-]{1,40}", artifact_type):
            raise ValueError("Artifact type must use letters, numbers, underscores, or hyphens.")
        if mission_id is not None and not self._owns_mission(user_id, mission_id):
            raise ValueError("Mission not found for this user.")

        if idempotency_key is not None:
            idempotency_key = str(idempotency_key).strip()
            if not idempotency_key or len(idempotency_key) > 200:
                raise ValueError("Idempotency key must be between 1 and 200 characters.")
            existing = self._get_by_idempotency_key(user_id, idempotency_key)
            if existing:
                return existing

        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120] or "artifact"
        digest = hashlib.sha256(encoded).hexdigest()
        locator_token = (
            hashlib.sha256(f"{idempotency_key}:{digest}".encode("utf-8")).hexdigest()[:32]
            if idempotency_key else uuid.uuid4().hex
        )
        locator = self.storage.put_bytes("artifacts", user_id, f"{locator_token}_{safe_name}.txt", encoded)
        conn = get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO artifacts(mission_id, user_id, name, artifact_type, path, content_type, "
                "size_bytes, checksum_sha256, status, updated_at, idempotency_key) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ready', CURRENT_TIMESTAMP, ?) "
                "ON CONFLICT(user_id, idempotency_key) WHERE idempotency_key IS NOT NULL DO NOTHING RETURNING id",
                (mission_id, user_id, name, artifact_type, locator, "text/plain; charset=utf-8",
                 len(encoded), digest, idempotency_key),
            )
            row = cursor.fetchone()
            if row:
                artifact_id = row["id"]
                conn.commit()
            else:
                conn.rollback()
                existing_row = conn.execute(
                    "SELECT id,path FROM artifacts WHERE user_id=? AND idempotency_key=? LIMIT 1",
                    (user_id, idempotency_key),
                ).fetchone()
                if not existing_row:
                    raise RuntimeError("Artifact idempotency conflict did not resolve to an existing record.")
                artifact_id = existing_row["id"]
                if existing_row["path"] != locator:
                    try:
                        self.storage.delete("artifacts", user_id, locator)
                    except Exception:
                        pass
        except Exception:
            try:
                # If a row already references this deterministic object, leave it intact.
                existing = self._get_by_idempotency_key(user_id, idempotency_key) if idempotency_key else None
                if not existing or existing.get("path") != locator:
                    self.storage.delete("artifacts", user_id, locator)
            except Exception:
                pass
            raise
        finally:
            conn.close()
        return self.get(user_id, artifact_id)

    def _get_by_idempotency_key(self, user_id, idempotency_key):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id, mission_id, user_id, name, artifact_type, path, content_type, size_bytes, "
                "checksum_sha256, status, created_at, updated_at FROM artifacts "
                "WHERE user_id=? AND idempotency_key=? LIMIT 1",
                (user_id, idempotency_key),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_for_user(self, user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, mission_id, user_id, name, artifact_type, content_type, size_bytes, "
                "checksum_sha256, status, created_at, updated_at FROM artifacts "
                "WHERE user_id=? ORDER BY created_at DESC, id DESC", (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get(self, user_id, artifact_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id, mission_id, user_id, name, artifact_type, path, content_type, size_bytes, "
                "checksum_sha256, status, created_at, updated_at FROM artifacts "
                "WHERE id=? AND user_id=? LIMIT 1", (artifact_id, user_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def read_content(self, user_id, artifact_id):
        record = self.get(user_id, artifact_id)
        if not record:
            return None, None
        try:
            content = self.storage.get_bytes("artifacts", user_id, record["path"])
        except Exception:
            return None, record
        if len(content) > self.MAX_CONTENT_BYTES:
            raise ValueError("Stored artifact exceeds the configured read limit.")
        return content.decode("utf-8"), record

    def delete(self, user_id, artifact_id):
        record = self.get(user_id, artifact_id)
        if not record:
            return False
        conn = get_connection()
        try:
            cursor = conn.execute("DELETE FROM artifacts WHERE id=? AND user_id=?", (artifact_id, user_id))
            conn.commit()
            deleted = cursor.rowcount == 1
        finally:
            conn.close()
        if deleted:
            try:
                self.storage.delete("artifacts", user_id, record["path"])
            except Exception:
                # The row is gone; an orphan is safer than exposing a live broken reference.
                pass
        return deleted

    @staticmethod
    def _owns_mission(user_id, mission_id):
        conn = get_connection()
        try:
            return conn.execute(
                "SELECT id FROM missions WHERE id=? AND user_id=? LIMIT 1", (mission_id, user_id)
            ).fetchone() is not None
        finally:
            conn.close()
