# Requirements Document

## Introduction

The Scenario Engine is a module within the Future Self Voice Simulator project. It accepts a `Persona` object (produced by the Future Persona Generator) and returns a structured `Scenario` object that provides the situational context for a future-self voice message — for example, "you're about to quit your job" or "you just finished your first marathon." The module supports two scenario modes: selecting from a library of preset scenario templates, and generating a custom scenario via a large language model. Scenarios must be plausible within a 5–10 year horizon, include specific life details, and create emotional contrast. Extreme fantasy outcomes and generic statements are explicitly prohibited. It exposes a REST API via FastAPI and a React frontend component (`ScenarioPicker`). The resulting `Scenario` is consumed downstream by the Dialogue Generator module.

---

## Glossary

- **ScenarioEngine_API**: The FastAPI application that handles scenario generation and preset retrieval requests.
- **ScenarioGenerator**: The internal service layer that constructs prompts and communicates with a configured large language model provider to produce custom Scenario objects.
- **LLM_Provider**: An external large language model service — either OpenAI (GPT-4o) or Anthropic (Claude) — used by the ScenarioGenerator to produce custom scenarios.
- **Persona**: The input data model produced by the Future Persona Generator, containing `persona_id`, `summary`, `tone`, `key_life_events`, `life_outcome`, `key_message`, and `scenario_type`. Consumed by the ScenarioEngine_API as the basis for scenario generation.
- **Scenario**: The output data model containing `scenario_id`, `title`, `context`, `emotional_target`, and `trigger`.
- **scenario_id**: A unique string identifier assigned to a generated or selected Scenario at creation time.
- **Scenario_Type**: The outcome framing inherited from the Persona — one of `"success"`, `"regret"`, or `"neutral"` — that determines the emotional register of the generated Scenario.
- **Preset_Scenario**: A built-in, pre-authored Scenario template stored within the module and available without LLM generation.
- **Preset_Library**: The collection of all Preset_Scenarios available via the `GET /scenario/presets` endpoint, organised by `scenario_type`.
- **Custom_Scenario**: A Scenario produced by the ScenarioGenerator in response to a specific Persona, using the LLM_Provider.
- **Emotional_Target**: The intended emotional register of the scenario — derived from `scenario_type`: `"success"` → `"celebratory"`, `"regret"` → `"challenging"`, `"neutral"` → `"reassuring"`.
- **Trigger**: A concise description of the specific life moment the scenario addresses (e.g., "the night before submitting your resignation"). Must reference a plausible real-world milestone.
- **Context**: A narrative prose description of the scenario's situational setup, providing background for the Dialogue Generator. Must include specific life details and avoid generic statements.
- **ScenarioPicker**: The React frontend component that renders a card grid of Preset_Scenarios and a custom scenario input form.
- **Dialogue_Generator**: The downstream module that consumes a Scenario to produce voice-ready dialogue lines.
- **Persona_Alignment**: The property of a Scenario whose `emotional_target`, `context`, and `trigger` are coherent with the `tone`, `scenario_type`, and `key_life_events` of the input Persona.
- **Plausibility_Constraint**: The requirement that all Scenario content must be achievable within a 5–10 year real-world horizon, with no extreme fantasy outcomes.

---

## Requirements

### Requirement 1: Custom Scenario Generation via LLM

**User Story:** As a user, I want to generate a scenario tailored to my future self persona, so that the voice message I receive is relevant to my specific life context.

#### Acceptance Criteria

1. WHEN a POST request is made to `/scenario/generate` with a valid Persona, THE ScenarioEngine_API SHALL forward the Persona to the ScenarioGenerator and return HTTP 201 with the generated Scenario as a JSON object.
2. THE ScenarioGenerator SHALL construct a prompt that incorporates the Persona's `summary`, `tone`, and `key_life_events` fields.
3. WHEN the LLM_Provider returns a response, THE ScenarioGenerator SHALL parse it into a Scenario containing `scenario_id`, `title`, `context`, `emotional_target`, and `trigger`.
4. THE ScenarioEngine_API SHALL assign a unique `scenario_id` to each generated Scenario at the time of creation.
5. WHEN two generation requests are processed concurrently, THE ScenarioEngine_API SHALL assign distinct `scenario_id` values to each resulting Scenario.
6. IF the LLM_Provider returns an error or times out, THEN THE ScenarioEngine_API SHALL return HTTP 502 with a descriptive error message and SHALL NOT persist a Scenario.

