# Requirements Document

## Introduction

The Dialogue Generator is a module within the Future Self Voice Simulator project. It accepts a `persona_id` and `scenario_id`, retrieves the corresponding Persona and Scenario records from their respective upstream modules, and uses a large language model to produce a voice-ready `DialogueScript` — a spoken monologue from the user's future self, grounded in the persona's narrative and the scenario's situational context. Every script must follow a four-part structure: opening hook, reflection, advice or warning, and closing line. The script must be written in first-person, use natural spoken language, and target a 30–60 second delivery. The script includes inline emotional markers (e.g., `[pause]`, `[softer]`, `[warmth]`) that guide expressive speech synthesis. The module exposes a REST API via FastAPI and a React frontend component (`ScriptEditor`). The resulting `script_id` and `voice_id` are consumed downstream by the Audio Production Engine.

---

## Glossary

- **DialogueGenerator_API**: The FastAPI application that handles script generation, regeneration, and retrieval requests.
- **ScriptBuilder**: The internal service layer that constructs LLM prompts from Persona and Scenario data and parses the LLM response into a DialogueScript.
- **LLM_Provider**: An external large language model service — either OpenAI (GPT-4o) or Anthropic (Claude) — used by the ScriptBuilder to generate dialogue.
- **Persona**: The data model produced by the Future Persona Generator, containing `persona_id`, `summary`, `tone`, `key_life_events`, `life_outcome`, `key_message`, and `scenario_type`. Retrieved by the DialogueGenerator_API as the basis for script generation.
- **Scenario**: The data model produced by the Scenario Engine, containing `scenario_id`, `title`, `context`, `emotional_target`, and `trigger`. Retrieved by the DialogueGenerator_API as the situational context for the script.
- **DialogueRequest**: The input data model for script generation, containing `persona_id`, `scenario_id`, `length`, and an optional `tone_override`.
- **DialogueScript**: The output data model containing `script_id`, `text`, `estimated_duration_sec`, and `emotional_markers`.
- **script_id**: A unique string identifier assigned to a generated DialogueScript at creation time.
- **Script_Structure**: The mandatory four-part structure every generated script must follow: (1) opening hook, (2) reflection, (3) advice or warning, (4) closing line.
- **Emotional_Marker**: An inline annotation embedded in the script `text` that instructs the voice synthesizer to apply a specific expressive quality at that point (e.g., `[pause]`, `[softer]`, `[warmth]`, `[urgency]`).
- **Length_Variant**: The requested duration class for the generated script — one of `"short"` (~30 seconds) or `"long"` (~60 seconds), aligned with the system's 30–60 second output target.
- **Tone_Override**: An optional caller-supplied string that replaces the Persona's default tone when constructing the LLM prompt for regeneration.
- **System_Prompt**: The LLM prompt component that encodes the Persona summary, scenario type, and Scenario context, establishing the voice and situation for the generated script.
- **User_Prompt**: The LLM prompt component that requests the spoken message with the four-part structure and inline Emotional_Markers.
- **ScriptEditor**: The React frontend component that renders the DialogueScript text with Emotional_Markers highlighted, supports inline editing, and exposes tone and length controls for regeneration.
- **Audio_Production_Engine**: The downstream module that consumes `voice_id` and `script_id` to synthesize the final audio output.
- **Script_Store**: The persistence layer that stores and retrieves DialogueScript records by `script_id`.
- **PersonaGenerator_API**: The upstream module that exposes Persona records by `persona_id`.
- **ScenarioEngine_API**: The upstream module that exposes Scenario records by `scenario_id`.

---

## Requirements

### Requirement 1: Dialogue Script Generation

**User Story:** As a user, I want to generate a spoken script from my future self persona and a chosen scenario, so that I receive a voice-ready monologue grounded in my personal narrative.

#### Acceptance Criteria

