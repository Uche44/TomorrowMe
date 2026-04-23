from typing import Literal
from pydantic import BaseModel, Field, field_validator


class DialogueRequest(BaseModel):
    persona_id: str
    scenario_id: str
    length: Literal["short", "long"]
    tone_override: str | None = Field(default=None, max_length=100)

    @field_validator("persona_id", "scenario_id")
    @classmethod
    def no_whitespace(cls, v: str) -> str:
        if not v or v != v.strip() or " " in v:
            raise ValueError("must be a non-empty string with no whitespace")
        return v

    @field_validator("tone_override")
    @classmethod
    def tone_not_empty(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("tone_override must not be blank if provided")
        return v


class DialogueScript(BaseModel):
    script_id: str
    text: str
    estimated_duration_sec: float
    emotional_markers: list[str]


class ErrorResponse(BaseModel):
    detail: str
