"""Owner-scoped intelligence, evidence, routing and account-lifecycle services.

These services deliberately separate deterministic foundations from model execution.
"""
import json
import os
from datetime import datetime, timezone

from database import get_connection
from providers.model_catalog import MODEL_CATALOG

ROLES = {
    "planner": "Break the objective into ordered, testable tasks.",
    "researcher": "Gather evidence from explicitly available sources.",
    "critic": "Identify assumptions, risks and missing evidence.",
    "executor": "Use only approved registered capabilities.",
    "reviewer": "Check outputs against acceptance criteria.",
}
PROVIDER_ENV = {
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "google": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    "groq": ("GROQ_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
}
# Deliberate allowlist: never export authentication/session tables, connector
# installation secrets, OAuth state, budget internals, or arbitrary tables.
EXPORT_TABLES = (
    "projects", "missions", "mission_runs", "files", "memory", "research",
    "evidence", "workflows", "workflow_runs", "decision_ledger",
    "agent_team_runs", "agent_evaluations", "artifacts", "social_content",
    "social_content_versions", "logs", "conversations", "messages",
)
SENSITIVE_COLUMN_PARTS = (
    "password", "secret", "token", "credential", "private_key", "api_key",
    "cookie", "session", "authorization", "refresh", "access_key",
)
EXPORT_ROW_LIMIT = 10000
EXPORT_BYTE_LIMIT = 5_000_000


def _json_size(value):
    return len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8"))


class DecisionLedger:
    def record(self, user_id, decision_type, decision, evidence=None,
               mission_id=None, workflow_run_id=None, outcome=None):
        if not isinstance(decision_type, str) or not decision_type.strip() or len(decision_type) > 100:
            raise ValueError("decision_type must be 1–100 characters.")
        if not isinstance(decision, dict) or _json_size(decision) > 20000:
            raise ValueError("decision must be an object no larger than 20 KB.")
        evidence = [] if evidence is None else evidence
        if not isinstance(evidence, list) or len(evidence) > 100 or _json_size(evidence) > 50000:
            raise ValueError("evidence must be a list of at most 100 items and 50 KB.")
        conn = get_connection()
        try:
            if mission_id is not None and not conn.execute(
                "SELECT id FROM missions WHERE id=? AND user_id=?", (mission_id, user_id)
            ).fetchone():
                raise ValueError("Mission not found for this user.")
            if workflow_run_id is not None and not conn.execute(
                "SELECT id FROM workflow_runs WHERE id=? AND user_id=?", (workflow_run_id, user_id)
            ).fetchone():
                raise ValueError("Workflow run not found for this user.")
            cursor = conn.execute(
                "INSERT INTO decision_ledger(user_id,mission_id,workflow_run_id,decision_type,decision_json,evidence_json,outcome) "
                "VALUES (?,?,?,?,?,?,?)",
                (user_id, mission_id, workflow_run_id, decision_type.strip(),
                 json.dumps(decision, ensure_ascii=False), json.dumps(evidence, ensure_ascii=False),
                 str(outcome)[:2000] if outcome else None),
            )
            item_id = cursor.lastrowid
            conn.commit()
            return self.get(user_id, item_id)
        finally:
            conn.close()

    def get(self, user_id, item_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM decision_ledger WHERE id=? AND user_id=?", (item_id, user_id)
            ).fetchone()
            if not row:
                return None
            item = dict(row)
            for source, target, default in (
                ("decision_json", "decision", {}),
                ("evidence_json", "evidence", []),
            ):
                try:
                    item[target] = json.loads(item.pop(source) or json.dumps(default))
                except (TypeError, json.JSONDecodeError):
                    item[target] = default
                    item.pop(source, None)
            return item
        finally:
            conn.close()

    def list(self, user_id, limit=50):
        try:
            limit = max(1, min(100, int(limit)))
        except (TypeError, ValueError):
            limit = 50
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id FROM decision_ledger WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        finally:
            conn.close()
        return [self.get(user_id, row["id"]) for row in rows]


class SpecialistPlanner:
    def create(self, user_id, objective, specialists=None):
        objective = (objective or "").strip()
        roles = specialists or ["planner", "critic", "reviewer"]
        if not objective or len(objective) > 12000:
            raise ValueError("Objective must be between 1 and 12000 characters.")
        if (not isinstance(roles, list) or not 1 <= len(roles) <= 5
                or len(set(roles)) != len(roles)
                or any(role not in ROLES for role in roles)):
            raise ValueError("Choose 1–5 unique supported specialist roles.")
        assignments = [
            {"role": role, "responsibility": ROLES[role], "task": objective,
             "requires_approval_for_side_effects": role == "executor"}
            for role in roles
        ]
        conn = get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO agent_team_runs(user_id,objective,assignments_json,status) VALUES (?,?,?,'planned')",
                (user_id, objective, json.dumps(assignments, ensure_ascii=False)),
            )
            item_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()
        return {
            "id": item_id, "objective": objective, "status": "planned",
            "assignments": assignments, "execution_status": "planning_only",
            "note": "Specialist execution and inter-agent messaging are not enabled.",
        }

    def list(self, user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id,objective,assignments_json,status,created_at,updated_at "
                "FROM agent_team_runs WHERE user_id=? ORDER BY id DESC LIMIT 50", (user_id,)
            ).fetchall()
        finally:
            conn.close()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["assignments"] = json.loads(item.pop("assignments_json") or "[]")
            except (TypeError, json.JSONDecodeError):
                item["assignments"] = []
                item.pop("assignments_json", None)
            result.append(item)
        return result


