# Design Document: Audio Production Engine

## Overview

The Audio Production Engine is a FastAPI module that accepts a `script_id`, `voice_id`, and `emotion_type`, synthesizes speech exclusively via the ElevenLabs TTS API using the user's cloned voice, applies an emotion-driven post-processing chain (emotional marker processing, effects chain, background music layering, optional sound effects), and delivers a 30–60 second MP3 output. Jobs are processed asynchronously via Celery + Redis so the HTTP layer remains non-blocking. A React `AudioPlayer` component polls for job status, renders a waveform, and provides download.

The module extends the existing `backend/` FastAPI project, following the same patterns established by the Dialogue Generator: Pydantic models, aiosqlite persistence, structured exception handling, and httpx-based upstream clients.

### Key Design Decisions

- **ElevenLabs only**: No alternative TTS providers. The `ElevenLabsClient` wraps the `elevenlabs` Python SDK and is the sole synthesis path.
- **Celery + Redis for async**: The API enqueues a Celery task and returns HTTP 202 immediately. The worker runs in a separate process.
- **pydub + ffmpeg for audio**: All post-processing (marker application, effects chain, music mixing, MP3 encoding) uses pydub with ffmpeg as the backend.
- **SQLite via aiosqlite**: AudioJob records are persisted in a dedicated `audio.db` file, consistent with the existing `dialogue.db` pattern.
- **Local filesystem**: Output files are written to `backend/audio_files/{job_id}.mp3`.
- **Marker stripping before synthesis**: Emotional marker tokens are stripped from the script text before submission to ElevenLabs. Their character positions are recorded so segment-level audio modifications can be applied post-synthesis.

---

## Architecture

```mermaid
graph TD
    Client["React AudioPlayer"] -->|POST /audio/synthesize| API["FastAPI\nAudioProduction_API"]
    Client -->|GET /audio/status/{job_id}| API
    Client -->|GET /audio/download/{job_id}| API

    API -->|enqueue task| Redis["Redis\nJobQueue"]
    API -->|read/write AudioJob| SQLite["SQLite\naudio.db"]
    API -->|stream file| FS["Filesystem\naudio_files/"]

    Redis -->|dispatch| Worker["Celery\nSynthesisWorker"]
    Worker -->|GET /dialogue/{script_id}| DialogueAPI["DialogueGenerator_API"]
    Worker -->|GET /voice/{voice_id}| VoiceAPI["VoiceCapture_API"]
    Worker -->|TTS synthesis| ElevenLabs["ElevenLabs TTS API"]
    Worker -->|write AudioJob status| SQLite
    Worker -->|write MP3| FS
```

### Request Lifecycle

1. Client POSTs `SynthesisRequest` → API validates, creates `AudioJob(status="queued")`, persists to SQLite, enqueues Celery task, returns HTTP 202 + `job_id`.
2. Celery worker picks up task → updates status to `"processing"` → fetches `DialogueScript` and `VoiceProfile` from upstream APIs → strips markers from text, records positions → calls ElevenLabs TTS → applies emotional marker audio modifications → applies effects chain → layers background music → encodes MP3 → runs quality checks → updates status to `"done"` (or `"failed"`).
3. Client polls `GET /audio/status/{job_id}` every 3 seconds until terminal state.
4. Client calls `GET /audio/download/{job_id}` to stream the MP3.

---

## Components and Interfaces

### Backend Components

```
backend/app/
├── routes/
│   └── audio.py              # FastAPI router: /audio/synthesize, /audio/status, /audio/download
├── models/
│   ├── audio_api.py          # SynthesisRequest, AudioJobResponse, ErrorResponse
│   └── audio_persistence.py  # PersistedAudioJob
├── store/
│   └── audio_job_store.py    # AudioJobStore (aiosqlite CRUD)
├── clients/
│   └── audio_upstream_client.py  # Fetches DialogueScript + VoiceProfile with retry logic
├── services/
│   ├── elevenlabs_client.py  # ElevenLabs SDK wrapper
│   ├── marker_processor.py   # Strips markers, records positions, applies segment modifications
│   ├── effects_processor.py  # Effects chain: reverb, warmth EQ, ambient, sound effects
│   ├── music_mixer.py        # Background music selection and mixing
│   └── quality_checker.py    # Duration, file size, speech-to-background ratio checks
└── worker/
    ├── celery_app.py         # Celery application instance + Redis broker config
    └── synthesis_task.py     # @celery_app.task: orchestrates the full synthesis pipeline
```

