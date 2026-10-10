import time

import config
from repositories.conversation_repository import ConversationRepository
from providers.provider_manager import provider_manager
from services.model_evaluation_service import ModelEvaluationService
from services.memory_service import MemoryService
from services.knowledge_service import KnowledgeService
from services.usage_budget_service import UsageBudgetService, BudgetExceededError
from logging_setup import get_logger

logger = get_logger("chat")


class ChatService:
    """
    Real chat capability: persists messages and calls an actual AI
    provider/model. If no provider is configured, it returns an honest
    "not configured" result instead of a fabricated reply - this is the
    behaviour required by the "no fake AI response" rule.
    """

    def __init__(
        self,
        repo: ConversationRepository = None,
        eval_service: ModelEvaluationService = None,
        memory_service: MemoryService = None,
        knowledge_service: KnowledgeService = None,
        budget_service: UsageBudgetService = None,
    ):
        self.repo = repo or ConversationRepository()
        self.eval_service = eval_service or ModelEvaluationService()
        self.memory_service = memory_service or MemoryService()
        self.knowledge_service = knowledge_service or KnowledgeService()
        self.budget_service = budget_service or UsageBudgetService()

    def get_or_create_conversation(self, user_id, conversation_id=None):
        if conversation_id:
            existing = self.repo.get(conversation_id, user_id)
            if existing:
                return existing["id"], False
        return self.repo.create(user_id), True

    def history(self, user_id, conversation_id):
        convo = self.repo.get(conversation_id, user_id)
        if not convo:
            return []
        return self.repo.list_messages(conversation_id)

    def list_conversations(self, user_id):
        return self.repo.list_for_user(user_id)

    def send(self, user_id, message, conversation_id=None, selection=None, workspace="default", extra_context=None):
        """
        `selection` is whatever the UI sent: "auto" (or None/empty),
        "<provider>", or "<provider>:<model_id>". Auto mode uses Smart
        BethG's own simple complexity heuristic (see
        provider_manager.choose_auto) rather than pretending to a more
        sophisticated routing model than actually exists.

        `workspace` scopes which project-level memory (T0804) gets
        recalled into this request - see services/memory_service.py.

        `extra_context`, when given, is prepended alongside recalled
        memory - this is how grounded generation (T0904) injects real
        search results into a research request without needing a
        separate code path from plain chat.
        """
        message = (message or "").strip()
        if not message:
            raise ValueError("Message must not be empty.")

        conversation_id, is_new = self.get_or_create_conversation(user_id, conversation_id)
        self.repo.add_message(conversation_id, "user", message)
        if is_new:
            self.repo.set_title(conversation_id, message[:60])

        if not selection or selection == "auto":
            provider_name, model_id = provider_manager.choose_auto(message)
        else:
            provider_name, model_id = provider_manager.resolve_selection(selection)

        if not provider_name:
            reply = (
                "Smart BethG isn't connected to an AI model yet. An operator "
                "needs to set an API key (e.g. ANTHROPIC_API_KEY, "
                "OPENAI_API_KEY, or GOOGLE_API_KEY) on this deployment "
                "before chat can produce real responses."
            )
            logger.warning("Chat request from user %s but no provider is configured", user_id)
            self.repo.add_message(conversation_id, "assistant", reply)
            self.repo.touch(conversation_id)
            return {
                "conversation_id": conversation_id,
                "reply": reply,
                "provider_configured": False,
            }

        provider = provider_manager.get(user_id, provider_name)
        history = self.repo.list_messages(conversation_id)
        provider_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in history
            if m["role"] in ("user", "assistant")
        ]

        memory_context = self.memory_service.recall_context(user_id, workspace, conversation_id)
        leading_context = []
        if memory_context:
            leading_context.append(memory_context)
        if self.knowledge_service.has_knowledge(user_id):
            knowledge_context = self.knowledge_service.recall_context(user_id, message)
            if knowledge_context:
                leading_context.append(knowledge_context)
        if extra_context:
            leading_context.append(extra_context)
        if leading_context:
            # Prepended as leading user-role messages rather than a
            # provider-specific "system" field, since not every provider
            # SDK call here is wired the same way - this keeps the
            # injection provider-agnostic.
            provider_messages = [{"role": "user", "content": c} for c in leading_context] + provider_messages

        result, used_provider, used_model, attempted, last_error = self._generate_with_fallback(
            provider, provider_name, model_id, provider_messages, user_id,
        )

        if result is None:
            if isinstance(last_error, BudgetExceededError):
                reply = "The daily usage budget has been reached. Your usage will reset at 00:00 UTC."
            else:
                reply = (
                "Smart BethG could not reach a configured AI provider "
                f"(attempted: {', '.join(attempted)}). Please try again later "
                "or contact the operator if the problem continues."
                )
            self.repo.add_message(conversation_id, "assistant", reply)
            self.repo.touch(conversation_id)
            return {
                "conversation_id": conversation_id,
                "reply": reply,
                "provider_configured": True,
                "error": True,
            }

        reply = result["text"]
        fallback_used = used_provider != provider_name
        if fallback_used:
            logger.warning(
                "Chat used fallback provider (user=%s, requested=%s, used=%s)",
                user_id, provider_name, used_provider,
            )
        logger.info(
            "Chat reply generated (user=%s, provider=%s, model=%s, in=%s, out=%s)",
            user_id, used_provider, used_model, result.get("input_tokens"), result.get("output_tokens"),
        )
        self.repo.add_message(
            conversation_id,
            "assistant",
            reply,
            provider=used_provider,
            model=used_model,
            tokens_in=result.get("input_tokens"),
            tokens_out=result.get("output_tokens"),
        )
        self.repo.touch(conversation_id)
        return {
            "conversation_id": conversation_id,
            "reply": reply,
            "provider_configured": True,
            "provider": used_provider,
            "model": used_model,
            "fallback_used": fallback_used,
        }

    def generate_task(self, user_id, prompt, selection=None, extra_context=None):
        """Generate a structured task result with normal provider fallback and budget enforcement.

        Unlike send(), this helper does not create a chat conversation or persist
        the prompt as a user-facing chat message. Usage is still reserved and
        reconciled by the same provider pipeline.
        """
        prompt = (prompt or "").strip()
        if not prompt:
            raise ValueError("Generation prompt must not be empty.")
        if not selection or selection == "auto":
            provider_name, model_id = provider_manager.choose_auto(prompt)
        else:
            provider_name, model_id = provider_manager.resolve_selection(selection)
        if not provider_name:
            return {"provider_configured": False, "error": "No AI provider is configured."}
        provider = provider_manager.get(user_id, provider_name)
        messages = []
        if extra_context:
            messages.append({"role": "user", "content": str(extra_context)})
        messages.append({"role": "user", "content": prompt})
        result, used_provider, used_model, attempted, last_error = self._generate_with_fallback(
            provider, provider_name, model_id, messages, user_id,
        )
        if result is None:
            return {
                "provider_configured": True,
                "error": "All configured AI providers failed or the usage budget was exhausted.",
                "attempted": attempted,
                "error_type": type(last_error).__name__ if last_error else "ProviderError",
            }
        return {
            "provider_configured": True,
            "text": result["text"],
            "provider": used_provider,
            "model": used_model,
            "fallback_used": used_provider != provider_name,
            "input_tokens": result.get("input_tokens"),
            "output_tokens": result.get("output_tokens"),
        }

    def _generate_with_fallback(self, provider, provider_name, model_id, provider_messages, user_id):
        """
        Tries the requested/auto-chosen provider first; if it raises,
        tries every other currently-configured provider (priority order)
        before giving up. Only actually falls back on a real failure -
        never silently swaps a provider that would have worked. Every
        attempt (success or failure) is recorded via
        ModelEvaluationService, not just the one that ultimately
        answered - otherwise a provider failing 30% of the time behind
        a fallback would be invisible.
        Returns (result_or_None, provider_used, model_used, attempted_names, last_error).
        """
        attempted = []
        candidates = [(provider_name, provider, model_id)] + [
            (name, provider_manager.get(user_id, name), self._balanced_model_for(name))
            for name in provider_manager.fallback_candidates(exclude={provider_name})
        ]
        candidates = candidates[:max(1, config.MAX_PROVIDER_ATTEMPTS_PER_CHAT)]

        last_error = None
        input_estimate = self.budget_service.estimate_input_tokens(
            self._bound_context(provider_messages, config.MAX_CHAT_CONTEXT_CHARS)
        )
        for name, candidate_provider, candidate_model in candidates:
            if candidate_provider is None:
                continue
            try:
                reservation = self.budget_service.reserve(
                    user_id, name, candidate_model, input_estimate, config.CHAT_MAX_OUTPUT_TOKENS
                )
            except BudgetExceededError as exc:
                last_error = exc
                attempted.append(name)
                logger.warning("Provider attempt blocked by usage budget (user=%s, provider=%s)", user_id, name)
                break

            start = time.monotonic()
            try:
                bounded_messages = self._bound_context(provider_messages, config.MAX_CHAT_CONTEXT_CHARS)
                result = candidate_provider.generate(
                    bounded_messages, model=candidate_model, max_tokens=config.CHAT_MAX_OUTPUT_TOKENS
                )
            except Exception as exc:
                latency_ms = int((time.monotonic() - start) * 1000)
                try:
                    self.budget_service.mark_failed(reservation["id"])
                except Exception:
                    logger.exception("Could not finalize failed usage reservation")
                try:
                    self.eval_service.record_call(
                        user_id, name, candidate_model, False, latency_ms, error=type(exc).__name__
                    )
                except Exception:
                    logger.exception("Could not record failed provider telemetry")
                last_error = exc
                attempted.append(name)
                logger.error(
                    "Provider call failed (user=%s, provider=%s, model=%s, error_type=%s)",
                    user_id, name, candidate_model, type(exc).__name__,
                )
                continue

            latency_ms = int((time.monotonic() - start) * 1000)
            try:
                self.budget_service.reconcile(
                    reservation["id"], result.get("input_tokens"), result.get("output_tokens")
                )
            except Exception:
                # The reservation remains counted at its conservative estimate;
                # never retry a successful provider call because telemetry failed.
                logger.exception("Could not reconcile provider usage reservation")
            try:
                self.eval_service.record_call(user_id, name, candidate_model, True, latency_ms)
            except Exception:
                logger.exception("Could not record successful provider telemetry")
            return result, name, candidate_model, attempted, last_error

        return None, None, None, attempted, last_error

    @staticmethod
    def _bound_context(messages, max_chars):
        """Keep the newest context within a hard character budget."""
        budget = max(4000, int(max_chars))
        kept = []
        used = 0
        for message in reversed(messages):
            content = str(message.get("content", ""))
            remaining = budget - used
            if remaining <= 0:
                break
            if len(content) > remaining:
                content = content[-remaining:]
            kept.append({"role": message.get("role", "user"), "content": content})
            used += len(content)
        kept.reverse()
        return kept

    @staticmethod
    def _balanced_model_for(provider_name):
        from providers.model_catalog import model_for_tier
        entry = model_for_tier(provider_name, "balanced")
        return entry["id"] if entry else None

    def usage(self, user_id):
        usage = self.repo.usage_totals_for_user(user_id)
        usage["budget"] = self.budget_service.get_usage(user_id)
        return usage