class AgentEvaluator:
    RUBRIC_VERSION = "deterministic-v2"
    ALLOWED_CRITERIA = {"non_empty", "bounded_size", "structured_output", "contains_citations"}

    def evaluate(self, user_id, subject_type, subject_id, output, criteria=None):
        if subject_type not in {"mission", "workflow", "artifact", "response"}:
            raise ValueError("Unsupported evaluation subject type.")
        if not isinstance(output, (str, dict, list)):
            raise ValueError("Output must be text, an object, or a list.")
        text = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False, default=str)
        if len(text) > 100000:
            raise ValueError("Output exceeds the 100000-character evaluation limit.")
        criteria = criteria or ["non_empty", "bounded_size", "structured_output"]
        if (not isinstance(criteria, list) or not 1 <= len(criteria) <= 10
                or any(item not in self.ALLOWED_CRITERIA for item in criteria)
                or len(set(criteria)) != len(criteria)):
            raise ValueError("Choose 1–10 unique supported evaluation criteria.")
        # Validate references in the caller's ownership scope; response outputs
        # are not tied to a database object.
        conn = get_connection()
        try:
            if subject_id is not None and subject_type in {"mission", "workflow", "artifact"}:
                table = {"mission": "missions", "workflow": "workflows", "artifact": "artifacts"}[subject_type]
                try:
                    object_id = int(subject_id)
                except (TypeError, ValueError):
                    raise ValueError(f"{subject_type.title()} ID must be a positive integer.")
                if object_id < 1 or not conn.execute(
                    f"SELECT id FROM {table} WHERE id=? AND user_id=?",
                    (object_id, user_id),
                ).fetchone():
                    raise ValueError(f"{subject_type.title()} not found for this user.")
            findings = []
            for criterion in criteria:
                passed = {
                    "non_empty": bool(text.strip()),
                    "bounded_size": len(text) <= 100000,
                    "structured_output": isinstance(output, (dict, list)),
                    "contains_citations": ("http://" in text or "https://" in text or "source" in text.lower()),
                }[criterion]
                findings.append({"criterion": criterion, "passed": passed, "weight": 1})
            score = sum(item["passed"] for item in findings) / len(findings)
            cursor = conn.execute(
                "INSERT INTO agent_evaluations(user_id,subject_type,subject_id,rubric_version,score,findings_json,evaluator_type) "
                "VALUES (?,?,?,?,?,?, 'deterministic')",
                (user_id, subject_type, str(subject_id)[:200] if subject_id is not None else None,
                 self.RUBRIC_VERSION, score, json.dumps(findings)),
            )
            item_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()
        return {
            "id": item_id, "subject_type": subject_type, "subject_id": subject_id,
            "rubric_version": self.RUBRIC_VERSION, "score": score, "findings": findings,
            "evaluator_type": "deterministic",
            "warning": "This deterministic score is not proof of factual correctness or calibrated reliability.",
        }


    def label(self, user_id, evaluation_id, outcome, note=None):
        try:
            outcome = float(outcome)
        except (TypeError, ValueError):
            raise ValueError("Label outcome must be a number between 0 and 1.")
        if not 0 <= outcome <= 1:
            raise ValueError("Label outcome must be between 0 and 1.")
        note = str(note or "").strip()
        if len(note) > 1000:
            raise ValueError("Label note must be at most 1000 characters.")
        conn = get_connection()
        try:
            cursor = conn.execute(
                "UPDATE agent_evaluations SET labelled_outcome=?,labelled_at=CURRENT_TIMESTAMP::text,label_note=? "
                "WHERE id=? AND user_id=?",
                (outcome, note or None, evaluation_id, user_id),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                raise ValueError("Evaluation not found for this user.")
            conn.commit()
            row = conn.execute(
                "SELECT id,score,labelled_outcome,labelled_at,label_note FROM agent_evaluations WHERE id=? AND user_id=?",
                (evaluation_id, user_id),
            ).fetchone()
            return dict(row)
        finally:
            conn.close()

    def calibration(self, user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT score,labelled_outcome FROM agent_evaluations "
                "WHERE user_id=? AND labelled_outcome IS NOT NULL ORDER BY labelled_at DESC LIMIT 10000",
                (user_id,),
            ).fetchall()
        finally:
            conn.close()
        pairs = [(float(row["score"]), float(row["labelled_outcome"])) for row in rows]
        count = len(pairs)
        if not count:
            return {
                "status": "insufficient_labels", "labelled_samples": 0, "minimum_samples": 10,
                "metrics": None, "warning": "Scores are deterministic checks, not calibrated reliability probabilities.",
            }
        brier = sum((predicted - observed) ** 2 for predicted, observed in pairs) / count
        mae = sum(abs(predicted - observed) for predicted, observed in pairs) / count
        return {
            "status": "measured" if count >= 10 else "insufficient_labels",
            "labelled_samples": count, "minimum_samples": 10,
            "metrics": {
                "brier_score": round(brier, 6),
                "mean_absolute_error": round(mae, 6),
                "mean_predicted_score": round(sum(p for p, _ in pairs) / count, 6),
                "observed_success_rate": round(sum(y for _, y in pairs) / count, 6),
            },
            "warning": "These are empirical diagnostics over user-labelled samples, not a guarantee of factuality or a calibrated probability.",
        }


class CostAwareRouter:
    def preview(self, task_type="general", complexity="balanced", max_cost_usd=None, prefer_provider=None):
        valid_tiers = {"fast", "balanced", "capable"}
        if complexity not in valid_tiers:
            complexity = "capable" if task_type in {"code_review", "architecture", "complex_reasoning"} else "balanced"
        if prefer_provider is not None and prefer_provider not in MODEL_CATALOG:
            return {"mode": "unavailable", "tier": complexity, "selected": None,
                    "provider_call_made": False, "reason": "Unknown preferred provider."}
        providers = [prefer_provider] if prefer_provider else list(MODEL_CATALOG)
        candidates = []
        for provider in providers:
            if not any(os.getenv(key, "").strip() for key in PROVIDER_ENV.get(provider, ())):
                continue
            for model in MODEL_CATALOG[provider]["models"]:
                if model.get("tier") != complexity:
                    continue
                pricing = model.get("pricing_usd_per_million")
                if not isinstance(pricing, dict) or "input" not in pricing or "output" not in pricing:
                    continue
                try:
                    input_price, output_price = float(pricing["input"]), float(pricing["output"])
                except (TypeError, ValueError):
                    continue
                if input_price < 0 or output_price < 0:
                    continue
                # Estimate a conservative 1k input + 1k output token request.
                estimate = (input_price + output_price) / 1000
                if max_cost_usd is not None and estimate > max(0, float(max_cost_usd)):
                    continue
                candidates.append({
                    "provider": provider, "model": model["id"], "label": model.get("label"),
                    "tier": complexity, "estimated_usd_per_1k_input_plus_1k_output_tokens": round(estimate, 8),
                })
        candidates.sort(key=lambda item: (item["estimated_usd_per_1k_input_plus_1k_output_tokens"],
                                         item["provider"], item["model"]))
        if not candidates:
            return {"mode": "unavailable", "tier": complexity, "selected": None,
                    "provider_call_made": False, "budget_reserved": False,
                    "reason": "No configured provider meets the tier and cost ceiling."}
        return {
            "mode": "preview", "tier": complexity, "selected": candidates[0],
            "alternatives": candidates[1:5], "provider_call_made": False, "budget_reserved": False,
            "warning": "Catalog estimates only. Live catalog verification, latency feedback, and budget reservation are not part of preview.",
        }


class AccountLifecycle:
    def export(self, user_id):
        conn = get_connection()
        try:
            user = conn.execute(
                "SELECT id,username,status,role,created_at FROM users WHERE id=?", (user_id,)
            ).fetchone()
            if not user:
                return None
            result = {
                "schema_version": "1.0", "exported_at": datetime.now(timezone.utc).isoformat(),
                "account": dict(user), "data": {}, "export_manifest": {
                    "included_tables": [], "omitted_tables": [], "truncated_tables": [],
                    "row_limit_per_table": EXPORT_ROW_LIMIT,
                },
            }
            for table in EXPORT_TABLES:
                exists = conn.execute(
                    "SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() AND table_name=?",
                    (table,),
                ).fetchone()
                if not exists:
                    result["export_manifest"]["omitted_tables"].append({"table": table, "reason": "not_installed"})
                    continue
                columns = conn.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema=current_schema() AND table_name=? ORDER BY ordinal_position",
                    (table,),
                ).fetchall()
                names = [row["column_name"] for row in columns]
                owner_column = "user_id" if "user_id" in names else ("owner_id" if "owner_id" in names else None)
                if owner_column is None:
                    result["export_manifest"]["omitted_tables"].append({
                        "table": table, "reason": "no_direct_owner_column; not exported to prevent cross-account leakage",
                    })
                    continue
                safe_columns = [
                    name for name in names
                    if not any(part in name.lower() for part in SENSITIVE_COLUMN_PARTS)
                ]
                if not safe_columns:
                    result["export_manifest"]["omitted_tables"].append({"table": table, "reason": "no_exportable_columns"})
                    continue
                order_column = "id" if "id" in safe_columns else safe_columns[0]
                query_columns = ", ".join('"' + name.replace('"', '""') + '"' for name in safe_columns)
                query_owner = '"' + owner_column.replace('"', '""') + '"'
                rows = conn.execute(
                    f'SELECT {query_columns} FROM "{table}" WHERE {query_owner}=? ORDER BY "{order_column}" LIMIT ?',
                    (user_id, EXPORT_ROW_LIMIT + 1),
                ).fetchall()
                row_list = [dict(row) for row in rows[:EXPORT_ROW_LIMIT]]
                if len(rows) > EXPORT_ROW_LIMIT:
                    result["export_manifest"]["truncated_tables"].append(table)
                result["data"][table] = row_list
                result["export_manifest"]["included_tables"].append({"table": table, "rows": len(row_list)})
            # Never silently return a huge or partial export as if it were complete.
            while _json_size(result) > EXPORT_BYTE_LIMIT and result["data"]:
                largest = max(result["data"], key=lambda key: _json_size(result["data"][key]))
                if len(result["data"][largest]) <= 1:
                    result["export_manifest"]["omitted_tables"].append({"table": largest, "reason": "export_size_limit"})
                    del result["data"][largest]
                    result["export_manifest"]["included_tables"] = [
                        entry for entry in result["export_manifest"]["included_tables"] if entry["table"] != largest
                    ]
                    result["export_manifest"]["truncated_tables"].append(largest)
                else:
                    result["data"][largest] = result["data"][largest][:len(result["data"][largest]) // 2]
                    if largest not in result["export_manifest"]["truncated_tables"]:
                        result["export_manifest"]["truncated_tables"].append(largest)
                    for entry in result["export_manifest"]["included_tables"]:
                        if entry["table"] == largest:
                            entry["rows"] = len(result["data"][largest])
                            break
                if _json_size(result) <= EXPORT_BYTE_LIMIT:
                    break
            result["export_manifest"]["complete"] = not (
                result["export_manifest"]["omitted_tables"] or result["export_manifest"]["truncated_tables"]
            )
            result["export_manifest"]["notice"] = (
                "Export includes only listed owner-scoped tables and excludes sensitive columns. "
                "Check export_manifest before treating it as complete."
            )
            return result
        finally:
            conn.close()

    def request(self, user_id, request_type):
        if request_type not in {"data_export", "account_deletion"}:
            raise ValueError("Unsupported lifecycle request.")
        conn = get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO account_lifecycle_requests(user_id,request_type,status,details_json) VALUES (?,?,'pending','{}')",
                (user_id, request_type),
            )
            item_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()
        note = (
            "Deletion request recorded but not executed. Account deletion requires verified identity, explicit confirmation, retention checks, and an operational review."
            if request_type == "account_deletion"
            else "Request recorded. Generate the export and inspect export_manifest for omissions or truncation."
        )
        return {"id": item_id, "request_type": request_type, "status": "pending", "note": note}

    def list(self, user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id,request_type,status,details_json,created_at,updated_at "
                "FROM account_lifecycle_requests WHERE user_id=? ORDER BY id DESC LIMIT 50", (user_id,)
            ).fetchall()
        finally:
            conn.close()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["details"] = json.loads(item.pop("details_json") or "{}")
            except (TypeError, json.JSONDecodeError):
                item["details"] = {}
                item.pop("details_json", None)
            result.append(item)
        return result
