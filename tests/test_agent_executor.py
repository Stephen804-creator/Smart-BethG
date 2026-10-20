import shutil
import subprocess
import tempfile

import config
from agent.executor import AgentExecutor
from agent.request import AgentRequest
from services.tool_service import ToolService, resolve_workspace_root
from services.chat_service import ChatService
from tests.base import SmartBethGTestCase
from services.auth_service import create_user


class TestAgentExecutor(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.mkdtemp(prefix="sbg_exec_projects_")
        self._orig_projects_dir = config.STORAGE_DIRS["projects"]
        config.STORAGE_DIRS["projects"] = self._tmp
        self.user = create_user("alice", "password123")
        self.executor = AgentExecutor(tool_service=ToolService(), chat_service=ChatService())

    def tearDown(self):
        config.STORAGE_DIRS["projects"] = self._orig_projects_dir
        shutil.rmtree(self._tmp, ignore_errors=True)
        super().tearDown()

    def test_chat_intent_falls_through_to_chat_service_honestly(self):
        req = AgentRequest(text="what's the weather like?", user=self.user)
        outcome = self.executor.run(req)
        self.assertEqual(outcome["intent"], "chat")
        self.assertEqual(outcome["status"], "no_provider")  # no API key in tests
        self.assertIn("isn't connected", outcome["result"]["reply"])

    def test_git_read_intent_requires_a_connector(self):
        outcome = self.executor.run(AgentRequest(text="what's the git status?", user=self.user))
        self.assertEqual(outcome["intent"], "git.read")
        self.assertEqual(outcome["status"], "unavailable")
        self.assertTrue(outcome["result"]["tool_result"]["connector_required"])
    def test_git_read_intent_is_unavailable_without_a_connector(self):
        outcome = self.executor.run(AgentRequest(text="check repo status", user=self.user))
        self.assertEqual(outcome["intent"], "git.read")
        self.assertEqual(outcome["status"], "unavailable")
    def test_blocked_tool_exchange_is_recorded_in_conversation_history(self):
        outcome = self.executor.run(AgentRequest(text="git status", user=self.user))
        conversation_id = outcome["result"]["conversation_id"]
        history = self.executor.chat_service.history(self.user["id"], conversation_id)
        self.assertEqual([m["role"] for m in history], ["user", "assistant"])
        self.assertEqual(history[0]["content"], "git status")
        self.assertIn("connector", history[1]["content"].lower())
    def test_approval_required_is_summarized_honestly_not_hidden(self):
        req = AgentRequest(text="git status", user=self.user, workspace="default")
        # Force a HIGH-risk-style outcome by using a fake tool_service.
        class FakeToolService:
            def execute(self, user, action, workspace="default", **kwargs):
                return {"success": False, "status": "approval_required", "approval_id": "abc-123", "reason": "High risk"}

        executor = AgentExecutor(tool_service=FakeToolService(), chat_service=ChatService())
        outcome = executor.run(req)
        self.assertEqual(outcome["status"], "approval_required")
        self.assertIn("abc-123", outcome["result"]["reply"])

    def test_selection_is_passed_through_to_chat_service(self):
        calls = {}

        class RecordingChatService(ChatService):
            def send(self, user_id, message, conversation_id=None, selection=None, workspace="default", extra_context=None):
                calls["selection"] = selection
                return super().send(user_id, message, conversation_id, selection, workspace, extra_context)

        executor = AgentExecutor(tool_service=ToolService(), chat_service=RecordingChatService())
        req = AgentRequest(text="hello", user=self.user, selection="anthropic:claude-opus-5")
        executor.run(req)
        self.assertEqual(calls["selection"], "anthropic:claude-opus-5")

    def test_remember_intent_stores_a_real_memory_entry(self):
        req = AgentRequest(text="remember that I prefer concise answers", user=self.user)
        outcome = self.executor.run(req)
        self.assertEqual(outcome["intent"], "memory.write")
        self.assertEqual(outcome["status"], "executed")

        entries = self.executor.memory_service.list_all(self.user["id"])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["content"], "I prefer concise answers")

    def test_remember_intent_is_recorded_in_conversation_history(self):
        req = AgentRequest(text="remember that I use FastAPI", user=self.user)
        outcome = self.executor.run(req)
        conversation_id = outcome["result"]["conversation_id"]
        history = self.executor.chat_service.history(self.user["id"], conversation_id)
        self.assertEqual(history[0]["content"], "remember that I use FastAPI")
        self.assertIn("I use FastAPI", history[1]["content"])

    def test_remembered_fact_is_recalled_in_a_later_plain_chat_message(self):
        """
        End-to-end: a "remember" instruction followed by a normal chat
        message must actually inject that fact into what gets sent to
        the AI provider - not just sit in a database nobody reads.
        """
        remember_req = AgentRequest(text="remember that I prefer Python", user=self.user)
        self.executor.run(remember_req)

        from providers.provider_manager import provider_manager
        import config

        class _CapturingProvider:
            def generate(self, messages, model=None, **kwargs):
                self.last_messages = messages
                return {"text": "ok", "input_tokens": 1, "output_tokens": 1}

        fake_provider = _CapturingProvider()
        orig_platform = dict(provider_manager.platform)
        orig_default = config.DEFAULT_PROVIDER
        provider_manager.platform = {"anthropic": fake_provider}
        config.DEFAULT_PROVIDER = ""
        try:
            chat_req = AgentRequest(text="what should I learn next?", user=self.user)
            self.executor.run(chat_req)
        finally:
            provider_manager.platform = orig_platform
            config.DEFAULT_PROVIDER = orig_default

        combined = " ".join(m["content"] for m in fake_provider.last_messages)
        self.assertIn("I prefer Python", combined)

    def test_filesystem_read_requires_a_connector(self):
        outcome = self.executor.run(AgentRequest(text='read the file "notes.txt"', user=self.user))
        self.assertEqual(outcome["intent"], "filesystem.read")
        self.assertEqual(outcome["status"], "unavailable")
        self.assertTrue(outcome["result"]["tool_result"]["connector_required"])
    def test_filesystem_read_without_clear_path_asks_instead_of_guessing(self):
        req = AgentRequest(text="please read the file for me", user=self.user)
        outcome = self.executor.run(req)
        self.assertEqual(outcome["status"], "needs_clarification")
        self.assertIn("Which file", outcome["result"]["reply"])

    def test_clarification_exchange_is_recorded_in_history(self):
        req = AgentRequest(text="read the file", user=self.user)
        outcome = self.executor.run(req)
        conversation_id = outcome["result"]["conversation_id"]
        history = self.executor.chat_service.history(self.user["id"], conversation_id)
        self.assertEqual(history[0]["content"], "read the file")
        self.assertIn("Which file", history[1]["content"])

    def test_research_without_query_asks_instead_of_guessing(self):
        req = AgentRequest(text="please research", user=self.user)
        outcome = self.executor.run(req)
        self.assertEqual(outcome["status"], "needs_clarification")
        self.assertIn("research", outcome["result"]["reply"].lower())

    def test_research_without_search_configured_fails_honestly(self):
        """
        No BRAVE_SEARCH_API_KEY in the test environment - this must
        report a clean failure, not silently fall back to the AI model
        making something up and presenting it as researched fact.
        """
        req = AgentRequest(text="research quantum computing", user=self.user)
        outcome = self.executor.run(req)
        self.assertEqual(outcome["status"], "search_failed")
        self.assertIn("couldn't search", outcome["result"]["reply"])

    def test_research_with_no_results_is_honest(self):
        class EmptySearchService:
            def search(self, query, count=5):
                return []

        executor = AgentExecutor(
            tool_service=self.executor.tool_service,
            chat_service=self.executor.chat_service,
            memory_service=self.executor.memory_service,
            search_service=EmptySearchService(),
        )
        req = AgentRequest(text="research an extremely obscure topic", user=self.user)
        outcome = executor.run(req)
        self.assertEqual(outcome["status"], "no_results")
        self.assertIn("no results", outcome["result"]["reply"])

    def test_research_full_flow_grounds_synthesis_in_real_search_results(self):
        """
        The actual point of multi-step planning: search runs first, and
        its results must genuinely reach the AI call as context - not
        just get logged and discarded while the AI answers from nothing.
        """
        class FakeSearchService:
            def search(self, query, count=5):
                return [{"title": "Quantum Computing Basics", "url": "https://example.com/qc", "snippet": "Qubits and superposition."}]

        class CapturingProvider:
            def generate(self, messages, model=None, **kwargs):
                self.last_messages = messages
                return {"text": "Quantum computers use qubits [example.com/qc].", "input_tokens": 1, "output_tokens": 1}

        from providers.provider_manager import provider_manager
        import config
        fake_provider = CapturingProvider()
        orig_platform = dict(provider_manager.platform)
        orig_default = config.DEFAULT_PROVIDER
        provider_manager.platform = {"anthropic": fake_provider}
        config.DEFAULT_PROVIDER = ""

        executor = AgentExecutor(
            tool_service=self.executor.tool_service,
            chat_service=self.executor.chat_service,
            memory_service=self.executor.memory_service,
            search_service=FakeSearchService(),
        )
        try:
            req = AgentRequest(text="research quantum computing", user=self.user)
            outcome = executor.run(req)
        finally:
            provider_manager.platform = orig_platform
            config.DEFAULT_PROVIDER = orig_default

        self.assertEqual(outcome["intent"], "research")
        self.assertEqual(outcome["status"], "completed")
        combined = " ".join(m["content"] for m in fake_provider.last_messages)
        self.assertIn("Quantum Computing Basics", combined)
        self.assertIn("Qubits and superposition", combined)
        self.assertIn("https://example.com/qc", combined)
        # The instruction to cite/be honest must actually be present, not
        # just the raw snippet - grounded generation, not decoration.
        self.assertIn("Cite the specific URL", combined)


