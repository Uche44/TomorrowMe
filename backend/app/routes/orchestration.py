"""
Orchestration Pipeline Controller
Calls all modules in order: voice_capture → persona → scenario → dialogue → audio
Returns a job_id that the client polls for the final audio.
"""
import logging
import uuid
from typing import Literal

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

BASE = "http://localhost:8000"  # self-referential — all modules on same server


class GenerateRequest(BaseModel):
    # Voice
    voice_id: str  # already cloned voice_id from /voice/upload

    # Persona inputs
    current_age: int = Field(ge=18, le=100)
    years_ahead: int = Field(ge=5, le=10)
    goals: list[str] = Field(min_length=1, max_length=10)
    current_state: str = Field(min_length=1, max_length=500)
    personality_traits: list[str] = Field(min_length=1, max_length=5)
    scenario_type: Literal["success", "regret", "neutral"]

    # Dialogue
    length: Literal["short", "long"] = "short"

    # Audio
    effects: list[str] = Field(default_factory=list)

    # Optional: skip LLM scenario and use a preset
    preset_id: str | None = None


class GenerateResponse(BaseModel):
    session_id: str
    persona_id: str
    scenario_id: str
    script_id: str
    job_id: str  # audio synthesis job — poll /audio/status/{job_id}


async def _post(client: httpx.AsyncClient, url: str, payload: dict) -> dict:
    r = await client.post(url, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


@router.post("/generate", status_code=202)
async def generate_full_pipeline(req: GenerateRequest, request: Request):
    """
    Full pipeline:
    1. Generate persona
    2. Generate scenario
    3. Generate dialogue script
    4. Submit audio synthesis job
    Returns job_id for polling.
    """
    session_id = str(uuid.uuid4())
    logger.info("Pipeline START: session_id=%s", session_id)

    async with httpx.AsyncClient(base_url=BASE) as client:
        # Step 1: Persona
        try:
            persona = await _post(client, "/persona/generate", {
                "current_age": req.current_age,
                "years_ahead": req.years_ahead,
                "goals": req.goals,
                "current_state": req.current_state,
                "personality_traits": req.personality_traits,
                "scenario_type": req.scenario_type,
            })
        except httpx.HTTPStatusError as exc:
            logger.error("Pipeline persona failed: %s", exc)
            return JSONResponse(status_code=502, content={"detail": f"Persona generation failed: {exc.response.text}"})
        except Exception as exc:
            return JSONResponse(status_code=502, content={"detail": f"Persona generation error: {exc}"})

        persona_id = persona["persona_id"]
        logger.info("Pipeline persona done: session_id=%s persona_id=%s", session_id, persona_id)

        # Step 2: Scenario
        scenario_payload = {
            "persona_id": persona_id,
            "summary": persona["summary"],
            "tone": persona["tone"],
            "key_life_events": persona["key_life_events"],
            "life_outcome": persona.get("life_outcome", ""),
            "key_message": persona.get("key_message", ""),
            "scenario_type": persona["scenario_type"],
        }
        if req.preset_id:
            scenario_payload["preset_id"] = req.preset_id

        try:
            scenario = await _post(client, "/scenario/generate", scenario_payload)
        except httpx.HTTPStatusError as exc:
            logger.error("Pipeline scenario failed: %s", exc)
            return JSONResponse(status_code=502, content={"detail": f"Scenario generation failed: {exc.response.text}"})
        except Exception as exc:
            return JSONResponse(status_code=502, content={"detail": f"Scenario generation error: {exc}"})

        scenario_id = scenario["scenario_id"]
        logger.info("Pipeline scenario done: session_id=%s scenario_id=%s", session_id, scenario_id)

        # Step 3: Dialogue
        try:
            script = await _post(client, "/dialogue/generate", {
                "persona_id": persona_id,
                "scenario_id": scenario_id,
                "length": req.length,
            })
        except httpx.HTTPStatusError as exc:
            logger.error("Pipeline dialogue failed: %s", exc)
            return JSONResponse(status_code=502, content={"detail": f"Dialogue generation failed: {exc.response.text}"})
        except Exception as exc:
            return JSONResponse(status_code=502, content={"detail": f"Dialogue generation error: {exc}"})

        script_id = script["script_id"]
        logger.info("Pipeline dialogue done: session_id=%s script_id=%s", session_id, script_id)

        # Step 4: Audio synthesis
        try:
            audio_job = await _post(client, "/audio/synthesize", {
                "script_id": script_id,
                "voice_id": req.voice_id,
                "emotion_type": req.scenario_type,
                "effects": req.effects,
            })
        except httpx.HTTPStatusError as exc:
            logger.error("Pipeline audio failed: %s", exc)
            return JSONResponse(status_code=502, content={"detail": f"Audio synthesis failed: {exc.response.text}"})
        except Exception as exc:
            return JSONResponse(status_code=502, content={"detail": f"Audio synthesis error: {exc}"})

        job_id = audio_job["job_id"]
        logger.info("Pipeline audio queued: session_id=%s job_id=%s", session_id, job_id)

    return JSONResponse(status_code=202, content={
        "session_id": session_id,
        "persona_id": persona_id,
        "scenario_id": scenario_id,
        "script_id": script_id,
        "job_id": job_id,
    })
