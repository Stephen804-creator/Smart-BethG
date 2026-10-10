import os
import unittest
import uuid

from services.project_service import ProjectService
from services.mission_service import MissionService
from services.workflow_service import WorkflowService
from services.social_content_service import SocialContentService
from services.research_service import ResearchService
from services.evidence_service import EvidenceService
from services.memory_service import MemoryService
from services.artifact_service import ArtifactService
from services.task_service import TaskService
from services.auth_service import create_user
from database import initialize_database


@unittest.skipUnless(
    os.getenv("SMART_BETHG_RUN_POSTGRES_TESTS") == "1",
    "Requires the dedicated PostgreSQL integration-test job",
)
class TestPostgresCapabilityServices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def test_capability_services_round_trip(self):
        suffix = uuid.uuid4().hex[:10]
        user = create_user('pg-slice-' + suffix, 'test-password-123')
        uid = user['id']
        project = ProjectService().create(uid, 'Project ' + suffix)
        mission = MissionService().create(uid, 'Check services', 'normal', project['id'])
        workflow = WorkflowService().create(uid, 'Workflow ' + suffix, steps=[{'type': 'research', 'query': 'example'}])
        self.assertEqual(WorkflowService().validate(uid, workflow['id'])['status'], 'validated')
        social = SocialContentService().create(uid, 'facebook', 'Draft', 'Draft content', ['#test'])
        self.assertEqual(social['status'], 'draft')
        updated_social = SocialContentService().update(
            uid, social['id'],
            {'title': 'Revised ' + suffix, 'content': 'Revised content', 'hashtags': ['#updated']},
        )
        self.assertEqual(updated_social['version'], 2)
        self.assertEqual(len(updated_social['versions']), 2)
        self.assertEqual(updated_social['content'], 'Revised content')
        research = ResearchService().create(uid, 'Topic', 'Summary', ['https://example.org/source'], mission['id'])
        self.assertEqual(research['source_urls'], ['https://example.org/source'])
        evidence = EvidenceService().create(uid, 'Claim', 'https://example.org/evidence', 'Excerpt', 0.5, mission['id'])
        self.assertEqual(evidence['validation_status'], 'unverified')
        memory = MemoryService().remember(uid, 'Test memory')
        self.assertEqual(memory['content'], 'Test memory')
        artifact = ArtifactService().create(uid, 'artifact.txt', 'persisted content', 'text', mission['id'])
        self.assertEqual(ArtifactService().read_content(uid, artifact['id'])[0], 'persisted content')
        task_service = TaskService()
        task = task_service.create(uid, 'Task', 'default')
        self.assertTrue(task_service.update_status(uid, task['task_id'], 'completed'))
        self.assertEqual(task_service.list_tasks(uid)[0]['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