1. WHEN a POST request is made to `/dialogue/generate` with a valid DialogueRequest, THE DialogueGenerator_API SHALL retrieve the Persona from the PersonaGenerator_API using `persona_id` and the Scenario from the ScenarioEngine_API using `scenario_id`.
2. WHEN both the Persona and Scenario are successfully retrieved, THE ScriptBuilder SHALL construct a System_Prompt that encodes the Persona `summary`, `tone`, and `key_life_events`, and the Scenario `context`, `emotional_target`, and `trigger`.
3. WHEN the System_Prompt is constructed, THE ScriptBuilder SHALL construct a User_Prompt that requests a spoken monologue of the appropriate Length_Variant with inline Emotional_Markers.
4. WHEN the LLM_Provider returns a response, THE ScriptBuilder SHALL parse it into a DialogueScript containing `script_id`, `text`, `estimated_duration_sec`, and `emotional_markers`.
5. WHEN the DialogueScript is successfully generated, THE DialogueGenerator_API SHALL return HTTP 201 with the DialogueScript as a JSON object.
6. THE DialogueGenerator_API SHALL assign a unique `script_id` to each generated DialogueScript at the time of creation.
7. WHEN two generation requests are processed concurrently, THE DialogueGenerator_API SHALL assign distinct `script_id` values to each resulting DialogueScript.
8. IF the LLM_Provider returns an error or times out, THEN THE DialogueGenerator_API SHALL return HTTP 502 with a descriptive error message and SHALL NOT persist a DialogueScript.

---

### Requirement 2: DialogueRequest Input Validation

**User Story:** As a developer, I want all DialogueRequest inputs to be validated before processing, so that the ScriptBuilder receives only well-formed data.

#### Acceptance Criteria

1. WHEN a POST request to `/dialogue/generate` or `/dialogue/regenerate` is received, THE DialogueGenerator_API SHALL validate that `persona_id` is a non-empty string with no whitespace.
2. WHEN a POST request to `/dialogue/generate` or `/dialogue/regenerate` is received, THE DialogueGenerator_API SHALL validate that `scenario_id` is a non-empty string with no whitespace.
3. WHEN a POST request to `/dialogue/generate` or `/dialogue/regenerate` is received, THE DialogueGenerator_API SHALL validate that `length` is one of the values `"short"`, `"medium"`, or `"long"`.
4. WHEN a POST request to `/dialogue/generate` or `/dialogue/regenerate` is received and `tone_override` is present, THE DialogueGenerator_API SHALL validate that `tone_override` is a non-empty string no longer than 100 characters.
5. WHEN any DialogueRequest field fails validation, THE DialogueGenerator_API SHALL return HTTP 422 with a JSON body identifying each invalid field and a descriptive error message per field.
6. WHEN all DialogueRequest fields pass validation, THE DialogueGenerator_API SHALL proceed with script generation without modification to the input values.

---

### Requirement 3: Upstream Data Resolution

**User Story:** As a developer, I want the module to resolve Persona and Scenario records from upstream APIs before generating a script, so that the generated dialogue is always grounded in current, authoritative data.

#### Acceptance Criteria

1. WHEN a valid `persona_id` is provided, THE DialogueGenerator_API SHALL retrieve the Persona by sending a GET request to the PersonaGenerator_API at `/persona/{persona_id}`.
2. WHEN a valid `scenario_id` is provided, THE DialogueGenerator_API SHALL retrieve the Scenario by sending a GET request to the ScenarioEngine_API at `/scenario/{scenario_id}`.
3. WHEN the PersonaGenerator_API returns HTTP 404 for the given `persona_id`, THE DialogueGenerator_API SHALL return HTTP 404 with a descriptive error message indicating the Persona was not found.
4. WHEN the ScenarioEngine_API returns HTTP 404 for the given `scenario_id`, THE DialogueGenerator_API SHALL return HTTP 404 with a descriptive error message indicating the Scenario was not found.
5. IF the PersonaGenerator_API or ScenarioEngine_API returns an HTTP 5xx error, THEN THE DialogueGenerator_API SHALL return HTTP 502 with a descriptive error message and SHALL NOT proceed with script generation.
6. THE DialogueGenerator_API SHALL apply a timeout of 10 seconds to each upstream API call, and IF the timeout is exceeded, THEN THE DialogueGenerator_API SHALL return HTTP 504 with a descriptive error message.

---

### Requirement 4: Length Variant Targeting

**User Story:** As a user, I want to choose the length of my script, so that the generated monologue fits the system's 30–60 second output target.

#### Acceptance Criteria

