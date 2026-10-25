"""Regression coverage for Units 10–15 initial foundations."""
from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.workflow_service import WorkflowService
from services.units_11_15 import DecisionLedger, SpecialistPlanner, AgentEvaluator, AccountLifecycle
from services.mission_service import MissionService
from services.workflow_executor import WorkflowExecutor


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

    def test_workflow_rejects_step_without_executor(self):
        service = WorkflowService()
        workflow = service.create(self.owner["id"], "Research", steps=[
            {"type": "research", "config": {"query": "not executed"}}
        ])
        service.validate(self.owner["id"], workflow["id"])
        with self.assertRaisesRegex(ValueError, "adapters are not enabled"):
            service.start_run(self.owner["id"], workflow["id"])

    def test_decision_ledger_is_owner_scoped(self):
        ledger = DecisionLedger()
        item = ledger.record(self.owner["id"], "route_selection", {"selected": "balanced"}, [{"source": "catalog"}])
        self.assertIsNotNone(ledger.get(self.owner["id"], item["id"]))
        self.assertIsNone(ledger.get(self.other["id"], item["id"]))

    def test_specialist_planner_does_not_claim_model_execution(self):
        plan = SpecialistPlanner().create(self.owner["id"], "Prepare release notes")
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["execution_status"], "planning_only")

    def test_deterministic_evaluation_persists_score_and_rubric(self):
        result = AgentEvaluator().evaluate(self.owner["id"], "response", "demo", {"summary": "ok"})
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 1)
        self.assertEqual(result["rubric_version"], "deterministic-v2")

    def test_export_excludes_password_hash_and_provider_credentials(self):
        data = AccountLifecycle().export(self.owner["id"])
        self.assertNotIn("password_hash", data["account"])
        self.assertNotIn("connector_credentials", data["data"])

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
