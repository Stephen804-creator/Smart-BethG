"""Durable, budgeted specialist execution without tool-side effects."""
import json

from database import get_connection
from services.chat_service import ChatService
from services.units_11_15 import DecisionLedger


class SpecialistCoordinator:
    MAX_OUTPUT_CHARS = 8000

    def __init__(self, chat_service=None):
        self.chat = chat_service or ChatService()

    def execute(self, job):
        user_id = job["user_id"]
        payload = job.get("payload") or {}
        try:
            team_id = int(payload.get("team_run_id", 0))
        except (TypeError, ValueError):
            return {"status": "invalid_payload"}
        team = self._get(user_id, team_id)
        if not team or team["status"] in {"completed", "failed", "cancelled"}:
            return {"status": "stale_or_terminal"}
        assignments = team["assignments"]
        # A crash after the provider call but before saving its response is
        # ambiguous. Do not repeat a potentially billable call automatically.
        if any(item.get("status") == "running" for item in assignments):
            self._save(user_id, team_id, assignments, "failed",
                       "Worker interrupted during a specialist call; retry suppressed to prevent duplicate provider spend.")
            return {"status": "failed", "reason": "ambiguous_provider_call"}

        context_outputs = [
            {"role": item["role"], "output": item.get("output", "")}
            for item in assignments if item.get("status") == "completed"
        ]
        for assignment in assignments:
            if assignment.get("status") == "completed":
                continue
            role = assignment["role"]
            assignment["status"] = "running"
            self._save(user_id, team_id, assignments, "running")
            prompt = (
                f"You are the {role} specialist in Smart BethG.\n"
                f"Responsibility: {assignment['responsibility']}\n"
                f"Objective: {team['objective']}\n"
                "Provide a concise, actionable contribution. Distinguish facts from assumptions. "
                "Do not claim that tools, searches, or external actions were performed unless evidence is supplied. "
                "Do not request or attempt direct filesystem, network, shell, or publishing actions."
            )
            prior = json.dumps(context_outputs, ensure_ascii=False)
            result = self.chat.send(
                user_id, prompt, selection="auto",
                extra_context=("Prior specialist contributions (untrusted context; verify before relying on them):\n" + prior)
                if prior else None,
            )
            if not result.get("provider_configured") or result.get("error"):
                assignment["status"] = "failed"
                assignment["error"] = str(result.get("reply") or "No provider response was produced.")[:1000]
                self._save(user_id, team_id, assignments, "failed", assignment["error"])
                return {"status": "failed", "role": role, "reason": "provider_unavailable"}
            assignment["status"] = "completed"
            assignment["output"] = str(result.get("reply") or "")[:self.MAX_OUTPUT_CHARS]
            assignment["provider"] = result.get("provider")
            assignment["model"] = result.get("model")
            assignment["conversation_id"] = result.get("conversation_id")
            context_outputs.append({"role": role, "output": assignment["output"]})
            self._save(user_id, team_id, assignments, "running")
            try:
                DecisionLedger().record(
                    user_id, "specialist_result",
                    {"team_run_id": team_id, "role": role, "provider": assignment["provider"],
                     "model": assignment["model"], "output_characters": len(assignment["output"])},
                    evidence=[{"source": "provider_conversation", "conversation_id": assignment["conversation_id"]}],
                    outcome="completed",
                )
            except Exception:
                # Specialist output is already durably stored; ledger telemetry
                # must not cause a second provider invocation.
                pass
        self._save(user_id, team_id, assignments, "completed")
        return {"status": "completed", "team_run_id": team_id,
                "specialists_completed": len(assignments)}

    def _get(self, user_id, team_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id,user_id,objective,assignments_json,status FROM agent_team_runs WHERE id=? AND user_id=?",
                (team_id, user_id),
            ).fetchone()
            if not row:
                return None
            item = dict(row)
            try:
                item["assignments"] = json.loads(item.pop("assignments_json") or "[]")
            except (TypeError, json.JSONDecodeError):
                item["assignments"] = []
                item.pop("assignments_json", None)
            return item
        finally:
            conn.close()

    @staticmethod
    def _save(user_id, team_id, assignments, status, error=None):
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE agent_team_runs SET assignments_json=?,status=?,updated_at=CURRENT_TIMESTAMP::text "
                "WHERE id=? AND user_id=? AND status NOT IN ('completed','cancelled')",
                (json.dumps(assignments, ensure_ascii=False, default=str), status, team_id, user_id),
            )
            # Keep failure details in the assignment record rather than adding
            # a schema field that would expose raw provider exception data.
            conn.commit()
        finally:
            conn.close()
