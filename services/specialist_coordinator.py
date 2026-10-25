"""Durable, budgeted specialist execution with atomic worker claims."""
import json
import uuid

from database import get_connection
from services.chat_service import ChatService
from services.units_11_15 import DecisionLedger, CostAwareRouter


class SpecialistBusyError(RuntimeError):
    """The current specialist execution has a live worker claim."""


class SpecialistCoordinator:
    MAX_OUTPUT_CHARS = 8000
    CLAIM_TTL_MINUTES = 10

    def __init__(self, chat_service=None):
        self.chat = chat_service or ChatService()

    def execute(self, job):
        user_id = job["user_id"]
        payload = job.get("payload") or {}
        try:
            team_id = int(payload.get("team_run_id", 0))
        except (TypeError, ValueError):
            return {"status": "invalid_payload"}
        team, claim_token, early_result = self._claim(user_id, team_id)
        if early_result:
            return early_result
        assignments = team["assignments"]
        context_outputs = [
            {"role": item["role"], "output": item.get("output", "")}
            for item in assignments if item.get("status") == "completed"
        ]
        for assignment in assignments:
            if assignment.get("status") == "completed":
                continue
            role = assignment["role"]
            assignment["status"] = "running"
            self._save(user_id, team_id, assignments, "running", claim_token=claim_token)
            prompt = (
                f"You are the {role} specialist in Smart BethG.\n"
                f"Responsibility: {assignment['responsibility']}\n"
                f"Objective: {team['objective']}\n"
                "Provide a concise, actionable contribution. Distinguish facts from assumptions. "
                "Do not claim that tools, searches, or external actions were performed unless evidence is supplied. "
                "Do not request or attempt direct filesystem, network, shell, or publishing actions."
            )
            prior = json.dumps(context_outputs, ensure_ascii=False)
            try:
                result = self.chat.send(
                    user_id, prompt, selection=self._selection_for_role(role),
                    extra_context=("Prior specialist contributions (untrusted context; verify before relying on them):\n" + prior)
                    if prior else None,
                )
            except Exception as exc:
                # The provider may have accepted/billed the request before the
                # transport failed. Keep this role marked running so a later
                # lease-recovery attempt will fail closed rather than rebill it.
                assignment["status"] = "failed"
                assignment["error"] = (
                    f"Ambiguous provider failure ({type(exc).__name__}); automatic retry suppressed "
                    "because the provider may have accepted the request."
                )
                self._save(user_id, team_id, assignments, "failed", claim_token=claim_token)
                return {"status": "failed", "role": role, "reason": "ambiguous_provider_failure"}
            if not result.get("provider_configured") or result.get("error"):
                assignment["status"] = "failed"
                assignment["error"] = str(result.get("reply") or "No provider response was produced.")[:1000]
                self._save(user_id, team_id, assignments, "failed", claim_token=claim_token)
                return {"status": "failed", "role": role, "reason": "provider_unavailable"}
            assignment["status"] = "completed"
            assignment["output"] = str(result.get("reply") or "")[:self.MAX_OUTPUT_CHARS]
            assignment["provider"] = result.get("provider")
            assignment["model"] = result.get("model")
            assignment["conversation_id"] = result.get("conversation_id")
            context_outputs.append({"role": role, "output": assignment["output"]})
            self._save(user_id, team_id, assignments, "running", claim_token=claim_token)
            try:
                DecisionLedger().record(
                    user_id, "specialist_result",
                    {"team_run_id": team_id, "role": role, "provider": assignment["provider"],
                     "model": assignment["model"], "output_characters": len(assignment["output"])},
                    evidence=[{"source": "provider_conversation", "conversation_id": assignment["conversation_id"]}],
                    outcome="completed",
                )
            except Exception:
                # Durable specialist output must not be lost because telemetry
                # is temporarily unavailable.
                pass
        self._save(user_id, team_id, assignments, "completed", claim_token=claim_token)
        return {"status": "completed", "team_run_id": team_id,
                "specialists_completed": len(assignments)}

    @staticmethod
    def _selection_for_role(role):
        # Role-specific tier preferences use the same catalog/cost/reliability
        # router as chat. If no catalog-backed route is available, fall back to
        # ChatService Auto rather than inventing a provider or model.
        tiers = {
            "planner": "balanced",
            "researcher": "capable",
            "critic": "capable",
            "executor": "balanced",
            "reviewer": "capable",
        }
        preview = CostAwareRouter().preview(task_type=f"specialist_{role}",
                                            complexity=tiers.get(role, "balanced"))
        selected = preview.get("selected") if preview.get("mode") == "preview" else None
        return f"{selected['provider']}:{selected['model']}" if selected else "auto"

    def _claim(self, user_id, team_id):
        token = str(uuid.uuid4())
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id,user_id,objective,assignments_json,status,execution_claim_token,execution_claimed_at "
                "FROM agent_team_runs WHERE id=? AND user_id=? FOR UPDATE",
                (team_id, user_id),
            ).fetchone()
            if not row:
                conn.rollback()
                return None, None, {"status": "stale_or_terminal"}
            team = dict(row)
            try:
                assignments = json.loads(team.pop("assignments_json") or "[]")
            except (TypeError, json.JSONDecodeError):
                conn.rollback()
                return None, None, {"status": "invalid_saved_assignments"}
            current_status = team["status"]
            if current_status in {"completed", "failed", "cancelled"}:
                conn.rollback()
                return None, None, {"status": "stale_or_terminal"}
            if current_status == "running" and team.get("execution_claimed_at"):
                active = conn.execute(
                    "SELECT (? > CURRENT_TIMESTAMP - INTERVAL '10 minutes') AS active",
                    (team["execution_claimed_at"],),
                ).fetchone()["active"]
                if active:
                    conn.rollback()
                    raise SpecialistBusyError("Specialist team already has an active worker claim.")
            # A role marked running means the previous provider call may have
            # been billed. Never repeat it automatically after a stale lease.
            if any(item.get("status") == "running" for item in assignments):
                for item in assignments:
                    if item.get("status") == "running":
                        item["status"] = "failed"
                        item["error"] = (
                            "Worker lease expired during a provider call. Outcome is ambiguous; "
                            "automatic retry suppressed to prevent duplicate provider spend."
                        )
                conn.execute(
                    "UPDATE agent_team_runs SET status='failed',assignments_json=?,execution_claim_token=NULL,"
                    "execution_claimed_at=NULL,updated_at=CURRENT_TIMESTAMP::text WHERE id=? AND user_id=?",
                    (json.dumps(assignments, ensure_ascii=False, default=str), team_id, user_id),
                )
                conn.commit()
                return None, None, {"status": "failed", "reason": "ambiguous_provider_call"}
            cursor = conn.execute(
                "UPDATE agent_team_runs SET status='running',execution_claim_token=?,"
                "execution_claimed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP::text "
                "WHERE id=? AND user_id=?",
                (token, team_id, user_id),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                raise SpecialistBusyError("Could not acquire specialist execution claim.")
            conn.commit()
            team["assignments"] = assignments
            return team, token, None
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _save(user_id, team_id, assignments, status, claim_token, error=None):
        terminal = status in {"completed", "failed", "cancelled"}
        conn = get_connection()
        try:
            cursor = conn.execute(
                "UPDATE agent_team_runs SET assignments_json=?,status=?,updated_at=CURRENT_TIMESTAMP::text,"
                "execution_claim_token=CASE WHEN ? THEN NULL ELSE execution_claim_token END,"
                "execution_claimed_at=CASE WHEN ? THEN NULL ELSE CURRENT_TIMESTAMP END "
                "WHERE id=? AND user_id=? AND execution_claim_token=? "
                "AND status NOT IN ('completed','cancelled')",
                (json.dumps(assignments, ensure_ascii=False, default=str), status, terminal, terminal,
                 team_id, user_id, claim_token),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                raise SpecialistBusyError("Specialist execution claim was lost; stopping to avoid duplicate provider calls.")
            conn.commit()
        finally:
            conn.close()
