"""Regression coverage for Units 10–15 initial foundations."""
import os
import threading
from unittest.mock import patch

from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.workflow_service import WorkflowService
from services.units_11_15 import DecisionLedger, SpecialistPlanner, AgentEvaluator, AccountLifecycle, CostAwareRouter
from services.mission_service import MissionService
from services.workflow_executor import WorkflowExecutor
from services.specialist_coordinator import SpecialistCoordinator, SpecialistBusyError


class TestUnits10To15(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.owner = create_user("units1015-owner", "password123")
        self.other = create_user("units1015-other", "password123")

    def test_workflow_run_requires_validation_and_is_persisted(self):
        service = WorkflowService()
        workflow = service.create(self.owner["id"], "Weekly review", steps=[
            {"type": "mission", "config": {"objective": "Review the project"}}
        ])
        with self.assertRaises(ValueError):
            service.start_run(self.owner["id"], workflow["id"])
        service.validate(self.owner["id"], workflow["id"])
        run = service.start_run(self.owner["id"], workflow["id"])
        self.assertEqual(run["status"], "queued")
        self.assertEqual(run["workflow_version"], workflow["version"])

    def test_workflow_executes_research_artifact_and_social_draft_adapters(self):
        service = WorkflowService()
        workflow = service.create(self.owner["id"], "Content workflow", steps=[
            {"id": "research", "type": "research", "config": {
                "query": "Quarterly product update", "summary": "Reviewed product milestones.",
                "source_urls": ["https://example.com/release-notes"],
            }},
            {"id": "artifact", "type": "artifact", "config": {
                "name": "release-summary", "content": "Release summary content",
            }},
            {"id": "social", "type": "social_content", "config": {
                "platform": "linkedin", "title": "Product update",
                "content": "We shipped the latest product improvements.",
                "hashtags": ["ProductUpdate"],
            }},
        ])
        service.validate(self.owner["id"], workflow["id"])
        run = service.start_run(self.owner["id"], workflow["id"])
        executor = WorkflowExecutor()
        for index in range(3):
            result = executor.execute({"user_id": self.owner["id"], "payload": {
                "workflow_id": workflow["id"], "run_id": run["id"],
                "workflow_version": workflow["version"], "step_index": index,
            }})
            self.assertEqual(result["status"], "step_completed")
        final_run = service.get_run(self.owner["id"], run["id"])
        self.assertEqual(final_run["status"], "completed")
        self.assertEqual(final_run["result"]["completion_semantics"], "all_steps_completed")

    def test_decision_ledger_is_owner_scoped(self):
        ledger = DecisionLedger()
        item = ledger.record(self.owner["id"], "route_selection", {"selected": "balanced"}, [{"source": "catalog"}])
        self.assertIsNotNone(ledger.get(self.owner["id"], item["id"]))
        self.assertIsNone(ledger.get(self.other["id"], item["id"]))

    def test_specialist_plan_is_queued_for_real_model_execution(self):
        plan = SpecialistPlanner().create(self.owner["id"], "Prepare release notes")
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["execution_status"], "queued")
        self.assertEqual(len(plan["assignments"]), 3)

    def test_specialist_coordinator_persists_each_role_result(self):
        class FakeChatService:
            def __init__(self):
                self.calls = 0

            def send(self, user_id, message, **kwargs):
                self.calls += 1
                return {
                    "provider_configured": True, "reply": f"Contribution {self.calls}",
                    "provider": "test-provider", "model": "test-model",
                    "conversation_id": self.calls,
                }

        plan = SpecialistPlanner().create(self.owner["id"], "Prepare release notes")
        fake = FakeChatService()
        result = SpecialistCoordinator(chat_service=fake).execute({
            "user_id": self.owner["id"], "payload": {"team_run_id": plan["id"]},
        })
        self.assertEqual(result["status"], "completed")
        self.assertEqual(fake.calls, 3)
        saved = SpecialistPlanner().list(self.owner["id"])[0]
        self.assertEqual(saved["status"], "completed")
        self.assertTrue(all(item["status"] == "completed" for item in saved["assignments"]))

    def test_specialist_execution_claim_prevents_concurrent_duplicate_calls(self):
        started = threading.Event()
        release = threading.Event()
        class SlowFakeChatService:
            def __init__(self):
                self.calls = 0
                self.lock = threading.Lock()
            def send(self, user_id, message, **kwargs):
                with self.lock:
                    self.calls += 1
                    call_number = self.calls
                if call_number == 1:
                    started.set()
                    if not release.wait(8):
                        raise RuntimeError("test provider timed out")
                return {"provider_configured": True, "reply": f"Contribution {call_number}",
                        "provider": "test-provider", "model": "test-model",
                        "conversation_id": call_number}

        plan = SpecialistPlanner().create(self.owner["id"], "Prepare release notes")
        fake = SlowFakeChatService()
        coordinator = SpecialistCoordinator(chat_service=fake)
        job = {"user_id": self.owner["id"], "payload": {"team_run_id": plan["id"]}}
        results, errors = [], []
        def first_worker():
            try:
                results.append(coordinator.execute(job))
            except Exception as exc:
                errors.append(exc)
        thread = threading.Thread(target=first_worker)
        thread.start()
        self.assertTrue(started.wait(5), "first specialist call did not start")
        try:
            with self.assertRaises(SpecialistBusyError):
                coordinator.execute(job)
        finally:
            release.set()
            thread.join(10)
        self.assertFalse(thread.is_alive(), "first specialist worker did not finish")
        self.assertEqual(errors, [])
        self.assertEqual(results[0]["status"], "completed")
        self.assertEqual(fake.calls, 3)
    def test_cost_aware_router_uses_measured_reliability_and_latency(self):
        catalog = {
            "provider_a": {"label": "A", "models": [{"id": "model-a", "tier": "balanced",
                "pricing_usd_per_million": {"input": 1, "output": 1}}]},
            "provider_b": {"label": "B", "models": [{"id": "model-b", "tier": "balanced",
                "pricing_usd_per_million": {"input": 1, "output": 1}}]},
        }
        stats = [
            {"provider": "provider_a", "model": "model-a", "attempts": 20, "success_rate": 0.5, "avg_latency_ms": 2000},
            {"provider": "provider_b", "model": "model-b", "attempts": 20, "success_rate": 0.99, "avg_latency_ms": 100},
        ]
        with patch("services.units_11_15.MODEL_CATALOG", catalog), patch("services.units_11_15.PROVIDER_ENV", {"provider_a": ("PROVIDER_A_KEY",), "provider_b": ("PROVIDER_B_KEY",)}), patch("services.units_11_15.ModelEvaluationService.stats", return_value=stats), patch.dict(os.environ, {"PROVIDER_A_KEY": "configured", "PROVIDER_B_KEY": "configured"}):
            result = CostAwareRouter().preview(complexity="balanced")
        self.assertEqual(result["selected"]["provider"], "provider_b")
        self.assertEqual(result["selected"]["observed_attempts"], 20)
        self.assertGreater(result["selected"]["routing_score"], 0)
    def test_deterministic_evaluation_persists_score_and_rubric(self):
        result = AgentEvaluator().evaluate(self.owner["id"], "response", "demo", {"summary": "ok"})
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 1)
        self.assertEqual(result["rubric_version"], "deterministic-v2")

    def test_export_excludes_password_hash_and_provider_credentials(self):
        data = AccountLifecycle().export(self.owner["id"])
        self.assertNotIn("password_hash", data["account"])
        self.assertNotIn("connector_credentials", data["data"])
        self.assertNotIn("logs", data["data"])
        self.assertIn("logs", [item["table"] for item in data["export_manifest"]["excluded_tables"]])

    def test_workflow_conditions_can_skip_downstream_side_effects(self):
        service = WorkflowService()
        workflow = service.create(self.owner["id"], "Conditional workflow", steps=[
            {"id": "research", "type": "research", "config": {
                "query": "Release readiness", "summary": "Not ready for publishing.",
            }},
            {"id": "ready_check", "type": "condition", "config": {
                "source_step_id": "research", "path": "summary",
                "operator": "contains", "value": "READY",
            }},
            {"id": "social_draft", "type": "social_content", "config": {
                "platform": "linkedin", "title": "Release", "content": "Release update",
                "when": {"step_id": "ready_check", "equals": True},
            }},
        ])
        service.validate(self.owner["id"], workflow["id"])
        run = service.start_run(self.owner["id"], workflow["id"])
        executor = WorkflowExecutor()
        for index in range(3):
            result = executor.execute({"user_id": self.owner["id"], "payload": {
                "workflow_id": workflow["id"], "run_id": run["id"],
                "workflow_version": workflow["version"], "step_index": index,
            }})
            if index == 0:
                self.assertEqual(result["status"], "step_completed")
            elif index == 1:
                self.assertEqual(result["status"], "condition_evaluated")
                self.assertFalse(result["matched"])
            else:
                self.assertEqual(result["status"], "step_skipped")
        final_run = service.get_run(self.owner["id"], run["id"])
        self.assertEqual(final_run["status"], "completed")
        skipped = service.get_step_run(self.owner["id"], run["id"], 2)
        self.assertEqual(skipped["status"], "skipped")

    def test_workflow_waits_for_child_completion_and_advances_sequentially(self):
        service = WorkflowService()
        workflow = service.create(self.owner["id"], "Two-stage workflow", steps=[
            {"id": "first", "type": "mission", "config": {"objective": "Complete first task"}},
            {"id": "second", "type": "mission", "config": {"objective": "Complete second task"}},
        ])
        service.validate(self.owner["id"], workflow["id"])
        run = service.start_run(self.owner["id"], workflow["id"])
        executor = WorkflowExecutor()
        payload = {"workflow_id": workflow["id"], "run_id": run["id"],
                   "workflow_version": workflow["version"]}
        result = executor.execute({"user_id": self.owner["id"], "payload": payload})
        self.assertEqual(result["status"], "waiting_for_child_mission")
        step = service.get_step_run(self.owner["id"], run["id"], 0)
        self.assertIsNotNone(step["mission_id"])
        mission_service = MissionService()
        mission = mission_service.get(self.owner["id"], step["mission_id"])
        mission_service.finish_run(self.owner["id"], mission["id"], mission["runs"][0]["id"],
                                   "completed", result={"outputs": [{"ok": True}]})
        after_first = service.get_run(self.owner["id"], run["id"])
        self.assertEqual(after_first["status"], "queued")
        self.assertEqual(after_first["current_step"], 1)

        payload["step_index"] = 1
        second_result = executor.execute({"user_id": self.owner["id"], "payload": payload})
        self.assertEqual(second_result["status"], "waiting_for_child_mission")
        second_step = service.get_step_run(self.owner["id"], run["id"], 1)
        second_mission = mission_service.get(self.owner["id"], second_step["mission_id"])
        mission_service.finish_run(self.owner["id"], second_mission["id"], second_mission["runs"][0]["id"],
                                   "completed", result={"outputs": [{"ok": True}]})
        final_run = service.get_run(self.owner["id"], run["id"])
        self.assertEqual(final_run["status"], "completed")
        self.assertEqual(final_run["result"]["completion_semantics"], "all_steps_completed")

    def test_workflow_step_replay_reuses_the_same_child_mission(self):
        service = WorkflowService()
        workflow = service.create(self.owner["id"], "Replay test", steps=[
            {"type": "mission", "config": {"objective": "A replay-safe task"}},
        ])
        service.validate(self.owner["id"], workflow["id"])
        run = service.start_run(self.owner["id"], workflow["id"])
        executor = WorkflowExecutor()
        payload = {"workflow_id": workflow["id"], "run_id": run["id"],
                   "workflow_version": workflow["version"]}
        first = executor.execute({"user_id": self.owner["id"], "payload": payload})
        self.assertEqual(first["status"], "waiting_for_child_mission")
        original_step = service.get_step_run(self.owner["id"], run["id"], 0)
        # Simulate queue replay after the parent run is re-queued.
        conn = __import__("database").get_connection()
        try:
            conn.execute("UPDATE workflow_runs SET status='queued' WHERE id=? AND user_id=?",
                         (run["id"], self.owner["id"]))
            conn.commit()
        finally:
            conn.close()
        replay = executor.execute({"user_id": self.owner["id"], "payload": payload})
        self.assertEqual(replay["status"], "waiting_for_child_mission")
        replayed_step = service.get_step_run(self.owner["id"], run["id"], 0)
        self.assertEqual(replayed_step["mission_id"], original_step["mission_id"])

    def test_evaluation_cannot_reference_another_users_mission(self):
        mission_service = MissionService()
        foreign_mission = mission_service.create(self.other["id"], "Private mission")
        with self.assertRaisesRegex(ValueError, "not found for this user"):
            AgentEvaluator().evaluate(self.owner["id"], "mission", str(foreign_mission["id"]), "some output")

    def test_export_reports_omissions_instead_of_claiming_full_completeness(self):
        data = AccountLifecycle().export(self.owner["id"])
        self.assertIn("export_manifest", data)
        self.assertIn("complete", data["export_manifest"])
        self.assertIn("included_tables", data["export_manifest"])
        self.assertIn("omitted_tables", data["export_manifest"])
        self.assertNotIn("password_hash", data["account"])

    def test_evaluation_labels_are_owner_scoped_and_calibration_is_honest(self):
        evaluator = AgentEvaluator()
        evaluation = evaluator.evaluate(self.owner["id"], "response", None, {"summary": "ok"})
        labelled = evaluator.label(self.owner["id"], evaluation["id"], 1.0, "Reviewed by a human")
        self.assertEqual(labelled["labelled_outcome"], 1.0)
        with self.assertRaisesRegex(ValueError, "not found for this user"):
            evaluator.label(self.other["id"], evaluation["id"], 0.0)
        calibration = evaluator.calibration(self.owner["id"])
        self.assertEqual(calibration["labelled_samples"], 1)
        self.assertEqual(calibration["status"], "insufficient_labels")
        self.assertIsNotNone(calibration["metrics"])
