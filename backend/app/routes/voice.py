import io
import logging
from datetime import datetime, timezone

from elevenlabs import ElevenLabs
from elevenlabs.core import ApiError
from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse
from pydub import AudioSegment

from app.config import settings
from app.store.voice_store import VoiceStore, VoiceStoreError

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_FORMATS = {"wav", "mp3", "m4a", "ogg", "webm"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MIN_DURATION_SEC = 5.0
MAX_DURATION_SEC = 15.0

FORMAT_MAP = {
    "wav": "wav",
    "mp3": "mp3",
    "m4a": "mp4",
    "ogg": "ogg",
    "webm": "webm",
}


def _get_voice_store(request: Request) -> VoiceStore:
    return request.app.state.voice_store


def _ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _measure_duration(data: bytes, ext: str) -> float:
    fmt = FORMAT_MAP.get(ext, ext)
    try:
        seg = AudioSegment.from_file(io.BytesIO(data), format=fmt)
        return len(seg) / 1000.0
    except Exception as exc:
        logger.warning("Duration measurement failed for format=%s: %s", fmt, exc)
        try:
            seg = AudioSegment.from_file(io.BytesIO(data))
            return len(seg) / 1000.0
        except Exception as exc2:
            logger.warning("Duration measurement fallback also failed: %s", exc2)
            return 0.0


@router.post("/voice/upload", status_code=201)
async def upload_voice(request: Request, files: list[UploadFile] = File(...)):
    store = _get_voice_store(request)

    # Read all files into memory once — avoids double-read / seek issues
    file_records: list[tuple[bytes, str, str]] = []  # (data, filename, ext)
    for f in files:
        ext = _ext(f.filename or "")
        if ext not in ALLOWED_FORMATS:
            return JSONResponse(
                status_code=415,
                content={"detail": f"Unsupported format: '{ext}'. Allowed: {sorted(ALLOWED_FORMATS)}"},
            )
        data = await f.read()
        if len(data) > MAX_FILE_SIZE_BYTES:
            return JSONResponse(
                status_code=422,
                content={"detail": f"File '{f.filename}' exceeds 50 MB limit"},
            )
        if len(data) == 0:
            return JSONResponse(
                status_code=422,
                content={"detail": f"File '{f.filename}' is empty"},
            )
        file_records.append((data, f.filename or f"sample.{ext}", ext))

    # Measure total duration
    total_duration = 0.0
    for data, filename, ext in file_records:
        dur = _measure_duration(data, ext)
        logger.info("File '%s': duration=%.2fs ext=%s size=%d bytes", filename, dur, ext, len(data))
        total_duration += dur

    logger.info("Total audio duration: %.2fs across %d file(s)", total_duration, len(file_records))

    if total_duration < MIN_DURATION_SEC:
        return JSONResponse(
            status_code=422,
            content={"detail": (
                f"Total sample duration {total_duration:.1f}s is less than the required "
                f"{MIN_DURATION_SEC:.0f} seconds. Please record at least {MIN_DURATION_SEC:.0f} seconds."
            )},
        )

    if total_duration > MAX_DURATION_SEC:
        logger.warning("Voice upload: total duration %.1fs exceeds recommended %.0fs maximum", total_duration, MAX_DURATION_SEC)

    # Clone via ElevenLabs IVC (Instant Voice Cloning) — SDK v2.x API
    el = ElevenLabs(api_key=settings.elevenlabs_api_key)
    voice_name = f"future-self-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    last_error: Exception | None = None
    voice_id: str | None = None

    for attempt in range(2):
        try:
            response = el.voices.ivc.create(
                name=voice_name,
                description="Personal voice clone for Future Self Voice Simulator",
                files=[io.BytesIO(data) for data, _, _ in file_records],
            )
            voice_id = response.voice_id
            break
        except ApiError as exc:
            last_error = exc
            if attempt == 0:
                logger.warning("ElevenLabs ivc.create failed (attempt 1): %s — retrying", exc)
                continue
            logger.error("ElevenLabs ivc.create failed after retry: %s", exc)
            return JSONResponse(
                status_code=502,
                content={"detail": f"ElevenLabs voice cloning failed: {exc}"},
            )
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                logger.warning("Voice cloning error (attempt 1): %s — retrying", exc)
                continue
            logger.exception("Voice cloning unexpected error after retry")
            return JSONResponse(
                status_code=502,
                content={"detail": f"Voice cloning error: {exc}"},
            )

    if voice_id is None:
        return JSONResponse(
            status_code=502,
            content={"detail": f"Voice cloning failed: {last_error}"},
        )

    # Persist
    try:
        await store.save(voice_id=voice_id, sample_duration_sec=total_duration, similarity_score=None)
    except VoiceStoreError as exc:
        logger.error("VoiceStore save failed: %s", exc)
        return JSONResponse(status_code=503, content={"detail": "Voice store unavailable"})

    logger.info("Voice cloned successfully: voice_id=%s duration=%.1fs", voice_id, total_duration)
    return JSONResponse(
        status_code=201,
        content={"voice_id": voice_id, "provider": "elevenlabs", "sample_duration_sec": total_duration},
    )


@router.get("/voice/{voice_id}")
async def get_voice(voice_id: str, request: Request):
    store = _get_voice_store(request)
    try:
        profile = await store.get(voice_id)
    except VoiceStoreError as exc:
        return JSONResponse(status_code=503, content={"detail": str(exc)})
    if profile is None:
        return JSONResponse(status_code=404, content={"detail": f"Voice '{voice_id}' not found"})
    return profile


@router.delete("/voice/{voice_id}", status_code=204)
async def delete_voice(voice_id: str, request: Request):
    store = _get_voice_store(request)
    profile = await store.get(voice_id)
    if profile is None:
        return JSONResponse(status_code=404, content={"detail": f"Voice '{voice_id}' not found"})

    el = ElevenLabs(api_key=settings.elevenlabs_api_key)
    try:
        el.voices.delete(voice_id)
    except ApiError as exc:
        logger.error("ElevenLabs delete failed: %s", exc)
        return JSONResponse(status_code=502, content={"detail": f"ElevenLabs deletion failed: {exc}"})

    await store.delete(voice_id)
    return JSONResponse(status_code=204, content=None)
