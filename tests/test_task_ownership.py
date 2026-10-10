import unittest

from repositories.task_repository import TaskRepository
from services.task_service import TaskService
from tests.base import SmartBethGTestCase


class TestTaskOwnership(SmartBethGTestCase):
    def test_status_update_requires_owner(self):
        repo = TaskRepository()
        task_id = repo.create(101, "first user's task", "queued", "default")

        service = TaskService()
        self.assertFalse(service.update_status(202, task_id, "completed"))
        self.assertEqual(repo.list(101)[0]["status"], "queued")

        self.assertTrue(service.update_status(101, task_id, "running"))
        self.assertEqual(repo.list(101)[0]["status"], "running")

    def test_invalid_status_is_rejected(self):
        service = TaskService()
        with self.assertRaises(ValueError):
            service.update_status(101, 1, "admin")


if __name__ == "__main__":
    unittest.main()
