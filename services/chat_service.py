from repositories.conversation_repository import ConversationRepository
from providers.provider_manager import provider_manager


class ChatService:
    """
    Real chat capability: persists messages and calls an actual AI
    provider. If no provider is configured, it returns an honest
    "not configured" result instead of a fabricated reply - this is the
    behaviour required by the "no fake AI response" rule.
    """

    def __init__(self, repo: ConversationRepository = None):
        self.repo = repo or ConversationRepository()

    def get_or_create_conversation(self, user_id, conversation_id=None):
        if conversation_id:
            existing = self.repo.get(conversation_id, user_id)
            if existing:
                return existing["id"]
        return self.repo.create(user_id)

    def history(self, user_id, conversation_id):
        convo = self.repo.get(conversation_id, user_id)
        if not convo:
            return []
        return self.repo.list_messages(conversation_id)

    def send(self, user_id, message, conversation_id=None, provider_name=None):
        message = (message or "").strip()
        if not message:
            raise ValueError("Message must not be empty.")

        conversation_id = self.get_or_create_conversation(user_id, conversation_id)
        self.repo.add_message(conversation_id, "user", message)

        if provider_name and provider_name not in provider_manager.platform:
            provider_name = None  # ignore an invalid/unavailable choice rather than error
        provider_name = provider_name or provider_manager.default_provider_name()

        if not provider_name:
            reply = (
                "Smart BethG isn't connected to an AI model yet. An operator "
                "needs to set an API key (e.g. ANTHROPIC_API_KEY, "
                "OPENAI_API_KEY, or GOOGLE_API_KEY) on this deployment "
                "before chat can produce real responses."
            )
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

        try:
            reply = provider.generate(provider_messages, model=None)
        except Exception as exc:
            reply = f"Smart BethG could not reach the AI provider: {exc}"
            self.repo.add_message(conversation_id, "assistant", reply)
            self.repo.touch(conversation_id)
            return {
                "conversation_id": conversation_id,
                "reply": reply,
                "provider_configured": True,
                "error": True,
            }

        self.repo.add_message(conversation_id, "assistant", reply, provider=provider_name)
        self.repo.touch(conversation_id)
        return {
            "conversation_id": conversation_id,
            "reply": reply,
            "provider_configured": True,
        }
