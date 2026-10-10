from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.project_service import ProjectService


class TestProjectService(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.owner = create_user("project-owner", "password123")
        self.other = create_user("project-other", "password123")
        self.service = ProjectService()

    def test_create_update_and_archive_project(self):
        project = self.service.create(self.owner["id"], "Launch", "First public release")
        self.assertEqual(project["status"], "active")
        updated = self.service.update(self.owner["id"], project["id"], {"status": "paused"})
        self.assertEqual(updated["status"], "paused")
        self.assertTrue(self.service.archive(self.owner["id"], project["id"]))
        self.assertEqual(self.service.get(self.owner["id"], project["id"])["status"], "archived")

    def test_project_isolation_between_users(self):
        project = self.service.create(self.owner["id"], "Private project")
        self.assertIsNone(self.service.get(self.other["id"], project["id"]))
        self.assertEqual(self.service.list_for_user(self.other["id"]), [])
        self.assertFalse(self.service.archive(self.other["id"], project["id"]))


if __name__ == "__main__":
    import unittest
    unittest.main()
