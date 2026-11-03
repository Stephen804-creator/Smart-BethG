from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.chat_service import ChatService
from services.artifact_service import ArtifactService
from repositories.provenance_repository import ProvenanceRepository
from repositories.conversation_repository import ConversationRepository
from providers.provider_manager import provider_manager
import config


class _FailingProvider:
    def generate(self, messages, model=None, **kwargs):
        raise RuntimeError("simulated outage")


class _WorkingProvider:
    def generate(self, messages, model=None, **kwargs):
        return {"text": "fallback reply", "input_tokens": 3, "output_tokens": 5}


class TestChatServiceProviderFallback(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user("alice", "password123")
        self.service = ChatService()

        # Save real state and substitute controllable fake providers on
        # the shared provider_manager singleton chat_service.py imports.
        self._orig_platform = dict(provider_manager.platform)
        self._orig_default = config.DEFAULT_PROVIDER
        config.DEFAULT_PROVIDER = ""

    def tearDown(self):
        provider_manager.platform = self._orig_platform
        config.DEFAULT_PROVIDER = self._orig_default
        super().tearDown()

    def test_falls_back_to_working_provider_after_failure(self):
        provider_manager.platform = {"anthropic": _FailingProvider(), "openai": _WorkingProvider()}
        result = self.service.send(self.user["id"], "hello")
        self.assertEqual(result["reply"], "fallback reply")
        self.assertEqual(result["provider"], "openai")
        self.assertTrue(result["fallback_used"])

    def test_stored_message_records_the_provider_that_actually_answered(self):
        provider_manager.platform = {"anthropic": _FailingProvider(), "openai": _WorkingProvider()}
        result = self.service.send(self.user["id"], "hello")
        history = self.service.history(self.user["id"], result["conversation_id"])
        assistant_msg = [m for m in history if m["role"] == "assistant"][0]
        self.assertEqual(assistant_msg["provider"], "openai")
        self.assertEqual(assistant_msg["orchestrator_id"], "direct_chat")
        self.assertTrue(assistant_msg["fallback_used"])

    def test_generated_asset_records_actual_provider_and_agent_separately(self):
        provider_manager.platform = {"anthropic": _FailingProvider(), "openai": _WorkingProvider()}
        result = self.service.send(
            self.user["id"], "private prompt must not enter public provenance",
            orchestrator_id="agent_executor",
        )
        artifact = ArtifactService().create_from_chat_message(
            self.user["id"], result["conversation_id"], result["message_id"], "generated-note.txt"
        )
        events = ProvenanceRepository().list_events(self.user["id"], artifact["id"])
        self.assertEqual(
            [event["event_type"] for event in events],
            ["asset_created", "ai_contribution", "agent_contribution"],
        )
        ai_event, agent_event = events[1], events[2]
        self.assertEqual(ai_event["actor_type"], "provider")
        self.assertEqual(ai_event["provider"], "openai")
        self.assertEqual(ai_event["model"], result["model"])
        self.assertEqual(agent_event["actor_type"], "smart_bethg")
        self.assertEqual(agent_event["agent_id"], "agent_executor")
        self.assertTrue(__import__("json").loads(ai_event["payload_json"])["fallback_used"])
        self.assertEqual(
            __import__("json").loads(ai_event["payload_json"])["output_sha256"],
            artifact["checksum_sha256"],
        )
        self.assertNotIn("private prompt", ai_event["payload_json"])
        self.assertTrue(ProvenanceRepository().verify_chain(self.user["id"], artifact["id"])["valid"])

    def test_asset_creation_rejects_messages_without_successful_provider_metadata(self):
        provider_manager.platform = {}
        result = self.service.send(self.user["id"], "no provider configured")
        messages = ConversationRepository().list_messages(result["conversation_id"])
        assistant_message = [item for item in messages if item["role"] == "assistant"][0]
        with self.assertRaisesRegex(ValueError, "no successful provider/model"):
            ArtifactService().create_from_chat_message(
                self.user["id"], result["conversation_id"], assistant_message["id"], "not-generated.txt"
            )

    def test_no_fallback_needed_when_first_provider_works(self):
        provider_manager.platform = {"anthropic": _WorkingProvider(), "openai": _WorkingProvider()}
        result = self.service.send(self.user["id"], "hello")
        self.assertEqual(result["provider"], "anthropic")
        self.assertFalse(result["fallback_used"])

    def test_honest_failure_when_every_provider_fails(self):
        provider_manager.platform = {"anthropic": _FailingProvider(), "openai": _FailingProvider()}
        result = self.service.send(self.user["id"], "hello")
        self.assertTrue(result.get("error"))
        self.assertIn("anthropic", result["reply"])
        self.assertIn("openai", result["reply"])

    def test_every_attempt_is_recorded_for_evaluation(self):
        """
        The failed attempt must be visible too, not just the eventual
        successful one - otherwise a flaky provider hiding behind
        fallback would look perfectly healthy.
        """
        provider_manager.platform = {"anthropic": _FailingProvider(), "openai": _WorkingProvider()}
        self.service.send(self.user["id"], "hello")
        stats = self.service.eval_service.stats()
        by_provider = {row["provider"]: row for row in stats}
        self.assertEqual(by_provider["anthropic"]["successes"], 0)
        self.assertEqual(by_provider["anthropic"]["attempts"], 1)
        self.assertEqual(by_provider["openai"]["successes"], 1)
