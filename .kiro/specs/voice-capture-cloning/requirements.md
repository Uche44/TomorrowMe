# Requirements Document

## Introduction

The Voice Capture & Cloning module is part of the Future Self Voice Simulator project. It is responsible for collecting audio samples from the user, validating their quality, extracting a voice profile, and cloning the voice exclusively using the ElevenLabs voice cloning API. The module exposes a REST API via FastAPI and a React frontend component (`VoiceRecorder`) that supports both microphone capture and file upload. The resulting `voice_id` is consumed downstream by the Audio Production Engine module. Audio samples must be 30–60 seconds of clear, single-speaker audio with no heavy background noise.

---

## Glossary

- **VoiceCapture_API**: The FastAPI application that handles audio upload, voice profile retrieval, and voice deletion.
- **VoiceCloner**: The internal service layer that communicates with the ElevenLabs API to register and clone a voice.
- **ElevenLabs_API**: The exclusively supported external voice cloning and TTS service. No alternative providers (e.g., Coqui, Google TTS) are permitted.
- **VoiceProfile**: A data record containing metadata about a cloned voice, including `voice_id`, `provider`, `sample_duration_sec`, and `created_at`.
- **VoiceRecorder**: The React frontend component that enables microphone capture and audio file upload, and renders a waveform preview.
- **Audio_Sample**: A user-submitted audio recording used as the source material for voice cloning. Must be 30–60 seconds, single speaker, with no heavy background noise.
- **voice_id**: A unique string identifier for a cloned voice, returned by ElevenLabs after successful upload and usable by the Audio Production Engine.
- **Audio_Production_Engine**: The downstream module that consumes `voice_id` to synthesize speech in the user's cloned voice.
- **Waveform_Preview**: A visual representation of the audio signal rendered in the VoiceRecorder component.
- **Sample_Duration**: The total playback length of an Audio_Sample, measured in seconds.
- **Single_Speaker_Constraint**: The requirement that each Audio_Sample contains exactly one speaker's voice with no overlapping voices or background speech.

---

## Requirements

### Requirement 1: Audio Sample Upload

**User Story:** As a user, I want to upload audio recordings of my voice, so that the system can use them to clone my voice via ElevenLabs.

#### Acceptance Criteria

1. WHEN a user submits a POST request to `/voice/upload` with one or more audio files, THE VoiceCapture_API SHALL accept files in WAV, MP3, M4A, and OGG formats.
2. WHEN a submitted audio file exceeds 50 MB in size, THE VoiceCapture_API SHALL reject the request and return HTTP 422 with a descriptive error message.
3. WHEN a submitted audio file is in an unsupported format, THE VoiceCapture_API SHALL reject the request and return HTTP 415 with a descriptive error message.
4. WHEN all submitted audio files pass validation, THE VoiceCapture_API SHALL forward the files to the VoiceCloner for processing.
5. WHEN the VoiceCloner successfully registers the voice with ElevenLabs, THE VoiceCapture_API SHALL return HTTP 201 with a JSON body containing the `voice_id`.
6. IF ElevenLabs returns an error during registration, THEN THE VoiceCapture_API SHALL retry the request once before returning HTTP 502 with a descriptive error message, and SHALL NOT persist a VoiceProfile.

---

### Requirement 2: Audio Sample Quality Validation

**User Story:** As a system, I want to validate the quality of submitted audio samples, so that only samples sufficient for accurate ElevenLabs voice cloning are accepted.

#### Acceptance Criteria

1. WHEN an Audio_Sample is received, THE VoiceCloner SHALL measure the Sample_Duration of the submitted audio.
2. WHEN the total Sample_Duration of all submitted files is less than 30 seconds, THE VoiceCapture_API SHALL reject the request and return HTTP 422 with a message indicating insufficient sample duration.
3. WHEN the total Sample_Duration of all submitted files exceeds 60 seconds, THE VoiceCapture_API SHALL accept the request but SHALL log a warning that the sample exceeds the recommended maximum.
4. WHEN an Audio_Sample has a signal-to-noise ratio below 20 dB, THE VoiceCapture_API SHALL reject the request and return HTTP 422 with a message indicating poor audio quality and prompting the user to retry with a cleaner recording.
5. WHEN an Audio_Sample has a sample rate below 16,000 Hz, THE VoiceCapture_API SHALL reject the request and return HTTP 422 with a message indicating insufficient audio resolution.
6. WHEN an Audio_Sample is detected to contain more than one simultaneous speaker, THE VoiceCapture_API SHALL reject the request and return HTTP 422 with a message indicating the single-speaker constraint was violated.
7. WHEN all quality checks pass, THE VoiceCloner SHALL proceed with voice registration via ElevenLabs.

