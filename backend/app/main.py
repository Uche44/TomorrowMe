import logging
import os
from contextlib import asynccontextmanager

# Point pydub at the bundled ffmpeg binary (no system install needed on Render)
try:
    import imageio_ffmpeg
    _ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    os.environ.setdefault("PATH", "")
    os.environ["PATH"] = os.path.dirname(_ffmpeg_path) + os.pathsep + os.environ["PATH"]
    from pydub import AudioSegment
    AudioSegment.converter = _ffmpeg_path
    AudioSegment.ffmpeg = _ffmpeg_path
    AudioSegment.ffprobe = _ffmpeg_path.replace("ffmpeg", "ffprobe")
except Exception:
    pass  # ffmpeg not available — audio processing will fail gracefully at runtime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.exceptions import (
    LLMProviderError,
    LLMTimeoutError,
    PersonaNotFoundError,
    ScenarioNotFoundError,
    ScriptQualityError,
    StoreError,
    UpstreamServiceError,
    UpstreamTimeoutError,
)
from app.routes.audio import router as audio_router
from app.routes.dialogue import router as dialogue_router
from app.routes.orchestration import router as orchestration_router
from app.routes.persona import router as persona_router
from app.routes.scenario import router as scenario_router
from app.routes.voice import router as voice_router
from app.store.audio_job_store import AudioJobStore, AudioStoreError, init_audio_db
from app.store.persona_store import PersonaStore, PersonaStoreError, init_persona_db
from app.store.scenario_store import ScenarioStore, ScenarioStoreError, init_scenario_db
from app.store.script_store import ScriptStore, init_db
from app.store.voice_store import VoiceStore, VoiceStoreError, init_voice_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(settings.database_url)
    app.state.store = ScriptStore(settings.database_url)

    await init_audio_db(settings.audio_db_url)
    app.state.audio_store = AudioJobStore(settings.audio_db_url)

    await init_voice_db(settings.voice_db_url)
    app.state.voice_store = VoiceStore(settings.voice_db_url)

    await init_persona_db(settings.persona_db_url)
    app.state.persona_store = PersonaStore(settings.persona_db_url)

    await init_scenario_db(settings.scenario_db_url)
    app.state.scenario_store = ScenarioStore(settings.scenario_db_url)

    yield


app = FastAPI(title="Future Self Voice Simulator", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(voice_router, tags=["Voice"])
app.include_router(persona_router, tags=["Persona"])
app.include_router(scenario_router, tags=["Scenario"])
app.include_router(dialogue_router, tags=["Dialogue"])
app.include_router(audio_router, tags=["Audio"])
app.include_router(orchestration_router, tags=["Orchestration"])


def _log_error(request: Request, exc: Exception) -> None:
    logger.error("Error: method=%s path=%s detail=%s", request.method, request.url.path, str(exc))


@app.exception_handler(PersonaNotFoundError)
async def persona_not_found(request: Request, exc: PersonaNotFoundError):
    _log_error(request, exc)
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ScenarioNotFoundError)
async def scenario_not_found(request: Request, exc: ScenarioNotFoundError):
    _log_error(request, exc)
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(UpstreamServiceError)
async def upstream_service_error(request: Request, exc: UpstreamServiceError):
    _log_error(request, exc)
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(UpstreamTimeoutError)
async def upstream_timeout(request: Request, exc: UpstreamTimeoutError):
    _log_error(request, exc)
    return JSONResponse(status_code=504, content={"detail": str(exc)})


@app.exception_handler(LLMTimeoutError)
async def llm_timeout(request: Request, exc: LLMTimeoutError):
    _log_error(request, exc)
    return JSONResponse(status_code=504, content={"detail": str(exc)})


@app.exception_handler(LLMProviderError)
async def llm_provider_error(request: Request, exc: LLMProviderError):
    _log_error(request, exc)
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(ScriptQualityError)
async def script_quality_error(request: Request, exc: ScriptQualityError):
    _log_error(request, exc)
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(StoreError)
async def store_error(request: Request, exc: StoreError):
    _log_error(request, exc)
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(AudioStoreError)
async def audio_store_error(request: Request, exc: AudioStoreError):
    _log_error(request, exc)
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
