# Implementation Plan: Dialogue Generator

## Overview

Implement the Dialogue Generator microservice: a FastAPI backend that fetches Persona and Scenario records from upstream APIs, calls Google Gemini to produce voice-ready `DialogueScript` monologues, validates and persists results to SQLite, and exposes a React `ScriptEditor` frontend component.

## Tasks

- [x] 1. Project setup and configuration
  - Create the project directory structure: `app/`, `app/models/`, `app/services/`, `app/clients/`, `app/store/`, `tests/`, `frontend/src/components/ScriptEditor/`
  - Create `requirements.txt` (or `pyproject.toml`) with: `fastapi`, `uvicorn`, `pydantic`, `google-generativeai`, `aiosqlite`, `httpx`, `pytest`, `pytest-asyncio`, `hypothesis`, `pytest-hypothesis`
  - Create `app/config.py` with a `Settings` class (Pydantic `BaseSettings`) for `GEMINI_API_KEY`, `GEMINI_MODEL`, `PERSONA_API_BASE_URL`, `SCENARIO_API_BASE_URL`, `DATABASE_URL`, `LLM_TIMEOUT_SEC=30`, `UPSTREAM_TIMEOUT_SEC=10`
  - Create `app/main.py` with the bare FastAPI app instance, lifespan handler for DB init, and router inclusion
  - _Requirements: 1.1, 8.1, 9.1_

- [ ] 2. Exception hierarchy and error handlers
  - [ ] 2.1 Create `app/exceptions.py` with the full exception hierarchy: `DialogueGeneratorError`, `UpstreamError`, `PersonaNotFoundError`, `ScenarioNotFoundError`, `UpstreamServiceError`, `UpstreamTimeoutError`, `LLMError`, `LLMTimeoutError`, `LLMProviderError`, `ScriptQualityError`, `StoreError`
    - _Requirements: 3.3, 3.4, 3.5, 3.6, 1.8, 8.6, 12.2_
  - [ ] 2.2 Register FastAPI exception handlers in `app/main.py` for each exception type, mapping to the correct HTTP status codes (404, 502, 503, 504, 500)
    - Each handler must log: UTC timestamp, request path, HTTP method, error detail
    - Unhandled exception handler must return HTTP 500 with `{"detail": "Internal server error"}` and never expose stack traces
    - _Requirements: 12.1, 12.2, 12.3_

- [ ] 3. Data models
  - [ ] 3.1 Create `app/models/api.py` with `DialogueRequest`, `DialogueScript`, and `ErrorResponse` Pydantic models
    - `DialogueRequest`: `persona_id` and `scenario_id` validators reject empty strings and any whitespace; `length` is `Literal["short", "long"]`; `tone_override` is optional with `max_length=100` and blank-string rejection
    - `DialogueScript`: `script_id` (str), `text` (str), `estimated_duration_sec` (float), `emotional_markers` (list[str])
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 4.3, 11.1, 11.2, 11.3, 11.4_
  - [ ] 3.2 Create `app/models/upstream.py` with `Persona` and `Scenario` Pydantic models matching the upstream API response shapes
    - _Requirements: 1.1, 3.1, 3.2_
  - [ ] 3.3 Create `app/models/persistence.py` with `PersistedScript` Pydantic model including all fields: `script_id`, `text`, `estimated_duration_sec`, `emotional_markers`, `persona_id`, `scenario_id`, `length`, `created_at` (datetime UTC), `quality_pass` (bool), `quality_detail` (str JSON)
    - _Requirements: 8.2, 13.5_
  - [ ]* 3.4 Write property test for `DialogueRequest` ID field validation (Property 7)
    - **Property 7: ID field validation rejects whitespace and empty strings**
    - **Validates: Requirements 2.1, 2.2**
    - Use `hypothesis` `st.text()` strategy; assert empty/whitespace strings raise `ValidationError`, non-empty no-whitespace strings are accepted
    - Tag: `# Feature: dialogue-generator, Property 7: ID field validation`
    - File: `tests/test_validation.py`
  - [ ]* 3.5 Write property test for `DialogueRequest` length field validation (Property 8)
    - **Property 8: Length field validation rejects all non-enum values**
    - **Validates: Requirements 2.3, 4.3**
    - Use `st.text()` strategy; assert only `"short"` and `"long"` are accepted, all other strings raise `ValidationError`
    - Tag: `# Feature: dialogue-generator, Property 8: Length field validation`
    - File: `tests/test_validation.py`

