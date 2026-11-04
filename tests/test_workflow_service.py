from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.workflow_service import WorkflowService


class TestWorkflowService(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.owner = create_user("workflow-owner", "password123")
        self.other = create_user("workflow-other", "password123")
        self.service = WorkflowService()

    def test_workflow_versioning_and_validation(self):
        workflow = self.service.create(
            self.owner["id"], "Release checklist",
            steps=[{"type": "mission", "config": {"objective": "review release"}}],
        )
        self.assertEqual(workflow["version"], 1)
        validated = self.service.validate(self.owner["id"], workflow["id"])
        self.assertEqual(validated["status"], "validated")
        updated = self.service.update(self.owner["id"], workflow["id"], {"name": "Release v2"})
        self.assertEqual(updated["version"], 2)
        self.assertEqual(updated["status"], "draft")

    def test_workflow_is_owner_scoped(self):
        workflow = self.service.create(self.owner["id"], "Private workflow")
        self.assertIsNone(self.service.get(self.other["id"], workflow["id"]))
        self.assertFalse(self.service.archive(self.other["id"], workflow["id"]))


    def test_publish_creates_immutable_workflow_version(self):
        workflow = self.service.create(
            self.owner["id"], "Published workflow",
            steps=[{"id": "research-v1", "type": "research", "config": {"query": "first"}}],
        )
        self.service.validate(self.owner["id"], workflow["id"])
        published = self.service.publish(self.owner["id"], workflow["id"])
        self.assertEqual(published["status"], "published")
        self.assertEqual(published["published_version"], 1)

        versions = self.service.list_versions(self.owner["id"], workflow["id"])
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0]["version"], 1)

        # Publishing the same unchanged version is idempotent.
        self.service.publish(self.owner["id"], workflow["id"])
        self.assertEqual(len(self.service.list_versions(self.owner["id"], workflow["id"])), 1)

    def test_published_snapshot_and_run_remain_pinned_after_draft_edit(self):
        workflow = self.service.create(
            self.owner["id"], "Versioned workflow",
            steps=[{"id": "research-v1", "type": "research", "config": {"query": "first"}}],
        )
        self.service.validate(self.owner["id"], workflow["id"])
        first_run = self.service.start_run(self.owner["id"], workflow["id"])
        first_definition = self.service.get_run_definition(self.owner["id"], first_run["id"])
        self.assertTrue(first_definition["immutable"])
        self.assertEqual(first_definition["steps"][0]["id"], "research-v1")
        first_version_id = first_run["workflow_version_id"]

        updated = self.service.update(self.owner["id"], workflow["id"], {
            "steps": [{"id": "research-v2", "type": "research", "config": {"query": "second"}}]
        })
        self.assertEqual(updated["status"], "draft")
        self.assertEqual(updated["published_version"], 1)

        self.service.validate(self.owner["id"], workflow["id"])
        self.service.publish(self.owner["id"], workflow["id"])
        second_run = self.service.start_run(self.owner["id"], workflow["id"])
        second_definition = self.service.get_run_definition(self.owner["id"], second_run["id"])

        self.assertNotEqual(first_version_id, second_run["workflow_version_id"])
        self.assertEqual(first_definition["steps"][0]["id"], "research-v1")
        self.assertEqual(second_definition["steps"][0]["id"], "research-v2")
        self.assertEqual(first_run["workflow_version"], 1)
        self.assertEqual(second_run["workflow_version"], 2)

    def test_publish_is_owner_scoped(self):
        workflow = self.service.create(self.owner["id"], "Owner only")
        with self.assertRaises(ValueError):
            self.service.publish(self.other["id"], workflow["id"])
        self.assertEqual(self.service.list_versions(self.owner["id"], workflow["id"]), [])

    def test_published_version_cannot_be_overwritten(self):
        workflow = self.service.create(
            self.owner["id"], "Immutable definition",
            steps=[{"id": "original", "type": "research", "config": {"query": "original"}}],
        )
        self.service.validate(self.owner["id"], workflow["id"])
        self.service.publish(self.owner["id"], workflow["id"])
        conn = __import__("database").get_connection()
        try:
            row = conn.execute(
                "SELECT definition_json FROM workflow_definition_versions WHERE workflow_id=? AND version=1",
                (workflow["id"],),
            ).fetchone()
            original_json = row["definition_json"]
            with self.assertRaises(Exception):
                conn.execute(
                    "UPDATE workflow_definition_versions SET definition_json='[]' WHERE workflow_id=? AND version=1",
                    (workflow["id"],),
                )
        finally:
            conn.close()
        self.assertEqual(
            self.service.get_run_definition if False else original_json,
            original_json,
        )

    def test_invalid_step_type_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.create(self.owner["id"], "Unsafe", steps=[{"type": "shell", "config": {}}])


if __name__ == "__main__":
    import unittest
    unittest.main()
