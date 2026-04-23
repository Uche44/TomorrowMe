import json
import logging
import re
import uuid
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.clients.hf_client import HFClient
from app.store.persona_store import PersonaStore, PersonaStoreError

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_RETRIES = 2

TONE_MAP = {
    "success": "confident, fulfilled",
    "regret": "reflective, slightly heavy",
    "neutral": "calm, observational",
}


class UserProfileRequest(BaseModel):
    current_age: int = Field(ge=18, le=100)
    years_ahead: int = Field(ge=5, le=10)
    goals: list[str] = Field(min_length=1, max_length=10)
    current_state: str = Field(min_length=1, max_length=500)
    personality_traits: list[str] = Field(min_length=1, max_length=5)
    scenario_type: Literal["success", "regret", "neutral"]

    @field_validator("goals")
    @classmethod
    def goals_length(cls, v: list[str]) -> list[str]:
        for g in v:
            if len(g) > 200:
                raise ValueError("Each goal must be ≤ 200 characters")
        return v

    @field_validator("personality_traits")
    @classmethod
    def traits_length(cls, v: list[str]) -> list[str]:
        for t in v:
            if len(t) > 50:
                raise ValueError("Each trait must be ≤ 50 characters")
        return v


def _get_persona_store(request: Request) -> PersonaStore:
    return request.app.state.persona_store


def _build_prompt(req: UserProfileRequest) -> str:
    tone = TONE_MAP[req.scenario_type]
    goals_str = "\n".join(f"- {g}" for g in req.goals)
    traits_str = ", ".join(req.personality_traits)
    outcome_hint = (
        "achieved major goals" if req.scenario_type == "success"
        else "failed or gave up on key goals" if req.scenario_type == "regret"
        else "mixed or average outcome"
    )
    return f"""You are a creative writer generating a "future self" persona for a voice simulator.

USER PROFILE:
- Current age: {req.current_age}, projecting {req.years_ahead} years ahead
- Current state: {req.current_state}
- Personality traits: {traits_str}
- Goals:
{goals_str}
- Scenario type: {req.scenario_type} (tone: "{tone}", outcome: {outcome_hint})

Return ONLY a valid JSON object with these exact fields (no explanation, no markdown, no code fences):
{{
  "summary": "150-250 word first-person narrative spoken by the future self. Emotional, specific, references the goals.",
  "tone": "{tone}",
  "key_life_events": ["specific event 1", "specific event 2", "specific event 3"],
  "life_outcome": "One sentence max 180 chars describing life {req.years_ahead} years from now matching {req.scenario_type}.",
  "key_message": "Max 120 chars. The single most important thing to tell your present self."
}}"""


def _extract_json(raw: str) -> str:
    """Extract the JSON object from the response, stripping any surrounding text."""
    text = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text


def _parse_persona(raw: str, persona_id: str, req: UserProfileRequest) -> dict | None:
    try:
        text = _extract_json(raw)
        data = json.loads(text)
        data["tone"] = TONE_MAP[req.scenario_type]  # enforce deterministic tone
        data["persona_id"] = persona_id
        data["scenario_type"] = req.scenario_type
        return data
    except Exception as exc:
        logger.warning("Persona parse failed: %s | raw preview: %.300s", exc, raw)
        return None


def _validate_persona(data: dict) -> list[str]:
    issues = []
    if len(data.get("summary", "").split()) < 30:
        issues.append("summary too short (need ≥30 words)")
    if not (3 <= len(data.get("key_life_events", [])) <= 7):
        issues.append(f"key_life_events count {len(data.get('key_life_events', []))} outside 3-7")
    if not data.get("life_outcome", "").strip():
        issues.append("life_outcome is empty")
    if not data.get("key_message", "").strip():
        issues.append("key_message is empty")
    return issues


@router.post("/persona/generate", status_code=201)
async def generate_persona(req: UserProfileRequest, request: Request):
    store = _get_persona_store(request)
    client = HFClient(max_tokens=1024, temperature=0.7)
    prompt = _build_prompt(req)
    persona_id = str(uuid.uuid4())

    for attempt in range(MAX_RETRIES + 1):
        try:
            raw = await client.generate(system_prompt="", user_prompt=prompt)
            logger.debug("Persona raw (attempt %d): %.400s", attempt + 1, raw)

            data = _parse_persona(raw, persona_id, req)
            if data is None:
                logger.warning("Persona parse failed attempt %d", attempt + 1)
                if attempt < MAX_RETRIES:
                    continue
                return JSONResponse(status_code=502, content={"detail": "Could not parse LLM response as JSON after retries"})

            issues = _validate_persona(data)
            if issues:
                logger.warning("Persona quality issues attempt %d: %s", attempt + 1, issues)
                if attempt < MAX_RETRIES:
                    continue
                return JSONResponse(status_code=502, content={"detail": f"Persona quality checks failed: {issues}"})

            try:
                await store.save({**data, **req.model_dump(), "narrative_coherence": True})
            except PersonaStoreError as exc:
                return JSONResponse(status_code=503, content={"detail": str(exc)})

            return JSONResponse(status_code=201, content={
                "persona_id": data["persona_id"],
                "summary": data["summary"],
                "tone": data["tone"],
                "key_life_events": data["key_life_events"],
                "life_outcome": data["life_outcome"],
                "key_message": data["key_message"],
                "scenario_type": data["scenario_type"],
            })

        except Exception as exc:
            logger.warning("Persona LLM error attempt %d: %s", attempt + 1, exc)
            if attempt == MAX_RETRIES:
                return JSONResponse(status_code=502, content={"detail": f"LLM generation failed: {exc}"})

    return JSONResponse(status_code=502, content={"detail": "Persona generation failed after retries"})


@router.get("/persona/{persona_id}")
async def get_persona(persona_id: str, request: Request):
    store = _get_persona_store(request)
    try:
        persona = await store.get(persona_id)
    except PersonaStoreError as exc:
        return JSONResponse(status_code=503, content={"detail": str(exc)})
    if persona is None:
        return JSONResponse(status_code=404, content={"detail": f"Persona '{persona_id}' not found"})
    return {
        "persona_id": persona["persona_id"],
        "summary": persona["summary"],
        "tone": persona["tone"],
        "key_life_events": persona["key_life_events"],
        "life_outcome": persona["life_outcome"],
        "key_message": persona["key_message"],
        "scenario_type": persona["scenario_type"],
    }
