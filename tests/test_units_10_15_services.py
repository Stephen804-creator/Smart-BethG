"""Regression coverage for Units 10–15 initial foundations."""
from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.workflow_service import WorkflowService
from services.units_11_15 import DecisionLedger, SpecialistPlanner, AgentEvaluator, AccountLifecycle


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
        self.assertEqual(result["rubric_version"], "deterministic-v1")

    def test_export_excludes_password_hash_and_provider_credentials(self):
        data = AccountLifecycle().export(self.owner["id"])
        self.assertNotIn("password_hash", data["account"])
        self.assertNotIn("connector_credentials", data["data"])