- [-] 4. SQLite persistence layer
  - [x] 4.1 Create `app/store/script_store.py` with `ScriptStore` class using `aiosqlite`
    - `async def init_db(db_path: str) -> None` — creates the `scripts` table if not exists using the schema from the design
    - `async def save(self, script: PersistedScript) -> None` — inserts a record; raises `StoreError` on any `aiosqlite` exception
    - `async def get(self, script_id: str) -> PersistedScript | None` — returns the record or `None`; raises `StoreError` on DB errors
    - Store `emotional_markers` as a JSON array string; store `created_at` as UTC ISO 8601 string
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_
  - [ ]* 4.2 Write property test for persistence round-trip (Property 6)
    - **Property 6: Persistence round-trip preserves all fields exactly**
    - **Validates: Requirements 8.1, 8.3, 8.5, 11.5, 11.6**
    - Use `st.builds(PersistedScript, ...)` strategy with an in-memory SQLite DB; assert every field is byte-for-byte identical after save + get
    - Tag: `# Feature: dialogue-generator, Property 6: Persistence round-trip`
    - File: `tests/test_script_store.py`

- [ ] 5. Checkpoint — core infrastructure ready
  - Ensure all tests pass, ask the user if questions arise.

- [-] 6. UpstreamClient
  - [ ] 6.1 Create `app/clients/upstream_client.py` with `UpstreamClient` using `httpx.AsyncClient`
    - `async def get_persona(self, persona_id: str) -> Persona` — GET `{PERSONA_API_BASE_URL}/persona/{persona_id}` with 10s timeout; raise `PersonaNotFoundError` on 404, `UpstreamServiceError` on 5xx, `UpstreamTimeoutError` on `httpx.TimeoutException`
    - `async def get_scenario(self, scenario_id: str) -> Scenario` — GET `{SCENARIO_API_BASE_URL}/scenario/{scenario_id}` with 10s timeout; raise `ScenarioNotFoundError` on 404, `UpstreamServiceError` on 5xx, `UpstreamTimeoutError` on timeout
    - Log upstream failures with: service name, HTTP status code, request URL
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 12.5_
  - [ ]* 6.2 Write unit tests for `UpstreamClient`
    - Test 404 → `PersonaNotFoundError`, 5xx → `UpstreamServiceError`, timeout → `UpstreamTimeoutError` for both persona and scenario endpoints using `httpx` mock transport
    - File: `tests/test_upstream_client.py`
    - _Requirements: 3.3, 3.4, 3.5, 3.6_

- [-] 7. GeminiClient
  - [ ] 7.1 Create `app/clients/gemini_client.py` with `GeminiClient` wrapping `google-generativeai`
    - `__init__`: configure `genai.GenerativeModel` with `model_name`, `api_key`, `generation_config` (`temperature=0.85`, `max_output_tokens` based on length)
    - `async def generate(self, system_prompt: str, user_prompt: str) -> str` — call `generate_content` wrapped in `asyncio.wait_for` with 30s timeout; raise `LLMTimeoutError` on timeout, `LLMProviderError` on SDK exceptions
    - _Requirements: 1.8, 9.1, 9.2, 9.3, 9.6_
  - [ ]* 7.2 Write unit tests for `GeminiClient`
    - Test successful generation returns string, timeout raises `LLMTimeoutError`, SDK error raises `LLMProviderError`
    - File: `tests/test_gemini_client.py`
    - _Requirements: 1.8, 9.6_