---

### Requirement 2: Persona Input Validation

**User Story:** As a developer, I want all Persona inputs to be validated before processing, so that the ScenarioGenerator receives only well-formed data.

#### Acceptance Criteria

1. WHEN a POST request to `/scenario/generate` is received, THE ScenarioEngine_API SHALL validate that the request body contains a `persona_id` field that is a non-empty string with no whitespace.
2. WHEN a POST request to `/scenario/generate` is received, THE ScenarioEngine_API SHALL validate that the `summary` field is a non-empty string of no more than 500 words.
3. WHEN a POST request to `/scenario/generate` is received, THE ScenarioEngine_API SHALL validate that the `tone` field is one of the values `"warm"`, `"reflective"`, or `"urgent"`.
4. WHEN a POST request to `/scenario/generate` is received, THE ScenarioEngine_API SHALL validate that `key_life_events` is a non-empty list containing between 1 and 7 strings, each no longer than 150 characters.
5. WHEN any Persona field fails validation, THE ScenarioEngine_API SHALL return HTTP 422 with a JSON body identifying each invalid field and a descriptive error message per field.
6. WHEN all Persona fields pass validation, THE ScenarioEngine_API SHALL proceed with scenario generation without modification to the input values.

---

### Requirement 3: Persona Alignment and Scenario Type Mapping

**User Story:** As a user, I want the generated scenario to feel coherent with my future self persona and scenario type, so that the voice message is believable and emotionally resonant.

#### Acceptance Criteria

1. THE ScenarioGenerator SHALL include the Persona's `scenario_type` and `tone` in the prompt to instruct the LLM_Provider to select an `emotional_target` consistent with both.
2. WHEN the Persona `scenario_type` is `"success"`, THE ScenarioGenerator SHALL instruct the LLM_Provider to produce a Scenario with `emotional_target` set to `"celebratory"`.
3. WHEN the Persona `scenario_type` is `"regret"`, THE ScenarioGenerator SHALL instruct the LLM_Provider to produce a Scenario with `emotional_target` set to `"challenging"`.
4. WHEN the Persona `scenario_type` is `"neutral"`, THE ScenarioGenerator SHALL instruct the LLM_Provider to produce a Scenario with `emotional_target` set to `"reassuring"`.
5. THE ScenarioGenerator SHALL include at least one item from the Persona's `key_life_events` list in the prompt so that the generated `trigger` references a plausible milestone from the Persona's narrative.
6. THE ScenarioGenerator SHALL include the Persona's `life_outcome` in the prompt so that the generated `context` is coherent with the future self's overall life situation.
7. THE ScenarioEngine_API SHALL reject any Scenario returned by the LLM_Provider whose `emotional_target` value does not match the expected value for the given `scenario_type`, and SHALL retry the LLM_Provider request up to 2 additional times before returning HTTP 502.
8. THE ScenarioGenerator SHALL instruct the LLM_Provider that the scenario must be plausible within a 5–10 year real-world horizon and must include specific life details. Generic statements (e.g., "you achieved your dreams") are not acceptable and SHALL trigger a retry.

---

### Requirement 4: Scenario Structure and Content Completeness

**User Story:** As a developer, I want every generated Scenario to contain all required fields with valid values, so that the Dialogue Generator can consume it without additional transformation.

#### Acceptance Criteria

1. THE ScenarioEngine_API SHALL return a Scenario JSON object containing exactly the fields `scenario_id`, `title`, `context`, `emotional_target`, and `trigger` in every successful generation response.
2. THE ScenarioGenerator SHALL instruct the LLM_Provider to produce a `title` that is a non-empty string no longer than 80 characters.
3. THE ScenarioGenerator SHALL instruct the LLM_Provider to produce a `context` that is a prose narrative of no fewer than 30 words and no more than 200 words.
4. THE ScenarioGenerator SHALL instruct the LLM_Provider to produce a `trigger` that is a non-empty string no longer than 150 characters describing a specific life moment.
5. WHEN the LLM_Provider returns a `context` outside the 30–200 word range, THE ScenarioEngine_API SHALL log a warning and retry the LLM_Provider request up to 2 additional times before returning HTTP 502.
6. WHEN the LLM_Provider returns a `title` exceeding 80 characters, THE ScenarioEngine_API SHALL log a warning and retry the LLM_Provider request up to 2 additional times before returning HTTP 502.
7. THE ScenarioEngine_API SHALL NOT expose raw LLM_Provider response text to the client; it SHALL return only the structured Scenario fields.

