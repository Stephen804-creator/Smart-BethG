"""Owner-scoped artifact storage with content integrity and pluggable backends."""
import hashlib
import json
import os
import re
import uuid
from pathlib import Path

import config

from database import get_connection
from services.artifact_storage import get_artifact_storage


class ArtifactService:
    MAX_CONTENT_BYTES = 1024 * 1024
    MAX_BINARY_BYTES = 25 * 1024 * 1024
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
    SOURCE_TYPES = {
        "user_created", "upload", "campaign", "mission", "research",
        "provider_generation", "tool_execution", "export",
    }
    BINARY_TYPES = {
        "image/png": (".png", "image/png"),
        "image/jpeg": (".jpg", "image/jpeg"),
        "image/webp": (".webp", "image/webp"),
        "application/pdf": (".pdf", "application/pdf"),
        "video/mp4": (".mp4", "video/mp4"),
        "audio/mpeg": (".mp3", "audio/mpeg"),
        "audio/wav": (".wav", "audio/wav"),
        "application/zip": (".zip", "application/zip"),
        "application/octet-stream": (".bin", "application/octet-stream"),
    }

    @classmethod
    def _prepare_provenance(cls, source_type, source_id, provider, model, metadata):
        source_type = (source_type or "user_created").strip().lower()
        if source_type not in cls.SOURCE_TYPES:
            raise ValueError("Unsupported artifact source type.")
        source_id = None if source_id is None else str(source_id).strip()
        if source_id is not None and (not source_id or len(source_id) > 160):
            raise ValueError("Artifact source ID must be between 1 and 160 characters.")
        provider = (provider or "").strip() or None
        model = (model or "").strip() or None
        if provider and len(provider) > 120:
            raise ValueError("Artifact provider name is too long.")
        if model and len(model) > 160:
            raise ValueError("Artifact model name is too long.")
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            raise ValueError("Artifact metadata must be a JSON object.")
        try:
            metadata_json = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Artifact metadata must contain JSON-compatible values.") from exc
        if len(metadata_json.encode("utf-8")) > 16 * 1024:
            raise ValueError("Artifact metadata exceeds the 16 KiB limit.")
        return source_type, source_id, provider, model, metadata_json

    def create(
        self, user_id, name, content, artifact_type="text", mission_id=None, *,
        source_type="user_created", source_id=None, provider=None, model=None, metadata=None,
    ):
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
        if mission_id is not None and source_type == "user_created":
            source_type, source_id = "mission", str(mission_id)
        provenance = self._prepare_provenance(source_type, source_id, provider, model, metadata)

        extension, content_type = self.TYPES[artifact_type]
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120] or "artifact"
        key = f"{user_id}/{uuid.uuid4().hex}_{safe_name}{extension}"
        digest = hashlib.sha256(encoded).hexdigest()
        storage = get_artifact_storage()
        storage.put(key, encoded)

        conn = None
        try:
            conn = get_connection()
            cursor = conn.execute(
                "INSERT INTO artifacts(mission_id, user_id, name, artifact_type, path, content_type, "
                "size_bytes, checksum_sha256, source_type, source_id, provider, model, metadata_json, "
                "status, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', CURRENT_TIMESTAMP)",
                (mission_id, user_id, name, artifact_type, key, content_type, len(encoded), digest, *provenance),
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
            if conn is not None:
                conn.close()
        return self.get(user_id, artifact_id)

    @staticmethod
    def _validate_binary_signature(content, content_type):
        valid = True
        if content_type == "image/png":
            valid = content.startswith(b"\x89PNG\r\n\x1a\n")
        elif content_type == "image/jpeg":
            valid = content.startswith(b"\xff\xd8\xff")
        elif content_type == "image/webp":
            valid = len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
        elif content_type == "application/pdf":
            valid = content.startswith(b"%PDF-")
        elif content_type == "application/zip":
            valid = content.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))
        elif content_type == "audio/wav":
            valid = len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WAVE"
        elif content_type == "audio/mpeg":
            valid = content.startswith(b"ID3") or (
                len(content) >= 2 and content[0] == 0xFF and (content[1] & 0xE0) == 0xE0
            )
        elif content_type == "video/mp4":
            valid = len(content) >= 12 and content[4:8] == b"ftyp"
        if not valid:
            raise ValueError("Binary content does not match its declared media type.")

    def create_bytes(
        self, user_id, name, content, content_type, mission_id=None, *,
        source_type="upload", source_id=None, provider=None, model=None, metadata=None,
    ):
        """Store a bounded binary output (image, audio, video, PDF, or archive)."""
        name = (name or "").strip()
        if not name or len(name) > 160:
            raise ValueError("Artifact name must be between 1 and 160 characters.")
        if not isinstance(content, (bytes, bytearray, memoryview)):
            raise ValueError("Binary artifact content must be bytes.")
        encoded = bytes(content)
        if not encoded:
            raise ValueError("Binary artifact content cannot be empty.")
        if len(encoded) > self.MAX_BINARY_BYTES:
            raise ValueError("Binary artifact exceeds the 25 MiB limit.")
        supplied_type = (content_type or "application/octet-stream").split(";", 1)[0].strip().lower()
        extension, safe_type = self.BINARY_TYPES.get(
            supplied_type, self.BINARY_TYPES["application/octet-stream"]
        )
        self._validate_binary_signature(encoded, safe_type)
        if mission_id is not None and not self._owns_mission(user_id, mission_id):
            raise ValueError("Mission not found for this user.")
        provenance = self._prepare_provenance(source_type, source_id, provider, model, metadata)

        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120] or "artifact"
        if not safe_name.lower().endswith(extension):
            safe_name += extension
        key = f"{user_id}/{uuid.uuid4().hex}_{safe_name}"
        digest = hashlib.sha256(encoded).hexdigest()
        storage = get_artifact_storage()
        storage.put(key, encoded)

        conn = None
        try:
            conn = get_connection()
            cursor = conn.execute(
                "INSERT INTO artifacts(mission_id, user_id, name, artifact_type, path, content_type, "
                "size_bytes, checksum_sha256, source_type, source_id, provider, model, metadata_json, "
                "status, updated_at) VALUES (?, ?, ?, 'binary', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', CURRENT_TIMESTAMP)",
                (mission_id, user_id, safe_name, key, safe_type, len(encoded), digest, *provenance),
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
            if conn is not None:
                conn.close()
        return self.get(user_id, artifact_id)

    def read_bytes(self, user_id, artifact_id):
        """Return verified bytes for download without assuming UTF-8 text."""
        record = self.get(user_id, artifact_id)
        if not record:
            return None, None
        encoded = self._read_encoded(user_id, record)
        if encoded is None:
            return None, record
        return encoded, record

    def _read_encoded(self, user_id, record):
        key = record.get("path")
        if not isinstance(key, str) or ".." in key.split("/"):
            return None
        limit = self.MAX_BINARY_BYTES if record.get("artifact_type") == "binary" else self.MAX_CONTENT_BYTES
        if os.path.isabs(key):
            root = Path(config.STORAGE_DIRS["artifacts"], str(user_id)).resolve()
            legacy_path = Path(key).resolve()
            if os.getenv("SMART_BETHG_OBJECT_STORAGE_BACKEND", "local").lower() != "local" or root not in legacy_path.parents:
                return None
            if not legacy_path.is_file():
                return None
            if legacy_path.stat().st_size > limit:
                raise ValueError("Stored artifact exceeds the configured read limit.")
            encoded = legacy_path.read_bytes()
        else:
            if not key.startswith(f"{user_id}/"):
                return None
            try:
                encoded = get_artifact_storage().get(key, max_bytes=limit)
            except FileNotFoundError:
                return None
        if len(encoded) > limit:
            raise ValueError("Stored artifact exceeds the configured read limit.")
        digest = hashlib.sha256(encoded).hexdigest()
        if not record.get("checksum_sha256") or digest != record["checksum_sha256"]:
            raise ValueError("Stored artifact failed its integrity check.")
        return encoded

    def list_for_user(self, user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, mission_id, user_id, name, artifact_type, content_type, size_bytes, "
                "checksum_sha256, source_type, source_id, provider, model, metadata_json, "
                "status, created_at, updated_at FROM artifacts "
                "WHERE user_id=? ORDER BY created_at DESC, id DESC",
                (user_id,),
            ).fetchall()
            return [self._decode_provenance(row) for row in rows]
        finally:
            conn.close()

    def get(self, user_id, artifact_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id, mission_id, user_id, name, artifact_type, path, content_type, size_bytes, "
                "checksum_sha256, source_type, source_id, provider, model, metadata_json, "
                "status, created_at, updated_at FROM artifacts "
                "WHERE id=? AND user_id=? LIMIT 1",
                (artifact_id, user_id),
            ).fetchone()
            return self._decode_provenance(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def _decode_provenance(row):
        item = dict(row)
        raw = item.pop("metadata_json", None)
        try:
            metadata = json.loads(raw or "{}")
            item["metadata"] = metadata if isinstance(metadata, dict) else {}
        except (TypeError, json.JSONDecodeError):
            item["metadata"] = {}
        return item

    def read_content(self, user_id, artifact_id):
        record = self.get(user_id, artifact_id)
        if not record:
            return None, None
        if record.get("artifact_type") == "binary":
            raise ValueError("Binary artifacts must be downloaded using the download endpoint.")
        encoded = self._read_encoded(user_id, record)
        if encoded is None:
            return None, record
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
            if isinstance(key, str) and ".." not in key.split("/"):
                try:
                    if os.path.isabs(key):
                        root = Path(config.STORAGE_DIRS["artifacts"], str(user_id)).resolve()
                        legacy_path = Path(key).resolve()
                        if os.getenv("SMART_BETHG_OBJECT_STORAGE_BACKEND", "local").lower() == "local" and root in legacy_path.parents:
                            legacy_path.unlink(missing_ok=True)
                    elif key.startswith(f"{user_id}/"):
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
