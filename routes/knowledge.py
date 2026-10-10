from fastapi import APIRouter, Depends, HTTPException, Query
import config
from services.rate_limiter import check_rate_limit

from api.dependencies import get_current_user
from services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def get_knowledge_service():
    return KnowledgeService()


@router.get("/search")
def search_knowledge(q: str = Query(min_length=1, max_length=1000), user=Depends(get_current_user), service: KnowledgeService = Depends(get_knowledge_service)):
    if not check_rate_limit(
        f"knowledge-search-user:{user['id']}",
        max_attempts=config.KNOWLEDGE_SEARCH_RATE_LIMIT_MAX_ATTEMPTS,
        window_seconds=config.KNOWLEDGE_SEARCH_RATE_LIMIT_WINDOW_SECONDS,
    ):
        raise HTTPException(status_code=429, detail="Knowledge search rate limit reached. Please wait.")
    """
    Direct access to the same retrieval used to ground chat (T0903) -
    lets a user (or a future UI) see exactly what would be recalled,
    rather than only observing it indirectly through a chat reply.
    """
    return {"results": service.search(user["id"], q)}
