from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.mission_service import MissionService
from services.research_service import ResearchService
from services.evidence_service import EvidenceService


class TestResearchEvidenceServices(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.owner = create_user("research-owner", "password123")
        self.other = create_user("research-other", "password123")
        self.missions = MissionService()
        self.research = ResearchService()
        self.evidence = EvidenceService()

    def test_research_preserves_source_provenance(self):
        mission = self.missions.create(self.owner["id"], "Investigate source")
        record = self.research.create(
            self.owner["id"], "Question", "Summary",
            ["https://example.com/source"], mission_id=mission["id"],
        )
        self.assertEqual(record["source_urls"], ["https://example.com/source"])
        self.assertIsNone(self.research.get(self.other["id"], record["id"]))

    def test_evidence_starts_unverified_and_is_owner_scoped(self):
        record = self.evidence.create(
            self.owner["id"], "Claim", "https://example.com/source",
            source_excerpt="Quoted source", confidence=0.7,
        )
        self.assertEqual(record["validation_status"], "unverified")
        self.assertIsNone(self.evidence.get(self.other["id"], record["id"]))
        reviewed = self.evidence.review(self.owner["id"], record["id"], "reviewed")
        self.assertEqual(reviewed["validation_status"], "reviewed")

    def test_evidence_cannot_reference_another_users_mission(self):
        mission = self.missions.create(self.owner["id"], "Private mission")
        with self.assertRaises(ValueError):
            self.evidence.create(
                self.other["id"], "Claim", "https://example.com/source",
                mission_id=mission["id"],
            )


if __name__ == "__main__":
    import unittest
    unittest.main()
