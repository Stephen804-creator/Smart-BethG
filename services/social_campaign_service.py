"""Owner-scoped social campaigns and durable scheduled-post records.

This module plans and queues posts; it does not claim to publish to a social
network unless a real, reviewed platform adapter is installed.
"""
import json
import re
from datetime import datetime, time, timedelta, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from database import get_connection
from services.social_content_service import SocialContentService
from connectors.social import ConnectorNotConfigured, SocialConnectorRegistry
from services.chat_service import ChatService


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
               audience="", tone="clear, helpful", reference_urls=None, content_rules="",
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
        audience = (audience or "").strip()
        tone = (tone or "clear, helpful").strip()
        content_rules = (content_rules or "").strip()
        if len(audience) > 300 or len(tone) > 300 or len(content_rules) > 4000:
            raise ValueError("Audience and tone must be at most 300 characters; content rules at most 4000.")
        if not isinstance(reference_urls, (list, type(None))) or len(reference_urls or []) > 20:
            raise ValueError("Provide at most 20 reference URLs.")
        references = []
        for value in reference_urls or []:
            if not isinstance(value, str) or len(value) > 2000:
                raise ValueError("Each reference URL must be a string of at most 2000 characters.")
            parsed = urlsplit(value.strip())
            if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
                raise ValueError("Reference links must be valid HTTPS URLs without embedded credentials.")
            references.append(value.strip())
        references = list(dict.fromkeys(references))
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
                "INSERT INTO social_campaigns(user_id, name, objective, audience, tone, reference_urls_json, "
                "content_rules, platforms_json, timezone, start_at, end_at, cadence_json, autonomy_mode, "
                "autopublish_authorized_at, authorization_scope_json, daily_post_limit, status, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', CURRENT_TIMESTAMP)",
                (user_id, name, objective, audience, tone, json.dumps(references), content_rules,
                 json.dumps(cleaned_platforms), timezone_name, start, end, json.dumps(cadence),
                 autonomy_mode, authorized_at,
                 json.dumps({"platforms": cleaned_platforms, "daily_post_limit": daily_post_limit,
                             "start_at": start, "end_at": end}) if authorized_at else None,
                 daily_post_limit),
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
                "SELECT c.id, c.platform, c.topic AS title, c.caption AS content, c.status, c.scheduled_at, "
                "c.external_post_id, c.published_at, c.hashtags, c.created_at, j.status AS publish_status, "
                "j.error_code AS publish_error_code, j.error_message AS publish_error_message "
                "FROM social_content c LEFT JOIN social_publish_jobs j "
                "ON j.content_id=c.id AND j.user_id=c.user_id "
                "WHERE c.user_id=? AND c.campaign_id=? ORDER BY c.scheduled_at, c.id",
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
                auto_authorized = campaign["autonomy_mode"] == "auto_publish_after_campaign_approval"
                initial_content_status = "approved" if auto_authorized else "draft"
                initial_job_status = "awaiting_connection" if auto_authorized else "awaiting_approval"
                conn.execute(
                    "UPDATE social_content SET status=? WHERE id=? AND user_id=?",
                    (initial_content_status, content_id, user_id),
                )
                conn.execute(
                    "INSERT INTO social_publish_jobs(user_id, campaign_id, content_id, platform, scheduled_at, "
                    "status, idempotency_key, error_code, error_message, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                    (user_id, campaign_id, content_id, platform, scheduled, initial_job_status,
                     f"social-post:{user_id}:{campaign_id}:{content_id}",
                     "connector_not_configured" if auto_authorized else None,
                     "Platform connection and publisher must be configured before publishing." if auto_authorized else None),
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

    def generate_plan(self, user_id, campaign_id, count=30, selection=None):
        """Use the configured AI provider to prepare a scheduled plan, not publish it."""
        if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 30:
            raise ValueError("Generate between 1 and 30 posts per request.")
        campaign = self.get(user_id, campaign_id)
        if not campaign:
            return None
        if campaign["status"] in {"active", "paused", "completed", "cancelled"}:
            raise ValueError("Pause or create a new campaign before generating more posts.")
        if campaign.get("posts"):
            raise ValueError("This campaign already has posts. Add a separate batch instead of duplicating the calendar.")
        cadence = campaign.get("cadence") or {}
        interval_days = cadence.get("interval_days", 1)
        local_time = cadence.get("local_time", "09:00")
        if not isinstance(interval_days, int) or isinstance(interval_days, bool) or not 1 <= interval_days <= 30:
            raise ValueError("cadence.interval_days must be an integer from 1 to 30.")
        if not isinstance(local_time, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", local_time):
            raise ValueError("cadence.local_time must use 24-hour HH:MM format.")
        zone = ZoneInfo(campaign["timezone"])
        start_local = datetime.fromisoformat(campaign["start_at"]).astimezone(zone)
        hour, minute = (int(part) for part in local_time.split(":"))
        slots = []
        for index in range(count):
            day = start_local.date() + timedelta(days=index * interval_days)
            local_slot = datetime.combine(day, time(hour=hour, minute=minute), tzinfo=zone)
            if campaign["end_at"] and local_slot.astimezone(timezone.utc) > datetime.fromisoformat(campaign["end_at"]):
                raise ValueError("The campaign end date is too early for the requested number of posts.")
            slots.append({
                "platform": campaign["platforms"][index % len(campaign["platforms"])],
                "scheduled_at": local_slot.astimezone(timezone.utc).isoformat(timespec="seconds"),
            })

        generator = ChatService()
        generated = []
        batch_size = 3
        references = campaign.get("reference_urls") or []
        for offset in range(0, count, batch_size):
            batch_slots = slots[offset:offset + batch_size]
            target_lines = "\n".join(
                f"{i + 1}. platform={slot['platform']}; scheduled_at={slot['scheduled_at']}"
                for i, slot in enumerate(batch_slots)
            )
            prompt = (
                "You are Smart BethG's social campaign content planner. Return only a valid JSON array, "
                "with exactly one object per requested slot. Each object must have string keys title, content "
                "and array-of-strings hashtags. Do not wrap the JSON in markdown. Do not claim you read a "
                "reference link unless its content is included in the prompt. Avoid invented statistics, "
                "quotes, citations, and guarantees. Make every post distinct and suitable for its target platform. "
                "Do not include a platform or schedule field; the server assigns those from the validated plan.\n\n"
                f"Campaign objective: {campaign['objective']}\n"
                f"Target audience: {campaign.get('audience') or 'General audience'}\n"
                f"Tone/brand voice: {campaign.get('tone') or 'Clear and helpful'}\n"
                f"Content rules: {campaign.get('content_rules') or 'Be accurate, useful, original, and respectful.'}\n"
                f"Reference URLs supplied by the user (not fetched or verified here): {json.dumps(references)}\n"
                f"Slots:\n{target_lines}\n\n"
                "Keep each post concise (normally under 700 characters), use 0-8 relevant hashtags, and "
                "make the post useful without unsupported factual claims."
            )
            result = generator.generate_task(user_id, prompt, selection=selection)
            if not result.get("provider_configured"):
                raise ValueError(result.get("error", "No AI provider is configured."))
            if result.get("error"):
                raise ValueError(result["error"])
            raw = result["text"].strip()
            if raw.startswith("```"):
                raw = re.sub(r"^\x60\x60\x60(?:json)?\s*|\s*\x60\x60\x60$", "", raw, flags=re.I)
            start_index, end_index = raw.find("["), raw.rfind("]")
            if start_index < 0 or end_index <= start_index:
                raise ValueError("The AI response was not a valid JSON array. No posts were saved; try again.")
            try:
                items = json.loads(raw[start_index:end_index + 1])
            except json.JSONDecodeError as exc:
                raise ValueError("The AI response contained invalid JSON. No posts were saved; try again.") from exc
            if not isinstance(items, list) or len(items) != len(batch_slots):
                raise ValueError("The AI returned the wrong number of posts. No posts were saved; try again.")
            for item, slot in zip(items, batch_slots):
                if not isinstance(item, dict):
                    raise ValueError("The AI returned an invalid post object. No posts were saved; try again.")
                title = item.get("title")
                body = item.get("content")
                hashtags = item.get("hashtags", [])
                if not isinstance(title, str) or not title.strip() or len(title) > 200:
                    raise ValueError("The AI returned an invalid post title. No posts were saved; try again.")
                if not isinstance(body, str) or not body.strip() or len(body) > 20000:
                    raise ValueError("The AI returned invalid post content. No posts were saved; try again.")
                if not isinstance(hashtags, list) or len(hashtags) > 30 or any(not isinstance(tag, str) for tag in hashtags):
                    raise ValueError("The AI returned invalid hashtags. No posts were saved; try again.")
                generated.append({
                    "platform": slot["platform"],
                    "scheduled_at": slot["scheduled_at"],
                    "title": title.strip(),
                    "content": body.strip(),
                    "hashtags": hashtags,
                })
        # Only persist after every batch passed validation, avoiding partial calendars.
        return self.add_posts(user_id, campaign_id, generated)

    def approve_post(self, user_id, campaign_id, content_id):
        campaign = self.get(user_id, campaign_id)
        if not campaign:
            return None
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id, platform, status FROM social_content WHERE id=? AND user_id=? AND campaign_id=?",
                (content_id, user_id, campaign_id),
            ).fetchone()
            job = conn.execute(
                "SELECT id, status FROM social_publish_jobs WHERE user_id=? AND campaign_id=? AND content_id=?",
                (user_id, campaign_id, content_id),
            ).fetchone()
            if not row or not job:
                return None
            if row["status"] not in {"draft", "in_review"}:
                raise ValueError("Only draft or in-review posts can be approved.")
            if job["status"] != "awaiting_approval":
                raise ValueError("This post is not waiting for an approval decision.")
            connection = conn.execute(
                "SELECT id FROM social_connections WHERE user_id=? AND platform=? AND status='active' LIMIT 1",
                (user_id, row["platform"]),
            ).fetchone()
            publisher_ready = True
            try:
                SocialConnectorRegistry().get_publisher(row["platform"])
            except ConnectorNotConfigured:
                publisher_ready = False
            ready = bool(connection and publisher_ready)
            next_job_status = "queued" if ready else "awaiting_connection"
            error_code = None if ready else ("connector_not_configured" if not publisher_ready else "connection_required")
            error_message = None if ready else (
                "Publishing adapter is not installed for this platform."
                if not publisher_ready else "Connect and verify a social account before publishing."
            )
            conn.execute(
                "UPDATE social_content SET status='approved', updated_at=CURRENT_TIMESTAMP "
                "WHERE id=? AND user_id=? AND campaign_id=?",
                (content_id, user_id, campaign_id),
            )
            conn.execute(
                "UPDATE social_publish_jobs SET status=?, connection_id=?, error_code=?, "
                "error_message=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=? "
                "AND status='awaiting_approval'",
                (next_job_status, connection["id"] if ready else None, error_code, error_message, job["id"], user_id),
            )
            conn.commit()
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
                "SELECT * FROM social_campaigns WHERE id=? AND user_id=? LIMIT 1",
                (campaign_id, user_id),
            ).fetchone()
            if not row:
                return None
            if status not in allowed[row["status"]]:
                raise ValueError(f"Cannot change campaign from {row['status']} to {status}.")
            campaign = self._decode(row)
            if status == "active":
                if campaign["autonomy_mode"] == "auto_publish_after_campaign_approval" and not campaign.get("autopublish_authorized_at"):
                    raise ValueError("Autonomous publishing has no recorded campaign authorization.")
                for platform in campaign["platforms"]:
                    try:
                        SocialConnectorRegistry().get_publisher(platform)
                    except ConnectorNotConfigured as exc:
                        raise ValueError(str(exc)) from exc
                    account = conn.execute(
                        "SELECT id FROM social_connections WHERE user_id=? AND platform=? AND status='active' LIMIT 1",
                        (user_id, platform),
                    ).fetchone()
                    if not account:
                        raise ValueError(f"No active {platform} account is connected.")
                if campaign["autonomy_mode"] == "auto_publish_after_campaign_approval":
                    conn.execute(
                        "UPDATE social_content SET status='approved', updated_at=CURRENT_TIMESTAMP "
                        "WHERE user_id=? AND campaign_id=? AND status='draft'",
                        (user_id, campaign_id),
                    )
                    conn.execute(
                        "UPDATE social_publish_jobs SET status='queued', error_code=NULL, error_message=NULL, updated_at=CURRENT_TIMESTAMP "
                        "WHERE user_id=? AND campaign_id=? AND status IN ('awaiting_approval','awaiting_connection')",
                        (user_id, campaign_id),
                    )
            conn.execute(
                "UPDATE social_campaigns SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
                (status, campaign_id, user_id),
            )
            if status == "cancelled":
                conn.execute(
                    "UPDATE social_publish_jobs SET status='cancelled', updated_at=CURRENT_TIMESTAMP "
                    "WHERE user_id=? AND campaign_id=? AND status IN ('queued','awaiting_approval','awaiting_connection','blocked')",
                    (user_id, campaign_id),
                )
            conn.commit()
        finally:
            conn.close()
        return self.get(user_id, campaign_id)

    @staticmethod
    def _decode(row):
        item = dict(row)
        for key in ("platforms_json", "cadence_json", "authorization_scope_json", "reference_urls_json"):
            raw = item.pop(key, None)
            target = {
                "platforms_json": "platforms",
                "cadence_json": "cadence",
                "authorization_scope_json": "authorization_scope",
                "reference_urls_json": "reference_urls",
            }[key]
            fallback = "[]" if key in {"platforms_json", "reference_urls_json"} else "{}"
            try:
                item[target] = json.loads(raw or fallback) if raw is not None else (None if key == "authorization_scope_json" else json.loads(fallback))
            except (TypeError, json.JSONDecodeError):
                item[target] = [] if key in {"platforms_json", "reference_urls_json"} else (None if key == "authorization_scope_json" else {})
        return item
