from fastapi import APIRouter, Request

from app.config import settings
from app.rate_limit import limiter
from app.schemas.translate import TranslateRequest, TranslateResponse
from app.services import translation_service

router = APIRouter(tags=["Translation"])


@router.post(
    "/api/translate",
    response_model=TranslateResponse,
    response_model_by_alias=True,
    summary="Translate a list of strings from one language to another",
)
@limiter.limit(settings.RATE_LIMIT_TRANSLATE)
async def translate(request: Request, payload: TranslateRequest):
    """
    Translates every string in `source_text` from `source_lang` to
    `target_lang`. `option` is passed through unchanged and can be used by
    a specific backend implementation (e.g. formality level, glossary id).
    """
    return await translation_service.translate(payload)
