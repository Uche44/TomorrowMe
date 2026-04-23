# Implementation Plan: Audio Production Engine

## Overview

Extend the existing FastAPI backend with an async audio synthesis pipeline: Pydantic models, aiosqlite persistence, Celery + Redis worker, ElevenLabs TTS integration, pydub post-processing chain, and a React AudioPlayer frontend component. Follows the same structural patterns as the Dialogue Generator module.

## Tasks

- [x] 1. Add dependencies and configuration
  - Add `elevenlabs`, `celery`, `redis`, `pydub` to `backend/requirements.txt`
  - Add `ELEVENLABS_API_KEY`, `REDIS_URL`, `DIALOGUE_API_BASE_URL`, `VOICE_API_BASE_URL`, `AUDIO_DB_URL`, `AUDIO_FILES_DIR` fields to `app/config.py` with sensible defaults
  - Create `backend/audio_files/` directory (add `.gitkeep`)
  - Create `backend/assets/music/` and `backend/assets/sfx/` directories with placeholder `.gitkeep` files
  - _Requirements: 2.1, 4.1, 7.2_

- [-] 2. Define data models
  - [x] 2.1 Create `app/models/audio_api.py`
    - Implement `SynthesisRequest` with `field_validator` for `script_id`/`voice_id` (no whitespace), `emotion_type` (literal), and `effects` (allowed set)
    - Implement `AudioJobResponse` with `job_id`, `status`, `output_url`, `duration_sec`
    - Define `VALID_EFFECTS` and `VALID_EMOTIONS` constants
    - _Requirements: 1.1, 1.5, 1.6, 1.7, 1.8, 1.9_

  - [ ]* 2.2 Write property tests for `SynthesisRequest` validation
    - **Property 3: Input Validation — Whitespace IDs**
    - **Property 4: Input Validation — Emotion Type**
    - **Property 5: Input Validation — Effects List**
    - **Validates: Requirements 1.5, 1.6, 1.7, 1.8**
    - Place in `backend/tests/audio/test_synthesis_request.py`

  - [x] 2.3 Create `app/models/audio_persistence.py`
    - Implement `PersistedAudioJob` with all fields: `job_id`, `status`, `script_id`, `voice_id`, `emotion_type`, `effects`, `output_url`, `duration_sec`, `created_at`, `quality_pass`, `quality_detail`
    - _Requirements: 11.1_

- [-] 3. Implement `AudioJobStore` persistence layer
  - [x] 3.1 Create `app/store/audio_job_store.py`
    - Implement `init_db(db_path)` with `CREATE TABLE IF NOT EXISTS audio_jobs` SQL matching the schema in the design
    - Implement `AudioJobStore` class with `save(job)`, `get(job_id) -> PersistedAudioJob | None`, and `update_status(job_id, status, output_url, duration_sec, quality_pass, quality_detail)` methods
    - Store `effects` as JSON string; parse on read
    - Raise `AudioStoreError` on all DB exceptions
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [ ]* 3.2 Write property test for `AudioJobStore` round-trip
    - **Property 21: AudioJob Persistence Round-Trip**
    - **Validates: Requirements 11.1**
    - Place in `backend/tests/audio/test_audio_job_store.py`

- [-] 4. Implement upstream API client
  - [x] 4.1 Create `app/clients/audio_upstream_client.py`
    - Implement `AudioUpstreamClient` with `get_dialogue_script(script_id)` and `get_voice_profile(voice_id)` methods using `httpx.AsyncClient`
    - Apply 10-second timeout per call
    - Retry up to 3 times (4 total attempts) with 2-second delay on HTTP 5xx
    - Raise `DialogueScriptNotFoundError` on 404 for script, `VoiceProfileNotFoundError` on 404 for voice, `UpstreamServiceError` on exhausted retries, `UpstreamTimeoutError` on timeout
    - Log each retry attempt with attempt number, target service, and failure reason
    - Define `DialogueScript` and `VoiceProfile` upstream response models in this file
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 14.5_

  - [ ]* 4.2 Write property test for upstream retry exhaustion
    - **Property 6: Upstream Retry Exhaustion**
    - **Validates: Requirements 3.5**
    - Place in `backend/tests/audio/test_synthesis_task.py`

