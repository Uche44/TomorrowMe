import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.clients.upstream_client import UpstreamClient
from app.exceptions import StoreError
from app.models.api import DialogueRequest, DialogueScript
from app.models.persistence import PersistedScript
from app.services.script_builder import ScriptBuilder
from app.services.quality_validator import QualityValidator

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_store(request: Request):
    return request.app.state.store


async def _generate(request: Request, req: DialogueRequest) -> JSONResponse:
    upstream = UpstreamClient()
    persona = await upstream.get_persona(req.persona_id)
    scenario = await upstream.get_scenario(req.scenario_id)

    builder = ScriptBuilder(validator=QualityValidator())
    script: DialogueScript = await builder.build_script(
        persona=persona,
        scenario=scenario,
        length=req.length,
        tone_override=req.tone_override,
    )

    # Build quality detail from the last validation (always passes here)
    quality_detail = json.dumps({"structure_ok": True, "duration_ok": True, "markers_ok": True})

    persisted = PersistedScript(
        script_id=script.script_id,
        text=script.text,
        estimated_duration_sec=script.estimated_duration_sec,
        emotional_markers=script.emotional_markers,
        persona_id=req.persona_id,
        scenario_id=req.scenario_id,
        length=req.length,
        created_at=datetime.now(timezone.utc),
        quality_pass=True,
        quality_detail=quality_detail,
    )

    store = _get_store(request)
    await store.save(persisted)

    return JSONResponse(status_code=201, content=script.model_dump())


@router.post("/dialogue/generate")
async def generate_dialogue(req: DialogueRequest, request: Request):
    return await _generate(request, req)


@router.post("/dialogue/regenerate")
async def regenerate_dialogue(req: DialogueRequest, request: Request):
    return await _generate(request, req)


@router.get("/dialogue/{script_id}")
async def get_dialogue(script_id: str, request: Request):
    store = _get_store(request)
    record = await store.get(script_id)
    if record is None:
        return JSONResponse(status_code=404, content={"detail": f"Script '{script_id}' not found"})
    script = DialogueScript(
        script_id=record.script_id,
        text=record.text,
        estimated_duration_sec=record.estimated_duration_sec,
        emotional_markers=record.emotional_markers,
    )
    return script.model_dump()
