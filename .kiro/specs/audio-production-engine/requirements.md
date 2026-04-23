# Requirements Document

## Introduction

The Audio Production Engine is a module within the Future Self Voice Simulator project. It accepts a `script_id`, `voice_id`, and `emotion_type` produced by the Dialogue Generator and Voice Capture & Cloning modules respectively, synthesizes speech exclusively using the ElevenLabs Text-to-Speech API with the user's cloned voice, and applies a post-processing chain (emotion-adjusted voice settings, background music layering, optional sound effects) to produce an emotionally authentic MP3 output of 30–60 seconds. ElevenLabs is the only permitted TTS provider — no alternative providers (e.g., Coqui TTS, Google TTS) are permitted. Synthesis is performed asynchronously via a Celery task queue backed by Redis, and the module exposes polling endpoints so clients can track job progress. The module exposes a REST API via FastAPI and a React frontend component (`AudioPlayer`) that renders a waveform player with a download button.

---

## Glossary

- **AudioProduction_API**: The FastAPI application that handles synthesis requests, job status polling, and audio file downloads.
- **SynthesisWorker**: The Celery task worker that performs voice synthesis and post-processing asynchronously.
- **JobQueue**: The Celery task queue backed by Redis that receives and dispatches synthesis jobs.
- **ElevenLabs_TTS**: The exclusively permitted external voice synthesis service. The SynthesisWorker MUST use the ElevenLabs Text-to-Speech API. No alternative TTS providers (e.g., Coqui TTS, Google TTS) are permitted.
- **SynthesisRequest**: The input data model for a synthesis job, containing `script_id`, `voice_id`, `emotion_type`, and `effects`.
- **Emotion_Type**: The scenario-derived emotional register — one of `"success"`, `"regret"`, or `"neutral"` — that determines ElevenLabs voice settings and background music selection.
- **AudioJob**: The data model representing the state of a synthesis job, containing `job_id`, `status`, `output_url`, and `duration_sec`.
- **job_id**: A unique string identifier assigned to an AudioJob at the time of submission.
- **Job_Status**: The current state of an AudioJob — one of `"queued"`, `"processing"`, `"done"`, or `"failed"`.
- **DialogueScript**: The data model produced by the Dialogue Generator, containing `script_id`, `text`, `estimated_duration_sec`, and `emotional_markers`. Retrieved by the SynthesisWorker before synthesis.
- **Emotional_Marker**: An inline annotation embedded in the DialogueScript `text` (e.g., `[pause]`, `[softer]`, `[warmth]`, `[urgency]`) that instructs the SynthesisWorker to apply a specific expressive quality at that point in synthesis.
- **ElevenLabs_Voice_Settings**: The `stability` and `similarity_boost` parameters passed to the ElevenLabs TTS API, adjusted dynamically based on `emotion_type`.
- **Background_Music**: An audio layer mixed beneath the synthesized speech, selected based on `emotion_type`: `"success"` → soft uplifting piano, `"regret"` → ambient low tones, `"neutral"` → minimal.
- **Effects_Chain**: The ordered sequence of post-processing operations applied to raw synthesized audio — comprising emotion adjustment, background music layering, and optional sound effects — executed by the SynthesisWorker.
- **Output_File**: The final MP3 audio file produced after synthesis and post-processing, 30–60 seconds in duration, stored and made available for download.
- **output_url**: A URL string pointing to the Output_File, populated in the AudioJob once the job reaches `"done"` status.
- **AudioPlayer**: The React frontend component that polls for job status, renders a waveform visualization of the Output_File, and provides a download button.
- **DialogueGenerator_API**: The upstream module that exposes DialogueScript records by `script_id`.
- **VoiceCapture_API**: The upstream module that exposes VoiceProfile records by `voice_id`.
- **Job_Store**: The persistence layer that stores and retrieves AudioJob records by `job_id`.
- **File_Store**: The storage layer (e.g., local filesystem or object storage) where Output_Files are written and served.
- **Intelligibility_Constraint**: The requirement that the synthesized voice must remain clearly intelligible at all times; background audio must not overpower speech.