- [-] 5. Implement ElevenLabs client
  - [x] 5.1 Create `app/services/elevenlabs_client.py`
    - Implement `ElevenLabsClient` wrapping the `elevenlabs` Python SDK
    - Implement `synthesize(text, voice_id, emotion_type) -> bytes` method
    - Apply `EMOTION_VOICE_SETTINGS` mapping for `stability` and `similarity_boost`
    - Apply 30-second timeout; raise `ElevenLabsTimeoutError` on timeout, `ElevenLabsError` on API error
    - Log ElevenLabs error detail and `job_id` on failure
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.7, 4.8_

  - [ ]* 5.2 Write property tests for ElevenLabs client
    - **Property 7: ElevenLabs Text Preservation**
    - **Property 8: ElevenLabs Voice Settings Correctness**
    - **Validates: Requirements 4.2, 4.4, 4.5, 12.2, 12.4, 13.1**
    - Place in `backend/tests/audio/test_elevenlabs_client.py`

- [-] 6. Implement marker processor
  - [x] 6.1 Create `app/services/marker_processor.py`
    - Define `MarkerSpan` and `StrippedScript` dataclasses
    - Implement `strip_markers(text) -> StrippedScript`: remove `[marker]` tokens, record character positions as `MarkerSpan` list
    - Implement `apply_markers(audio: AudioSegment, spans: list[MarkerSpan]) -> AudioSegment`:
      - `[pause]` → insert 500 ms silence
      - `[breath]` → insert 200 ms breath sound
      - `[softer]` → reduce amplitude −6 dB for segment
      - `[urgency]` → increase amplitude +3 dB for segment
      - `[warmth]` → apply low-shelf EQ boost (200 Hz, +3 dB) for segment
      - `[slower]` → reduce playback rate by 15% for segment
      - `[faster]` → increase playback rate by 15% for segment
    - Log warning when `emotional_markers` list is empty
    - Raise `MarkerProcessingError` on failure
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 12.4, 12.5_

  - [ ]* 6.2 Write property tests for marker processor
    - **Property 9: Marker Stripping Preserves Positions**
    - **Property 10: Pause Marker Inserts Silence**
    - **Property 11: Amplitude Markers Adjust Level Correctly**
    - **Property 12: Rate Markers Adjust Playback Speed**
    - **Validates: Requirements 5.1, 5.2, 5.4, 5.5, 5.6, 12.5**
    - Place in `backend/tests/audio/test_marker_processor.py`

- [ ] 7. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [-] 8. Implement effects processor
  - [x] 8.1 Create `app/services/effects_processor.py`
    - Implement `apply_effects(audio: AudioSegment, effects: list[str]) -> AudioSegment`
    - Apply in strict order: reverb → warmth EQ → ambient noise
    - `"reverb"` → short room-reverb via pydub/ffmpeg
    - `"warmth"` → low-shelf EQ boost (200 Hz, +3 dB) via pydub/ffmpeg
    - `"ambient"` → mix ambient noise layer at −30 dBFS
    - `"wind"` → mix wind layer at −35 dBFS
    - `"city"` → mix city layer at −35 dBFS
    - `"room_tone"` → mix room tone layer at −40 dBFS
    - Skip chain entirely when `effects` is empty
    - Raise `EffectsChainError` with failing effect name on any failure
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6b.1, 6b.2, 6b.3, 6b.4, 6b.5_

  - [ ]* 8.2 Write property tests for effects processor
    - **Property 13: Effects Chain Ordering**
    - **Property 16: Sound Effect Mixing Levels**
    - **Validates: Requirements 6.4, 6b.2, 6b.3, 6b.4**
    - Place in `backend/tests/audio/test_effects_processor.py`

