
from typing import Any

from fastapi import APIRouter, Request

from app.config import settings
from app.rate_limit import limiter
from app.schemas.semantic_match import SemanticMatchRequest
from app.services import semantic_match_service

router = APIRouter(tags=["Semantic Match"])


@router.post(
    "/api/semantic-match",
    response_model=Any,
    summary="Find the best semantic match for each string in `targets` within a corpus",
)
@limiter.limit(settings.RATE_LIMIT_SEMANTIC_MATCHING)
async def semantic_match(request: Request, payload: SemanticMatchRequest):
    """
    For every string in `targets`, find the most similar string in `corpus`.

    The response is returned exactly as the configured backend sends it --
    no fixed schema is enforced, so the backend's JSON (including `{}` or
    any other shape) passes straight through unmodified. See
    `app/schemas/semantic_match.py`'s `SemanticMatchResult` for the
    *typical* shape a backend would return, documented there for reference
    only.
    """
    return await semantic_match_service.match(payload)
