from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import config
from services.rate_limiter import check_rate_limit

from api.dependencies import get_current_user
from services.chat_service import ChatService
from providers.provider_manager import provider_manager
from agent.executor import AgentExecutor
from agent.request import AgentRequest

router = APIRouter(prefix="/chat", tags=["chat"])

_executor = AgentExecutor()


def get_chat_service():
    return ChatService()


class ChatMessage(BaseModel):
    message: str = Field(min_length=1, max_length=config.MAX_CHAT_MESSAGE_CHARS)
    conversation_id: int | None = Field(default=None, ge=1)
    # "auto" (default), "<provider>", or "<provider>:<model_id>"
    selection: str | None = Field(default=None, max_length=256)


@router.post("")
def send_message(payload: ChatMessage, user=Depends(get_current_user)):
    """
    Routes every message through the real agent loop (agent/executor.py)
    rather than calling ChatService directly. Previously this endpoint -
    the one the actual chat UI calls - never reached intent detection or
    tool execution at all; only the separate, UI-less /tasks endpoint
    did. That meant "check my repo status" typed into chat could only
    ever be handled by the AI provider making something up, never by
    actually checking. Now it can genuinely run git.read.
    """
    if not check_rate_limit(
        f"chat-user:{user['id']}",
        max_attempts=config.CHAT_RATE_LIMIT_MAX_ATTEMPTS,
        window_seconds=config.CHAT_RATE_LIMIT_WINDOW_SECONDS,
    ):
        raise HTTPException(status_code=429, detail="Chat rate limit reached. Please wait before sending another request.")

    agent_request = AgentRequest(
        text=payload.message,
        user=user,
        conversation_id=payload.conversation_id,
        selection=payload.selection,
    )
    outcome = _executor.run(agent_request)
    return {**outcome["result"], "intent": outcome["intent"]}


@router.get("/providers")
def list_providers(user=Depends(get_current_user)):
    default_provider = provider_manager.default_provider_name()
    return {
        "catalog": provider_manager.catalog_for_ui(),
        "default_provider": default_provider,
    }


@router.get("/conversations")
def list_conversations(user=Depends(get_current_user), service: ChatService = Depends(get_chat_service)):
    return {"conversations": service.list_conversations(user["id"])}


@router.get("/usage")
def usage(user=Depends(get_current_user), service: ChatService = Depends(get_chat_service)):
    return service.usage(user["id"])


@router.get("/model-stats")
def model_stats(user=Depends(get_current_user), service: ChatService = Depends(get_chat_service)):
    """
    Aggregated, global reliability/latency per provider+model (T0504).
    Not per-user - which model performs well is an operational fact
    shared across the deployment, not private to one account.
    """
    return {"stats": service.eval_service.stats()}


@router.get("/{conversation_id}")
def get_history(conversation_id: int, user=Depends(get_current_user), service: ChatService = Depends(get_chat_service)):
    return {"messages": service.history(user["id"], conversation_id)}