---

### Requirement 3: Voice Profile Storage

**User Story:** As a developer, I want voice profile metadata to be persisted after cloning, so that it can be retrieved and used by downstream modules.

#### Acceptance Criteria

1. WHEN the VoiceCloner successfully registers a voice with ElevenLabs, THE VoiceCapture_API SHALL persist a VoiceProfile record containing `voice_id`, `provider`, `sample_duration_sec`, and `created_at`.
2. THE VoiceCapture_API SHALL assign a `created_at` timestamp in UTC ISO 8601 format at the time of successful registration.
3. THE VoiceCapture_API SHALL store the `provider` field as `"elevenlabs"` for all VoiceProfile records. No other provider value is permitted.
4. WHEN two upload requests are processed concurrently, THE VoiceCapture_API SHALL assign distinct `voice_id` values to each resulting VoiceProfile.

---

### Requirement 4: Voice Profile Retrieval

**User Story:** As a developer, I want to retrieve voice profile metadata by ID, so that downstream modules can look up cloned voice details.

#### Acceptance Criteria

1. WHEN a GET request is made to `/voice/{voice_id}` with a valid `voice_id`, THE VoiceCapture_API SHALL return HTTP 200 with the corresponding VoiceProfile as a JSON object.
2. WHEN a GET request is made to `/voice/{voice_id}` with a `voice_id` that does not exist, THE VoiceCapture_API SHALL return HTTP 404 with a descriptive error message.
3. THE VoiceCapture_API SHALL return the VoiceProfile JSON with fields `voice_id`, `provider`, `sample_duration_sec`, and `created_at` in every successful retrieval response.

---

### Requirement 5: Voice Profile Deletion

**User Story:** As a user, I want to delete my cloned voice, so that my voice data is removed from the system and from ElevenLabs.

#### Acceptance Criteria

1. WHEN a DELETE request is made to `/voice/{voice_id}` with a valid `voice_id`, THE VoiceCapture_API SHALL request deletion of the voice from ElevenLabs via the ElevenLabs API.
2. WHEN ElevenLabs confirms deletion, THE VoiceCapture_API SHALL remove the corresponding VoiceProfile from storage and return HTTP 204.
3. WHEN a DELETE request is made to `/voice/{voice_id}` with a `voice_id` that does not exist, THE VoiceCapture_API SHALL return HTTP 404 with a descriptive error message.
4. IF ElevenLabs returns an error during deletion, THEN THE VoiceCapture_API SHALL return HTTP 502 with a descriptive error message and SHALL NOT remove the VoiceProfile from storage.

---

### Requirement 6: ElevenLabs as Exclusive Voice Cloning Provider

**User Story:** As a developer, I want the system to use ElevenLabs exclusively for voice cloning, so that voice quality and API contract are consistent and predictable.

#### Acceptance Criteria

1. THE VoiceCloner SHALL use the ElevenLabs voice cloning API for all voice registration, retrieval, and deletion operations. No alternative TTS or voice cloning provider (e.g., Coqui TTS, Google TTS) is permitted.
2. THE VoiceCloner SHALL authenticate with ElevenLabs using an API key supplied via environment variable and SHALL NOT hard-code credentials.
3. WHEN registering a voice, THE VoiceCloner SHALL call the ElevenLabs `POST /v1/voices/add` endpoint with the audio samples and a descriptive voice name.
4. WHEN deleting a voice, THE VoiceCloner SHALL call the ElevenLabs `DELETE /v1/voices/{voice_id}` endpoint.
5. THE VoiceCapture_API SHALL expose the same request and response schema regardless of ElevenLabs API version changes, isolating the rest of the system from provider-level changes.

---

### Requirement 7: Voice Identity and Emotional Authenticity

**User Story:** As a user, I want the cloned voice to match my tone and feel emotionally authentic, so that the synthesized output sounds like a genuine version of me.

