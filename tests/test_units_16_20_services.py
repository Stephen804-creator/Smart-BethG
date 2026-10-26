"""Regression coverage for Units 16–20: workspace RBAC, sandbox boundaries, publishing and operations."""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.workspace_service import WorkspaceService
from services.sandbox_service import SandboxService, SandboxUnavailableError
from services.social_content_service import SocialContentService
from services.social_publishing_service import SocialPublishingService
from services.operations_service import OperationsService


class TestUnits16To20(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        suffix = os.path.basename(self._tmp_dir)[-8:]
        self.owner = create_user("u1620-owner-" + suffix, "password123")
        self.editor = create_user("u1620-editor-" + suffix, "password123")
        self.viewer = create_user("u1620-viewer-" + suffix, "password123")
        self.service = WorkspaceService()

    def test_organization_and_workspace_membership_enforce_roles(self):
        result = self.service.create_organization(
            self.owner["id"], "Team Space", "team-space",
        )
        org_id = result["organization"]["id"]
        workspace_id = result["default_workspace"]["id"]
        self.service.add_organization_member(self.owner["id"], org_id, self.editor["username"], "member")
        self.service.add_workspace_member(self.owner["id"], workspace_id, self.editor["username"], "editor")
        self.service.add_organization_member(self.owner["id"], org_id, self.viewer["username"], "viewer")
        self.service.add_workspace_member(self.owner["id"], workspace_id, self.viewer["username"], "viewer")

        self.assertEqual(self.service.require_workspace_access(self.editor["id"], workspace_id, "edit")["role"], "editor")
        with self.assertRaises(PermissionError):
            self.service.require_workspace_access(self.viewer["id"], workspace_id, "edit")
        with self.assertRaises(PermissionError):
            self.service.add_organization_member(self.owner["id"], org_id, self.owner["username"], "admin")
        self.assertEqual(len(self.service.list_organization_members(self.editor["id"], org_id)), 3)

    def test_organization_admin_inherits_workspace_admin_access(self):
        result = self.service.create_organization(
            self.owner["id"], "Inherited Access", "inherit-access",
        )
        org_id = result["organization"]["id"]
        workspace_id = result["default_workspace"]["id"]
        self.service.add_organization_member(self.owner["id"], org_id, self.editor["username"], "admin")
        access = self.service.require_workspace_access(self.editor["id"], workspace_id, "admin")
        self.assertEqual(access["role"], "admin")

    def test_sandbox_fails_closed_when_not_configured_and_records_attempt(self):
        with patch.dict(os.environ, {"SMART_BETHG_SANDBOX_ENABLED": "false"}):
            with self.assertRaises(SandboxUnavailableError):
                SandboxService().execute_python(self.owner["id"], "print('safe')")
        runs = SandboxService().list_for_user(self.owner["id"])
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["status"], "rejected")
        self.assertEqual(runs[0]["error_code"], "sandbox_unavailable")

    def test_only_approved_content_can_be_scheduled_and_schedule_is_idempotent(self):
        content_service = SocialContentService()
        item = content_service.create(self.owner["id"], "linkedin", "Launch", "Announcement")
        with self.assertRaises(PermissionError):
            SocialPublishingService().schedule(
                self.owner["id"], item["id"],
                (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(), "not-approved",
            )
        content_service.transition(self.owner["id"], item["id"], "in_review")
        content_service.transition(self.owner["id"], item["id"], "approved")
        when = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        service = SocialPublishingService()
        first = service.schedule(self.owner["id"], item["id"], when, "launch-schedule")
        second = service.schedule(self.owner["id"], item["id"], when, "launch-schedule")
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["status"], "scheduled")
        self.assertTrue(service.cancel(self.owner["id"], first["id"]))
        self.assertFalse(service.cancel(self.owner["id"], first["id"]))

    def test_due_social_schedule_blocks_without_real_publisher_adapter(self):
        content_service = SocialContentService()
        item = content_service.create(self.owner["id"], "linkedin", "Launch", "Announcement")
        content_service.transition(self.owner["id"], item["id"], "in_review")
        content_service.transition(self.owner["id"], item["id"], "approved")
        service = SocialPublishingService()
        schedule = service.schedule(
            self.owner["id"], item["id"],
            (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat(), "due-schedule",
        )
        conn = __import__("database").get_connection()
        try:
            conn.execute("UPDATE social_publish_jobs SET scheduled_at=CURRENT_TIMESTAMP - INTERVAL '1 minute' WHERE id=?",
                         (schedule["id"],))
            conn.commit()
        finally:
            conn.close()
        result = service.process_due()
        self.assertEqual(result[0]["status"], "blocked")
        self.assertEqual(result[0]["reason"], "publisher_not_configured")
        saved = next(row for row in service.list_for_user(self.owner["id"]) if row["id"] == schedule["id"])
        self.assertEqual(saved["status"], "blocked")

    def test_request_metrics_and_worker_heartbeat_are_persisted(self):
        service = OperationsService()
        service.record_request("trace-test-id", "GET", "/test-route", 503, 42)
        service.heartbeat_worker("units16-20-test-worker", "healthy", {"test": True})
        metrics = service.metrics(hours=1)
        self.assertGreaterEqual(metrics["totals"]["requests"], 1)
        self.assertGreaterEqual(metrics["totals"]["server_errors"], 1)
        self.assertTrue(any(route["route"] == "/test-route" for route in metrics["routes"]))
        self.assertTrue(any(worker["worker_id"] == "units16-20-test-worker" for worker in metrics["workers"]))

    def test_readiness_reports_missing_restore_drill_attestation(self):
        with patch.dict(os.environ, {"SMART_BETHG_BACKUP_RESTORE_VERIFIED": "false"}):
            result = OperationsService().readiness()
        self.assertEqual(result["checks"]["backup_restore_drill"]["status"], "not_ready")
        self.assertIn(result["status"], {"ready", "not_ready"})