### Frontend Components

```
frontend/src/components/
└── AudioPlayer/
    ├── AudioPlayer.tsx        # Main component: polling, waveform, controls
    ├── useAudioJob.ts         # Custom hook: polling logic, status state
    ├── WaveformDisplay.tsx    # Waveform visualization (wavesurfer.js)
    └── types.ts               # AudioJob, AudioPlayerProps types
```

### API Interfaces

**POST /audio/synthesize**
- Request: `SynthesisRequest`
- Response 202: `{ "job_id": "<uuid>" }`
- Response 422: `{ "detail": [{ "loc": [...], "msg": "...", "type": "..." }] }`
- Response 503: `{ "detail": "Job queue unavailable" }` | `{ "detail": "Job store unavailable" }`

**GET /audio/status/{job_id}**
- Response 200: `AudioJobResponse`
- Response 404: `{ "detail": "Job not found" }`
- Response 503: `{ "detail": "Job store unavailable" }`

**GET /audio/download/{job_id}**
- Response 200: MP3 binary, `Content-Type: audio/mpeg`, `Content-Disposition: attachment; filename="{job_id}.mp3"`
- Response 202: `{ "detail": "Job not yet complete" }`
- Response 404: `{ "detail": "Job not found" }`
- Response 410: `{ "detail": "Job failed — no audio file available" }`
- Response 500: `{ "detail": "Audio file missing despite completed status" }`

---

## Data Models

### API Models (`audio_api.py`)

```python
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
            raise ValueError(f"invalid effect(s): {invalid}. Allowed: {VALID_EFFECTS}")
        return v


class AudioJobResponse(BaseModel):
    job_id: str
    status: Literal["queued", "processing", "done", "failed"]
    output_url: str | None
    duration_sec: float | None
```

### Persistence Model (`audio_persistence.py`)

```python
from datetime import datetime
from pydantic import BaseModel

class PersistedAudioJob(BaseModel):
    job_id: str
    status: str                  # "queued" | "processing" | "done" | "failed"
    script_id: str
    voice_id: str
    emotion_type: str
    effects: list[str]           # stored as JSON string in SQLite
    output_url: str | None
    duration_sec: float | None
    created_at: datetime         # UTC ISO 8601
    quality_pass: bool | None    # None until quality check runs
    quality_detail: str | None   # JSON: {"duration_ok": bool, "size_ok": bool, "snr_ok": bool}
```

### SQLite Schema

```sql
CREATE TABLE IF NOT EXISTS audio_jobs (
    job_id          TEXT PRIMARY KEY,
    status          TEXT NOT NULL,
    script_id       TEXT NOT NULL,
    voice_id        TEXT NOT NULL,
    emotion_type    TEXT NOT NULL,
    effects         TEXT NOT NULL,      -- JSON array
    output_url      TEXT,
    duration_sec    REAL,
    created_at      TEXT NOT NULL,      -- UTC ISO 8601
    quality_pass    INTEGER,            -- NULL until checked; 0/1 after
    quality_detail  TEXT                -- JSON string
);
```

### Upstream Models

```python
# Consumed from DialogueGenerator_API
class DialogueScript(BaseModel):
    script_id: str
    text: str
    estimated_duration_sec: float
    emotional_markers: list[str]

# Consumed from VoiceCapture_API
class VoiceProfile(BaseModel):
    voice_id: str
    display_name: str
```

### Marker Processing Internal Model

```python
from dataclasses import dataclass

@dataclass
class MarkerSpan:
    marker: str        # e.g. "pause", "softer", "urgency"
    start_ms: int      # approximate start position in synthesized audio (ms)
    end_ms: int | None # None means "until next marker or end of audio"

@dataclass
class StrippedScript:
    clean_text: str          # text with [marker] tokens removed
    marker_spans: list[MarkerSpan]  # ordered list of marker positions
```

### ElevenLabs Voice Settings

```python
EMOTION_VOICE_SETTINGS: dict[str, dict] = {
    "success": {"stability": 0.35, "similarity_boost": 0.75},
    "regret":  {"stability": 0.55, "similarity_boost": 0.75},
    "neutral": {"stability": 0.50, "similarity_boost": 0.75},
}
```

### Background Music Mapping

```python
EMOTION_MUSIC_MAP: dict[str, str] = {
    "success": "assets/music/success.mp3",
    "regret":  "assets/music/regret.mp3",
    "neutral": "assets/music/neutral.mp3",
}
```

