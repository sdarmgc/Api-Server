
from typing import Any

from fastapi import APIRouter, Body, Request

from app.config import settings
from app.rate_limit import limiter
from app.services import pass_through_service

router = APIRouter(tags=["Pass-through"])


@router.post(
    "/api/pass-through",
    response_model=Any,
    summary="Forward arbitrary JSON to the configured backend and return its response as-is",
)
@limiter.limit(settings.RATE_LIMIT_PASS_THROUGH)
async def pass_through(
    request: Request, payload: dict[str, Any] = Body(default_factory=dict)  # noqa: B008
):
    """
    Generic pass-through: the request body is forwarded verbatim to the
    configured backend, and the backend's response is returned verbatim.
    Neither side has a fixed schema -- `{}` is a valid request and a valid
    response.
    """
    return await pass_through_service.pass_through(payload)
