"""
Audio synthesis pipeline — runs as a plain asyncio background task.
No Celery or Redis required.
"""
import io
import json
import logging
import os

from pydub import AudioSegment

from app.clients.audio_upstream_client import (
    AudioUpstreamClient,
    DialogueScriptNotFoundError,
    VoiceProfileNotFoundError,
    UpstreamServiceError,
    UpstreamTimeoutError,
)
from app.config import settings
from app.services.elevenlabs_client import ElevenLabsClient, ElevenLabsError
from app.services.effects_processor import apply_effects, EffectsChainError
from app.services.marker_processor import strip_markers, apply_markers, MarkerProcessingError
from app.services.music_mixer import mix_music
from app.services.quality_checker import run_quality_checks, QualityCheckError
from app.store.audio_job_store import AudioJobStore, AudioStoreError

logger = logging.getLogger(__name__)


async def synthesize_audio(
    job_id: str,
    script_id: str,
    voice_id: str,
    emotion_type: str,
    effects: list[str],
    store: AudioJobStore,
) -> None:
    """
    Full async synthesis pipeline. Called via asyncio.create_task().
    Stages:
      1. Update status → processing
      2. Fetch DialogueScript + VoiceProfile
      3. Strip markers from text
      4. ElevenLabs TTS synthesis
      5. Apply emotional marker audio modifications
      6. Apply effects chain
      7. Layer background music
      8. Encode MP3, write to disk
      9. Quality checks → done or failed
    """
    stage = "init"

    try:
        # Stage 1
        stage = "status_update"
        await store.update_status(job_id, "processing")
        logger.info("SynthesisTask START: job_id=%s script_id=%s voice_id=%s", job_id, script_id, voice_id)

        # Stage 2
        stage = "upstream_resolution"
        upstream = AudioUpstreamClient()
        script = await upstream.get_dialogue_script(script_id)
        await upstream.get_voice_profile(voice_id)  # validates voice exists
        logger.info("SynthesisTask upstream resolved: job_id=%s", job_id)

        # Stage 3
        stage = "marker_stripping"
        stripped = strip_markers(script.text)
        clean_text = stripped.clean_text
        logger.info("SynthesisTask markers stripped: job_id=%s markers=%s", job_id, script.emotional_markers)

        # Stage 4 — ElevenLabs TTS (sync SDK call, run in thread)
        stage = "elevenlabs_synthesis"
        import asyncio
        el_client = ElevenLabsClient()
        raw_audio_bytes = await asyncio.to_thread(
            el_client.synthesize, clean_text, voice_id, emotion_type
        )

        if not raw_audio_bytes:
            raise ElevenLabsError("ElevenLabs returned empty audio")

        audio = AudioSegment.from_file(io.BytesIO(raw_audio_bytes), format="mp3")
        if len(audio) == 0:
            raise ElevenLabsError("Synthesized audio has zero duration")

        logger.info("SynthesisTask TTS done: job_id=%s duration_ms=%d", job_id, len(audio))

        # Stage 5
        stage = "marker_processing"
        if script.emotional_markers:
            audio = apply_markers(audio, script.emotional_markers)
        else:
            logger.warning("SynthesisTask no emotional markers: job_id=%s", job_id)

        # Stage 6
        stage = "effects_chain"
        audio = apply_effects(audio, effects)

        # Stage 7
        stage = "music_mixing"
        audio = mix_music(audio, emotion_type)

        # Stage 8
        stage = "mp3_encoding"
        os.makedirs(settings.audio_files_dir, exist_ok=True)
        output_path = os.path.join(settings.audio_files_dir, f"{job_id}.mp3")
        await asyncio.to_thread(audio.export, output_path, format="mp3", bitrate="128k")

        duration_sec = len(audio) / 1000.0
        if duration_sec == 0 or os.path.getsize(output_path) == 0:
            raise QualityCheckError(f"Output file is empty: {output_path}")

        logger.info("SynthesisTask MP3 written: job_id=%s path=%s duration=%.1fs", job_id, output_path, duration_sec)

        # Stage 9
        stage = "quality_checks"
        quality_result = run_quality_checks(
            audio_path=output_path,
            duration_sec=duration_sec,
            job_id=job_id,
            estimated_duration_sec=script.estimated_duration_sec,
        )

        output_url = f"/audio/download/{job_id}"
        quality_detail = json.dumps({k: v for k, v in quality_result.items() if k != "passed"})

        await store.update_status(
            job_id=job_id,
            status="done",
            output_url=output_url,
            duration_sec=duration_sec,
            quality_pass=True,
            quality_detail=quality_detail,
        )
        logger.info("SynthesisTask DONE: job_id=%s duration=%.1fs", job_id, duration_sec)

    except (
        DialogueScriptNotFoundError, VoiceProfileNotFoundError,
        UpstreamServiceError, UpstreamTimeoutError,
        ElevenLabsError, MarkerProcessingError, EffectsChainError, QualityCheckError,
    ) as exc:
        await _fail_job(store, job_id, stage, exc)
    except Exception as exc:
        await _fail_job(store, job_id, stage, exc)


async def _fail_job(store: AudioJobStore, job_id: str, stage: str, exc: Exception) -> None:
    logger.error(
        "SynthesisTask FAILED: job_id=%s stage=%s error_type=%s detail=%s",
        job_id, stage, type(exc).__name__, str(exc),
    )
    try:
        await store.update_status(job_id, "failed")
    except Exception as store_exc:
        logger.error("SynthesisTask could not update status to failed: %s", store_exc)