1. WHEN `length` is `"short"`, THE ScriptBuilder SHALL instruct the LLM_Provider to produce a script with an `estimated_duration_sec` between 25 and 35 seconds.
2. WHEN `length` is `"long"`, THE ScriptBuilder SHALL instruct the LLM_Provider to produce a script with an `estimated_duration_sec` between 50 and 65 seconds.
3. THE DialogueGenerator_API SHALL validate that `length` is one of `"short"` or `"long"` and SHALL return HTTP 422 if any other value is provided.
4. THE ScriptBuilder SHALL calculate `estimated_duration_sec` based on the word count of the generated `text` using an average spoken rate of 130 words per minute.
5. WHEN the generated script's `estimated_duration_sec` falls outside the target range for the requested `length`, THE DialogueGenerator_API SHALL log a warning and retry the LLM_Provider request up to 2 additional times before returning HTTP 502.

---

### Requirement 5: Emotional Marker Generation and Validation

**User Story:** As a user, I want the script to contain inline emotional markers, so that the voice synthesizer can render the monologue with appropriate expressiveness.

#### Acceptance Criteria

1. THE ScriptBuilder SHALL instruct the LLM_Provider to embed Emotional_Markers inline within the script `text` using square-bracket notation (e.g., `[pause]`, `[softer]`, `[warmth]`, `[urgency]`).
2. WHEN the LLM_Provider returns a script, THE ScriptBuilder SHALL extract all unique Emotional_Marker tokens from the `text` and populate the `emotional_markers` list field with them.
3. THE DialogueGenerator_API SHALL accept only the following Emotional_Marker values: `"pause"`, `"softer"`, `"warmth"`, `"urgency"`, `"breath"`, `"slower"`, `"faster"`. Any other marker token found in the LLM response SHALL be stripped from the `text` and excluded from `emotional_markers`.
4. WHEN the LLM_Provider returns a script containing no Emotional_Markers, THE DialogueGenerator_API SHALL log a warning and retry the LLM_Provider request up to 2 additional times before returning HTTP 502.
5. THE ScriptBuilder SHALL include the Scenario `emotional_target` in the User_Prompt to guide the selection of Emotional_Markers consistent with the scenario's intended register.
6. WHEN the Persona `tone` is `"warm"`, THE ScriptBuilder SHALL include `[warmth]` as a preferred marker in the User_Prompt instructions.
7. WHEN the Persona `tone` is `"urgent"`, THE ScriptBuilder SHALL include `[urgency]` as a preferred marker in the User_Prompt instructions.
8. WHEN the Persona `tone` is `"reflective"`, THE ScriptBuilder SHALL include `[slower]` and `[pause]` as preferred markers in the User_Prompt instructions.

---

### Requirement 6: Script Regeneration with Tone and Length Adjustment

**User Story:** As a user, I want to regenerate a script with a different tone or length, so that I can refine the output until it feels right.

#### Acceptance Criteria

1. WHEN a POST request is made to `/dialogue/regenerate` with a valid DialogueRequest, THE DialogueGenerator_API SHALL generate a new DialogueScript using the same process as `/dialogue/generate`.
2. WHEN `tone_override` is present in the DialogueRequest, THE ScriptBuilder SHALL substitute the Persona's `tone` with the `tone_override` value when constructing the System_Prompt.
3. WHEN `tone_override` is absent in the DialogueRequest, THE ScriptBuilder SHALL use the Persona's `tone` field as the tone for prompt construction.
4. THE DialogueGenerator_API SHALL assign a new unique `script_id` to each DialogueScript produced by `/dialogue/regenerate`.
5. WHEN `/dialogue/regenerate` produces a new DialogueScript, THE DialogueGenerator_API SHALL persist the new DialogueScript independently of any previously generated scripts for the same `persona_id` and `scenario_id`.

---

### Requirement 7: Emotional Authenticity and Script Structure

**User Story:** As a user, I want the generated script to feel like it is genuinely spoken by my future self and follow a clear narrative arc, so that the voice message is emotionally resonant and believable.

#### Acceptance Criteria

