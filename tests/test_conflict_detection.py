import unittest

from services.conflict_detection import pair_conflict_signal, find_pairwise_conflicts


class TestConflictDetection(unittest.TestCase):
    def test_detects_negation_disagreement_without_choosing_truth(self):
        result = pair_conflict_signal(
            "The service is available in production",
            "The service is not available in production",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["kind"], "polarity_difference")

    def test_detects_numeric_disagreement_on_similar_claims(self):
        result = pair_conflict_signal(
            "The retention period is 30 days",
            "The retention period is 90 days",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["kind"], "numeric_difference")

    def test_ignores_unrelated_statements(self):
        self.assertIsNone(pair_conflict_signal(
            "Python is used for data analysis",
            "The dashboard has a blue sidebar",
        ))

    def test_pairwise_results_preserve_source_labels(self):
        results = find_pairwise_conflicts([
            {"content": "The daily request limit is 10 requests", "citation": "policy-a"},
            {"content": "The daily request limit is 100 requests", "citation": "policy-b"},
        ])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["left_source"], "policy-a")
        self.assertEqual(results[0]["right_source"], "policy-b")


if __name__ == "__main__":
    unittest.main()