---

## Requirements

### Requirement 1: Synthesis Job Submission

**User Story:** As a user, I want to submit a script and voice ID for synthesis, so that the system begins producing my audio message asynchronously using ElevenLabs.

#### Acceptance Criteria

1. WHEN a POST request is made to `/audio/synthesize` with a valid SynthesisRequest, THE AudioProduction_API SHALL enqueue a synthesis job on the JobQueue and return HTTP 202 with a JSON body containing the `job_id`.
2. THE AudioProduction_API SHALL assign a unique `job_id` to each submitted AudioJob at the time of enqueue.
3. WHEN two synthesis requests are submitted concurrently, THE AudioProduction_API SHALL assign distinct `job_id` values to each resulting AudioJob.
4. WHEN a synthesis job is enqueued, THE AudioProduction_API SHALL persist an AudioJob record with `status` set to `"queued"`, `output_url` set to `null`, and `duration_sec` set to `null`.
5. WHEN a POST request to `/audio/synthesize` is received, THE AudioProduction_API SHALL validate that `script_id` is a non-empty string with no whitespace.
6. WHEN a POST request to `/audio/synthesize` is received, THE AudioProduction_API SHALL validate that `voice_id` is a non-empty string with no whitespace.
7. WHEN a POST request to `/audio/synthesize` is received, THE AudioProduction_API SHALL validate that `emotion_type` is one of the values `"success"`, `"regret"`, or `"neutral"`.
8. WHEN a POST request to `/audio/synthesize` is received, THE AudioProduction_API SHALL validate that `effects` is a list containing only the values `"reverb"`, `"warmth"`, and `"ambient"`.
9. WHEN any SynthesisRequest field fails validation, THE AudioProduction_API SHALL return HTTP 422 with a JSON body identifying each invalid field and a descriptive error message per field.

---

### Requirement 2: Asynchronous Job Processing

**User Story:** As a developer, I want synthesis to run in a background worker, so that the API remains responsive and long-running audio jobs do not block HTTP request threads.

#### Acceptance Criteria

1. THE SynthesisWorker SHALL process synthesis jobs exclusively via the Celery task queue backed by Redis, without blocking the AudioProduction_API request thread.
2. WHEN the SynthesisWorker begins processing a job, THE SynthesisWorker SHALL update the AudioJob `status` to `"processing"` in the Job_Store before performing any synthesis operations.
3. WHEN the SynthesisWorker completes synthesis and post-processing successfully, THE SynthesisWorker SHALL update the AudioJob `status` to `"done"`, set `output_url` to the URL of the Output_File, and set `duration_sec` to the measured playback duration of the Output_File in seconds.
4. IF the SynthesisWorker encounters an unrecoverable error during synthesis or post-processing, THEN THE SynthesisWorker SHALL update the AudioJob `status` to `"failed"` and SHALL log the error with the `job_id`, error type, and error detail.
5. THE SynthesisWorker SHALL process each job in the order it was enqueued, unless the JobQueue is configured for priority routing.
6. WHEN the Redis broker is unavailable at the time of job submission, THE AudioProduction_API SHALL return HTTP 503 with a descriptive error message and SHALL NOT persist an AudioJob record.

---

### Requirement 3: Upstream Data Resolution

**User Story:** As a developer, I want the SynthesisWorker to resolve the DialogueScript and VoiceProfile before synthesis, so that synthesis is always based on current, authoritative data.

#### Acceptance Criteria