### Sound Effect dBFS Levels

```python
EFFECT_LEVELS_DBFS: dict[str, float] = {
    "wind":      -35.0,
    "city":      -35.0,
    "room_tone": -40.0,
}
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Job ID Uniqueness

*For any* number of synthesis requests submitted to the API, all returned `job_id` values must be distinct strings — no two jobs may share the same identifier.

**Validates: Requirements 1.2, 1.3**

---

### Property 2: Initial Job State Invariant

*For any* valid `SynthesisRequest`, the `AudioJob` record persisted at submission time must have `status="queued"`, `output_url=None`, and `duration_sec=None`.

**Validates: Requirements 1.4, 11.1**

---

### Property 3: Input Validation — Whitespace IDs

*For any* string containing whitespace characters or the empty string submitted as `script_id` or `voice_id`, the API must return HTTP 422 with a field-level error identifying the offending field.

**Validates: Requirements 1.5, 1.6**

---

### Property 4: Input Validation — Emotion Type

*For any* string not in `{"success", "regret", "neutral"}` submitted as `emotion_type`, the API must return HTTP 422.

**Validates: Requirements 1.7**

---

### Property 5: Input Validation — Effects List

*For any* `effects` list containing a value not in `{"reverb", "warmth", "ambient", "wind", "city", "room_tone"}`, the API must return HTTP 422.

**Validates: Requirements 1.8**

---

### Property 6: Upstream Retry Exhaustion

*For any* upstream API (DialogueGenerator or VoiceCapture) that consistently returns HTTP 5xx, the `SynthesisWorker` must make exactly 4 total attempts (1 initial + 3 retries) before setting the `AudioJob` status to `"failed"`.

**Validates: Requirements 3.5**

---

### Property 7: ElevenLabs Text Preservation

*For any* `DialogueScript`, the text submitted to the ElevenLabs TTS API must equal the original `text` field with only `[marker]` tokens removed and no other modifications (no truncation, no reordering, no added content).

**Validates: Requirements 4.2, 12.4, 13.1, 13.3**

---

### Property 8: ElevenLabs Voice Settings Correctness

*For any* `emotion_type` in `{"success", "regret", "neutral"}`, the ElevenLabs TTS call must use `similarity_boost >= 0.75` and the `stability` value defined in `EMOTION_VOICE_SETTINGS` for that emotion type.

**Validates: Requirements 4.4, 4.5, 12.2**

---

### Property 9: Marker Stripping Preserves Positions

*For any* script text containing `[marker]` tokens, after stripping, the recorded `MarkerSpan` positions must correspond to the original token locations so that post-synthesis audio modifications are applied at the correct offsets.

**Validates: Requirements 12.5**

---

### Property 10: Pause Marker Inserts Silence

*For any* synthesized audio segment containing a `[pause]` marker, the processed audio must contain a silence segment of exactly 500 milliseconds at the marker position.

**Validates: Requirements 5.1**

---

### Property 11: Amplitude Markers Adjust Level Correctly

*For any* audio segment following a `[softer]` marker, the amplitude must be reduced by 6 dB relative to the preceding segment. *For any* audio segment following an `[urgency]` marker, the amplitude must be increased by 3 dB relative to the preceding segment.

**Validates: Requirements 5.2, 5.4**

---

### Property 12: Rate Markers Adjust Playback Speed

*For any* audio segment following a `[slower]` marker, the playback rate must be 0.85× the original rate. *For any* audio segment following a `[faster]` marker, the playback rate must be 1.15× the original rate.

**Validates: Requirements 5.5, 5.6**

---

### Property 13: Effects Chain Ordering

*For any* `effects` list containing multiple values, the effects must be applied in the order: reverb → warmth EQ → ambient noise. No other ordering is permitted.

**Validates: Requirements 6.4**

---

### Property 14: Background Music Selection

*For any* `emotion_type`, the `SynthesisWorker` must select the music file path defined in `EMOTION_MUSIC_MAP` for that emotion type and mix it beneath the synthesized speech.

**Validates: Requirements 6a.1, 6a.2, 6a.3, 6a.4**

---

### Property 15: Speech Intelligibility (SNR Invariant)

*For any* completed `Output_File`, the speech-to-background ratio must be at least 10 dB — the peak amplitude of the synthesized speech must exceed the peak amplitude of all background audio (music + effects) by at least 10 dB.

**Validates: Requirements 6a.5, 6b.5, 12.3, 16.3**

---

### Property 16: Sound Effect Mixing Levels

*For any* audio with `"wind"` or `"city"` in the effects list, those layers must be mixed at −35 dBFS. *For any* audio with `"room_tone"` in the effects list, that layer must be mixed at −40 dBFS.

**Validates: Requirements 6b.2, 6b.3, 6b.4**

---

### Property 17: MP3 Output Quality

*For any* completed job, the output MP3 file must have a bit rate of at least 128 kbps, a file size greater than zero bytes, and a `duration_sec` greater than zero.

**Validates: Requirements 7.1, 7.4, 16.2**

---

### Property 18: Output File Path Derivation

*For any* completed job, the output file must exist at `backend/audio_files/{job_id}.mp3` — the filename is always derived from the `job_id` with no other transformation.

**Validates: Requirements 7.2**

---

### Property 19: Status Response Field Nullability

*For any* `AudioJob` in any status, the `/audio/status/{job_id}` response must return `output_url` and `duration_sec` as `null` when `status` is `"queued"`, `"processing"`, or `"failed"`, and as non-null values when `status` is `"done"`.

**Validates: Requirements 8.3, 8.4, 8.5**

---

### Property 20: Download Endpoint Status Codes

*For any* `AudioJob` status, the `/audio/download/{job_id}` endpoint must return: HTTP 200 when `status="done"`, HTTP 202 when `status` is `"queued"` or `"processing"`, HTTP 410 when `status="failed"`, and HTTP 404 when the `job_id` does not exist.

**Validates: Requirements 9.1, 9.2, 9.3, 9.4**

---

### Property 21: AudioJob Persistence Round-Trip

*For any* `PersistedAudioJob`, after saving to the `AudioJobStore` and retrieving by `job_id`, all fields must be equal to the original — including `created_at` in UTC ISO 8601 format, `effects` as a list, and all nullable fields.

**Validates: Requirements 11.1**

---

### Property 22: Duration Formatting

*For any* `duration_sec` value, the `AudioPlayer` formatted display must produce a string matching the pattern `"m:ss / m:ss"` where minutes and seconds are correctly derived from the total seconds value.

**Validates: Requirements 10.6**

---

### Property 23: Identical Inputs Produce Equivalent Synthesis Calls

*For any* identical `SynthesisRequest` submitted twice (same `script_id`, `voice_id`, `effects`), both jobs must call ElevenLabs with the same stripped text and the same `voice_id`, ensuring equivalent spoken content.

**Validates: Requirements 13.4**

---

## Error Handling

### Exception Hierarchy

The module defines its own exception hierarchy, parallel to the existing `DialogueGeneratorError` tree:

```python
class AudioProductionError(Exception): pass

