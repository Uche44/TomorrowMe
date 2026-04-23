import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.models.audio_api import AudioJobResponse, SynthesisRequest
from app.models.audio_persistence import PersistedAudioJob
from app.store.audio_job_store import AudioJobStore, AudioStoreError

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_audio_store(request: Request) -> AudioJobStore:
    return request.app.state.audio_store


@router.post("/audio/synthesize", status_code=202)
async def synthesize(req: SynthesisRequest, request: Request):
    from app.worker.synthesis_task import synthesize_audio

    job_id = str(uuid.uuid4())
    store = _get_audio_store(request)

    job = PersistedAudioJob(
        job_id=job_id,
        status="queued",
        script_id=req.script_id,
        voice_id=req.voice_id,
        emotion_type=req.emotion_type,
        effects=req.effects,
        output_url=None,
        duration_sec=None,
        created_at=datetime.now(timezone.utc),
        quality_pass=None,
        quality_detail=None,
    )

    try:
        await store.save(job)
    except AudioStoreError as exc:
        logger.error("AudioRoute: store unavailable on submit: %s", exc)
        return JSONResponse(status_code=503, content={"detail": "Job store unavailable"})

    # Fire-and-forget background task — no Celery/Redis needed
    asyncio.create_task(
        synthesize_audio(
            job_id=job_id,
            script_id=req.script_id,
            voice_id=req.voice_id,
            emotion_type=req.emotion_type,
            effects=req.effects,
            store=store,
        )
    )

    logger.info(
        "AudioRoute SUBMIT: job_id=%s script_id=%s voice_id=%s effects=%s",
        job_id, req.script_id, req.voice_id, req.effects,
    )
    return JSONResponse(status_code=202, content={"job_id": job_id})


@router.get("/audio/status/{job_id}")
async def get_status(job_id: str, request: Request):
    store = _get_audio_store(request)
    try:
        job = await store.get(job_id)
    except AudioStoreError as exc:
        logger.error("AudioRoute: store unavailable on status read: %s", exc)
        return JSONResponse(status_code=503, content={"detail": "Job store unavailable"})

    if job is None:
        return JSONResponse(status_code=404, content={"detail": f"Job '{job_id}' not found"})

    response = AudioJobResponse(
        job_id=job.job_id,
        status=job.status,  # type: ignore[arg-type]
        output_url=job.output_url if job.status == "done" else None,
        duration_sec=job.duration_sec if job.status == "done" else None,
    )
    return response.model_dump()


@router.get("/audio/download/{job_id}")
async def download(job_id: str, request: Request):
    store = _get_audio_store(request)
    try:
        job = await store.get(job_id)
    except AudioStoreError as exc:
        logger.error("AudioRoute: store unavailable on download: %s", exc)
        return JSONResponse(status_code=503, content={"detail": "Job store unavailable"})

    if job is None:
        return JSONResponse(status_code=404, content={"detail": f"Job '{job_id}' not found"})

    if job.status in ("queued", "processing"):
        return JSONResponse(status_code=202, content={"detail": "Job not yet complete"})

    if job.status == "failed":
        return JSONResponse(status_code=410, content={"detail": "Job failed — no audio file available"})

    output_path = os.path.join(settings.audio_files_dir, f"{job_id}.mp3")
    if not os.path.exists(output_path):
        logger.error("AudioRoute: file missing despite done status: job_id=%s path=%s", job_id, output_path)
        return JSONResponse(status_code=500, content={"detail": "Audio file missing despite completed status"})

    return FileResponse(
        path=output_path,
        media_type="audio/mpeg",
        filename=f"{job_id}.mp3",
        headers={"Content-Disposition": f'attachment; filename="{job_id}.mp3"'},
    )
