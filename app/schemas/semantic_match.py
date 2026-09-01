
from pydantic import BaseModel, Field, field_validator


class SemanticMatchRequest(BaseModel):
    targets: list[str] = Field(..., description="List of query strings to match.")
    corpus: list[str] = Field(..., description="List of candidate strings to match against.")
    score: float = Field(
        0, description="Minimum similarity score (0-1) required to report a match."
    )

    @field_validator("targets", "corpus")
    @classmethod
    def not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("must not be an empty list")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "targets": ["How do I reset my password?"],
                "corpus": [
                    "Steps to reset your account password",
                    "How to cancel a subscription",
                ],
                "score": 0.3,
            }
        }
    }


class SemanticMatchResult(BaseModel):
    """Documents the *typical* shape of one item in the response, for
    reference/OpenAPI purposes only. The actual endpoint response is not
    validated against this (or any) schema -- see the response_model=Any
    note on the router -- since the response is a pass-through of
    whatever the configured backend returns, which may not match this
    shape (including something as minimal as `{}`)."""

    query_index: int
    query: str
    match_index: int | None = None
    best_match: str | None = None
    similarity_score: float = 0