# Upstream errors
class UpstreamError(AudioProductionError): pass
class DialogueScriptNotFoundError(UpstreamError): pass
class VoiceProfileNotFoundError(UpstreamError): pass
class UpstreamServiceError(UpstreamError): pass
class UpstreamTimeoutError(UpstreamError): pass

# ElevenLabs errors
class ElevenLabsError(AudioProductionError): pass
class ElevenLabsTimeoutError(ElevenLabsError): pass

# Processing errors
class MarkerProcessingError(AudioProductionError): pass
class EffectsChainError(AudioProductionError): pass
class EncodingError(AudioProductionError): pass
class QualityCheckError(AudioProductionError): pass

# Store / infrastructure errors
class AudioStoreError(AudioProductionError): pass
class QueueUnavailableError(AudioProductionError): pass
class FileMissingError(AudioProductionError): pass
```

### API-Level Error Handling

The FastAPI router registers exception handlers following the same pattern as `main.py`:

| Exception | HTTP Status | Notes |
|---|---|---|
| `AudioStoreError` | 503 | Job store unavailable |
| `QueueUnavailableError` | 503 | Redis broker unavailable |
| `DialogueScriptNotFoundError` | 404 | Surfaced only on status poll |
| `VoiceProfileNotFoundError` | 404 | Surfaced only on status poll |
| `FileMissingError` | 500 | File missing despite done status |
| `Exception` (unhandled) | 500 | Generic; no stack trace exposed |

All 4xx/5xx responses are JSON with a `detail` field. Internal stack traces and raw ElevenLabs responses are never exposed to clients.

### Worker-Level Error Handling

The `synthesis_task` Celery task wraps the entire pipeline in a try/except. Each stage has its own error boundary:

```
Stage 1: Upstream resolution  → DialogueScriptNotFoundError / VoiceProfileNotFoundError / UpstreamServiceError
Stage 2: ElevenLabs synthesis → ElevenLabsError / ElevenLabsTimeoutError
Stage 3: Marker processing    → MarkerProcessingError
Stage 4: Effects chain        → EffectsChainError (logs failing effect name)
Stage 5: Music mixing         → Warning only (job continues without music if file missing)
Stage 6: MP3 encoding         → EncodingError
Stage 7: Quality checks       → QualityCheckError (sets status to "failed")
```

Any unrecoverable exception sets `AudioJob.status = "failed"` and logs: `job_id`, processing stage, error type, error detail.

### Retry Logic

Upstream API calls (stages 1) use a simple retry loop with 3 retries and 2-second delays on HTTP 5xx. ElevenLabs calls (stage 2) have a 30-second timeout with no automatic retry (ElevenLabs errors are treated as terminal). Each retry attempt is logged with attempt number, target service, and failure reason.

### Logging

All log entries use structured key=value format consistent with the existing codebase:

```python
logger.error("SynthesisWorker failed: job_id=%s stage=%s error_type=%s detail=%s",
             job_id, stage, type(exc).__name__, str(exc))
