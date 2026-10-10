"""Owner-scoped social-content drafts with review states and version history."""
import json

from database import get_connection


class SocialContentService:
    PLATFORMS = {"facebook", "youtube", "instagram", "linkedin", "x", "blog", "other"}
    STATUSES = {"draft", "in_review", "approved", "archived"}

    def create(self, user_id, platform, title, content, hashtags=None):
        platform = (platform or "").strip().lower()
        title = (title or "").strip()
        if platform not in self.PLATFORMS:
            raise ValueError("Unsupported social platform.")
        if not title or len(title) > 200:
            raise ValueError("Title must be between 1 and 200 characters.")
        if not isinstance(content, str) or not content.strip() or len(content) > 20000:
            raise ValueError("Content must be between 1 and 20000 characters.")
        tags = self._clean_tags(hashtags or [])
        tags_json = json.dumps(tags, ensure_ascii=False)
        conn = get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO social_content(user_id, platform, title, content, hashtags, status, version, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 'draft', 1, CURRENT_TIMESTAMP)",
                (user_id, platform, title, content, tags_json),
            )
            content_id = cursor.lastrowid
            conn.execute(
                "INSERT INTO social_content_versions(social_content_id, user_id, version, title, content, hashtags) "
                "VALUES (?, ?, 1, ?, ?, ?)",
                (content_id, user_id, title, content, tags_json),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get(user_id, content_id)

    def list_for_user(self, user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, user_id, platform, title, content, hashtags, status, version, "
                "external_post_id, published_at, created_at, updated_at FROM social_content "
                "WHERE user_id=? ORDER BY updated_at DESC, id DESC",
                (user_id,),
            ).fetchall()
            return [self._decode(row) for row in rows]
        finally:
            conn.close()

    def get(self, user_id, content_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id, user_id, platform, title, content, hashtags, status, version, "
                "external_post_id, published_at, created_at, updated_at FROM social_content "
                "WHERE id=? AND user_id=? LIMIT 1",
                (content_id, user_id),
            ).fetchone()
            if not row:
                return None
            item = self._decode(row)
            versions = conn.execute(
                "SELECT version, title, content, hashtags, created_at FROM social_content_versions "
                "WHERE social_content_id=? AND user_id=? ORDER BY version DESC",
                (content_id, user_id),
            ).fetchall()
            item["versions"] = [self._decode_version(v) for v in versions]
            return item
        finally:
            conn.close()

    def update(self, user_id, content_id, fields):
        current = self.get(user_id, content_id)
        if not current:
            return None
        if current["status"] in {"approved", "archived"}:
            raise ValueError("Approved or archived content must be moved back to draft before editing.")
        platform = fields.get("platform", current["platform"])
        title = fields.get("title", current["title"])
        content = fields.get("content", current["content"])
        hashtags = fields.get("hashtags", current["hashtags"])
        platform = (platform or "").strip().lower()
        title = (title or "").strip()
        if platform not in self.PLATFORMS:
            raise ValueError("Unsupported social platform.")
        if not title or len(title) > 200:
            raise ValueError("Title must be between 1 and 200 characters.")
        if not isinstance(content, str) or not content.strip() or len(content) > 20000:
            raise ValueError("Content must be between 1 and 20000 characters.")
        tags_json = json.dumps(self._clean_tags(hashtags), ensure_ascii=False)
        version = int(current["version"]) + 1
        conn = get_connection()
        try:
            cursor = conn.execute(
                "UPDATE social_content SET platform=?, title=?, content=?, hashtags=?, version=?, "
                "status='draft', updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=? AND version=?",
                (platform, title, content, tags_json, version, content_id, user_id, current["version"]),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                raise ValueError("Content changed concurrently. Refresh and try again.")
            conn.execute(
                "INSERT INTO social_content_versions(social_content_id, user_id, version, title, content, hashtags) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (content_id, user_id, version, title, content, tags_json),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get(user_id, content_id)

    def transition(self, user_id, content_id, new_status):
        if new_status not in self.STATUSES:
            raise ValueError("Invalid content status.")
        current = self.get(user_id, content_id)
        if not current:
            return None
        allowed = {
            "draft": {"in_review", "archived"},
            "in_review": {"draft", "approved", "archived"},
            "approved": {"in_review", "archived"},
            "archived": set(),
        }
        if new_status not in allowed[current["status"]]:
            raise ValueError(f"Cannot change content from {current['status']} to {new_status}.")
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE social_content SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
                (new_status, content_id, user_id),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get(user_id, content_id)

    @staticmethod
    def _clean_tags(tags):
        if not isinstance(tags, list) or len(tags) > 30:
            raise ValueError("Hashtags must be a list of at most 30 items.")
        cleaned = []
        for tag in tags:
            if not isinstance(tag, str):
                raise ValueError("Hashtags must be strings.")
            tag = tag.strip().lstrip("#")
            if tag and len(tag) <= 80:
                cleaned.append(tag)
        return list(dict.fromkeys(cleaned))

    @staticmethod
    def _decode(row):
        item = dict(row)
        try:
            item["hashtags"] = json.loads(item.get("hashtags") or "[]")
        except (TypeError, json.JSONDecodeError):
            item["hashtags"] = []
        return item

    @staticmethod
    def _decode_version(row):
        item = dict(row)
        try:
            item["hashtags"] = json.loads(item.get("hashtags") or "[]")
        except (TypeError, json.JSONDecodeError):
            item["hashtags"] = []
        return item
