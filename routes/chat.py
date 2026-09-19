from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.dependencies import get_current_user
from services.chat_service import ChatService
from providers.provider_manager import provider_manager

router = APIRouter(prefix="/api/chat", tags=["chat"])


def get_chat_service():
    return ChatService()


class ChatMessage(BaseModel):
    message: str
    conversation_id: int | None = None
    provider: str | None = None


@router.post("")
def send_message(payload: ChatMessage, user=Depends(get_current_user), service: ChatService = Depends(get_chat_service)):
    return service.send(user["id"], payload.message, payload.conversation_id, payload.provider)


@router.get("/providers")
def list_providers(user=Depends(get_current_user)):
    return {
        "available": provider_manager.available_providers(),
        "default": provider_manager.default_provider_name(),
    }


@router.get("/{conversation_id}")
def get_history(conversation_id: int, user=Depends(get_current_user), service: ChatService = Depends(get_chat_service)):
    return {"messages": service.history(user["id"], conversation_id)}