1. WHEN a synthesis job begins processing, THE SynthesisWorker SHALL retrieve the DialogueScript by sending a GET request to the DialogueGenerator_API at `/dialogue/{script_id}`.
2. WHEN a synthesis job begins processing, THE SynthesisWorker SHALL retrieve the VoiceProfile by sending a GET request to the VoiceCapture_API at `/voice/{voice_id}`.
3. WHEN the DialogueGenerator_API returns HTTP 404 for the given `script_id`, THE SynthesisWorker SHALL set the AudioJob `status` to `"failed"` and log a descriptive error indicating the DialogueScript was not found.
4. WHEN the VoiceCapture_API returns HTTP 404 for the given `voice_id`, THE SynthesisWorker SHALL set the AudioJob `status` to `"failed"` and log a descriptive error indicating the VoiceProfile was not found.
5. IF the DialogueGenerator_API or VoiceCapture_API returns an HTTP 5xx error, THEN THE SynthesisWorker SHALL retry the request up to 3 times with a 2-second delay between attempts before setting the AudioJob `status` to `"failed"`.
6. THE SynthesisWorker SHALL apply a timeout of 10 seconds to each upstream API call, and IF the timeout is exceeded, THEN THE SynthesisWorker SHALL set the AudioJob `status` to `"failed"` and log a descriptive timeout error.

---

### Requirement 4: Voice Synthesis via ElevenLabs

**User Story:** As a user, I want the audio to be synthesized using my cloned voice via ElevenLabs, so that the output sounds like a genuine message from my future self.

#### Acceptance Criteria

1. THE SynthesisWorker SHALL use the ElevenLabs Text-to-Speech API exclusively for all voice synthesis. No alternative TTS providers are permitted.
2. WHEN the DialogueScript and VoiceProfile are successfully retrieved, THE SynthesisWorker SHALL submit the DialogueScript `text` and `voice_id` to the ElevenLabs TTS API to render raw audio.
3. THE SynthesisWorker SHALL use the `voice_id` from the VoiceProfile without modification when calling ElevenLabs, so that the synthesized voice matches the user's cloned voice.
4. THE SynthesisWorker SHALL set the ElevenLabs `similarity_boost` parameter to `high` (≥ 0.75) for all synthesis calls to maximise voice fidelity.
5. THE SynthesisWorker SHALL set the ElevenLabs `stability` parameter dynamically based on `emotion_type`: `"success"` → 0.35 (expressive), `"regret"` → 0.55 (measured), `"neutral"` → 0.50 (balanced).
6. WHEN ElevenLabs returns synthesized audio, THE SynthesisWorker SHALL store the raw audio as an intermediate file before applying the Effects_Chain.
7. WHEN ElevenLabs returns an error or times out after 30 seconds, THE SynthesisWorker SHALL set the AudioJob `status` to `"failed"` and log the ElevenLabs error detail and `job_id`.
8. THE SynthesisWorker SHALL apply a timeout of 30 seconds to all ElevenLabs TTS calls.

---

### Requirement 5: Emotional Marker Influence on Synthesis

**User Story:** As a user, I want the emotional markers in my script to influence how the audio is synthesized, so that the output reflects the intended expressiveness of each moment.

#### Acceptance Criteria

1. WHEN the DialogueScript `text` contains a `[pause]` marker, THE SynthesisWorker SHALL insert a silence of 500 milliseconds at that position in the synthesized audio.
2. WHEN the DialogueScript `text` contains a `[softer]` marker, THE SynthesisWorker SHALL reduce the audio amplitude by 6 dB for the segment following the marker until the next marker or end of audio.
3. WHEN the DialogueScript `text` contains a `[warmth]` marker, THE SynthesisWorker SHALL apply the Warmth_EQ to the segment following the marker until the next marker or end of audio.
4. WHEN the DialogueScript `text` contains a `[urgency]` marker, THE SynthesisWorker SHALL increase the audio amplitude by 3 dB and reduce the inter-word silence by 20% for the segment following the marker until the next marker or end of audio.
5. WHEN the DialogueScript `text` contains a `[slower]` marker, THE SynthesisWorker SHALL reduce the playback rate of the segment following the marker by 15% until the next marker or end of audio.
6. WHEN the DialogueScript `text` contains a `[faster]` marker, THE SynthesisWorker SHALL increase the playback rate of the segment following the marker by 15% until the next marker or end of audio.
7. WHEN the DialogueScript `text` contains a `[breath]` marker, THE SynthesisWorker SHALL insert a 200-millisecond breath sound at that position in the synthesized audio.
8. WHEN the DialogueScript `emotional_markers` list is empty, THE SynthesisWorker SHALL synthesize the `text` without any marker-driven modifications and SHALL log a warning with the `job_id`.

