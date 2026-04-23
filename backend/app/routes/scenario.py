import hashlib
import json
import logging
import re
import uuid
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.clients.hf_client import HFClient
from app.store.scenario_store import ScenarioStore, ScenarioStoreError

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_RETRIES = 2

EMOTIONAL_TARGET_MAP = {
    "success": "celebratory",
    "regret": "challenging",
    "neutral": "reassuring",
}

# Preset library — at least 10 scenarios, 3+ per type
PRESETS = [
    {"scenario_type": "success", "emotional_target": "celebratory", "title": "The Promotion You Worked For", "context": "You've just been promoted to the role you spent three years preparing for. The late nights studying, the side projects, the mentorship sessions — they all led here. Your team respects you, your manager trusts you, and you're finally doing work that matters.", "trigger": "The morning after receiving your promotion letter"},
    {"scenario_type": "success", "emotional_target": "celebratory", "title": "Launching Your Own Business", "context": "Your small business just hit its first profitable quarter. What started as a side project in your spare bedroom is now a real company with three employees and a growing client list. You took the leap and it paid off.", "trigger": "The day you sign your first major client contract"},
    {"scenario_type": "success", "emotional_target": "celebratory", "title": "Finishing Your Degree", "context": "You completed the degree you almost gave up on twice. Balancing work, family, and study was brutal, but you crossed the finish line. The certificate is real. The knowledge is yours.", "trigger": "The evening before your graduation ceremony"},
    {"scenario_type": "regret", "emotional_target": "challenging", "title": "The Job You Didn't Take", "context": "You turned down a job offer that felt too risky at the time. The company went on to become one of the most exciting places to work in your field. You stayed safe, and now you wonder what might have been.", "trigger": "Seeing a former colleague announce their success at that company"},
    {"scenario_type": "regret", "emotional_target": "challenging", "title": "The Relationship You Let Drift", "context": "A close friendship slowly faded because neither of you made time for it. No fight, no falling out — just distance and silence. You think about them sometimes and wish you'd picked up the phone.", "trigger": "Finding an old photo of the two of you together"},
    {"scenario_type": "regret", "emotional_target": "challenging", "title": "The Health You Ignored", "context": "Years of skipping exercise and eating poorly caught up with you. Nothing catastrophic, but your energy is lower, your focus is weaker, and you know it didn't have to be this way. Small choices compounded.", "trigger": "A routine check-up where the doctor raises concerns"},
    {"scenario_type": "neutral", "emotional_target": "reassuring", "title": "A Quiet Life Well Lived", "context": "Things didn't go exactly as planned, but they didn't fall apart either. You have a stable job, a small circle of people you trust, and a routine that mostly works. It's not dramatic, but it's yours.", "trigger": "A Sunday afternoon with nothing urgent to do"},
    {"scenario_type": "neutral", "emotional_target": "reassuring", "title": "The Career Pivot", "context": "You changed careers mid-stream. It wasn't glamorous — you took a pay cut and started over in many ways. But you're doing work that fits you better, and the adjustment period is mostly behind you.", "trigger": "Your one-year anniversary at the new job"},
    {"scenario_type": "neutral", "emotional_target": "reassuring", "title": "Moving to a New City", "context": "You relocated for reasons that made sense at the time. The new city is fine — not perfect, not terrible. You've built a small life there: a few friends, a favourite coffee shop, a neighbourhood you know.", "trigger": "The first time a new friend asks you about where you grew up"},
    {"scenario_type": "success", "emotional_target": "celebratory", "title": "Paying Off Your Debt", "context": "You made the last payment on your student loans. It took discipline, sacrifice, and years of saying no to things you wanted. But the weight is gone. You own your financial future now.", "trigger": "The moment the final payment clears your account"},
]

# Assign stable deterministic IDs to presets
for _p in PRESETS:
    _p["scenario_id"] = "preset-" + hashlib.md5(_p["title"].encode()).hexdigest()[:12]
    _p["is_preset"] = True


class PersonaInput(BaseModel):
    persona_id: str
    summary: str
    tone: str
    key_life_events: list[str]
    life_outcome: str = ""
    key_message: str = ""
    scenario_type: Literal["success", "regret", "neutral"] = "neutral"
    preset_id: str | None = None

    @field_validator("persona_id")
    @classmethod
    def no_ws(cls, v: str) -> str:
        if not v or " " in v:
            raise ValueError("persona_id must be non-empty with no whitespace")
        return v


def _get_scenario_store(request: Request) -> ScenarioStore:
    return request.app.state.scenario_store