- [-] 8. ScriptBuilder — prompt construction and parsing
  - [ ] 8.1 Create `app/services/script_builder.py` with `ScriptBuilder` class (no FastAPI dependency)
    - Implement `_build_system_prompt(persona, scenario, tone) -> str` using the system prompt template from the design: embed `persona.summary`, `tone`, `key_life_events` bullet list, `scenario_type` register guidance, `scenario.context`, `scenario.emotional_target`
    - Implement `_build_user_prompt(persona, scenario, length) -> str` using the user prompt template: include `[HOOK]`/`[REFLECTION]`/`[ADVICE]`/`[CLOSING]` structure instructions, word target and target seconds for the given length, marker list, tone marker guidance based on `persona.tone`, `scenario.emotional_target`, `scenario.trigger`, `persona.key_message`, one `key_life_event`
    - _Requirements: 1.2, 1.3, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 5.5, 5.6, 5.7, 5.8_
  - [ ]* 8.2 Write property test for system prompt completeness (Property 1)
    - **Property 1: System prompt contains all required persona and scenario fields**
    - **Validates: Requirements 1.2, 7.1, 7.4, 7.6, 7.9**
    - Use `st.builds(Persona)` and `st.builds(Scenario)` strategies; assert all required fields appear in the returned prompt string
    - Tag: `# Feature: dialogue-generator, Property 1: System prompt completeness`
    - File: `tests/test_script_builder.py`
  - [ ]* 8.3 Write property test for tone selection precedence (Property 4)
    - **Property 4: Tone selection — override takes precedence**
    - **Validates: Requirements 6.2, 6.3**
    - Use `st.builds(Persona)` and `st.text() | st.none()` for `tone_override`; assert non-empty override appears in prompt and persona tone does not appear in the tone position; assert `None` override uses persona tone
    - Tag: `# Feature: dialogue-generator, Property 4: Tone selection`
    - File: `tests/test_script_builder.py`
  - [ ] 8.4 Implement `_strip_labels`, `_strip_invalid_markers`, `_extract_markers`, and `_estimate_duration` in `ScriptBuilder`
    - `_strip_labels`: remove `[HOOK]`, `[REFLECTION]`, `[ADVICE]`, `[CLOSING]` tokens from text
    - `_strip_invalid_markers`: remove any `[token]` where token is not in `VALID_MARKERS`
    - `_extract_markers`: return sorted list of unique valid marker tokens found in text
    - `_estimate_duration`: strip markers, count words, return `round((words / 130.0) * 60, 1)`
    - _Requirements: 5.2, 5.3, 4.4_
  - [ ]* 8.5 Write property test for duration estimation formula (Property 2)
    - **Property 2: Duration estimation formula correctness**
    - **Validates: Requirements 4.4**
    - Use `st.text()` with injected marker tokens; assert result equals `round((word_count_of_clean_text / 130.0) * 60, 1)`
    - Tag: `# Feature: dialogue-generator, Property 2: Duration formula`
    - File: `tests/test_script_builder.py`
  - [ ]* 8.6 Write property test for marker extraction correctness (Property 3)
    - **Property 3: Marker extraction returns the correct unique valid set**
    - **Validates: Requirements 5.2, 5.3**
    - Use `st.text()` with random valid and invalid marker tokens; assert invalid tokens absent from cleaned text, valid tokens present in `emotional_markers` exactly once
    - Tag: `# Feature: dialogue-generator, Property 3: Marker extraction`
    - File: `tests/test_script_builder.py`

- [-] 9. QualityValidator
  - [ ] 9.1 Create `app/services/quality_validator.py` with `QualityValidator` and `ValidationResult` dataclass
    - `_check_structure(text) -> bool`: heuristic check — at least 4 sentence-level segments; first sentence is interrogative or declarative-imperative; last sentence ≤ 20 words
    - `_check_duration(duration, length) -> bool`: assert 25–35s for `"short"`, 50–65s for `"long"`
    - `_check_markers(text) -> bool`: assert at least one valid marker token present in text
    - `validate(text, duration, length) -> ValidationResult`: run all three checks, populate `failure_reasons`
    - _Requirements: 13.1, 13.2, 13.3, 4.1, 4.2, 5.4_
  - [ ]* 9.2 Write unit tests for `QualityValidator`
    - Test each check independently: structure pass/fail, duration boundary values for both lengths, markers present/absent
    - File: `tests/test_quality_validator.py`
    - _Requirements: 13.1, 13.2, 13.3_

- [ ] 10. ScriptBuilder — quality retry loop and `build_script`
  - [ ] 10.1 Implement `ScriptBuilder.build_script` with the quality retry loop (max 3 total attempts)
    - On each attempt: call `gemini_client.generate`, strip labels, strip invalid markers, extract markers, estimate duration, run `QualityValidator.validate`
    - On pass: return `DialogueScript` with a new `uuid.uuid4()` `script_id`
    - On fail: log warning with attempt number, LLM provider name, failure reasons; retry
    - After all retries exhausted: raise `ScriptQualityError`
    - Log each retry with attempt number, provider name, failure reason
    - _Requirements: 1.4, 1.6, 4.5, 5.4, 13.4, 12.4_
  - [ ]* 10.2 Write unit tests for `ScriptBuilder.build_script` retry behavior
    - Test: validator fails twice then passes → exactly 3 LLM calls made
    - Test: all 3 attempts fail → `ScriptQualityError` raised
    - Test: `tone_override` present → override used in system prompt, not persona tone
    - File: `tests/test_script_builder.py`
    - _Requirements: 4.5, 5.4, 6.2, 6.3, 13.4_