---

### Requirement 6: Post-Processing Effects Chain

**User Story:** As a user, I want post-processing effects applied to my audio, so that the output feels emotionally authentic and evokes the quality of a memory.

#### Acceptance Criteria

1. WHEN the `effects` list in the SynthesisRequest contains `"reverb"`, THE SynthesisWorker SHALL apply a short room-reverb effect to the synthesized audio using pydub or ffmpeg.
2. WHEN the `effects` list in the SynthesisRequest contains `"warmth"`, THE SynthesisWorker SHALL apply a low-shelf EQ boost (centered at 200 Hz, +3 dB) to the synthesized audio using pydub or ffmpeg.
3. WHEN the `effects` list in the SynthesisRequest contains `"ambient"`, THE SynthesisWorker SHALL mix the Ambient_Noise layer into the synthesized audio at −30 dBFS using pydub or ffmpeg.
4. WHEN the `effects` list contains multiple values, THE SynthesisWorker SHALL apply the Effects_Chain in the order: reverb first, warmth EQ second, ambient noise third.
5. WHEN the `effects` list is empty, THE SynthesisWorker SHALL skip the Effects_Chain and proceed directly to MP3 encoding without applying any post-processing.
6. THE SynthesisWorker SHALL apply all Effects_Chain operations to the full audio file after all Emotional_Marker segment modifications have been applied.
7. IF any Effects_Chain operation fails, THEN THE SynthesisWorker SHALL set the AudioJob `status` to `"failed"` and log the failing effect name, `job_id`, and error detail.

---

### Requirement 6a: Background Music Layering

**User Story:** As a user, I want background music that matches the emotional tone of my scenario, so that the audio feels immersive and emotionally resonant.

#### Acceptance Criteria

1. THE SynthesisWorker SHALL select and mix a Background_Music track based on the `emotion_type` field of the SynthesisRequest.
2. WHEN `emotion_type` is `"success"`, THE SynthesisWorker SHALL mix a soft uplifting piano track beneath the synthesized speech.
3. WHEN `emotion_type` is `"regret"`, THE SynthesisWorker SHALL mix an ambient low-tone track beneath the synthesized speech.
4. WHEN `emotion_type` is `"neutral"`, THE SynthesisWorker SHALL mix a minimal background track (or no music) beneath the synthesized speech.
5. THE SynthesisWorker SHALL mix the Background_Music at a level that does not overpower the synthesized speech, ensuring the voice remains clearly intelligible at all times.
6. THE SynthesisWorker SHALL apply Background_Music layering after all Emotional_Marker modifications and Effects_Chain operations have been applied.
7. IF the Background_Music file for the requested `emotion_type` is not found, THEN THE SynthesisWorker SHALL log a warning and proceed without background music rather than failing the job.

---

### Requirement 6b: Optional Sound Effects

**User Story:** As a user, I want optional ambient sound effects to enhance the atmosphere of my audio message.

#### Acceptance Criteria

1. THE SynthesisWorker SHALL support the following optional sound effect values in the `effects` list: `"wind"`, `"city"`, `"room_tone"`.
2. WHEN the `effects` list contains `"wind"`, THE SynthesisWorker SHALL mix a low-level wind ambience layer into the audio at −35 dBFS.
3. WHEN the `effects` list contains `"city"`, THE SynthesisWorker SHALL mix a low-level city ambience layer into the audio at −35 dBFS.
4. WHEN the `effects` list contains `"room_tone"`, THE SynthesisWorker SHALL mix a low-level room tone layer into the audio at −40 dBFS.
5. ALL sound effects SHALL be mixed at levels that preserve speech intelligibility.

---

### Requirement 7: MP3 Output Encoding and Duration Constraint

**User Story:** As a user, I want the final audio delivered as an MP3 file of 30–60 seconds, so that it is compatible with standard media players and fits the system's output target.

#### Acceptance Criteria