#### Acceptance Criteria

1. WHEN a voice is cloned from Audio_Samples, THE VoiceCloner SHALL submit all provided Audio_Samples to ElevenLabs to maximize tonal fidelity.
2. WHEN Audio_Samples contain varied emotional inflections (e.g., calm, expressive), THE VoiceCloner SHALL include all such samples in the ElevenLabs registration payload.
3. WHEN ElevenLabs returns a cloned voice, THE VoiceCapture_API SHALL store the resulting `voice_id` so that the Audio_Production_Engine can use it for synthesis without modification.
4. THE VoiceCloner SHALL set the ElevenLabs voice description field to indicate the voice is a personal clone, to assist ElevenLabs in optimizing similarity.

---

### Requirement 8: VoiceRecorder Frontend Component

**User Story:** As a user, I want a browser-based interface to record my voice or upload audio files, so that I can provide samples without leaving the application.

#### Acceptance Criteria

1. THE VoiceRecorder SHALL provide a microphone capture control that records audio directly in the browser using the Web Audio API.
2. THE VoiceRecorder SHALL provide a file upload control that accepts WAV, MP3, M4A, and OGG files.
3. WHEN audio is captured or a file is selected, THE VoiceRecorder SHALL render a Waveform_Preview of the audio signal.
4. THE VoiceRecorder SHALL display the current recording duration in real time and SHALL visually indicate when the 30-second minimum has been reached.
5. WHEN the user submits audio, THE VoiceRecorder SHALL send a POST request to `/voice/upload` with the audio data as multipart form data.
6. WHEN the VoiceCapture_API returns a successful response, THE VoiceRecorder SHALL display the returned `voice_id` to the user.
7. WHEN the VoiceCapture_API returns an error response, THE VoiceRecorder SHALL display a human-readable error message corresponding to the error code, including actionable guidance for quality-related rejections (e.g., "Recording too short — please record at least 30 seconds").
8. WHILE a submission is in progress, THE VoiceRecorder SHALL disable the submit control and display a loading indicator.

---

### Requirement 9: voice_id Compatibility with Audio Production Engine

**User Story:** As a developer, I want the `voice_id` returned by this module to be directly usable by the Audio Production Engine, so that the two modules integrate without transformation.

#### Acceptance Criteria

1. THE VoiceCapture_API SHALL return `voice_id` values as non-empty strings with no whitespace.
2. WHEN a `voice_id` is stored in a VoiceProfile, THE VoiceCapture_API SHALL return the identical `voice_id` string in all subsequent GET responses for that profile.
3. THE VoiceCapture_API SHALL NOT transform, truncate, or re-encode the `voice_id` value received from the TTS_Provider before storing or returning it.

---

### Requirement 11: Output Quality Evaluation

**User Story:** As a developer, I want the voice cloning output to be evaluated against quality thresholds, so that only acceptable clones proceed to downstream synthesis.

#### Acceptance Criteria

1. WHEN ElevenLabs returns a cloned voice, THE VoiceCloner SHALL record the voice similarity score if provided by the ElevenLabs API response.
2. THE VoiceCapture_API SHALL store the `similarity_score` field in the VoiceProfile record when available from ElevenLabs.
3. WHEN the `similarity_score` returned by ElevenLabs is below an acceptable threshold (configurable, default 0.75 on a 0–1 scale), THE VoiceCapture_API SHALL return HTTP 422 with a message indicating the voice clone did not meet quality standards and SHALL NOT persist the VoiceProfile.
4. THE VoiceCapture_API SHALL log the `similarity_score` alongside the `voice_id` and `sample_duration_sec` for every successful clone registration.

**User Story:** As a developer, I want all API errors to be logged and return structured responses, so that issues can be diagnosed quickly.

#### Acceptance Criteria

1. WHEN any request to the VoiceCapture_API results in an HTTP 4xx or 5xx response, THE VoiceCapture_API SHALL log the error with a timestamp, request path, HTTP method, and error detail.
2. WHEN an unhandled exception occurs during request processing, THE VoiceCapture_API SHALL return HTTP 500 with a JSON body containing a `detail` field and SHALL NOT expose internal stack traces to the client.
3. THE VoiceCapture_API SHALL return all error responses as JSON objects with at minimum a `detail` field describing the error.
