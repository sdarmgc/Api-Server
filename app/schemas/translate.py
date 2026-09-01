
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TranslateRequest(BaseModel):
    """
    Request body uses hyphenated JSON keys (source-text, source-lang,
    target-lang) as specified. Pydantic aliases map these to valid Python
    attribute names internally.
    """

    source_text: list[str] = Field(..., alias="source-text")
    source_lang: str = Field(..., alias="source-lang")
    target_lang: str = Field(..., alias="target-lang")
    option: int = Field(0, alias="option")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "source-text": ["Hello, how are you?"],
                "source-lang": "en",
                "target-lang": "es",
                "option": 0,
            }
        },
    )

    @field_validator("source_text")
    @classmethod
    def not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("source-text must not be an empty list")
        return v


class TranslateResponse(BaseModel):
    source_text: list[str] = Field(..., alias="source-text")
    target_text: list[str] = Field(..., alias="target-text")
    source_lang: str = Field(..., alias="source-lang")
    target_lang: str = Field(..., alias="target-lang")
    option: int = Field(0, alias="option")

    model_config = ConfigDict(populate_by_name=True)