1. THE SynthesisWorker SHALL encode the final post-processed audio as an MP3 file at a minimum bit rate of 128 kbps.
2. WHEN encoding is complete, THE SynthesisWorker SHALL write the Output_File to the File_Store using a filename derived from the `job_id`.
3. WHEN the Output_File is written, THE SynthesisWorker SHALL measure the playback duration of the Output_File in seconds and store it as `duration_sec` in the AudioJob record.
4. THE SynthesisWorker SHALL NOT produce an Output_File with a `duration_sec` of zero or a file size of zero bytes; IF either condition is detected, THEN THE SynthesisWorker SHALL set the AudioJob `status` to `"failed"` and log the anomaly.
5. WHEN the Output_File `duration_sec` is less than 25 seconds or greater than 65 seconds, THE SynthesisWorker SHALL log a warning with the `job_id` and actual duration, as the output falls outside the 30–60 second target range.
6. THE SynthesisWorker SHALL use pydub or ffmpeg for all encoding operations.

---

### Requirement 8: Job Status Polling

**User Story:** As a developer, I want a polling endpoint for job status, so that the frontend can track synthesis progress without requiring a persistent connection.

#### Acceptance Criteria

1. WHEN a GET request is made to `/audio/status/{job_id}` with a valid `job_id`, THE AudioProduction_API SHALL return HTTP 200 with the corresponding AudioJob as a JSON object containing `job_id`, `status`, `output_url`, and `duration_sec`.
2. WHEN a GET request is made to `/audio/status/{job_id}` with a `job_id` that does not exist, THE AudioProduction_API SHALL return HTTP 404 with a descriptive error message.
3. WHEN the AudioJob `status` is `"queued"` or `"processing"`, THE AudioProduction_API SHALL return `output_url` as `null` and `duration_sec` as `null` in the response.
4. WHEN the AudioJob `status` is `"done"`, THE AudioProduction_API SHALL return a non-null `output_url` and a non-null `duration_sec` in the response.
5. WHEN the AudioJob `status` is `"failed"`, THE AudioProduction_API SHALL return `output_url` as `null` and `duration_sec` as `null` in the response.
6. THE AudioProduction_API SHALL reflect the current `status` value from the Job_Store at the time of each polling request, without caching stale values.

---

### Requirement 9: Audio File Download

**User Story:** As a user, I want to download the final audio file, so that I can save or share my future self message.

#### Acceptance Criteria

1. WHEN a GET request is made to `/audio/download/{job_id}` and the corresponding AudioJob `status` is `"done"`, THE AudioProduction_API SHALL return the Output_File as an HTTP 200 response with `Content-Type: audio/mpeg` and `Content-Disposition: attachment; filename="{job_id}.mp3"`.
2. WHEN a GET request is made to `/audio/download/{job_id}` and the corresponding AudioJob `status` is `"queued"` or `"processing"`, THE AudioProduction_API SHALL return HTTP 202 with a descriptive message indicating the job is not yet complete.
3. WHEN a GET request is made to `/audio/download/{job_id}` and the corresponding AudioJob `status` is `"failed"`, THE AudioProduction_API SHALL return HTTP 410 with a descriptive error message indicating the job failed and no file is available.
4. WHEN a GET request is made to `/audio/download/{job_id}` with a `job_id` that does not exist, THE AudioProduction_API SHALL return HTTP 404 with a descriptive error message.
5. IF the Output_File is not found in the File_Store despite the AudioJob `status` being `"done"`, THEN THE AudioProduction_API SHALL return HTTP 500 with a descriptive error message and SHALL log the inconsistency with the `job_id`.

---

### Requirement 10: AudioPlayer Frontend Component

**User Story:** As a user, I want a browser-based audio player to preview and download my synthesized message, so that I can experience the output without leaving the application.

#### Acceptance Criteria

