"""Atomic daily token and estimated-cost budgets backed by the shared database."""
import math
import uuid
from datetime import datetime, timezone

import config
from database import get_connection
from providers.model_catalog import MODEL_CATALOG
from services.units_21_24 import PLAN_CATALOG


class BudgetExceededError(Exception):
    """Raised before a provider request when a configured daily budget is exhausted."""


class UsageBudgetService:
    def __init__(self, pricing_catalog=None):
        self.pricing_catalog = pricing_catalog or MODEL_CATALOG

    @staticmethod
    def estimate_input_tokens(messages):
        chars = sum(len(str(item.get("content", ""))) for item in messages)
        # Deliberately conservative for multilingual text; this is a budget
        # reservation estimate, not a billing-grade tokenizer.
        return max(1, math.ceil((chars + len(messages) * 12) / 2))

    def reserve(self, user_id, provider, model, input_tokens, output_tokens):
        input_tokens = max(1, int(input_tokens))
        output_tokens = max(1, int(output_tokens))
        pricing = self._pricing(provider, model)
        estimated_cost = self._cost_micros(input_tokens, output_tokens, pricing)
        user_token_limit = config.USER_DAILY_TOKEN_BUDGET
        global_token_limit = config.GLOBAL_DAILY_TOKEN_BUDGET
        user_cost_limit = int(config.USER_DAILY_SPEND_USD * 1_000_000)
        global_cost_limit = int(config.GLOBAL_DAILY_SPEND_USD * 1_000_000)

        if (
            input_tokens + output_tokens > user_token_limit
            or input_tokens + output_tokens > global_token_limit
            or estimated_cost > user_cost_limit
            or estimated_cost > global_cost_limit
            or config.USER_DAILY_REQUEST_BUDGET < 1
            or config.GLOBAL_DAILY_REQUEST_BUDGET < 1
        ):
            raise BudgetExceededError("The estimated request exceeds a configured daily usage budget.")

        period = datetime.now(timezone.utc).date().isoformat()
        reservation_id = str(uuid.uuid4())
        total_tokens = input_tokens + output_tokens
        conn = get_connection()
        try:
            if not getattr(conn, "is_postgres", False):
                conn.execute("BEGIN IMMEDIATE")
            assignment = conn.execute(
                "SELECT plan_key,status FROM account_plan_assignments WHERE user_id=?",
                (user_id,),
            ).fetchone()
            plan_key = assignment["plan_key"] if assignment else "free"
            plan_status = assignment["status"] if assignment else "active"
            if plan_status != "active":
                raise BudgetExceededError("This account's plan is not active.")
            plan_request_limit = PLAN_CATALOG.get(plan_key, PLAN_CATALOG["free"])["daily_requests"]
            # Seed from existing reservations on the first request after rollout,
            # then increment atomically so concurrent workers cannot oversubscribe.
            plan_counter = conn.execute(
                "INSERT INTO plan_usage_counters(period_start,user_id,requests) "
                "SELECT ?, ?, COUNT(*)+1 FROM usage_budget_reservations "
                "WHERE user_id=? AND created_at>=CURRENT_DATE HAVING COUNT(*) < ? "
                "ON CONFLICT(period_start,user_id) DO UPDATE SET "
                "requests=plan_usage_counters.requests+1,updated_at=CURRENT_TIMESTAMP "
                "WHERE plan_usage_counters.requests < ?",
                (period, user_id, user_id, plan_request_limit, plan_request_limit),
            )
            if plan_counter.rowcount != 1:
                conn.rollback()
                raise BudgetExceededError("Your plan's daily request capacity has been reached.")
            for scope, scope_id, token_limit, cost_limit, request_limit in (
                ("user", str(user_id), user_token_limit, user_cost_limit, config.USER_DAILY_REQUEST_BUDGET),
                ("global", "all", global_token_limit, global_cost_limit, config.GLOBAL_DAILY_REQUEST_BUDGET),
            ):
                cursor = conn.execute(
                    "INSERT INTO usage_budget_counters("
                    "period_start, scope, scope_id, reserved_tokens, reserved_cost_micros, requests"
                    ") VALUES (?, ?, ?, ?, ?, 1) "
                    "ON CONFLICT(period_start, scope, scope_id) DO UPDATE SET "
                    "reserved_tokens=usage_budget_counters.reserved_tokens + excluded.reserved_tokens, "
                    "reserved_cost_micros=usage_budget_counters.reserved_cost_micros + excluded.reserved_cost_micros, "
                    "requests=usage_budget_counters.requests + 1, updated_at=CURRENT_TIMESTAMP "
                    "WHERE usage_budget_counters.reserved_tokens + excluded.reserved_tokens <= ? "
                    "AND usage_budget_counters.reserved_cost_micros + excluded.reserved_cost_micros <= ? "
                    "AND usage_budget_counters.requests + 1 <= ?",
                    (period, scope, scope_id, total_tokens, estimated_cost,
                     token_limit, cost_limit, request_limit),
                )
                if cursor.rowcount != 1:
                    conn.rollback()
                    raise BudgetExceededError(
                        f"The daily {scope} usage budget is exhausted. Try again after the UTC daily reset."
                    )
            conn.execute(
                "INSERT INTO usage_budget_reservations("
                "id, period_start, user_id, provider, model, estimated_input_tokens, "
                "estimated_output_tokens, estimated_cost_micros, status"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'reserved')",
                (reservation_id, period, user_id, provider, model, input_tokens, output_tokens, estimated_cost),
            )
            conn.commit()
        except BudgetExceededError:
            raise
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return {
            "id": reservation_id,
            "period_start": period,
            "estimated_input_tokens": input_tokens,
            "estimated_output_tokens": output_tokens,
            "estimated_cost_micros": estimated_cost,
        }

    def reconcile(self, reservation_id, actual_input_tokens=None, actual_output_tokens=None):
        conn = get_connection()
        try:
            if not getattr(conn, "is_postgres", False):
                conn.execute("BEGIN IMMEDIATE")
            claim = conn.execute(
                "UPDATE usage_budget_reservations SET status='reconciling' "
                "WHERE id=? AND status='reserved'",
                (reservation_id,),
            )
            if claim.rowcount != 1:
                conn.rollback()
                return False
            row = conn.execute(
                "SELECT * FROM usage_budget_reservations WHERE id=? AND status='reconciling' LIMIT 1",
                (reservation_id,),
            ).fetchone()
            if not row:
                conn.rollback()
                return False
            record = dict(row)
            input_tokens = max(0, int(actual_input_tokens)) if actual_input_tokens is not None else record["estimated_input_tokens"]
            output_tokens = max(0, int(actual_output_tokens)) if actual_output_tokens is not None else record["estimated_output_tokens"]
            actual_cost = self._cost_micros(input_tokens, output_tokens, self._pricing(record["provider"], record["model"]))
            estimated_tokens = record["estimated_input_tokens"] + record["estimated_output_tokens"]
            actual_tokens = input_tokens + output_tokens
            token_delta = actual_tokens - estimated_tokens
            cost_delta = actual_cost - record["estimated_cost_micros"]
            for scope, scope_id in (("user", str(record["user_id"])), ("global", "all")):
                conn.execute(
                    "UPDATE usage_budget_counters SET "
                    "reserved_tokens=reserved_tokens+?, actual_tokens=actual_tokens+?, "
                    "reserved_cost_micros=reserved_cost_micros+?, actual_cost_micros=actual_cost_micros+?, "
                    "updated_at=CURRENT_TIMESTAMP WHERE period_start=? AND scope=? AND scope_id=?",
                    (token_delta, actual_tokens, cost_delta, actual_cost,
                     record["period_start"], scope, scope_id),
                )
            conn.execute(
                "UPDATE usage_budget_reservations SET actual_input_tokens=?, actual_output_tokens=?, "
                "actual_cost_micros=?, status='completed', completed_at=CURRENT_TIMESTAMP WHERE id=? AND status='reconciling'",
                (input_tokens, output_tokens, actual_cost, reservation_id),
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def mark_failed(self, reservation_id):
        """Keep the reservation charged conservatively when provider usage is unknown."""
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE usage_budget_reservations SET status='failed', completed_at=CURRENT_TIMESTAMP "
                "WHERE id=? AND status='reserved'",
                (reservation_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def get_usage(self, user_id):
        period = datetime.now(timezone.utc).date().isoformat()
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT reserved_tokens, actual_tokens, reserved_cost_micros, actual_cost_micros, requests "
                "FROM usage_budget_counters WHERE period_start=? AND scope='user' AND scope_id=? LIMIT 1",
                (period, str(user_id)),
            ).fetchone()
        finally:
            conn.close()
        data = dict(row) if row else {
            "reserved_tokens": 0, "actual_tokens": 0, "reserved_cost_micros": 0,
            "actual_cost_micros": 0, "requests": 0,
        }
        return {
            "period_start_utc": period,
            "tokens_reserved_or_used": data["reserved_tokens"],
            "actual_tokens": data["actual_tokens"],
            "estimated_spend_usd": round(data["reserved_cost_micros"] / 1_000_000, 6),
            "actual_spend_usd": round(data["actual_cost_micros"] / 1_000_000, 6),
            "requests": data["requests"],
            "daily_token_limit": config.USER_DAILY_TOKEN_BUDGET,
            "daily_spend_limit_usd": config.USER_DAILY_SPEND_USD,
            "daily_request_limit": config.USER_DAILY_REQUEST_BUDGET,
        }

    def _pricing(self, provider, model):
        # Embedding APIs have separate pricing from chat-completion models.
        if model == "text-embedding-3-small":
            return {"input": 0.02, "output": 0.0}
        if model == "gemini-embedding-001":
            return {"input": 0.15, "output": 0.0}
        for entry in self.pricing_catalog.get(provider, {}).get("models", []):
            if entry.get("id") == model and isinstance(entry.get("pricing_usd_per_million"), dict):
                pricing = entry["pricing_usd_per_million"]
                return {
                    "input": float(pricing.get("input", config.UNKNOWN_MODEL_INPUT_USD_PER_MILLION)),
                    "output": float(pricing.get("output", config.UNKNOWN_MODEL_OUTPUT_USD_PER_MILLION)),
                }
        # User-selected models outside the reviewed catalog are budgeted at a
        # deliberately high fallback rate rather than being treated as free.
        return {
            "input": config.UNKNOWN_MODEL_INPUT_USD_PER_MILLION,
            "output": config.UNKNOWN_MODEL_OUTPUT_USD_PER_MILLION,
        }

    @staticmethod
    def _cost_micros(input_tokens, output_tokens, pricing):
        return max(0, math.ceil(
            input_tokens * float(pricing["input"]) + output_tokens * float(pricing["output"])
        ))
