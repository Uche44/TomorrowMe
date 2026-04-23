# How Kiro Was Used to Build This Project

## Project Overview

This project is an AI-powered “Future Self” voice simulator that allows users to upload voice samples, generate a future persona, and hear an emotionally realistic conversation with a future version of themselves.

The stack includes:

* FastAPI backend
* ElevenLabs voice cloning and speech synthesis
* Persona generation using LLMs
* Spec-driven architecture
* Modular service-based backend

Kiro was used not just as a code assistant, but as a structured development environment that guided architecture, implementation, workflow automation, and AI-assisted engineering decisions.

---

# Vibe Coding

Vibe coding was used heavily during the exploration and prototyping phase.

Rather than immediately writing implementation details, development started by describing high-level intent to Kiro.

Examples of prompts used:

* “Build an API route for uploading voice samples and validating audio length.”
* “Create a service layer for ElevenLabs voice cloning.”
* “Generate a modular FastAPI structure for persona generation.”
* “Help me structure an emotional dialogue generation pipeline.”

The goal was to communicate outcomes rather than code.

Kiro performed best when prompts included:

* a clear outcome
* architectural expectations
* folder placement
* constraints around providers and libraries

### Most Impressive Code Generation

One of the strongest uses of Kiro was generating a complete voice-cloning integration flow.

Kiro helped scaffold:

* upload validation
* file buffering
* ElevenLabs SDK integration
* retry handling
* JSON error responses
* async persistence flow

Instead of generating isolated snippets, Kiro produced cohesive backend modules that aligned with the project structure.

This significantly accelerated backend development.

---

# Agent Hooks

Hooks were used conceptually to enforce consistency across generated code.

The project benefited from hook-like automation strategies such as:

## Architecture Validation Hook

Whenever backend modules were generated, Kiro was instructed to ensure:

* services remained inside `/services`
* routes remained lightweight
* business logic was not embedded directly inside endpoints

## Provider Enforcement Hook

Kiro was instructed to reject or avoid alternate voice providers.

This prevented accidental drift into:

* Coqui TTS
* pyttsx3
* local speech libraries

This kept ElevenLabs as the single source of truth for audio generation.

## API Pattern Hook

Generated endpoints followed a consistent format:

* async routes
* structured JSON responses
* centralized exception handling
* logging integration

Hooks improved development by reducing architectural drift.

Instead of repeatedly correcting generated code, the workflow stayed aligned with the project rules.

---

# Spec-Driven Development

Spec-driven development became the foundation of the project.

Instead of jumping directly into code generation, the project was broken into specifications.

Examples:

* `persona_generation.yaml`
* `voice_clone_flow.yaml`
* `dialogue_generation.yaml`
* `audio_pipeline.yaml`

Each spec described:

* purpose
* inputs
* outputs
* validation rules
* service ownership
* provider usage
* expected API behavior

## Why Spec-Driven Development Helped

Specs created a shared contract between architecture and implementation.

Benefits included:

* reduced ambiguity
* consistent service boundaries
* easier debugging
* modular implementation
* faster iteration

Kiro performed more accurately when implementing from specs because requirements were already formalized.

### Compared to Vibe Coding

Vibe coding worked best for:

* brainstorming
* prototyping
* experimentation
* discovering architecture

Spec-driven development worked best for:

* implementation
* maintaining consistency
* reducing hallucinated architecture
* scaling project complexity

The strongest workflow combined both:

1. Vibe coding for ideation
2. Specs for stabilization
3. Kiro implementation from specs

---

# Steering Docs

Steering docs became one of the most impactful features.

They were used to permanently guide Kiro’s behavior across the project.

Instead of repeating architectural instructions in every prompt, steering defined persistent project rules.

Examples of steering instructions:

* Backend must use FastAPI
* ElevenLabs is the only voice provider
* Business logic belongs inside `/services`
* Routes must remain lightweight
* Keep APIs async
* Use JSONResponse patterns
* Follow spec ownership per module

## Biggest Benefit

Steering dramatically reduced inconsistent generation.

Without steering, Kiro occasionally suggested:

* alternate TTS providers
* mixed architecture patterns
* duplicated business logic

With steering enabled, responses became more consistent and aligned with the project stack.

Steering effectively acted as long-term project memory.

---

# MCP (Model Context Protocol)

MCP expanded Kiro’s usefulness by making external tooling and structured context easier to integrate.

For this project, MCP-style workflows helped organize development around reusable context instead of isolated prompts.

Examples of MCP-enabled workflow improvements:

* persistent architectural context
* external API awareness
* reusable structured specifications
* consistent backend orchestration

MCP improved continuity between sessions.

Instead of re-explaining the system repeatedly, development retained shared understanding.

This reduced context loss and accelerated iteration.

---

# Kiro Powers

The project leveraged Kiro Powers to improve implementation quality and reduce documentation overhead.

Most important was the ElevenLabs Power.

## ElevenLabs Power

This gave Kiro contextual understanding of:

* voice cloning
* speech synthesis
* SDK usage
* provider methods
* request structures
* API integration patterns

This significantly reduced trial-and-error during integration.

Without the ElevenLabs Power, backend development would have required manually switching between docs and implementation.

### Benefits

* faster API integration
* fewer incorrect SDK assumptions
* more accurate endpoint generation
* stronger provider-specific implementation

---

# Development Outcome

Kiro was used as more than a code generator.

It functioned as:

* architecture assistant
* implementation partner
* spec executor
* workflow enforcer
* provider-aware integration layer

The combination of:

* vibe coding
* specs
* steering
* hooks
* powers

created a workflow that balanced creativity with structure.

This allowed rapid iteration while maintaining a clean and scalable architecture.

---

# Key Takeaway

The strongest advantage of Kiro was not simply generating code.

It was creating a development workflow where architecture, implementation, and AI assistance remained aligned throughout the build process.

Instead of repeatedly correcting generated output, Kiro was guided through specs, steering, and provider context to behave like a persistent engineering collaborator.
