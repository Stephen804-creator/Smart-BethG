"""Owner-scoped social campaigns and durable scheduled-post records.

This module plans and queues posts; it does not claim to publish to a social
network unless a real, reviewed platform adapter is installed.
"""
import json
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from database import get_connection
from services.social_content_service import SocialContentService


class SocialCampaignService:
    PLATFORMS = SocialContentService.PLATFORMS - {"blog", "other"}
    AUTONOMY_MODES = {"review_each_post", "auto_publish_after_campaign_approval"}
    STATUSES = {"draft", "planned", "active", "paused", "completed", "cancelled"}

    @staticmethod
    def _timestamp(value, field_name):
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be an ISO-8601 timestamp with a timezone offset.")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a valid ISO-8601 timestamp.") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(f"{field_name} must include a timezone offset.")
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")

    def create(self, user_id, *, name, objective, platforms, timezone_name, start_at,
               end_at=None, cadence=None, daily_post_limit=1, autonomy_mode="review_each_post",
               auto_publish_authorized=False):
        name = (name or "").strip()
        objective = (objective or "").strip()
        if not name or len(name) > 160:
            raise ValueError("Campaign name must be between 1 and 160 characters.")
        if not objective or len(objective) > 4000:
            raise ValueError("Campaign objective must be between 1 and 4000 characters.")
        if not isinstance(platforms, list) or not platforms or len(platforms) > 5:
            raise ValueError("Select between one and five target platforms.")
        cleaned_platforms = list(dict.fromkeys(str(p).strip().lower() for p in platforms))
        if any(p not in self.PLATFORMS for p in cleaned_platforms):
            raise ValueError("One or more target platforms are unsupported.")
        try:
            ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, TypeError):
            raise ValueError("Use a valid IANA timezone such as Africa/Lagos.")
        start = self._timestamp(start_at, "start_at")
        end = self._timestamp(end_at, "end_at") if end_at else None
        if end and end <= start:
            raise ValueError("end_at must be after start_at.")
        if not isinstance(daily_post_limit, int) or isinstance(daily_post_limit, bool) or not 1 <= daily_post_limit <= 20:
            raise ValueError("daily_post_limit must be between 1 and 20.")
        if autonomy_mode not in self.AUTONOMY_MODES:
            raise ValueError("Unsupported autonomy mode.")
        if autonomy_mode == "auto_publish_after_campaign_approval" and auto_publish_authorized is not True:
            raise ValueError("Autonomous publishing requires explicit campaign-level authorization.")
        if autonomy_mode == "review_each_post":
            authorized_at = None
        else:
            authorized_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cadence = cadence or {}
        if not isinstance(cadence, dict) or len(json.dumps(cadence)) > 4000:
            raise ValueError("cadence must be a JSON object of at most 4000 characters.")

        conn = get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO social_campaigns(user_id, name, objective, platforms_json, timezone, start_at, "
                "end_at, cadence_json, autonomy_mode, daily_post_limit, status, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', CURRENT_TIMESTAMP)",
                (user_id, name, objective, json.dumps(cleaned_platforms), timezone_name, start, end,
                 json.dumps(cadence), autonomy_mode, daily_post_limit),
            )
            campaign_id = cursor.lastrowid
            # Keep authorization evidence separate from free-form campaign text.
            if authorized_at:
                conn.execute(
                    "INSERT INTO logs(user_id, level, event_type, message) VALUES (?, 'info', "
                    "'social_campaign_autonomy_authorized', ?)",
                    (user_id, json.dumps({"campaign_id": campaign_id, "authorized_at": authorized_at,
                                          "scope": cleaned_platforms, "end_at": end})),
                )
            conn.commit()
        finally:
            conn.close()
        return self.get(user_id, campaign_id)

    def list_for_user(self, user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM social_campaigns WHERE user_id=? ORDER BY updated_at DESC, id DESC",
                (user_id,),
            ).fetchall()
            return [self._decode(row) for row in rows]
        finally:
            conn.close()

    def get(self, user_id, campaign_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM social_campaigns WHERE id=? AND user_id=? LIMIT 1",
                (campaign_id, user_id),
            ).fetchone()
            if not row:
                return None
            campaign = self._decode(row)
            posts = conn.execute(
                "SELECT id, platform, topic AS title, caption AS content, status, scheduled_at, "
                "external_post_id, published_at, created_at FROM social_content "
                "WHERE user_id=? AND campaign_id=? ORDER BY scheduled_at, id",
                (user_id, campaign_id),
            ).fetchall()
            campaign["posts"] = [dict(post) for post in posts]
            return campaign
        finally:
            conn.close()

    def add_posts(self, user_id, campaign_id, posts):
        if not isinstance(posts, list) or not posts or len(posts) > 90:
            raise ValueError("Provide between 1 and 90 planned posts per batch.")
        campaign = self.get(user_id, campaign_id)
        if not campaign:
            return None
        if campaign["status"] in {"cancelled", "completed"}:
            raise ValueError("Cannot add posts to a terminal campaign.")
        zone = ZoneInfo(campaign["timezone"])
        prepared = []
        for item in posts:
            if not isinstance(item, dict):
                raise ValueError("Each post must be an object.")
            platform = str(item.get("platform", "")).strip().lower()
            title = str(item.get("title", "")).strip()
            content = item.get("content")
            hashtags = item.get("hashtags", [])
            if platform not in campaign["platforms"]:
                raise ValueError(f"Platform {platform!r} is not part of this campaign.")
            if not title or len(title) > 200 or not isinstance(content, str) or not content.strip() or len(content) > 20000:
                raise ValueError("Each post needs a title and content within the supported limits.")
            scheduled = self._timestamp(item.get("scheduled_at"), "scheduled_at")
            instant = datetime.fromisoformat(scheduled)
            if instant < datetime.fromisoformat(campaign["start_at"]):
                raise ValueError("A post cannot be scheduled before the campaign start.")
            if campaign["end_at"] and instant > datetime.fromisoformat(campaign["end_at"]):
                raise ValueError("A post cannot be scheduled after the campaign end.")
            if not isinstance(hashtags, list) or len(hashtags) > 30:
                raise ValueError("Each post may contain at most 30 hashtags.")
            prepared.append((platform, title, content.strip(), hashtags, scheduled,
                             instant.astimezone(zone).date().isoformat()))
        counts = {}
        for platform, title, content, hashtags, scheduled, local_day in prepared:
            counts[local_day] = counts.get(local_day, 0) + 1
        if any(count > campaign["daily_post_limit"] for count in counts.values()):
            raise ValueError("The batch exceeds the campaign's daily post limit.")
        # The batch is inserted in one transaction; no half-created calendar.
        conn = get_connection()
        ids = []
        try:
            existing_rows = conn.execute(
                "SELECT scheduled_at FROM social_content WHERE user_id=? AND campaign_id=? AND scheduled_at IS NOT NULL",
                (user_id, campaign_id),
            ).fetchall()
            existing_counts = {}
            for row in existing_rows:
                day = datetime.fromisoformat(row["scheduled_at"]).astimezone(zone).date().isoformat()
                existing_counts[day] = existing_counts.get(day, 0) + 1
            for day, count in counts.items():
                if existing_counts.get(day, 0) + count > campaign["daily_post_limit"]:
                    raise ValueError(f"Campaign daily post limit would be exceeded on {day}.")
            for platform, title, content, hashtags, scheduled, _day in prepared:
                tags_json = json.dumps(SocialContentService._clean_tags(hashtags), ensure_ascii=False)
                cur = conn.execute(
                    "INSERT INTO social_content(user_id, platform, topic, caption, hashtags, status, version, "
                    "campaign_id, scheduled_at, updated_at) VALUES (?, ?, ?, ?, ?, 'draft', 1, ?, ?, CURRENT_TIMESTAMP)",
                    (user_id, platform, title, content, tags_json, campaign_id, scheduled),
                )
                content_id = cur.lastrowid
                ids.append(content_id)
                conn.execute(
                    "INSERT INTO social_content_versions(social_content_id, user_id, version, title, content, hashtags) "
                    "VALUES (?, ?, 1, ?, ?, ?)",
                    (content_id, user_id, title, content, tags_json),
                )
                conn.execute(
                    "INSERT INTO social_publish_jobs(user_id, campaign_id, content_id, platform, scheduled_at, "
                    "status, idempotency_key, updated_at) VALUES (?, ?, ?, ?, ?, 'awaiting_approval', ?, CURRENT_TIMESTAMP)",
                    (user_id, campaign_id, content_id, platform, scheduled,
                     f"social-post:{user_id}:{campaign_id}:{content_id}"),
                )
            conn.execute(
                "UPDATE social_campaigns SET status='planned', updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
                (campaign_id, user_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get(user_id, campaign_id)

    def set_status(self, user_id, campaign_id, status):
        allowed = {
            "draft": {"planned", "cancelled"},
            "planned": {"paused", "active", "cancelled"},
            "active": {"paused", "cancelled", "completed"},
            "paused": {"active", "cancelled"},
            "completed": set(),
            "cancelled": set(),
        }
        if status not in allowed:
            raise ValueError("Invalid campaign status.")
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT status FROM social_campaigns WHERE id=? AND user_id=? LIMIT 1",
                (campaign_id, user_id),
            ).fetchone()
            if not row:
                return None
            if status not in allowed[row["status"]]:
                raise ValueError(f"Cannot change campaign from {row['status']} to {status}.")
            conn.execute(
                "UPDATE social_campaigns SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
                (status, campaign_id, user_id),
            )
            if status == "cancelled":
                conn.execute(
                    "UPDATE social_publish_jobs SET status='cancelled', updated_at=CURRENT_TIMESTAMP "
                    "WHERE user_id=? AND campaign_id=? AND status IN ('queued','awaiting_approval','blocked')",
                    (user_id, campaign_id),
                )
            conn.commit()
        finally:
            conn.close()
        return self.get(user_id, campaign_id)

    @staticmethod
    def _decode(row):
        item = dict(row)
        for key in ("platforms_json", "cadence_json", "authorization_scope_json"):
            raw = item.pop(key, None)
            target = {
                "platforms_json": "platforms",
                "cadence_json": "cadence",
                "authorization_scope_json": "authorization_scope",
            }[key]
            fallback = "[]" if key == "platforms_json" else "{}"
            try:
                item[target] = json.loads(raw or fallback) if raw is not None else (None if key == "authorization_scope_json" else json.loads(fallback))
            except (TypeError, json.JSONDecodeError):
                item[target] = [] if key == "platforms_json" else (None if key == "authorization_scope_json" else {})
        return item
