from typing import Literal
from pydantic import BaseModel, Field, field_validator

VALID_EFFECTS = {"reverb", "warmth", "ambient", "wind", "city", "room_tone"}
VALID_EMOTIONS = {"success", "regret", "neutral"}


class SynthesisRequest(BaseModel):
    script_id: str
    voice_id: str
    emotion_type: Literal["success", "regret", "neutral"]
    effects: list[str] = Field(default_factory=list)

    @field_validator("script_id", "voice_id")
    @classmethod
    def no_whitespace(cls, v: str) -> str:
        if not v or v != v.strip() or " " in v:
            raise ValueError("must be a non-empty string with no whitespace")
        return v

    @field_validator("effects")
    @classmethod
    def valid_effects(cls, v: list[str]) -> list[str]:
        invalid = set(v) - VALID_EFFECTS
        if invalid:
            raise ValueError(f"invalid effect(s): {sorted(invalid)}. Allowed: {sorted(VALID_EFFECTS)}")
        return v


class AudioJobResponse(BaseModel):
    job_id: str
    status: Literal["queued", "processing", "done", "failed"]
    output_url: str | None
    duration_sec: float | None