class TestCodeIntelligence(SmartBethGTestCase):
    """
    code.explain / code.review: a real filesystem.read followed by a chat
    step that receives the file's actual contents - not the AI guessing
    what a file with that name might contain.
    """

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.mkdtemp(prefix="sbg_code_projects_")
        self._orig_projects_dir = config.STORAGE_DIRS["projects"]
        config.STORAGE_DIRS["projects"] = self._tmp
        self.user = create_user("alice", "password123")
        self.executor = AgentExecutor(tool_service=ToolService(), chat_service=ChatService())

    def tearDown(self):
        config.STORAGE_DIRS["projects"] = self._orig_projects_dir
        shutil.rmtree(self._tmp, ignore_errors=True)
        super().tearDown()

    def _run_with_capturing_provider(self, text):
        from providers.provider_manager import provider_manager

        class CapturingProvider:
            def generate(self, messages, model=None, **kwargs):
                self.last_messages = messages
                return {"text": "ok", "input_tokens": 1, "output_tokens": 1}

        fake_provider = CapturingProvider()
        orig_platform = dict(provider_manager.platform)
        orig_default = config.DEFAULT_PROVIDER
        provider_manager.platform = {"anthropic": fake_provider}
        config.DEFAULT_PROVIDER = ""
        try:
            outcome = self.executor.run(AgentRequest(text=text, user=self.user, workspace="default"))
        finally:
            provider_manager.platform = orig_platform
            config.DEFAULT_PROVIDER = orig_default
        return outcome, fake_provider

    def test_code_explain_waits_for_a_file_connector(self):
        outcome, provider = self._run_with_capturing_provider('explain the file "calc.py"')
        self.assertEqual(outcome["intent"], "code.explain")
        self.assertEqual(outcome["status"], "unavailable")
        self.assertFalse(hasattr(provider, "last_messages"))
    def test_code_review_waits_for_a_file_connector(self):
        outcome, provider = self._run_with_capturing_provider('review the file "risky.py"')
        self.assertEqual(outcome["intent"], "code.review")
        self.assertEqual(outcome["status"], "unavailable")
        self.assertFalse(hasattr(provider, "last_messages"))
    def test_code_explain_waits_for_connector_even_when_file_is_missing(self):
        outcome, provider = self._run_with_capturing_provider('explain the file "does_not_exist.py"')
        self.assertEqual(outcome["status"], "unavailable")
        self.assertFalse(hasattr(provider, "last_messages"))
    def test_code_explain_without_path_asks_instead_of_guessing(self):
        outcome, provider = self._run_with_capturing_provider("explain the file for me")
        self.assertEqual(outcome["status"], "needs_clarification")
        self.assertIn("Which file", outcome["result"]["reply"])
        self.assertFalse(hasattr(provider, "last_messages"))

    def test_code_review_waits_for_connector_before_accessing_paths(self):
        outcome, provider = self._run_with_capturing_provider('review the file "../../etc/passwd"')
        self.assertEqual(outcome["status"], "unavailable")
        self.assertFalse(hasattr(provider, "last_messages"))