1. THE ScriptBuilder SHALL construct the System_Prompt in first-person voice, instructing the LLM_Provider to speak as the user's future self addressing their present self.
2. THE ScriptBuilder SHALL instruct the LLM_Provider to structure the script in exactly four parts: (1) an opening hook that immediately engages the listener, (2) a reflection on the journey, (3) advice or a warning relevant to the present self, and (4) a closing line.
3. THE ScriptBuilder SHALL include the Persona `key_message` in the User_Prompt so that the closing line of the script reflects the future self's most important message.
4. THE ScriptBuilder SHALL include the Persona `summary` in the System_Prompt so that the generated script reflects the future self's life narrative.
5. THE ScriptBuilder SHALL include the Scenario `trigger` in the User_Prompt so that the opening hook anchors to the specific life moment described by the Scenario.
6. THE ScriptBuilder SHALL include at least one item from the Persona `key_life_events` list in the System_Prompt so that the reflection section references a plausible milestone from the Persona's narrative.
7. THE ScriptBuilder SHALL instruct the LLM_Provider to use natural spoken language — contractions, pauses implied by punctuation, and conversational phrasing — and SHALL NOT produce formal or academic prose.
8. THE ScriptBuilder SHALL NOT include implementation instructions, meta-commentary, or stage directions in the generated `text` outside of square-bracket Emotional_Marker notation.
9. THE ScriptBuilder SHALL include the Persona `scenario_type` in the System_Prompt so that the tone of the script matches the expected emotional register: `"success"` → confident and fulfilled, `"regret"` → reflective and slightly heavy, `"neutral"` → calm and observational.

---

### Requirement 8: DialogueScript Persistence and Retrieval

**User Story:** As a developer, I want generated scripts to be stored and retrievable by ID, so that the Audio Production Engine can access them on demand.

#### Acceptance Criteria

1. WHEN a DialogueScript is successfully generated, THE DialogueGenerator_API SHALL persist the DialogueScript in the Script_Store before returning the HTTP 201 response.
2. THE DialogueGenerator_API SHALL store `script_id`, `text`, `estimated_duration_sec`, `emotional_markers`, `persona_id`, `scenario_id`, `length`, and a `created_at` timestamp in UTC ISO 8601 format for each persisted DialogueScript.
3. WHEN a GET request is made to `/dialogue/{script_id}` with a valid `script_id`, THE DialogueGenerator_API SHALL return HTTP 200 with the corresponding DialogueScript as a JSON object.
4. WHEN a GET request is made to `/dialogue/{script_id}` with a `script_id` that does not exist, THE DialogueGenerator_API SHALL return HTTP 404 with a descriptive error message.
5. WHEN a DialogueScript is retrieved, THE DialogueGenerator_API SHALL return the identical `text`, `estimated_duration_sec`, and `emotional_markers` values that were stored at creation time, without modification.
6. IF the Script_Store is unavailable at the time of write, THEN THE DialogueGenerator_API SHALL return HTTP 503 with a descriptive error message and SHALL NOT return a `script_id` to the client.

---

### Requirement 9: LLM Provider Abstraction

**User Story:** As a developer, I want the system to support multiple LLM providers, so that the generation backend can be swapped without changing the API contract.

#### Acceptance Criteria

1. THE ScriptBuilder SHALL support GPT-4o (OpenAI) and Claude (Anthropic) as interchangeable LLM_Provider backends.
2. WHEN a provider is configured, THE ScriptBuilder SHALL route all generation requests to that provider exclusively.
3. WHERE GPT-4o is configured as the LLM_Provider, THE ScriptBuilder SHALL use the OpenAI Chat Completions API to generate DialogueScript content.
4. WHERE Claude is configured as the LLM_Provider, THE ScriptBuilder SHALL use the Anthropic Messages API to generate DialogueScript content.
5. THE DialogueGenerator_API SHALL expose the same request and response schema regardless of which LLM_Provider is configured.
6. THE ScriptBuilder SHALL apply a request timeout of 30 seconds to all LLM_Provider calls, and IF the timeout is exceeded, THEN THE DialogueGenerator_API SHALL return HTTP 504 with a descriptive error message.

---

### Requirement 10: ScriptEditor Frontend Component

**User Story:** As a user, I want a browser-based editor to view and refine my generated script, so that I can adjust the text and tone before sending it to voice synthesis.

#### Acceptance Criteria