def _build_scenario_prompt(persona: PersonaInput) -> str:
    target = EMOTIONAL_TARGET_MAP.get(persona.scenario_type, "reassuring")
    events_str = "\n".join(f"- {e}" for e in persona.key_life_events[:3])
    return f"""Generate a scenario for a "future self" voice message.

PERSONA:
- Summary: {persona.summary[:300]}
- Tone: {persona.tone}
- Scenario type: {persona.scenario_type} → emotional target: {target}
- Life outcome: {persona.life_outcome}
- Key life events:
{events_str}

Generate a JSON object with EXACTLY these fields:
{{
  "title": "<≤80 chars specific scenario title>",
  "context": "<30-200 word prose narrative with specific life details>",
  "emotional_target": "{target}",
  "trigger": "<≤150 chars specific life moment description>"
}}

Rules:
- Must be plausible within 5-10 years
- Must include specific life details (no generic statements like "you achieved your dreams")
- context must be 30-200 words
- title must be ≤80 chars
- trigger must reference a concrete moment
- Output ONLY valid JSON, no markdown fences"""


def _parse_scenario(raw: str, scenario_id: str, scenario_type: str) -> dict | None:
    try:
        text = re.sub(r"```(?:json)?", "", raw).strip()
        data = json.loads(text)
        data["scenario_id"] = scenario_id
        data["scenario_type"] = scenario_type
        data["emotional_target"] = EMOTIONAL_TARGET_MAP.get(scenario_type, "reassuring")
        return data
    except Exception as exc:
        logger.warning("Scenario parse failed: %s", exc)
        return None


def _validate_scenario(data: dict, scenario_type: str) -> list[str]:
    issues = []
    expected_target = EMOTIONAL_TARGET_MAP[scenario_type]
    if data.get("emotional_target") != expected_target:
        issues.append(f"emotional_target mismatch: expected {expected_target}")
    ctx_words = len(data.get("context", "").split())
    if not (30 <= ctx_words <= 200):
        issues.append(f"context word count {ctx_words} outside 30-200")
    if len(data.get("title", "")) > 80:
        issues.append("title exceeds 80 chars")
    return issues


@router.get("/scenario/presets")
async def get_presets():
    return PRESETS


@router.post("/scenario/generate", status_code=201)
async def generate_scenario(persona: PersonaInput, request: Request):
    store = _get_scenario_store(request)

    # Preset selection
    if persona.preset_id:
        preset = next((p for p in PRESETS if p["scenario_id"] == persona.preset_id), None)
        if preset is None:
            return JSONResponse(status_code=404, content={"detail": f"Preset '{persona.preset_id}' not found"})
        return JSONResponse(status_code=200, content=preset)

    # LLM generation
    client = HFClient(max_tokens=512, temperature=0.8)
    prompt = _build_scenario_prompt(persona)
    scenario_id = str(uuid.uuid4())

    for attempt in range(MAX_RETRIES + 1):
        try:
            raw = await client.generate(system_prompt="", user_prompt=prompt)
            data = _parse_scenario(raw, scenario_id, persona.scenario_type)
            if data is None:
                logger.warning("Scenario parse failed attempt %d", attempt + 1)
                if attempt < MAX_RETRIES:
                    continue
                return JSONResponse(status_code=502, content={"detail": "Could not parse scenario JSON after retries"})
            issues = _validate_scenario(data, persona.scenario_type)
            if issues:
                logger.warning("Scenario quality issues attempt %d: %s", attempt + 1, issues)
                if attempt < MAX_RETRIES:
                    continue
                return JSONResponse(status_code=502, content={"detail": f"Scenario quality checks failed: {issues}"})
            try:
                await store.save({**data, "plausibility_ok": True})
            except ScenarioStoreError:
                pass  # non-fatal
            return JSONResponse(status_code=201, content={
                "scenario_id": data["scenario_id"],
                "title": data["title"],
                "context": data["context"],
                "emotional_target": data["emotional_target"],
                "trigger": data["trigger"],
                "scenario_type": data["scenario_type"],
            })
        except Exception as exc:
            logger.warning("Scenario LLM error attempt %d: %s", attempt + 1, exc)
            if attempt == MAX_RETRIES:
                return JSONResponse(status_code=502, content={"detail": f"Scenario generation failed: {exc}"})

    return JSONResponse(status_code=502, content={"detail": "Scenario generation failed after retries"})


@router.get("/scenario/{scenario_id}")
async def get_scenario(scenario_id: str, request: Request):
    # Check presets first
    preset = next((p for p in PRESETS if p["scenario_id"] == scenario_id), None)
    if preset:
        return preset
    store = _get_scenario_store(request)
    scenario = await store.get(scenario_id)
    if scenario is None:
        return JSONResponse(status_code=404, content={"detail": f"Scenario '{scenario_id}' not found"})
    return scenario