1. THE AudioPlayer SHALL accept a `job_id` as a prop and poll the `/audio/status/{job_id}` endpoint at 3-second intervals until the AudioJob `status` is `"done"` or `"failed"`.
2. WHILE the AudioJob `status` is `"queued"` or `"processing"`, THE AudioPlayer SHALL display a loading indicator and the current `status` label.
3. WHEN the AudioJob `status` transitions to `"done"`, THE AudioPlayer SHALL stop polling and render a waveform visualization of the Output_File audio.
4. WHEN the AudioJob `status` transitions to `"failed"`, THE AudioPlayer SHALL stop polling and display a human-readable error message.
5. THE AudioPlayer SHALL provide a play/pause control that starts and stops playback of the Output_File.
6. THE AudioPlayer SHALL display the current playback position and total `duration_sec` formatted as minutes and seconds (e.g., "0:42 / 1:15").
7. THE AudioPlayer SHALL provide a download button that triggers a GET request to `/audio/download/{job_id}` and initiates a browser file download of the MP3.
8. WHEN the download request returns HTTP 202, THE AudioPlayer SHALL display a message indicating the file is not yet ready and SHALL NOT initiate a file download.
9. WHILE a download request is in progress, THE AudioPlayer SHALL disable the download button and display a loading indicator on it.
10. THE AudioPlayer SHALL display the `job_id` so that the user can reference it for support or debugging purposes.

---

### Requirement 11: Job Store Persistence and Consistency

**User Story:** As a developer, I want AudioJob records to be reliably persisted and consistent with worker state, so that polling clients always receive accurate job information.

#### Acceptance Criteria

1. THE AudioProduction_API SHALL persist AudioJob records containing `job_id`, `status`, `output_url`, `duration_sec`, `script_id`, `voice_id`, `effects`, and a `created_at` timestamp in UTC ISO 8601 format.
2. WHEN the SynthesisWorker updates an AudioJob `status`, THE SynthesisWorker SHALL write the update to the Job_Store atomically before proceeding to the next processing step.
3. WHEN a GET request is made to `/audio/status/{job_id}`, THE AudioProduction_API SHALL read the AudioJob record directly from the Job_Store and SHALL NOT return a cached value that predates the most recent worker update.
4. IF the Job_Store is unavailable at the time of a status read, THEN THE AudioProduction_API SHALL return HTTP 503 with a descriptive error message.
5. IF the Job_Store is unavailable at the time of a job submission write, THEN THE AudioProduction_API SHALL return HTTP 503 with a descriptive error message and SHALL NOT enqueue the job on the JobQueue.

---

### Requirement 12: Emotional Authenticity and Intelligibility

**User Story:** As a user, I want the synthesized audio to feel like a genuine message from my future self, with background audio that enhances rather than obscures the voice.

#### Acceptance Criteria

1. THE SynthesisWorker SHALL use the `voice_id` associated with the user's cloned voice from the Voice Capture & Cloning module, so that the synthesized voice matches the user's own tonal identity.
2. THE SynthesisWorker SHALL set ElevenLabs voice settings (`stability`, `similarity_boost`) based on `emotion_type` as defined in Requirement 4, to ensure the voice style matches the scenario's emotional register.
3. THE SynthesisWorker SHALL mix all background audio (music and sound effects) at levels that keep the synthesized speech clearly intelligible at all times. The speech-to-background ratio SHALL be at least 10 dB.
4. THE SynthesisWorker SHALL NOT alter the `text` content of the DialogueScript before submitting it to ElevenLabs, except to strip Emotional_Marker tokens from the raw synthesis input.
5. WHEN Emotional_Markers are stripped from the synthesis input, THE SynthesisWorker SHALL retain the marker positions as timestamps so that segment-level audio modifications can be applied after synthesis.
6. THE SynthesisWorker SHALL produce an Output_File whose `duration_sec` is within 10% of the DialogueScript `estimated_duration_sec`, and IF the deviation exceeds 10%, THEN THE SynthesisWorker SHALL log a warning with the `job_id`, expected duration, and actual duration.

---

### Requirement 13: Round-Trip Script-to-Audio Integrity

**User Story:** As a developer, I want the synthesis pipeline to preserve the full content of the DialogueScript, so that no spoken content is lost or duplicated between input and output.

#### Acceptance Criteria