1. THE ScriptEditor SHALL render the DialogueScript `text` in an editable text area, with each Emotional_Marker token visually highlighted using a distinct color or badge style.
2. THE ScriptEditor SHALL display the `estimated_duration_sec` value alongside the script text, formatted as minutes and seconds (e.g., "1m 02s").
3. THE ScriptEditor SHALL provide a `length` selection control offering the options `"short"`, `"medium"`, and `"long"`.
4. THE ScriptEditor SHALL provide an optional `tone_override` text input that accepts a free-text tone description.
5. WHEN the user submits a regeneration request, THE ScriptEditor SHALL send a POST request to `/dialogue/regenerate` with the current `persona_id`, `scenario_id`, `length`, and `tone_override` values.
6. WHEN the DialogueGenerator_API returns HTTP 201, THE ScriptEditor SHALL replace the displayed script with the newly generated DialogueScript.
7. WHEN the DialogueGenerator_API returns an error response, THE ScriptEditor SHALL display a human-readable error message corresponding to the HTTP status code.
8. WHILE a generation or regeneration request is in progress, THE ScriptEditor SHALL disable all interactive controls and display a loading indicator.
9. THE ScriptEditor SHALL display the `script_id` of the current DialogueScript so that the user can reference it for downstream use with the Audio Production Engine.
10. WHEN the user manually edits the script `text`, THE ScriptEditor SHALL re-parse the text for Emotional_Marker tokens and update the highlighted annotations in real time without sending a request to the server.

---

### Requirement 11: Downstream Compatibility with Audio Production Engine

**User Story:** As a developer, I want the DialogueScript output to be directly usable by the Audio Production Engine, so that the two modules integrate without data transformation.

#### Acceptance Criteria

1. THE DialogueGenerator_API SHALL return `script_id` values as non-empty UUID strings with no whitespace.
2. THE DialogueGenerator_API SHALL return `text` as a top-level string field containing the full spoken script with inline Emotional_Markers, so that the Audio_Production_Engine can pass it directly to the voice synthesizer.
3. THE DialogueGenerator_API SHALL return `emotional_markers` as a top-level list of strings so that the Audio_Production_Engine can inspect the marker set without parsing the `text` field.
4. THE DialogueGenerator_API SHALL return `estimated_duration_sec` as a top-level float field so that the Audio_Production_Engine can use it for scheduling and playback planning.
5. THE DialogueGenerator_API SHALL NOT transform, truncate, or re-encode any DialogueScript field value between storage and the response returned to the client.
6. WHEN a `script_id` is stored in the Script_Store, THE DialogueGenerator_API SHALL return the identical `script_id` string in all subsequent GET responses for that record.

---

### Requirement 12: API Error Handling and Observability

**User Story:** As a developer, I want all API errors to be logged and return structured responses, so that issues can be diagnosed quickly in production.

#### Acceptance Criteria

1. WHEN any request to the DialogueGenerator_API results in an HTTP 4xx or 5xx response, THE DialogueGenerator_API SHALL log the error with a timestamp, request path, HTTP method, and error detail.
2. WHEN an unhandled exception occurs during request processing, THE DialogueGenerator_API SHALL return HTTP 500 with a JSON body containing a `detail` field and SHALL NOT expose internal stack traces or raw LLM_Provider responses to the client.
3. THE DialogueGenerator_API SHALL return all error responses as JSON objects with at minimum a `detail` field describing the error.
4. WHEN the ScriptBuilder retries a failed LLM_Provider request, THE DialogueGenerator_API SHALL log each retry attempt with the attempt number, LLM_Provider name, and failure reason.
5. WHEN an upstream API call to the PersonaGenerator_API or ScenarioEngine_API fails, THE DialogueGenerator_API SHALL log the failure with the upstream service name, HTTP status code, and request URL.

---

### Requirement 13: Output Quality Evaluation

**User Story:** As a developer, I want generated scripts to be evaluated for structure, length, and emotional authenticity before being returned, so that only high-quality outputs reach the Audio Production Engine.

#### Acceptance Criteria

1. WHEN a DialogueScript is generated, THE DialogueGenerator_API SHALL verify that the `text` contains all four required structural sections: opening hook, reflection, advice or warning, and closing line.
2. WHEN a DialogueScript is generated, THE DialogueGenerator_API SHALL verify that the `estimated_duration_sec` falls within the target range for the requested `length`.
3. WHEN a DialogueScript is generated, THE DialogueGenerator_API SHALL verify that the `text` contains at least one Emotional_Marker.
4. WHEN any quality check fails, THE DialogueGenerator_API SHALL retry the LLM_Provider request up to 2 additional times before returning HTTP 502.
5. THE DialogueGenerator_API SHALL log a `script_quality` assessment (pass/fail per check) alongside each generated DialogueScript record in the Script_Store.
