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
        snapshot = self.service.get_version(self.owner["id"], workflow["id"], 1)
        self.assertEqual(snapshot["definition_format"], "graph_v1")
        self.assertEqual(snapshot["graph"]["format"], "smartbethg.workflow.graph")
        self.assertEqual(snapshot["steps"][0]["id"], "research-v1")
        self.assertIsNone(self.service.get_version(self.other["id"], workflow["id"], 1))

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


    def test_published_snapshot_is_append_only_in_postgresql(self):
        workflow = self.service.create(
            self.owner["id"], "Append-only",
            steps=[{"id": "stable", "type": "research", "config": {"query": "original"}}],
        )
        self.service.validate(self.owner["id"], workflow["id"])
        self.service.publish(self.owner["id"], workflow["id"])
        from database import get_connection
        conn = get_connection()
        try:
            result = conn.execute(
                "UPDATE workflow_definition_versions SET definition_json='[]' "
                "WHERE workflow_id=? AND version=1",
                (workflow["id"],),
            )
            self.assertEqual(result.rowcount, 0)
            row = conn.execute(
                "SELECT definition_json FROM workflow_definition_versions WHERE workflow_id=? AND version=1",
                (workflow["id"],),
            ).fetchone()
            self.assertIn("stable", row["definition_json"])
        finally:
            conn.close()

    def test_publish_is_owner_scoped(self):
        workflow = self.service.create(self.owner["id"], "Owner only")
        self.assertIsNone(self.service.publish(self.other["id"], workflow["id"]))
        self.assertEqual(self.service.list_versions(self.owner["id"], workflow["id"]), [])


    def test_duplicate_creates_owner_scoped_draft_without_history(self):
        source = self.service.create(
            self.owner["id"], "Source",
            steps=[{"id": "source-step", "type": "research", "config": {"query": "source"}}],
        )
        duplicate = self.service.duplicate(self.owner["id"], source["id"], "Copy")
        self.assertNotEqual(source["id"], duplicate["id"])
        self.assertEqual(duplicate["name"], "Copy")
        self.assertEqual(duplicate["status"], "draft")
        self.assertEqual(duplicate["version"], 1)
        self.assertEqual(duplicate["steps"][0]["id"], "source-step")
        self.assertEqual(self.service.list_versions(self.owner["id"], duplicate["id"]), [])
        self.assertIsNone(self.service.duplicate(self.other["id"], source["id"]))

    def test_malformed_legacy_definition_is_preserved_until_explicit_repair(self):
        workflow = self.service.create(self.owner["id"], "Malformed legacy")
        from database import get_connection
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE workflows SET definition_json=? WHERE id=? AND user_id=?",
                ("{not-json", workflow["id"], self.owner["id"]),
            )
            conn.commit()
        finally:
            conn.close()

        damaged = self.service.get(self.owner["id"], workflow["id"])
        self.assertFalse(damaged["definition_valid"])
        self.assertIn("invalid JSON", damaged["definition_error"])
        with self.assertRaisesRegex(ValueError, "Supply replacement steps explicitly"):
            self.service.update(self.owner["id"], workflow["id"], {"name": "Metadata only"})

        repaired = self.service.update(self.owner["id"], workflow["id"], {
            "steps": [{"id": "repaired", "type": "research", "config": {"query": "safe"}}]
        })
        self.assertTrue(repaired["definition_valid"])
        self.assertEqual(repaired["steps"][0]["id"], "repaired")
        conn = get_connection()
        try:
            record = conn.execute(
                "SELECT invalid_definition_json,repaired_definition_json,repaired_by "
                "FROM workflow_definition_recovery WHERE workflow_id=? AND user_id=?",
                (workflow["id"], self.owner["id"]),
            ).fetchone()
            self.assertEqual(record["invalid_definition_json"], "{not-json")
            self.assertIn("repaired", record["repaired_definition_json"])
            self.assertEqual(record["repaired_by"], self.owner["id"])
        finally:
            conn.close()

    def test_invalid_step_type_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.create(self.owner["id"], "Unsafe", steps=[{"type": "shell", "config": {}}])


if __name__ == "__main__":
    import unittest
    unittest.main()
