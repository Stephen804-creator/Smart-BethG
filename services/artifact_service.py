"""Owner-scoped artifact storage with content integrity and pluggable backends."""
import hashlib
import json
import re
import uuid

from database import get_connection
from services.artifact_storage import get_artifact_storage


class ArtifactService:
    MAX_CONTENT_BYTES = 1024 * 1024
    TYPES = {
        "text": (".txt", "text/plain; charset=utf-8"),
        "markdown": (".md", "text/markdown; charset=utf-8"),
        "json": (".json", "application/json; charset=utf-8"),
        "python": (".py", "text/plain; charset=utf-8"),
        "javascript": (".js", "text/plain; charset=utf-8"),
        "html": (".html", "text/html; charset=utf-8"),
        "csv": (".csv", "text/csv; charset=utf-8"),
        "yaml": (".yaml", "text/plain; charset=utf-8"),
    }

    def create(self, user_id, name, content, artifact_type="text", mission_id=None):
        name = (name or "").strip()
        if not name or len(name) > 160:
            raise ValueError("Artifact name must be between 1 and 160 characters.")
        if not isinstance(content, str):
            raise ValueError("Artifact content must be text.")
        encoded = content.encode("utf-8")
        if len(encoded) > self.MAX_CONTENT_BYTES:
            raise ValueError("Artifact content exceeds the 1 MiB limit.")
        artifact_type = (artifact_type or "text").strip().lower()
        if artifact_type not in self.TYPES:
            raise ValueError("Unsupported artifact type.")
        if artifact_type == "json":
            try:
                json.loads(content)
            except json.JSONDecodeError as exc:
                raise ValueError("JSON artifacts must contain valid JSON.") from exc
        if mission_id is not None and not self._owns_mission(user_id, mission_id):
            raise ValueError("Mission not found for this user.")

        extension, content_type = self.TYPES[artifact_type]
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120] or "artifact"
        key = f"{user_id}/{uuid.uuid4().hex}_{safe_name}{extension}"
        digest = hashlib.sha256(encoded).hexdigest()
        storage = get_artifact_storage()
        storage.put(key, encoded)

        conn = get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO artifacts(mission_id, user_id, name, artifact_type, path, content_type, "
                "size_bytes, checksum_sha256, status, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ready', CURRENT_TIMESTAMP)",
                (mission_id, user_id, name, artifact_type, key, content_type, len(encoded), digest),
            )
            artifact_id = cursor.lastrowid
            conn.commit()
        except Exception:
            try:
                storage.delete(key)
            except Exception:
                pass
            raise
        finally:
            conn.close()
        return self.get(user_id, artifact_id)

    def list_for_user(self, user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, mission_id, user_id, name, artifact_type, content_type, size_bytes, "
                "checksum_sha256, status, created_at, updated_at FROM artifacts "
                "WHERE user_id=? ORDER BY created_at DESC, id DESC",
                (user_id,),
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
                "WHERE id=? AND user_id=? LIMIT 1",
                (artifact_id, user_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def read_content(self, user_id, artifact_id):
        record = self.get(user_id, artifact_id)
        if not record:
            return None, None
        key = record["path"]
        if not isinstance(key, str) or not key.startswith(f"{user_id}/") or ".." in key.split("/"):
            return None, record
        storage = get_artifact_storage()
        try:
            encoded = storage.get(key)
        except FileNotFoundError:
            return None, record
        if len(encoded) > self.MAX_CONTENT_BYTES:
            raise ValueError("Stored artifact exceeds the configured read limit.")
        digest = hashlib.sha256(encoded).hexdigest()
        if not record.get("checksum_sha256") or digest != record["checksum_sha256"]:
            raise ValueError("Stored artifact failed its integrity check.")
        try:
            return encoded.decode("utf-8"), record
        except UnicodeDecodeError as exc:
            raise ValueError("Stored artifact is not valid UTF-8 text.") from exc

    def delete(self, user_id, artifact_id):
        record = self.get(user_id, artifact_id)
        if not record:
            return False
        conn = get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM artifacts WHERE id=? AND user_id=?",
                (artifact_id, user_id),
            )
            conn.commit()
            deleted = cursor.rowcount == 1
        finally:
            conn.close()
        if deleted:
            key = record.get("path", "")
            if isinstance(key, str) and key.startswith(f"{user_id}/") and ".." not in key.split("/"):
                try:
                    get_artifact_storage().delete(key)
                except Exception:
                    # DB row is gone; an orphan object is safer than an exposed
                    # artifact row. A future orphan-cleanup job can retry.
                    pass
        return deleted

    @staticmethod
    def _owns_mission(user_id, mission_id):
        conn = get_connection()
        try:
            return conn.execute(
                "SELECT id FROM missions WHERE id=? AND user_id=? LIMIT 1",
                (mission_id, user_id),
            ).fetchone() is not None
        finally:
            conn.close()
