from tests.base import SmartBethGTestCase
from services.model_evaluation_service import ModelEvaluationService


class TestModelEvaluationService(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.service = ModelEvaluationService()

    def test_no_calls_yet_returns_empty(self):
        self.assertEqual(self.service.stats(), [])

    def test_records_and_aggregates_success_rate(self):
        self.service.record_call(1, "anthropic", "claude-sonnet-5", True, 500)
        self.service.record_call(1, "anthropic", "claude-sonnet-5", True, 700)
        self.service.record_call(1, "anthropic", "claude-sonnet-5", False, 100, error="timeout")

        stats = self.service.stats()
        self.assertEqual(len(stats), 1)
        row = stats[0]
        self.assertEqual(row["attempts"], 3)
        self.assertEqual(row["successes"], 2)
        self.assertAlmostEqual(row["success_rate"], 2 / 3, places=4)

    def test_average_latency_only_counts_recorded_calls(self):
        self.service.record_call(1, "openai", "gpt-5.6-terra", True, 200)
        self.service.record_call(1, "openai", "gpt-5.6-terra", True, 400)
        stats = self.service.stats()
        self.assertEqual(stats[0]["avg_latency_ms"], 300)

    def test_separates_by_provider_and_model(self):
        self.service.record_call(1, "anthropic", "claude-sonnet-5", True, 300)
        self.service.record_call(1, "anthropic", "claude-opus-5", True, 900)
        stats = self.service.stats()
        self.assertEqual(len(stats), 2)
        models = {(r["provider"], r["model"]) for r in stats}
        self.assertIn(("anthropic", "claude-sonnet-5"), models)
        self.assertIn(("anthropic", "claude-opus-5"), models)

    def test_most_attempted_sorted_first(self):
        self.service.record_call(1, "anthropic", "claude-sonnet-5", True, 300)
        for _ in range(3):
            self.service.record_call(1, "openai", "gpt-5.6-terra", True, 300)
        stats = self.service.stats()
        self.assertEqual(stats[0]["provider"], "openai")
