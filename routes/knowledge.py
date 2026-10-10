from fastapi import APIRouter, Depends

from api.dependencies import get_current_user
from services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def get_knowledge_service():
    return KnowledgeService()


@router.get("/search")
def search_knowledge(q: str, user=Depends(get_current_user), service: KnowledgeService = Depends(get_knowledge_service)):
    """
    Direct access to the same retrieval used to ground chat (T0903) -
    lets a user (or a future UI) see exactly what would be recalled,
    rather than only observing it indirectly through a chat reply.
    """
    return {"results": service.search(user["id"], q)}
