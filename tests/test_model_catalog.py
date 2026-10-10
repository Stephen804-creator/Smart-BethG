import unittest

from providers.model_catalog import MODEL_CATALOG, is_known_model, model_for_tier


class TestModelCatalog(unittest.TestCase):
    def test_all_provider_tiers_have_model_ids(self):
        for provider, entry in MODEL_CATALOG.items():
            tiers = {model["tier"] for model in entry["models"]}
            self.assertEqual(tiers, {"fast", "balanced", "capable"}, provider)
            for model in entry["models"]:
                self.assertTrue(model["id"], provider)

    def test_corrected_official_model_ids_are_registered(self):
        expected = {
            ("anthropic", "claude-sonnet-5-5"),
            ("openai", "gpt-6.1-sol"),
            ("openai", "gpt-6-luna"),
            ("google", "gemini-3.1-pro-preview"),
            ("groq", "qwen/qwen3.8-27b"),
        }
        for provider, model_id in expected:
            self.assertTrue(is_known_model(provider, model_id))
        self.assertEqual(model_for_tier("openai", "balanced")["id"], "gpt-6.1-sol")


if __name__ == "__main__":
    unittest.main()