- [-] 11. API routes
  - [x] 11.1 Create `app/routes/dialogue.py` with the three route handlers and wire into `app/main.py`
    - `POST /dialogue/generate`: validate `DialogueRequest` (422 on failure), fetch Persona and Scenario via `UpstreamClient`, call `ScriptBuilder.build_script`, persist `PersistedScript` via `ScriptStore` (503 on `StoreError`), return HTTP 201 `DialogueScript`
    - `POST /dialogue/regenerate`: same flow as generate; assign new `script_id`; persist independently
    - `GET /dialogue/{script_id}`: fetch from `ScriptStore`; return HTTP 200 or 404
    - Persist `quality_pass` and `quality_detail` JSON alongside each script record
    - _Requirements: 1.1, 1.5, 1.7, 6.1, 6.4, 6.5, 8.1, 8.2, 8.3, 8.4, 8.6, 13.5_
  - [ ]* 11.2 Write property test for script ID uniqueness (Property 5)
    - **Property 5: Script ID uniqueness across all generated scripts**
    - **Validates: Requirements 1.6, 1.7, 11.1**
    - Use `st.integers(min_value=2, max_value=50)` for N; generate N scripts with mocked LLM and upstream; assert all `script_id` values are distinct non-empty UUID strings with no whitespace
    - Tag: `# Feature: dialogue-generator, Property 5: Script ID uniqueness`
    - File: `tests/test_api.py`
  - [ ]* 11.3 Write unit tests for API route error paths
    - HTTP 404 when persona not found; HTTP 404 when scenario not found; HTTP 502 when upstream returns 5xx; HTTP 504 when upstream times out; HTTP 502 when LLM times out; HTTP 502 when quality checks fail after all retries; HTTP 503 when SQLite unavailable; HTTP 500 for unhandled exception (no stack trace in response body); HTTP 201 response shape for successful generation
    - File: `tests/test_api.py`
    - _Requirements: 1.8, 3.3, 3.4, 3.5, 3.6, 8.6, 12.2_
  - [ ]* 11.4 Write unit tests for GET route and persistence retrieval
    - GET `/dialogue/{script_id}` returns HTTP 200 with correct body; GET `/dialogue/{unknown_id}` returns HTTP 404; retrieved fields are identical to stored values
    - File: `tests/test_api.py`
    - _Requirements: 8.3, 8.4, 8.5, 11.5, 11.6_

- [ ] 12. Checkpoint — backend complete
  - Ensure all tests pass, ask the user if questions arise.

- [-] 13. React ScriptEditor component
  - [x] 13.1 Create `frontend/src/components/ScriptEditor/MarkerBadge.tsx`
    - Renders a single marker token as a colored badge using the color map from the design (pause→slate, softer→sky, warmth→amber, urgency→red, breath→teal, slower→violet, faster→orange)
    - _Requirements: 10.1_
  - [x] 13.2 Create `frontend/src/components/ScriptEditor/DurationDisplay.tsx`
    - Accepts `estimated_duration_sec: number` and renders it as `"Xm YYs"` (e.g., `62.0` → `"1m 02s"`)
    - _Requirements: 10.2_
  - [x] 13.3 Create `frontend/src/components/ScriptEditor/ScriptDisplay.tsx`
    - Splits script text on `\[([a-z]+)\]` regex; renders plain text segments and `<MarkerBadge>` for each valid marker token
    - _Requirements: 10.1_
  - [x] 13.4 Create `frontend/src/components/ScriptEditor/RegenerateControls.tsx`
    - `length` selector (`"short"` / `"long"`), optional `tone_override` text input, regenerate button
    - All controls accept `disabled` prop; button shows loading state when `isLoading` is true
    - _Requirements: 10.3, 10.4, 10.8_
  - [x] 13.5 Create `frontend/src/components/ScriptEditor/useScriptEditor.ts` custom hook
    - State shape: `script`, `personaId`, `scenarioId`, `length`, `toneOverride`, `isLoading`, `error`
    - `handleRegenerate`: POST to `/dialogue/regenerate`, set `isLoading` during request, update `script` on 201, set human-readable `error` on non-2xx using the status→message map from the design
    - `handleTextChange`: re-parse markers client-side via `extractMarkers` regex, update `script.emotional_markers` without any network call
    - _Requirements: 10.5, 10.6, 10.7, 10.8, 10.10_
  - [x] 13.6 Create `frontend/src/components/ScriptEditor/ScriptEditor.tsx` root component
    - Compose `ScriptDisplay`, `DurationDisplay`, `RegenerateControls`; display `script_id`; wire `useScriptEditor` hook; render editable textarea that calls `handleTextChange` on change
    - _Requirements: 10.1, 10.2, 10.5, 10.6, 10.7, 10.8, 10.9, 10.10_
  - [ ]* 13.7 Write frontend unit tests (Vitest + React Testing Library)
    - `ScriptDisplay` renders marker tokens as colored badges
    - `DurationDisplay` formats seconds correctly (e.g., 62.0 → "1m 02s")
    - `RegenerateControls` disables all inputs while `isLoading` is true
    - `useScriptEditor` re-parses markers on text change without network call
    - Error messages map correctly to HTTP status codes
    - File: `frontend/src/components/ScriptEditor/__tests__/`
    - _Requirements: 10.1, 10.2, 10.7, 10.8, 10.10_

- [ ] 14. Final checkpoint — all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Property tests use `@settings(max_examples=100)` and the tag format `# Feature: dialogue-generator, Property N: ...`
- The design uses Python/TypeScript — no language selection prompt needed
- Checkpoints at tasks 5, 12, and 14 ensure incremental validation
