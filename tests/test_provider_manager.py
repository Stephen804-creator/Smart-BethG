import unittest

import config
from providers.provider_manager import ProviderManager
from providers.model_catalog import MODEL_CATALOG, is_known_model


class TestModelCatalog(unittest.TestCase):
    def test_every_provider_has_three_tiers(self):
        for name, info in MODEL_CATALOG.items():
            tiers = {m["tier"] for m in info["models"]}
            self.assertEqual(tiers, {"fast", "balanced", "capable"}, f"{name} missing a tier")

    def test_is_known_model_true_and_false(self):
        self.assertTrue(is_known_model("google", "gemini-3.6-flash"))
        self.assertFalse(is_known_model("google", "gemini-2.0-flash"))  # the retired model


class TestProviderManagerNoKeysConfigured(unittest.TestCase):
    def setUp(self):
        self.pm = ProviderManager()

    def test_no_providers_available(self):
        self.assertEqual(self.pm.available_providers(), [])

    def test_default_provider_is_none(self):
        self.assertIsNone(self.pm.default_provider_name())

    def test_choose_auto_returns_none_none(self):
        self.assertEqual(self.pm.choose_auto("hello"), (None, None))

    def test_resolve_selection_returns_none_none(self):
        self.assertEqual(self.pm.resolve_selection("auto"), (None, None))

    def test_catalog_for_ui_is_empty(self):
        self.assertEqual(self.pm.catalog_for_ui(), {})


class TestAutoTierClassification(unittest.TestCase):
    """Tests the heuristic directly - doesn't need a configured provider."""

    def test_short_message_is_fast_tier(self):
        self.assertEqual(ProviderManager._classify_tier("hi there"), "fast")

    def test_medium_message_is_balanced_tier(self):
        msg = "Can you help me plan out my whole week and also suggest some good restaurants nearby please"
        self.assertGreater(len(msg), 80)
        self.assertEqual(ProviderManager._classify_tier(msg), "balanced")

    def test_code_fence_forces_capable_tier(self):
        msg = "short but has code ```print(1)```"
        self.assertEqual(ProviderManager._classify_tier(msg), "capable")

    def test_complexity_keyword_forces_capable_tier(self):
        msg = "please refactor this"
        self.assertEqual(ProviderManager._classify_tier(msg), "capable")

    def test_long_message_forces_capable_tier(self):
        msg = "x" * 700
        self.assertEqual(ProviderManager._classify_tier(msg), "capable")


if __name__ == "__main__":
    unittest.main()


class TestGroqAndOpenRouterRegistration(unittest.TestCase):
    def setUp(self):
        self._orig_groq = config.GROQ_API_KEY
        self._orig_openrouter = config.OPENROUTER_API_KEY
        self._orig_anthropic = config.ANTHROPIC_API_KEY
        config.GROQ_API_KEY = ""
        config.OPENROUTER_API_KEY = ""
        config.ANTHROPIC_API_KEY = ""

    def tearDown(self):
        config.GROQ_API_KEY = self._orig_groq
        config.OPENROUTER_API_KEY = self._orig_openrouter
        config.ANTHROPIC_API_KEY = self._orig_anthropic

    def test_groq_registers_when_key_present(self):
        config.GROQ_API_KEY = "fake-groq-key"
        pm = ProviderManager()
        self.assertIn("groq", pm.available_providers())

    def test_openrouter_registers_when_key_present(self):
        config.OPENROUTER_API_KEY = "fake-or-key"
        pm = ProviderManager()
        self.assertIn("openrouter", pm.available_providers())

    def test_free_providers_become_default_when_nothing_paid_configured(self):
        """
        The exact scenario the user is building toward: no paid keys at
        all, Groq/OpenRouter are what's actually used - with zero
        special-casing needed, just the normal fallback order.
        """
        config.GROQ_API_KEY = "fake-groq-key"
        pm = ProviderManager()
        self.assertEqual(pm.default_provider_name(), "groq")

    def test_paid_provider_preferred_over_free_when_both_configured(self):
        config.ANTHROPIC_API_KEY = "fake-key"
        config.GROQ_API_KEY = "fake-groq-key"
        pm = ProviderManager()
        self.assertEqual(pm.default_provider_name(), "anthropic")

    def test_groq_is_a_real_fallback_candidate_behind_anthropic(self):
        """
        This is the specific behaviour requested: if the paid provider
        is unavailable (rate-limited, outage, quota exhausted), Groq is
        a genuine fallback candidate so the task can still complete.
        """
        config.ANTHROPIC_API_KEY = "fake-key"
        config.GROQ_API_KEY = "fake-groq-key"
        pm = ProviderManager()
        self.assertEqual(pm.fallback_candidates(exclude={"anthropic"}), ["groq"])

    def test_groq_not_used_for_embeddings(self):
        config.GROQ_API_KEY = "fake-groq-key"
        pm = ProviderManager()
        self.assertIsNone(pm.embedding_provider_name())

    def test_groq_catalog_models_are_real_current_ids(self):
        """
        llama-3.3-70b-versatile was deprecated by Groq on 2026-08-16 -
        this locks in that the catalog uses its confirmed replacements,
        not the retired model, so this doesn't silently regress later.
        """
        config.GROQ_API_KEY = "fake-groq-key"
        pm = ProviderManager()
        ids = {m["id"] for m in pm.catalog_for_ui()["groq"]["models"]}
        self.assertNotIn("llama-3.3-70b-versatile", ids)
        self.assertIn("openai/gpt-oss-120b", ids)
