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

    def test_invalid_step_type_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.create(self.owner["id"], "Unsafe", steps=[{"type": "shell", "config": {}}])


if __name__ == "__main__":
    import unittest
    unittest.main()