```

---

## Testing Strategy

### Dual Testing Approach

The module uses both example-based unit tests and property-based tests (via `hypothesis`, already in `requirements.txt`).

**Unit tests** cover:
- Specific endpoint behaviors (202 on submit, 404 on unknown job, correct headers on download)
- Error conditions (Redis unavailable → 503, ElevenLabs timeout → failed status)
- Marker processing examples (known input → known output)
- Worker stage transitions (queued → processing → done/failed)

**Property-based tests** cover the 23 correctness properties defined above, using `hypothesis` strategies to generate arbitrary inputs.

### Property-Based Test Configuration

- Library: `hypothesis` (already in `requirements.txt`)
- Minimum iterations: 100 per property (hypothesis default `max_examples=100`)
- Tag format in test docstrings: `Feature: audio-production-engine, Property N: <property_text>`

Example property test structure:

```python
from hypothesis import given, settings
from hypothesis import strategies as st

@given(
    script_id=st.text(min_size=1).filter(lambda s: " " not in s and s == s.strip()),
    voice_id=st.text(min_size=1).filter(lambda s: " " not in s and s == s.strip()),
    emotion_type=st.sampled_from(["success", "regret", "neutral"]),
    effects=st.lists(st.sampled_from(["reverb", "warmth", "ambient", "wind", "city", "room_tone"])),
)
@settings(max_examples=100)
def test_initial_job_state_invariant(script_id, voice_id, emotion_type, effects):
    """Feature: audio-production-engine, Property 2: Initial Job State Invariant"""
    # Submit request, read back persisted job, assert queued/null/null
    ...
```

### Test File Layout

```
backend/tests/
├── audio/
│   ├── test_audio_routes.py          # Unit: API endpoint behaviors
│   ├── test_audio_job_store.py       # Unit + Property 21: persistence round-trip
│   ├── test_synthesis_request.py     # Property 3, 4, 5: input validation
│   ├── test_marker_processor.py      # Property 9, 10, 11, 12: marker processing
│   ├── test_effects_processor.py     # Property 13, 16: effects chain ordering + levels
│   ├── test_music_mixer.py           # Property 14, 15: music selection + SNR
│   ├── test_elevenlabs_client.py     # Property 7, 8: text preservation + voice settings
│   ├── test_synthesis_task.py        # Property 6, 17, 18, 19, 20, 23: worker pipeline
│   └── test_audio_player.py          # Property 22: duration formatting (Jest/Vitest)
```

### Integration Tests

Integration tests (in `backend/tests/audio/integration/`) verify:
- Full pipeline with mocked ElevenLabs and upstream APIs
- Celery task execution with a real Redis instance (test environment)
- SQLite persistence across worker and API processes
- File system write and download streaming

### Frontend Tests

The `AudioPlayer` component is tested with Vitest + React Testing Library:
- Polling behavior (mock `fetch`, verify 3-second interval, stop on terminal state)
- Status display states (loading, done, failed)
- Download button behavior (disabled during request, 202 handling)
- Duration formatting (Property 22, using `hypothesis`-equivalent fast-check)