- [-] 9. Implement music mixer
  - [x] 9.1 Create `app/services/music_mixer.py`
    - Define `EMOTION_MUSIC_MAP` mapping `emotion_type` to asset paths
    - Implement `mix_music(audio: AudioSegment, emotion_type: str) -> AudioSegment`
    - Select music file by `emotion_type`; mix beneath speech ensuring speech-to-background ratio ≥ 10 dB
    - Log warning and return audio unchanged if music file not found (do not fail job)
    - Apply music layering after effects chain
    - _Requirements: 6a.1, 6a.2, 6a.3, 6a.4, 6a.5, 6a.6, 6a.7, 12.3_

  - [ ]* 9.2 Write property tests for music mixer
    - **Property 14: Background Music Selection**
    - **Property 15: Speech Intelligibility (SNR Invariant)**
    - **Validates: Requirements 6a.1–6a.5, 6b.5, 12.3, 16.3**
    - Place in `backend/tests/audio/test_music_mixer.py`

- [-] 10. Implement quality checker
  - [x] 10.1 Create `app/services/quality_checker.py`
    - Implement `run_quality_checks(audio_path: str, duration_sec: float, job_id: str) -> dict`
    - Check: `duration_sec` between 25–65 s, file size > 0 bytes, speech-to-background SNR ≥ 10 dB
    - Return `{"duration_ok": bool, "size_ok": bool, "snr_ok": bool}` and overall `pass` flag
    - Log warning when duration is outside 30–60 s target range
    - Log warning when actual duration deviates > 10% from `estimated_duration_sec`
    - Raise `QualityCheckError` with failing check name and measured value when any check fails
    - _Requirements: 7.4, 7.5, 12.3, 12.6, 16.1, 16.2, 16.3, 16.4, 16.5_

- [-] 11. Implement Celery app and synthesis task
  - [x] 11.1 Create `app/worker/celery_app.py`
    - Instantiate `Celery` app with Redis broker URL from `settings.REDIS_URL`
    - Configure result backend, task serializer, and timezone
    - _Requirements: 2.1_

  - [x] 11.2 Create `app/worker/synthesis_task.py`
    - Implement `@celery_app.task synthesize_audio(job_id, script_id, voice_id, emotion_type, effects)`
    - Stage 1: Update status → `"processing"` in `AudioJobStore`
    - Stage 2: Fetch `DialogueScript` and `VoiceProfile` via `AudioUpstreamClient`
    - Stage 3: Strip markers from script text via `MarkerProcessor`; retain `MarkerSpan` positions
    - Stage 4: Call `ElevenLabsClient.synthesize()` with stripped text and voice settings
    - Stage 5: Apply marker audio modifications via `apply_markers()`
    - Stage 6: Apply effects chain via `apply_effects()`
    - Stage 7: Layer background music via `mix_music()`
    - Stage 8: Encode MP3 at ≥ 128 kbps; write to `audio_files/{job_id}.mp3`; measure `duration_sec`
    - Stage 9: Run quality checks; set status → `"done"` with `output_url` and `duration_sec`, or `"failed"` on any check failure
    - Wrap entire pipeline in try/except; on any unrecoverable error set status → `"failed"` and log `job_id`, stage, error type, error detail
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 4.6, 5.8, 6.6, 6a.6, 7.1, 7.2, 7.3, 7.4, 7.6, 12.1, 12.4, 12.5, 12.6, 13.1, 13.2, 14.4_

  - [ ]* 11.3 Write property tests for synthesis task worker pipeline
    - **Property 17: MP3 Output Quality**
    - **Property 18: Output File Path Derivation**
    - **Property 19: Status Response Field Nullability**
    - **Property 23: Identical Inputs Produce Equivalent Synthesis Calls**
    - **Validates: Requirements 2.2, 2.3, 7.1, 7.2, 13.4**
    - Place in `backend/tests/audio/test_synthesis_task.py`

