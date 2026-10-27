"""Regression tests for roadmap Units 21-24."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.workflow_service import WorkflowService
from services.units_21_24 import (
    CommercialAccountService,
    ExtensionManifestService,
    ScheduledAgentJobService,
    UsageIntelligenceService,
)
from sdk.smartbethg import ExtensionBuilder, validate_manifest


class TestUnits21To24(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        suffix = self._tmp_dir[-8:]
        self.owner = create_user("u2124-owner-" + suffix, "password123")
        self.other = create_user("u2124-other-" + suffix, "password123")
        self.workflows = WorkflowService()
        self.schedules = ScheduledAgentJobService(self.workflows)
        self.extensions = ExtensionManifestService()
        self.commercial = CommercialAccountService()

    def _validated_workflow(self):
        workflow = self.workflows.create(
            self.owner["id"], "Scheduled workflow",
            steps=[{"type": "mission", "config": {"objective": "review a release"}}],
        )
        return self.workflows.validate(self.owner["id"], workflow["id"])

    def test_schedule_requires_owner_validated_workflow_and_timezone(self):
        workflow = self.workflows.create(self.owner["id"], "Draft")
        when = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        with self.assertRaisesRegex(ValueError, "Validate the workflow"):
            self.schedules.create(self.owner["id"], "Later", workflow["id"], when)
        with self.assertRaisesRegex(ValueError, "timezone"):
            self.schedules.create(self.owner["id"], "Bad time", workflow["id"], "2030-01-01T10:00:00")
        with self.assertRaisesRegex(ValueError, "not found"):
            self.schedules.create(self.other["id"], "Private", workflow["id"], when)

    def test_due_schedule_dispatches_once_and_advances_recurring_pointer(self):
        workflow = self._validated_workflow()
        when = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        schedule = self.schedules.create(
            self.owner["id"], "Daily task", workflow["id"], when,
            interval_seconds=3600, max_runs=3,
        )
        conn = __import__("database").get_connection()
        try:
            conn.execute(
                "UPDATE scheduled_agent_jobs SET next_run_at=CURRENT_TIMESTAMP - INTERVAL '1 second' WHERE id=?",
                (schedule["id"],),
            )
            conn.commit()
        finally:
            conn.close()
        first = self.schedules.process_due(limit=5)
        second = self.schedules.process_due(limit=5)
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 0)
        updated = self.schedules.get(self.owner["id"], schedule["id"])
        self.assertEqual(updated["run_count"], 1)
        self.assertEqual(updated["status"], "active")
        conn = __import__("database").get_connection()
        try:
            count = conn.execute(
                "SELECT COUNT(*) AS total FROM scheduled_job_runs WHERE scheduled_job_id=?",
                (schedule["id"],),
            ).fetchone()["total"]
            self.assertEqual(count, 1)
            queue = conn.execute(
                "SELECT COUNT(*) AS total FROM background_jobs WHERE user_id=? AND idempotency_key=?",
                (self.owner["id"], "scheduled-run:" + str(first[0]["scheduled_run_id"])),
            ).fetchone()["total"]
            self.assertEqual(queue, 1)
        finally:
            conn.close()

    def test_extension_sdk_builds_declarative_contract_and_rejects_code_fields(self):
        manifest = (
            ExtensionBuilder("sample-extension", "Sample extension", "1.0.0")
            .action("items.list", "List items", {"limit": "integer"}, ["limit"])
            .build()
        )
        self.assertEqual(manifest["actions"][0]["key"], "items.list")
        self.assertEqual(validate_manifest(manifest), manifest)
        with self.assertRaises(ValueError):
            validate_manifest({
                "key": "bad-extension", "name": "Bad", "version": "1",
                "actions": [{"key": "run", "python": "import os; os.system('id')"}],
            })

    def test_extension_manifests_are_owner_scoped_and_start_as_draft(self):
        manifest = {
            "key": "safe-extension", "name": "Safe Extension", "version": "1.0",
            "description": "Declarative test",
            "actions": [{
                "key": "records.read", "description": "Read records",
                "fields": {"query": "string"}, "required": ["query"],
                "risk": "read", "side_effecting": False,
            }],
        }
        created = self.extensions.create(self.owner["id"], manifest)
        self.assertEqual(created["status"], "draft")
        self.assertEqual(len(self.extensions.list_for_user(self.owner["id"])), 1)
        self.assertEqual(self.extensions.list_for_user(self.other["id"]), [])
        with self.assertRaises(ValueError):
            self.extensions.create(self.owner["id"], {
                **manifest,
                "actions": [{"key": "shell.exec", "description": "Run shell", "fields": {"command": "string"},
                             "required": ["command"], "risk": "destructive", "side_effecting": False}],
            })

    def test_plan_credits_are_idempotent_and_cannot_go_negative(self):
        self.commercial.assign_plan(self.owner["id"], "starter")
        overview = self.commercial.grant_credits(
            self.owner["id"], 100, "starter grant", "grant-1", source="admin_grant",
        )
        self.assertEqual(overview["credit_balance"], 100)
        duplicate = self.commercial.grant_credits(
            self.owner["id"], 100, "starter grant", "grant-1", source="admin_grant",
        )
        self.assertEqual(duplicate["credit_balance"], 100)
        consumed = self.commercial.consume_credits(
            self.owner["id"], 35, "render job", "debit-1",
        )
        self.assertEqual(consumed["credit_balance"], 65)
        replay = self.commercial.consume_credits(
            self.owner["id"], 35, "render job", "debit-1",
        )
        self.assertEqual(replay["credit_balance"], 65)
        with self.assertRaisesRegex(ValueError, "Insufficient credits"):
            self.commercial.consume_credits(self.owner["id"], 66, "large job", "debit-2")

    def test_reward_requires_review_before_credit_award(self):
        requested = self.commercial.request_reward(
            self.owner["id"], "community-contribution", 25, "reward-1",
        )
        self.assertEqual(requested["credit_balance"], 0)
        self.assertEqual(requested["rewards"][0]["status"], "pending")
        result = self.commercial.review_reward(self.other["id"], requested["rewards"][0]["id"], "approved")
        self.assertEqual(result["status"], "approved")
        self.assertEqual(result["credits_awarded"], 25)
        overview = self.commercial.overview(self.owner["id"])
        self.assertEqual(overview["credit_balance"], 25)

    def test_plan_daily_request_limit_is_enforced_atomically(self):
        from services.usage_budget_service import UsageBudgetService, BudgetExceededError
        with patch.dict("services.units_21_24.PLAN_CATALOG", {"free": {"label": "Free", "daily_requests": 1, "monthly_credits": 100, "features": []}}):
            budget = UsageBudgetService()
            budget.reserve(self.owner["id"], "openai", "gpt-6-luna", 10, 20)
            with self.assertRaises(BudgetExceededError):
                budget.reserve(self.owner["id"], "openai", "gpt-6-luna", 10, 20)

    def test_usage_summary_uses_plan_and_private_owner_scope(self):
        self.commercial.assign_plan(self.owner["id"], "pro")
        summary = UsageIntelligenceService().summary(self.owner["id"], days=7)
        self.assertEqual(summary["plan"], "pro")
        self.assertEqual(summary["daily_request_limit"], 600)
        other = UsageIntelligenceService().summary(self.other["id"], days=7)
        self.assertEqual(other["plan"], "free")
        self.assertEqual(other["requests"], 0)


if __name__ == "__main__":
    import unittest
    unittest.main()
