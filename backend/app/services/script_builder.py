import logging
import re
import uuid

from app.clients.hf_client import HFClient
from app.exceptions import ScriptQualityError
from app.models.api import DialogueScript
from app.models.upstream import Persona, Scenario
from app.services.quality_validator import QualityValidator

logger = logging.getLogger(__name__)

VALID_MARKERS = {"pause", "softer", "warmth", "urgency", "breath", "slower", "faster"}
MARKER_PATTERN = re.compile(r"\[([a-zA-Z]+)\]")
LABEL_PATTERN = re.compile(r"\[(HOOK|REFLECTION|ADVICE|CLOSING)\]", re.IGNORECASE)

# Word targets per length variant — relaxed for open models that write shorter
_WORD_TARGETS = {
    "short": (50, 90, 30),   # (min_words, max_words, target_seconds)
    "long": (90, 150, 60),
}

_TONE_MARKER_GUIDANCE = {
    "warm": "Prefer [warmth] markers.",
    "urgent": "Prefer [urgency] markers.",
    "reflective": "Prefer [slower] and [pause] markers.",
}

MAX_RETRIES = 2


class ScriptBuilder:
    def __init__(self, validator: QualityValidator | None = None) -> None:
        self._validator = validator or QualityValidator()

    def _build_system_prompt(self, persona: Persona, scenario: Scenario, tone: str) -> str:
        events_list = "\n".join(f"- {e}" for e in persona.key_life_events)
        return f"""You are {persona.summary}.

Your tone is {tone}. You are speaking directly to your younger self — the person you used to be.

Your life journey:
{events_list}

The scenario type is "{persona.scenario_type}":
- "success" → speak with confidence and quiet fulfillment
- "regret"  → speak with reflective weight and gentle honesty
- "neutral" → speak with calm, observational clarity

The situation your younger self is facing: {scenario.context}
The emotional register to aim for: {scenario.emotional_target}"""

    def _build_user_prompt(self, persona: Persona, scenario: Scenario, length: str) -> str:
        min_w, max_w, target_sec = _WORD_TARGETS.get(length, _WORD_TARGETS["short"])
        tone_guidance = _TONE_MARKER_GUIDANCE.get(persona.tone.lower(), "")
        first_event = persona.key_life_events[0] if persona.key_life_events else ""

        return f"""Write a spoken monologue from your future self to your present self.

STRUCTURE — you MUST include exactly these four labeled sections in order:
[HOOK] An opening line that immediately grabs attention, anchored to: "{scenario.trigger}"
[REFLECTION] A reflection on the journey, referencing this milestone: "{first_event}"
[ADVICE] Advice or a warning relevant to the present moment
[CLOSING] A closing line that delivers this core message: "{persona.key_message}"

LENGTH: Target {min_w}–{max_w} words (~{target_sec} seconds at 130 wpm).

EMOTIONAL MARKERS: Embed these inline markers where appropriate: [pause], [softer], [warmth], [urgency], [breath], [slower], [faster].
{tone_guidance}
Use the scenario's emotional target ("{scenario.emotional_target}") to guide marker selection.
You MUST include at least one marker.

STYLE: First-person, natural spoken language. Use contractions. No formal prose. No stage directions outside square-bracket markers. No meta-commentary.

Output ONLY the script text. Do not include section labels like [HOOK] in the final output."""

    def _strip_labels(self, text: str) -> str:
        return LABEL_PATTERN.sub("", text).strip()

    def _strip_invalid_markers(self, text: str) -> str:
        def replace(m: re.Match) -> str:
            token = m.group(1).lower()
            return m.group(0) if token in VALID_MARKERS else ""
        return MARKER_PATTERN.sub(replace, text)

    def _extract_markers(self, text: str) -> list[str]:
        found = {m.group(1).lower() for m in MARKER_PATTERN.finditer(text)}
        return sorted(found & VALID_MARKERS)

    def _estimate_duration(self, text: str) -> float:
        clean = MARKER_PATTERN.sub("", text)
        word_count = len(clean.split())
        return round((word_count / 130.0) * 60, 1)

    async def build_script(
        self,
        persona: Persona,
        scenario: Scenario,
        length: str,
        tone_override: str | None,
    ) -> DialogueScript:
        tone = tone_override if tone_override else persona.tone
        system_prompt = self._build_system_prompt(persona, scenario, tone)
        user_prompt = self._build_user_prompt(persona, scenario, length)

        gemini = HFClient(max_tokens=_WORD_TARGETS.get(length, _WORD_TARGETS["short"])[1] * 6, temperature=0.85)
        last_result = None

        for attempt in range(MAX_RETRIES + 1):
            raw = await gemini.generate(system_prompt, user_prompt)
            text = self._strip_labels(raw)
            text = self._strip_invalid_markers(text)
            markers = self._extract_markers(text)
            duration = self._estimate_duration(text)

            result = self._validator.validate(text, duration, length)
            if result.passed:
                return DialogueScript(
                    script_id=str(uuid.uuid4()),
                    text=text,
                    estimated_duration_sec=duration,
                    emotional_markers=markers,
                )

            logger.warning(
                "Quality check failed (attempt %d/%d) provider=HuggingFace reasons=%s",
                attempt + 1,
                MAX_RETRIES + 1,
                result.failure_reasons,
            )
            last_result = result

        raise ScriptQualityError(
            f"Script failed quality checks after {MAX_RETRIES + 1} attempts: "
            f"{last_result.failure_reasons if last_result else 'unknown'}"
        )