---

### Requirement 5: Preset Scenario Library

**User Story:** As a user, I want to browse and select from a set of built-in scenario templates, so that I can quickly choose a relevant scenario without waiting for LLM generation.

#### Acceptance Criteria

1. WHEN a GET request is made to `/scenario/presets`, THE ScenarioEngine_API SHALL return HTTP 200 with a JSON array of all available Preset_Scenarios.
2. THE ScenarioEngine_API SHALL include at least 10 Preset_Scenarios in the Preset_Library at all times — at least 3 per `scenario_type` (`"success"`, `"regret"`, `"neutral"`), with one additional preset of any type.
3. THE ScenarioEngine_API SHALL return each Preset_Scenario as a JSON object containing `scenario_id`, `title`, `context`, `emotional_target`, `trigger`, and `scenario_type`.
4. THE ScenarioEngine_API SHALL return at least one Preset_Scenario for each `emotional_target` value: `"reassuring"`, `"challenging"`, and `"celebratory"`.
5. WHEN the Preset_Library is retrieved, THE ScenarioEngine_API SHALL return the complete list in a single response without pagination.
6. THE ScenarioEngine_API SHALL assign a stable, deterministic `scenario_id` to each Preset_Scenario so that the same preset always returns the same `scenario_id` across requests.
7. ALL Preset_Scenarios SHALL contain specific life details in their `context` and `trigger` fields and SHALL NOT contain generic statements.

---

### Requirement 6: Preset Scenario Selection

**User Story:** As a user, I want to select a preset scenario and have it returned as a Scenario object, so that I can use it downstream without generating a custom one.

#### Acceptance Criteria

1. WHEN a POST request is made to `/scenario/generate` with a valid Persona and a `preset_id` field referencing an existing Preset_Scenario, THE ScenarioEngine_API SHALL return HTTP 200 with the corresponding Preset_Scenario as a JSON object without invoking the LLM_Provider.
2. WHEN a POST request to `/scenario/generate` includes a `preset_id` that does not match any Preset_Scenario in the Preset_Library, THE ScenarioEngine_API SHALL return HTTP 404 with a descriptive error message.
3. WHEN a Preset_Scenario is returned in response to a `preset_id` selection, THE ScenarioEngine_API SHALL return the Preset_Scenario's original `scenario_id`, `title`, `context`, `emotional_target`, and `trigger` without modification.

---

### Requirement 7: LLM Provider Abstraction

**User Story:** As a developer, I want the system to support multiple LLM providers, so that the generation backend can be swapped without changing the API contract.

#### Acceptance Criteria

1. THE ScenarioGenerator SHALL support GPT-4o (OpenAI) and Claude (Anthropic) as interchangeable LLM_Provider backends.
2. WHEN a provider is configured, THE ScenarioGenerator SHALL route all generation requests to that provider exclusively.
3. WHERE GPT-4o is configured as the LLM_Provider, THE ScenarioGenerator SHALL use the OpenAI Chat Completions API to generate Scenario content.
4. WHERE Claude is configured as the LLM_Provider, THE ScenarioGenerator SHALL use the Anthropic Messages API to generate Scenario content.
5. THE ScenarioEngine_API SHALL expose the same request and response schema regardless of which LLM_Provider is configured.
6. THE ScenarioGenerator SHALL apply a request timeout of 30 seconds to all LLM_Provider calls, and IF the timeout is exceeded, THEN THE ScenarioEngine_API SHALL return HTTP 504 with a descriptive error message.

---

### Requirement 8: ScenarioPicker Frontend Component

**User Story:** As a user, I want a browser-based interface to browse preset scenarios and optionally request a custom one, so that I can select the right context for my voice message without leaving the application.

#### Acceptance Criteria

