import unittest
from services.job_queue import JobWorker

class FakeQueue:
    def __init__(self):
        self.job={"id":"job-1","user_id":1,"job_type":"known","payload":{},"attempts":1,"max_attempts":3,"lease_token":"lease"}
        self.completed=None; self.failed=None
    def claim(self):
        job,self.job=self.job,None
        return job
    def complete(self,job,result): self.completed=result; return True
    def fail(self,job,error,retryable=True): self.failed=(error,retryable); return True

class TestJobWorker(unittest.TestCase):
    def test_runs_registered_handler(self):
        queue=FakeQueue(); worker=JobWorker(queue,{"known":lambda job:{"ok":True}})
        self.assertTrue(worker.run_once()); self.assertEqual(queue.completed,{"ok":True})
    def test_unregistered_handler_fails_without_execution(self):
        queue=FakeQueue(); worker=JobWorker(queue,{})
        self.assertTrue(worker.run_once()); self.assertIsNotNone(queue.failed); self.assertFalse(queue.failed[1])
