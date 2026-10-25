"""Owner-scoped research records with source provenance."""
import json
from urllib.parse import urlsplit

from database import get_connection


class ResearchService:
    def create(self, user_id, query, summary="", source_urls=None, mission_id=None, idempotency_key=None):
        query = (query or "").strip()
        summary = summary or ""
        if not query or len(query) > 4000:
            raise ValueError("Research query must be between 1 and 4000 characters.")
        if len(summary) > 50000:
            raise ValueError("Research summary exceeds the 50000-character limit.")
        if mission_id is not None and not self._owns_mission(user_id, mission_id):
            raise ValueError("Mission not found for this user.")
        if idempotency_key is not None:
            idempotency_key = str(idempotency_key).strip()
            if not idempotency_key or len(idempotency_key) > 200:
                raise ValueError("Idempotency key must be between 1 and 200 characters.")
        urls = self._clean_urls(source_urls or [])
        conn = get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO research(user_id, mission_id, topic, summary, source_info, idempotency_key) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id, idempotency_key) WHERE idempotency_key IS NOT NULL DO NOTHING RETURNING id",
                (user_id, mission_id, query, summary, json.dumps(urls, ensure_ascii=False), idempotency_key),
            )
            row = cursor.fetchone()
            if row:
                record_id = row["id"]
                conn.commit()
            else:
                conn.rollback()
                existing = conn.execute(
                    "SELECT id FROM research WHERE user_id=? AND idempotency_key=? LIMIT 1",
                    (user_id, idempotency_key),
                ).fetchone()
                if not existing:
                    raise RuntimeError("Research idempotency conflict did not resolve to an existing record.")
                record_id = existing["id"]
        finally:
            conn.close()
        return self.get(user_id, record_id)

    def list_for_user(self, user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, user_id, mission_id, topic AS query, summary, source_info AS source_urls, created_at "
                "FROM research WHERE user_id=? ORDER BY created_at DESC, id DESC",
                (user_id,),
            ).fetchall()
            return [self._decode(row) for row in rows]
        finally:
            conn.close()

    def get(self, user_id, research_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id, user_id, mission_id, topic AS query, summary, source_info AS source_urls, created_at "
                "FROM research WHERE id=? AND user_id=? LIMIT 1",
                (research_id, user_id),
            ).fetchone()
            return self._decode(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def _clean_urls(urls):
        if not isinstance(urls, list) or len(urls) > 100:
            raise ValueError("Source URLs must be a list of at most 100 items.")
        cleaned = []
        for url in urls:
            if not isinstance(url, str) or len(url) > 2048:
                raise ValueError("Each source URL must be a string under 2048 characters.")
            parts = urlsplit(url)
            if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
                raise ValueError("Source URLs must use HTTP/HTTPS and contain no embedded credentials.")
            cleaned.append(url)
        return list(dict.fromkeys(cleaned))

    @staticmethod
    def _decode(row):
        item = dict(row)
        try:
            item["source_urls"] = json.loads(item.get("source_urls") or "[]")
        except (TypeError, json.JSONDecodeError):
            item["source_urls"] = []
        return item

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