1. THE ScenarioPicker SHALL render a card grid displaying all Preset_Scenarios retrieved from `GET /scenario/presets`, with each card showing the `title`, `emotional_target`, and `trigger` fields.
2. THE ScenarioPicker SHALL group preset cards visually by `emotional_target` category.
3. WHEN the user selects a preset card, THE ScenarioPicker SHALL send a POST request to `/scenario/generate` with the current Persona and the selected `preset_id`.
4. THE ScenarioPicker SHALL provide a custom scenario input area where the user can submit the current Persona without a `preset_id` to trigger LLM generation.
5. WHEN the ScenarioEngine_API returns a successful response, THE ScenarioPicker SHALL display the returned Scenario's `title`, `context`, `emotional_target`, and `trigger` to the user.
6. WHEN the ScenarioEngine_API returns an error response, THE ScenarioPicker SHALL display a human-readable error message corresponding to the HTTP status code.
7. WHILE a generation or selection request is in progress, THE ScenarioPicker SHALL disable all interactive controls and display a loading indicator.
8. THE ScenarioPicker SHALL display the `scenario_id` of the selected or generated Scenario so that the user can reference it for downstream use.
9. WHEN no Persona is available in the application state, THE ScenarioPicker SHALL display an informational message instructing the user to generate a Persona first, and SHALL disable the custom generation control.

---

### Requirement 9: Downstream Compatibility with Dialogue Generator

**User Story:** As a developer, I want the Scenario output to be directly consumable by the Dialogue Generator, so that the modules integrate without data transformation.

#### Acceptance Criteria

1. THE ScenarioEngine_API SHALL return `scenario_id` values as non-empty UUID strings with no whitespace.
2. WHEN a Scenario is returned by the ScenarioEngine_API, THE ScenarioEngine_API SHALL include `emotional_target` as a top-level string field so that the Dialogue_Generator can apply it directly to voice synthesis instructions.
3. THE ScenarioEngine_API SHALL include `context` as a top-level string field in the Scenario JSON so that the Dialogue_Generator can use it as narrative background without parsing nested structures.
4. THE ScenarioEngine_API SHALL include `trigger` as a top-level string field in the Scenario JSON so that the Dialogue_Generator can use it to anchor the opening line of the voice message.
5. THE ScenarioEngine_API SHALL NOT transform, truncate, or re-encode any Scenario field value between generation and the response returned to the client.

---

### Requirement 10: API Error Handling and Observability

**User Story:** As a developer, I want all API errors to be logged and return structured responses, so that issues can be diagnosed quickly in production.

#### Acceptance Criteria

1. WHEN any request to the ScenarioEngine_API results in an HTTP 4xx or 5xx response, THE ScenarioEngine_API SHALL log the error with a timestamp, request path, HTTP method, and error detail.
2. WHEN an unhandled exception occurs during request processing, THE ScenarioEngine_API SHALL return HTTP 500 with a JSON body containing a `detail` field and SHALL NOT expose internal stack traces or raw LLM_Provider responses to the client.
3. THE ScenarioEngine_API SHALL return all error responses as JSON objects with at minimum a `detail` field describing the error.
4. WHEN the ScenarioGenerator retries a failed LLM_Provider request, THE ScenarioEngine_API SHALL log each retry attempt with the attempt number, LLM_Provider name, and failure reason.

---

### Requirement 11: Output Quality Evaluation

**User Story:** As a developer, I want generated scenarios to be evaluated for plausibility and specificity before being returned, so that only high-quality outputs reach the Dialogue Generator.

#### Acceptance Criteria

1. WHEN a Scenario is generated, THE ScenarioEngine_API SHALL verify that the `emotional_target` matches the deterministic mapping for the Persona's `scenario_type` as defined in Requirement 3.
2. WHEN a Scenario is generated, THE ScenarioEngine_API SHALL verify that the `context` word count is within the 30–200 word range.
3. WHEN a Scenario is generated, THE ScenarioEngine_API SHALL verify that the `trigger` is specific (i.e., references a concrete life moment) and not a generic statement.
4. WHEN any quality check fails, THE ScenarioEngine_API SHALL retry the LLM_Provider request up to 2 additional times before returning HTTP 502.
5. THE ScenarioEngine_API SHALL log a `plausibility_check` result (pass/fail) alongside each generated Scenario record.