- [-] 12. Implement FastAPI audio router
  - [x] 12.1 Create `app/routes/audio.py`
    - Implement `POST /audio/synthesize`: validate `SynthesisRequest`, create `PersistedAudioJob(status="queued")`, persist to `AudioJobStore`, enqueue `synthesize_audio` Celery task, return HTTP 202 `{"job_id": ...}`
    - Return HTTP 503 if Redis is unavailable (catch `QueueUnavailableError`)
    - Return HTTP 503 if `AudioJobStore` write fails (catch `AudioStoreError`)
    - Log each submission with `job_id`, `script_id`, `voice_id`, `effects`
    - Implement `GET /audio/status/{job_id}`: read from `AudioJobStore`, return `AudioJobResponse`; 404 if not found; 503 if store unavailable
    - Implement `GET /audio/download/{job_id}`: return MP3 `FileResponse` (200) when done; 202 when queued/processing; 410 when failed; 404 when not found; 500 if file missing despite done status
    - _Requirements: 1.1, 1.2, 1.4, 1.9, 2.6, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 9.1, 9.2, 9.3, 9.4, 9.5, 11.3, 11.4, 11.5, 14.1, 14.2, 14.3, 14.6_

  - [ ]* 12.2 Write unit and property tests for audio routes
    - **Property 1: Job ID Uniqueness**
    - **Property 2: Initial Job State Invariant**
    - **Property 19: Status Response Field Nullability**
    - **Property 20: Download Endpoint Status Codes**
    - **Validates: Requirements 1.2, 1.3, 1.4, 8.1–8.6, 9.1–9.5**
    - Place in `backend/tests/audio/test_audio_routes.py`

- [-] 13. Wire audio router into `app/main.py`
  - Import `audio_router` from `app/routes/audio`
  - Call `init_db` for `audio.db` in the `lifespan` context manager
  - Attach `AudioJobStore` to `app.state`
  - Register exception handlers for `AudioStoreError`, `QueueUnavailableError`, `FileMissingError`
  - Include `audio_router` with `app.include_router(audio_router)`
  - _Requirements: 1.1, 8.1, 9.1, 11.4, 14.2_

- [ ] 14. Checkpoint — Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [-] 15. Implement frontend AudioPlayer component
  - [x] 15.1 Create `frontend/src/components/AudioPlayer/types.ts`
    - Define `AudioJob` interface: `job_id`, `status`, `output_url`, `duration_sec`
    - Define `AudioPlayerProps` interface: `job_id: string`
    - _Requirements: 10.1_

  - [x] 15.2 Create `frontend/src/components/AudioPlayer/useAudioJob.ts`
    - Implement `useAudioJob(job_id)` custom hook
    - Poll `/audio/status/{job_id}` every 3 seconds using `setInterval`
    - Stop polling when status is `"done"` or `"failed"`
    - Return `{ job, isLoading, error }`
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [ ]* 15.3 Write property test for duration formatting
    - **Property 22: Duration Formatting**
    - **Validates: Requirements 10.6**
    - Place in `frontend/src/components/AudioPlayer/AudioPlayer.test.tsx` using Vitest + fast-check

  - [x] 15.4 Create `frontend/src/components/AudioPlayer/WaveformDisplay.tsx`
    - Implement waveform visualization using `wavesurfer.js`
    - Accept `audioUrl: string` prop; initialize WaveSurfer on mount, destroy on unmount
    - Expose `play()` / `pause()` via `ref` or callback props
    - _Requirements: 10.3, 10.5_

  - [x] 15.5 Create `frontend/src/components/AudioPlayer/AudioPlayer.tsx`
    - Compose `useAudioJob` hook and `WaveformDisplay` component
    - Show loading indicator + status label while `"queued"` or `"processing"`
    - Show human-readable error message when `"failed"`
    - Render waveform, play/pause button, and formatted `"m:ss / m:ss"` position display when `"done"`
    - Render download button that calls `GET /audio/download/{job_id}`; disable and show loading indicator during in-flight request; show "not ready" message on HTTP 202
    - Display `job_id` for reference
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 10.10_

- [ ] 16. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- The Celery worker must be started separately: `celery -A app.worker.celery_app worker --loglevel=info` (run manually from `backend/`)
- Property tests use `hypothesis` (already in `requirements.txt`) for backend and `fast-check` for frontend
- Background music and SFX asset files must be placed in `backend/assets/music/` and `backend/assets/sfx/` before running the full pipeline
- ElevenLabs is the only permitted TTS provider — no alternative providers
