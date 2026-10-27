"""Services for roadmap Units 21-24.

Only trusted workflow definitions are scheduled. Extension manifests are declarative
metadata; this module never imports or executes code supplied by an extension.
"""
import json
import re
from datetime import datetime, timedelta, timezone

from database import get_connection
from services.workflow_service import WorkflowService
from services.job_queue import JobQueue


PLAN_CATALOG = {
    "free": {"label": "Free", "daily_requests": 30, "monthly_credits": 100, "features": ["chat", "basic_workflows"]},
    "starter": {"label": "Starter", "daily_requests": 150, "monthly_credits": 1000, "features": ["chat", "workflows", "scheduled_jobs"]},
    "pro": {"label": "Pro", "daily_requests": 600, "monthly_credits": 5000, "features": ["chat", "workflows", "scheduled_jobs", "extensions", "advanced_usage"]},
    "team": {"label": "Team", "daily_requests": 2000, "monthly_credits": 20000, "features": ["chat", "workflows", "scheduled_jobs", "extensions", "advanced_usage", "team_workspaces"]},
}
RISK_LEVELS = {"read", "write", "destructive", "financial"}
FIELD_TYPES = {"string", "integer", "number", "boolean", "object", "array"}


def _iso(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _json(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return {}
    return value or {}


def _parse_datetime(value):
    if isinstance(value, datetime):
        result = value
    else:
        try:
            result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Provide a valid ISO-8601 date/time including a timezone.") from exc
    if result.tzinfo is None:
        raise ValueError("Date/time must include a timezone offset.")
    return result.astimezone(timezone.utc)


class ScheduledAgentJobService:
    """Durable one-off/recurring workflow dispatch with transactional idempotency."""

    def __init__(self, workflows=None):
        self.workflows = workflows or WorkflowService()

    def create(self, user_id, name, workflow_id, scheduled_at, interval_seconds=None, max_runs=None):
        name = str(name or "").strip()
        if not 1 <= len(name) <= 120:
            raise ValueError("Schedule name must be between 1 and 120 characters.")
        try:
            workflow_id = int(workflow_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("workflow_id must be an integer.") from exc
        workflow = self.workflows.get(user_id, workflow_id)
        if not workflow:
            raise ValueError("Workflow was not found for this account.")
        if workflow.get("status") != "validated":
            raise ValueError("Validate the workflow before scheduling it.")
        when = _parse_datetime(scheduled_at)
        if when < datetime.now(timezone.utc) - timedelta(minutes=1):
            raise ValueError("Scheduled time must be in the future.")
        if interval_seconds is not None:
            if isinstance(interval_seconds, bool):
                raise ValueError("interval_seconds must be between 60 and 2592000.")
            interval_seconds = int(interval_seconds)
            if not 60 <= interval_seconds <= 2592000:
                raise ValueError("Recurring intervals must be between 60 seconds and 30 days.")
        if max_runs is not None:
            if isinstance(max_runs, bool):
                raise ValueError("max_runs must be between 1 and 10000.")
            max_runs = int(max_runs)
            if not 1 <= max_runs <= 10000:
                raise ValueError("max_runs must be between 1 and 10000.")
        conn = get_connection()
        try:
            row = conn.execute(
                "INSERT INTO scheduled_agent_jobs(user_id,name,workflow_id,scheduled_at,interval_seconds,"
                "next_run_at,max_runs) VALUES (?,?,?,?,?,?,?) RETURNING id",
                (user_id, name, workflow_id, _iso(when), interval_seconds, _iso(when), max_runs),
            ).fetchone()
            conn.commit()
            return self.get(user_id, row["id"])
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get(self, user_id, schedule_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM scheduled_agent_jobs WHERE id=? AND user_id=?",
                (schedule_id, user_id),
            ).fetchone()
            return self._decode(row) if row else None
        finally:
            conn.close()

    def list_for_user(self, user_id, limit=50):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM scheduled_agent_jobs WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
                (user_id, max(1, min(100, int(limit)))),
            ).fetchall()
            return [self._decode(row) for row in rows]
        finally:
            conn.close()

    def set_status(self, user_id, schedule_id, status):
        if status not in {"active", "paused", "cancelled"}:
            raise ValueError("Status must be active, paused, or cancelled.")
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id,interval_seconds,status FROM scheduled_agent_jobs WHERE id=? AND user_id=?",
                (schedule_id, user_id),
            ).fetchone()
            if not row:
                return None
            if row["status"] == "completed" and status == "active":
                raise ValueError("A completed schedule cannot be reactivated; create a new schedule.")
            cursor = conn.execute(
                "UPDATE scheduled_agent_jobs SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
                (status, schedule_id, user_id),
            )
            conn.commit()
            return self.get(user_id, schedule_id) if cursor.rowcount else None
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def process_due(self, limit=10):
        """Dispatch due workflows in one transaction per occurrence.

        The schedule occurrence, workflow run, queue message, and next-run
        advancement commit together. A unique schedule-occurrence link prevents
        duplicate workflow runs if multiple workers race.
        """
        dispatched = []
        for _ in range(max(1, min(50, int(limit)))):
            conn = get_connection()
            try:
                conn.execute("BEGIN")
                row = conn.execute(
                    "SELECT s.* FROM scheduled_agent_jobs s "
                    "WHERE s.status='active' AND s.next_run_at<=CURRENT_TIMESTAMP "
                    "ORDER BY s.next_run_at,s.id FOR UPDATE OF s SKIP LOCKED LIMIT 1"
                ).fetchone()
                if not row:
                    conn.rollback()
                    break
                schedule = dict(row)
                scheduled_for = _iso(schedule["next_run_at"])
                occurrence = conn.execute(
                    "INSERT INTO scheduled_job_runs(scheduled_job_id,user_id,scheduled_for,status) "
                    "VALUES (?,?,?,'dispatching') ON CONFLICT(scheduled_job_id,scheduled_for) DO NOTHING "
                    "RETURNING id",
                    (schedule["id"], schedule["user_id"], scheduled_for),
                ).fetchone()
                if not occurrence:
                    # A duplicate occurrence should never dispatch twice. Move the
                    # pointer forward defensively so a damaged old row cannot spin.
                    self._advance(conn, schedule)
                    conn.commit()
                    continue
                workflow = conn.execute(
                    "SELECT id,version,status FROM workflows WHERE id=? AND user_id=?",
                    (schedule["workflow_id"], schedule["user_id"]),
                ).fetchone()
                if not workflow or workflow["status"] != "validated":
                    conn.execute(
                        "UPDATE scheduled_job_runs SET status='failed',error_code='workflow_not_validated' WHERE id=?",
                        (occurrence["id"],),
                    )
                    conn.execute(
                        "UPDATE scheduled_agent_jobs SET status='paused',updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (schedule["id"],),
                    )
                    conn.commit()
                    continue
                run = conn.execute(
                    "INSERT INTO workflow_runs(workflow_id,user_id,workflow_version,status,result_json,scheduled_job_run_id) "
                    "VALUES (?,?,?,'queued','{}',?) RETURNING id",
                    (workflow["id"], schedule["user_id"], workflow["version"], occurrence["id"]),
                ).fetchone()
                JobQueue().enqueue_in_transaction(
                    conn, schedule["user_id"], "workflow.execute",
                    {"workflow_id": workflow["id"], "run_id": run["id"],
                     "workflow_version": workflow["version"], "step_index": 0},
                    idempotency_key=f"scheduled-run:{occurrence['id']}", priority=0,
                )
                conn.execute(
                    "UPDATE scheduled_job_runs SET workflow_run_id=?,status='dispatched' WHERE id=?",
                    (run["id"], occurrence["id"]),
                )
                self._advance(conn, schedule)
                conn.commit()
                dispatched.append({"schedule_id": schedule["id"], "scheduled_run_id": occurrence["id"], "workflow_run_id": run["id"]})
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        return dispatched

    @staticmethod
    def _advance(conn, schedule):
        new_count = int(schedule["run_count"]) + 1
        interval = schedule.get("interval_seconds")
        max_runs = schedule.get("max_runs")
        if interval is None or (max_runs is not None and new_count >= int(max_runs)):
            conn.execute(
                "UPDATE scheduled_agent_jobs SET status='completed',last_run_at=CURRENT_TIMESTAMP,"
                "run_count=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (new_count, schedule["id"]),
            )
        else:
            conn.execute(
                "UPDATE scheduled_agent_jobs SET next_run_at=CURRENT_TIMESTAMP + (? * INTERVAL '1 second'),"
                "last_run_at=CURRENT_TIMESTAMP,run_count=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (int(interval), new_count, schedule["id"]),
            )

    @staticmethod
    def _decode(row):
        item = dict(row)
        for key in ("scheduled_at", "next_run_at", "last_run_at", "created_at", "updated_at"):
            if item.get(key) is not None:
                item[key] = _iso(item[key])
        return item


class ExtensionManifestService:
    """Validated, versioned, declarative extension contracts; never executes plugin code."""

    def create(self, owner_user_id, manifest):
        normalized = self.validate_manifest(manifest)
        conn = get_connection()
        try:
            row = conn.execute(
                "INSERT INTO extension_manifests(owner_user_id,extension_key,version,manifest_json,status) "
                "VALUES (?,?,?,?,'draft') ON CONFLICT(owner_user_id,extension_key,version) DO NOTHING RETURNING id",
                (owner_user_id, normalized["key"], normalized["version"], json.dumps(normalized, ensure_ascii=False)),
            ).fetchone()
            if row:
                extension_id = row["id"]
            else:
                existing = conn.execute(
                    "SELECT id,manifest_json,status FROM extension_manifests "
                    "WHERE owner_user_id=? AND extension_key=? AND version=?",
                    (owner_user_id, normalized["key"], normalized["version"]),
                ).fetchone()
                if not existing or _json(existing["manifest_json"]) != normalized:
                    raise ValueError("This extension key/version already exists with different content.")
                extension_id = existing["id"]
            conn.commit()
            return self.get(owner_user_id, extension_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_for_user(self, owner_user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM extension_manifests WHERE owner_user_id=? ORDER BY created_at DESC,id DESC",
                (owner_user_id,),
            ).fetchall()
            return [self._decode(row) for row in rows]
        finally:
            conn.close()

    def get(self, owner_user_id, extension_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM extension_manifests WHERE id=? AND owner_user_id=?",
                (extension_id, owner_user_id),
            ).fetchone()
            return self._decode(row) if row else None
        finally:
            conn.close()

    def review(self, extension_id, status):
        if status not in {"approved", "disabled"}:
            raise ValueError("Review status must be approved or disabled.")
        conn = get_connection()
        try:
            row = conn.execute(
                "UPDATE extension_manifests SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=? RETURNING id",
                (status, extension_id),
            ).fetchone()
            conn.commit()
            return bool(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def validate_manifest(manifest):
        if not isinstance(manifest, dict) or set(manifest) - {"key", "name", "version", "description", "actions"}:
            raise ValueError("Manifest must contain only key, name, version, description, and actions.")
        key = str(manifest.get("key", "")).strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_-]{1,62}", key):
            raise ValueError("Extension key must be a lowercase identifier of 2-63 characters.")
        version = str(manifest.get("version", "")).strip()
        if not version or len(version) > 40:
            raise ValueError("Extension version must be between 1 and 40 characters.")
        name = str(manifest.get("name", "")).strip()
        description = str(manifest.get("description", "")).strip()
        actions = manifest.get("actions")
        if not name or len(name) > 120 or len(description) > 1000:
            raise ValueError("Extension name or description is invalid.")
        if not isinstance(actions, list) or not 1 <= len(actions) <= 30:
            raise ValueError("An extension must define between 1 and 30 actions.")
        seen = set()
        clean_actions = []
        for action in actions:
            if not isinstance(action, dict) or set(action) - {"key", "description", "fields", "required", "risk", "side_effecting"}:
                raise ValueError("Each action must use only the documented declarative fields.")
            action_key = str(action.get("key", "")).strip().lower()
            if not re.fullmatch(r"[a-z][a-z0-9_.-]{1,79}", action_key) or action_key in seen:
                raise ValueError("Action keys must be unique lowercase identifiers.")
            seen.add(action_key)
            fields = action.get("fields", {})
            required = action.get("required", [])
            if not isinstance(fields, dict) or len(fields) > 40 or not isinstance(required, list):
                raise ValueError("Action fields/required must be bounded objects/lists.")
            if set(required) - set(fields):
                raise ValueError("Required fields must exist in the action field definitions.")
            clean_fields = {}
            for field, kind in fields.items():
                if not isinstance(field, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", field) or kind not in FIELD_TYPES:
                    raise ValueError("Unsupported field name or field type.")
                clean_fields[field] = kind
            risk = action.get("risk", "read")
            if risk not in RISK_LEVELS:
                raise ValueError("Unsupported extension action risk.")
            side_effecting = action.get("side_effecting", False)
            if not isinstance(side_effecting, bool):
                raise ValueError("side_effecting must be a boolean.")
            if risk in {"write", "destructive", "financial"} and not side_effecting:
                raise ValueError("Write/destructive/financial actions must be marked side_effecting.")
            clean_actions.append({
                "key": action_key,
                "description": str(action.get("description", ""))[:500],
                "fields": clean_fields,
                "required": sorted(set(required)),
                "risk": risk,
                "side_effecting": side_effecting,
            })
        return {"key": key, "name": name, "version": version, "description": description, "actions": clean_actions}

    @staticmethod
    def _decode(row):
        item = dict(row)
        item["manifest"] = _json(item.pop("manifest_json", "{}"))
        for key in ("created_at", "updated_at"):
            if item.get(key) is not None:
                item[key] = _iso(item[key])
        return item


class UsageIntelligenceService:
    """Read-only cost/usage analytics plus plan-aware daily request admission."""

    def summary(self, user_id, days=30):
        days = max(1, min(90, int(days)))
        conn = get_connection()
        try:
            assignment = conn.execute(
                "SELECT plan_key,status FROM account_plan_assignments WHERE user_id=?",
                (user_id,),
            ).fetchone()
            plan_key = assignment["plan_key"] if assignment else "free"
            plan_status = assignment["status"] if assignment else "active"
            totals = conn.execute(
                "SELECT COUNT(*) AS requests,"
                "COALESCE(SUM(COALESCE(actual_input_tokens,estimated_input_tokens)),0) AS input_tokens,"
                "COALESCE(SUM(COALESCE(actual_output_tokens,estimated_output_tokens)),0) AS output_tokens,"
                "COALESCE(SUM(COALESCE(actual_cost_micros,estimated_cost_micros)),0) AS cost_micros "
                "FROM usage_budget_reservations WHERE user_id=? "
                "AND created_at >= CURRENT_TIMESTAMP - (? * INTERVAL '1 day')",
                (user_id, days),
            ).fetchone()
            by_model = conn.execute(
                "SELECT provider,model,COUNT(*) AS requests,"
                "COALESCE(SUM(COALESCE(actual_cost_micros,estimated_cost_micros)),0) AS cost_micros "
                "FROM usage_budget_reservations WHERE user_id=? "
                "AND created_at >= CURRENT_TIMESTAMP - (? * INTERVAL '1 day') "
                "GROUP BY provider,model ORDER BY cost_micros DESC LIMIT 20",
                (user_id, days),
            ).fetchall()
            today = conn.execute(
                "SELECT COUNT(*) AS requests FROM usage_budget_reservations "
                "WHERE user_id=? AND created_at >= CURRENT_DATE",
                (user_id,),
            ).fetchone()
            plan = PLAN_CATALOG.get(plan_key, PLAN_CATALOG["free"])
            return {
                "period_days": days, "plan": plan_key, "plan_status": plan_status,
                "requests": int(totals["requests"]), "input_tokens": int(totals["input_tokens"]),
                "output_tokens": int(totals["output_tokens"]), "cost_micros": int(totals["cost_micros"]),
                "daily_requests": int(today["requests"]), "daily_request_limit": plan["daily_requests"],
                "daily_capacity_remaining": max(0, plan["daily_requests"] - int(today["requests"])),
                "models": [dict(row) for row in by_model],
                "notice": "Costs are recorded estimates, not provider invoices. Model names are shown only in the private account usage view.",
            }
        finally:
            conn.close()

    def assert_plan_request_allowed(self, user_id):
        conn = get_connection()
        try:
            assignment = conn.execute(
                "SELECT plan_key,status FROM account_plan_assignments WHERE user_id=?",
                (user_id,),
            ).fetchone()
            plan_key = assignment["plan_key"] if assignment else "free"
            status = assignment["status"] if assignment else "active"
            if status != "active":
                raise PermissionError("This account's plan is not active.")
            limit = PLAN_CATALOG.get(plan_key, PLAN_CATALOG["free"])["daily_requests"]
            row = conn.execute(
                "SELECT COUNT(*) AS requests FROM usage_budget_reservations "
                "WHERE user_id=? AND created_at >= CURRENT_DATE",
                (user_id,),
            ).fetchone()
            if int(row["requests"]) >= limit:
                raise PermissionError("Your plan's daily request capacity has been reached.")
        finally:
            conn.close()


class CommercialAccountService:
    """Plan metadata, append-only credit ledger, and reviewed rewards; no fake payments."""

    def overview(self, user_id):
        conn = get_connection()
        try:
            assignment = conn.execute(
                "SELECT plan_key,status,effective_at,updated_at FROM account_plan_assignments WHERE user_id=?",
                (user_id,),
            ).fetchone()
            plan_key = assignment["plan_key"] if assignment else "free"
            ledger = conn.execute(
                "SELECT COALESCE(SUM(delta_credits),0) AS balance FROM credit_ledger WHERE user_id=?",
                (user_id,),
            ).fetchone()
            rewards = conn.execute(
                "SELECT id,reward_key,credits,status,created_at,reviewed_at FROM reward_events "
                "WHERE user_id=? ORDER BY created_at DESC LIMIT 20",
                (user_id,),
            ).fetchall()
            return {
                "plan": dict(assignment) if assignment else {"plan_key": "free", "status": "active"},
                "plan_details": PLAN_CATALOG.get(plan_key, PLAN_CATALOG["free"]),
                "credit_balance": int(ledger["balance"]),
                "credits_are_internal_units": True,
                "payment_processing": "not_configured",
                "rewards": [dict(row) for row in rewards],
            }
        finally:
            conn.close()

    def assign_plan(self, user_id, plan_key, status="active"):
        if plan_key not in PLAN_CATALOG:
            raise ValueError("Unknown plan.")
        if status not in {"active", "past_due", "cancelled", "suspended"}:
            raise ValueError("Invalid plan status.")
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO account_plan_assignments(user_id,plan_key,status) VALUES (?,?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET plan_key=EXCLUDED.plan_key,status=EXCLUDED.status,updated_at=CURRENT_TIMESTAMP",
                (user_id, plan_key, status),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.overview(user_id)

    def grant_credits(self, user_id, credits, reason, idempotency_key, source="admin_grant", metadata=None):
        if isinstance(credits, bool):
            raise ValueError("credits must be a non-zero integer.")
        credits = int(credits)
        if not 1 <= credits <= 1000000:
            raise ValueError("Credit grants must be between 1 and 1,000,000.")
        reason = str(reason or "").strip()
        key = str(idempotency_key or "").strip()
        if not reason or len(reason) > 120 or not 1 <= len(key) <= 200:
            raise ValueError("A bounded reason and idempotency key are required.")
        if source not in {"plan_allocation", "admin_grant", "approved_reward", "refund", "adjustment"}:
            raise ValueError("Unsupported credit grant source.")
        conn = get_connection()
        try:
            row = conn.execute(
                "INSERT INTO credit_ledger(user_id,delta_credits,reason,source,idempotency_key,metadata_json) "
                "VALUES (?,?,?,?,?,?) ON CONFLICT(user_id,idempotency_key) DO NOTHING RETURNING id",
                (user_id, credits, reason, source, key, json.dumps(metadata or {}, ensure_ascii=False)[:4000]),
            ).fetchone()
            if not row:
                existing = conn.execute(
                    "SELECT delta_credits,reason,source FROM credit_ledger WHERE user_id=? AND idempotency_key=?",
                    (user_id, key),
                ).fetchone()
                if not existing or int(existing["delta_credits"]) != credits or existing["reason"] != reason or existing["source"] != source:
                    raise ValueError("Idempotency key was already used for a different credit operation.")
            conn.commit()
            return self.overview(user_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def consume_credits(self, user_id, credits, reason, idempotency_key):
        if isinstance(credits, bool):
            raise ValueError("credits must be a positive integer.")
        credits = int(credits)
        if not 1 <= credits <= 1000000:
            raise ValueError("credits must be between 1 and 1,000,000.")
        reason = str(reason or "").strip()
        key = str(idempotency_key or "").strip()
        if not reason or len(reason) > 120 or not 1 <= len(key) <= 200:
            raise ValueError("A bounded reason and idempotency key are required.")
        conn = get_connection()
        try:
            conn.execute("BEGIN")
            conn.execute(
                "INSERT INTO account_plan_assignments(user_id,plan_key,status) VALUES (?,'free','active') "
                "ON CONFLICT(user_id) DO NOTHING",
                (user_id,),
            )
            conn.execute("SELECT user_id FROM account_plan_assignments WHERE user_id=? FOR UPDATE", (user_id,))
            existing = conn.execute(
                "SELECT delta_credits,reason,source FROM credit_ledger WHERE user_id=? AND idempotency_key=?",
                (user_id, key),
            ).fetchone()
            if existing:
                if int(existing["delta_credits"]) != -credits or existing["reason"] != reason or existing["source"] != "usage_debit":
                    raise ValueError("Idempotency key was already used for a different credit operation.")
                conn.commit()
                return self.overview(user_id)
            balance = conn.execute(
                "SELECT COALESCE(SUM(delta_credits),0) AS balance FROM credit_ledger WHERE user_id=?",
                (user_id,),
            ).fetchone()
            if int(balance["balance"]) < credits:
                raise ValueError("Insufficient credits.")
            conn.execute(
                "INSERT INTO credit_ledger(user_id,delta_credits,reason,source,idempotency_key) "
                "VALUES (?,?,?,'usage_debit',?)",
                (user_id, -credits, reason, key),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.overview(user_id)

    def request_reward(self, user_id, reward_key, credits, idempotency_key):
        reward_key = str(reward_key or "").strip().lower()
        key = str(idempotency_key or "").strip()
        if not re.fullmatch(r"[a-z][a-z0-9_-]{1,62}", reward_key):
            raise ValueError("Invalid reward key.")
        if isinstance(credits, bool):
            raise ValueError("credits must be between 1 and 100000.")
        credits = int(credits)
        if not 1 <= credits <= 100000:
            raise ValueError("credits must be between 1 and 100000.")
        if not 1 <= len(key) <= 200:
            raise ValueError("A bounded idempotency key is required.")
        conn = get_connection()
        try:
            row = conn.execute(
                "INSERT INTO reward_events(user_id,reward_key,credits,idempotency_key,status) "
                "VALUES (?,?,?,?,'pending') ON CONFLICT(user_id,idempotency_key) DO NOTHING RETURNING id",
                (user_id, reward_key, credits, key),
            ).fetchone()
            if not row:
                existing = conn.execute(
                    "SELECT reward_key,credits FROM reward_events WHERE user_id=? AND idempotency_key=?",
                    (user_id, key),
                ).fetchone()
                if not existing or existing["reward_key"] != reward_key or int(existing["credits"]) != credits:
                    raise ValueError("Idempotency key was already used for a different reward.")
            conn.commit()
            return self.overview(user_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def review_reward(self, reviewer_id, reward_id, decision):
        if decision not in {"approved", "rejected"}:
            raise ValueError("Decision must be approved or rejected.")
        conn = get_connection()
        try:
            conn.execute("BEGIN")
            reward = conn.execute(
                "SELECT * FROM reward_events WHERE id=? FOR UPDATE",
                (reward_id,),
            ).fetchone()
            if not reward:
                return None
            if reward["status"] != "pending":
                conn.rollback()
                return {"id": reward_id, "status": reward["status"], "already_reviewed": True}
            conn.execute(
                "UPDATE reward_events SET status=?,reviewed_by=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?",
                (decision, reviewer_id, reward_id),
            )
            if decision == "approved":
                conn.execute(
                    "INSERT INTO credit_ledger(user_id,delta_credits,reason,source,idempotency_key,metadata_json) "
                    "VALUES (?,?,?,'approved_reward',?,?) ON CONFLICT(user_id,idempotency_key) DO NOTHING",
                    (reward["user_id"], reward["credits"], "Approved reward: " + reward["reward_key"],
                     "reward-event:" + str(reward_id), json.dumps({"reward_event_id": reward_id})),
                )
            conn.commit()
            return {"id": reward_id, "status": decision, "credits_awarded": int(reward["credits"]) if decision == "approved" else 0}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
