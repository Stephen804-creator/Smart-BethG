"""Owner-scoped artifact storage using the configured storage adapter."""
import codecs
import config
import hashlib
import os
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

        digest = hashlib.sha256(encoded).hexdigest()
        if idempotency_key is not None:
            idempotency_key = str(idempotency_key).strip()
            if not idempotency_key or len(idempotency_key) > 200:
                raise ValueError("Idempotency key must be between 1 and 200 characters.")
            existing = self._get_by_idempotency_key(user_id, idempotency_key)
            if existing:
                if existing.get("checksum_sha256") != digest:
                    raise ValueError("Idempotency key was already used for different artifact content.")
                return existing

        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120] or "artifact"
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
        try:
            from repositories.provenance_repository import ProvenanceRepository
            ProvenanceRepository().append_event(
                user_id, artifact_id, "asset_created", "unknown",
                payload={
                    "content_type": "text/plain; charset=utf-8",
                    "size_bytes": len(encoded),
                    "checksum_sha256": digest,
                    "source_filename": name,
                },
                idempotency_key=(
                    f"asset-create:{hashlib.sha256(idempotency_key.encode('utf-8')).hexdigest()}"
                    if idempotency_key else None
                ),
            )
        except Exception:
            self.delete(user_id, artifact_id)
            raise
        return self.get(user_id, artifact_id)

    ALLOWED_BINARY_TYPES = {
        "text/plain", "text/markdown", "text/csv", "application/json",
        "application/pdf", "image/jpeg", "image/png", "image/webp",
        "video/mp4", "video/webm",
    }

    def create_binary_from_path(
        self, user_id, name, source_path, content_type, mission_id=None,
        idempotency_key=None,
    ):
        """Persist a bounded, signature-checked binary asset and its upload event."""
        name = (name or "").strip()
        if not name or len(name) > 160:
            raise ValueError("Artifact name must be between 1 and 160 characters.")
        if mission_id is not None and not self._owns_mission(user_id, mission_id):
            raise ValueError("Mission not found for this user.")
        media_type = (content_type or "").split(";", 1)[0].strip().lower()
        if media_type not in self.ALLOWED_BINARY_TYPES:
            raise ValueError("This asset media type is not supported.")
        if idempotency_key is not None:
            idempotency_key = str(idempotency_key).strip()
            if not idempotency_key or len(idempotency_key) > 180:
                raise ValueError("Idempotency key must be between 1 and 180 characters.")

        source_path = os.fspath(source_path)
        digest = hashlib.sha256()
        size = 0
        header = b""
        decoder = codecs.getincrementaldecoder("utf-8-sig")("strict") if media_type in {
            "text/plain", "text/markdown", "text/csv", "application/json"
        } else None
        try:
            with open(source_path, "rb") as source:
                while True:
                    chunk = source.read(64 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > config.MAX_ASSET_UPLOAD_BYTES:
                        raise ValueError("Asset exceeds the configured upload size limit.")
                    digest.update(chunk)
                    if len(header) < 32:
                        header += chunk[:32 - len(header)]
                    if decoder:
                        decoder.decode(chunk, final=False)
                if decoder:
                    decoder.decode(b"", final=True)
        except UnicodeDecodeError as exc:
            raise ValueError("Text assets must contain valid UTF-8.") from exc
        except OSError as exc:
            raise ValueError("The uploaded asset could not be read.") from exc

        signatures = {
            "application/pdf": header.startswith(b"%PDF-"),
            "image/jpeg": header.startswith(bytes.fromhex("ffd8ff")),
            "image/png": header.startswith(bytes.fromhex("89504e470d0a1a0a")),
            "image/webp": len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP",
            "video/mp4": len(header) >= 8 and header[4:8] == b"ftyp",
            "video/webm": header.startswith(bytes.fromhex("1a45dfa3")),
        }
        if media_type in signatures and not signatures[media_type]:
            raise ValueError("Uploaded file signature does not match its declared media type.")
        if size == 0 and media_type not in {"text/plain", "text/markdown", "text/csv", "application/json"}:
            raise ValueError("The uploaded asset is empty or incomplete.")

        checksum = digest.hexdigest()
        if idempotency_key:
            existing = self._get_by_idempotency_key(user_id, idempotency_key)
            if existing:
                if existing.get("checksum_sha256") != checksum:
                    raise ValueError("Idempotency key was already used for different asset content.")
                return existing

        artifact_type = (
            "image" if media_type.startswith("image/") else
            "video" if media_type.startswith("video/") else
            "document" if media_type == "application/pdf" else "text"
        )
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120] or "asset"
        locator_token = (
            hashlib.sha256(f"{idempotency_key}:{checksum}".encode("utf-8")).hexdigest()[:32]
            if idempotency_key else uuid.uuid4().hex
        )
        object_name = f"{locator_token}_{safe_name}"
        if hasattr(self.storage, "put_file"):
            locator = self.storage.put_file("artifacts", user_id, object_name, source_path)
        else:
            with open(source_path, "rb") as source:
                locator = self.storage.put_bytes("artifacts", user_id, object_name, source.read())

        conn = get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO artifacts(mission_id, user_id, name, artifact_type, path, content_type, "
                "size_bytes, checksum_sha256, status, updated_at, idempotency_key) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ready', CURRENT_TIMESTAMP, ?) "
                "ON CONFLICT(user_id, idempotency_key) WHERE idempotency_key IS NOT NULL "
                "DO NOTHING RETURNING id",
                (mission_id, user_id, name, artifact_type, locator, media_type, size, checksum, idempotency_key),
            )
            row = cursor.fetchone()
            if row:
                artifact_id = row["id"]
                conn.commit()
            else:
                conn.rollback()
                existing = self._get_by_idempotency_key(user_id, idempotency_key)
                if not existing or existing.get("checksum_sha256") != checksum:
                    raise ValueError("Artifact idempotency conflict could not be resolved safely.")
                artifact_id = existing["id"]
                if existing.get("path") != locator:
                    self.storage.delete("artifacts", user_id, locator)
                return existing
        except Exception:
            conn.rollback()
            try:
                self.storage.delete("artifacts", user_id, locator)
            except Exception:
                pass
            raise
        finally:
            conn.close()

        try:
            from repositories.provenance_repository import ProvenanceRepository
            ProvenanceRepository().append_event(
                user_id, artifact_id, "asset_uploaded", "human",
                actor_id=str(user_id),
                payload={
                    "content_type": media_type,
                    "size_bytes": size,
                    "checksum_sha256": checksum,
                    "source_filename": name,
                },
                idempotency_key=f"asset-upload:{idempotency_key}" if idempotency_key else None,
            )
        except Exception:
            self.delete(user_id, artifact_id)
            raise
        return self.get(user_id, artifact_id)

    def create_from_chat_message(self, user_id, conversation_id, message_id, name):
        """Create an asset from one owned successful assistant message and cite its real execution."""
        from repositories.conversation_repository import ConversationRepository
        from repositories.provenance_repository import ProvenanceRepository

        message = ConversationRepository().get_message_for_user(
            user_id, conversation_id, message_id
        )
        if not message:
            raise LookupError("Chat message not found.")
        if message.get("role") != "assistant":
            raise ValueError("Only successful assistant messages can become generated assets.")
        provider = (message.get("provider") or "").strip()
        model = (message.get("model") or "").strip()
        orchestrator_id = (message.get("orchestrator_id") or "").strip()
        if not provider or not model:
            raise ValueError("This assistant message has no successful provider/model execution to attribute.")
        if orchestrator_id not in {"agent_executor", "direct_chat"}:
            raise ValueError("The chat orchestrator identity is missing or unsupported.")

        artifact = self.create(
            user_id, name, message["content"], artifact_type="text",
            idempotency_key=f"chat-message:{message_id}",
        )
        provenance = ProvenanceRepository()
        output_hash = artifact["checksum_sha256"]
        provenance.append_event(
            user_id, artifact["id"], "ai_contribution", "provider",
            actor_id=provider, actor_label=provider,
            provider=provider, model=model,
            payload={
                "source_type": "chat_message",
                "source_conversation_id": conversation_id,
                "source_message_id": message_id,
                "fallback_used": bool(message.get("fallback_used")),
                "output_sha256": output_hash,
            },
            idempotency_key=f"chat-ai:{message_id}",
        )
        orchestrator_label = (
            "Smart BethG Agent Executor"
            if orchestrator_id == "agent_executor" else "Smart BethG Direct Chat"
        )
        provenance.append_event(
            user_id, artifact["id"], "agent_contribution", "smart_bethg",
            actor_id="smart_bethg", actor_label=orchestrator_label,
            agent_id=orchestrator_id,
            payload={
                "role": "orchestrator",
                "source_type": "chat_message",
                "source_conversation_id": conversation_id,
                "source_message_id": message_id,
                "output_sha256": output_hash,
            },
            idempotency_key=f"chat-agent:{message_id}",
        )
        return self.get(user_id, artifact["id"])

    def read_bytes(self, user_id, artifact_id):
        record = self.get(user_id, artifact_id)
        if not record:
            return None, None
        try:
            content = self.storage.get_bytes("artifacts", user_id, record["path"])
        except Exception:
            return None, record
        if len(content) > config.MAX_ASSET_UPLOAD_BYTES:
            raise ValueError("Stored asset exceeds the configured read limit.")
        if len(content) != record.get("size_bytes") or hashlib.sha256(content).hexdigest() != record.get("checksum_sha256"):
            raise ValueError("Stored asset failed its SHA-256 integrity check.")
        return content, record

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