1. THE SynthesisWorker SHALL submit the complete DialogueScript `text` to the TTS_Provider without truncation, so that every word in the script is present in the synthesized audio.
2. WHEN the TTS_Provider returns audio, THE SynthesisWorker SHALL verify that the returned audio duration is greater than zero seconds before proceeding to post-processing.
3. FOR ALL valid DialogueScript inputs, the SynthesisWorker SHALL produce an Output_File that contains audio corresponding to the full `text` content without omission or repetition.
4. WHEN the same `script_id` and `voice_id` are submitted in two separate SynthesisRequests with identical `effects` lists, THE SynthesisWorker SHALL produce two Output_Files with equivalent spoken content, though minor acoustic variation between runs is acceptable.

---

### Requirement 14: API Error Handling and Observability

**User Story:** As a developer, I want all API errors and worker failures to be logged with structured detail, so that issues can be diagnosed quickly in production.

#### Acceptance Criteria

1. WHEN any request to the AudioProduction_API results in an HTTP 4xx or 5xx response, THE AudioProduction_API SHALL log the error with a timestamp, request path, HTTP method, and error detail.
2. WHEN an unhandled exception occurs during request processing, THE AudioProduction_API SHALL return HTTP 500 with a JSON body containing a `detail` field and SHALL NOT expose internal stack traces or raw TTS_Provider responses to the client.
3. THE AudioProduction_API SHALL return all error responses as JSON objects with at minimum a `detail` field describing the error.
4. WHEN the SynthesisWorker sets an AudioJob `status` to `"failed"`, THE SynthesisWorker SHALL log the `job_id`, the processing stage at which the failure occurred, and the error detail.
5. WHEN the SynthesisWorker retries an upstream API call, THE SynthesisWorker SHALL log each retry attempt with the attempt number, target service name, and failure reason.
6. THE AudioProduction_API SHALL log each job submission with the `job_id`, `script_id`, `voice_id`, and `effects` list at the time of enqueue.

---

### Requirement 15: Upstream Module Compatibility

**User Story:** As a developer, I want the Audio Production Engine to consume `script_id` and `voice_id` exactly as produced by the Dialogue Generator and Voice Capture modules, so that the modules integrate without data transformation.

#### Acceptance Criteria

1. THE AudioProduction_API SHALL accept `script_id` values as non-empty strings matching the format returned by the DialogueGenerator_API, without requiring any transformation.
2. THE AudioProduction_API SHALL accept `voice_id` values as non-empty strings matching the format returned by the VoiceCapture_API, without requiring any transformation.
3. THE SynthesisWorker SHALL pass the `voice_id` to ElevenLabs without modification, so that the provider resolves the correct cloned voice.
4. THE SynthesisWorker SHALL pass the `script_id` to the DialogueGenerator_API retrieval call without modification, so that the correct DialogueScript is resolved.
5. WHEN the DialogueGenerator_API returns a DialogueScript with an `emotional_markers` list, THE SynthesisWorker SHALL use that list as the authoritative set of markers for synthesis, without re-parsing the `text` field independently.

---

### Requirement 16: Output Quality Evaluation

**User Story:** As a developer, I want the synthesized audio to be evaluated against quality thresholds before the job is marked done, so that only acceptable outputs are delivered to users.

#### Acceptance Criteria

1. WHEN the Output_File is produced, THE SynthesisWorker SHALL verify that `duration_sec` is between 25 and 65 seconds (the acceptable range for the 30–60 second target).
2. WHEN the Output_File is produced, THE SynthesisWorker SHALL verify that the file size is greater than zero bytes.
3. WHEN the Output_File is produced, THE SynthesisWorker SHALL verify that the speech-to-background ratio is at least 10 dB by measuring peak speech amplitude against background audio amplitude.
4. WHEN any quality check fails, THE SynthesisWorker SHALL set the AudioJob `status` to `"failed"` and log the failing check name, `job_id`, and measured value.
5. THE SynthesisWorker SHALL log a `audio_quality` assessment (pass/fail per check) alongside each completed AudioJob record in the Job_Store.
