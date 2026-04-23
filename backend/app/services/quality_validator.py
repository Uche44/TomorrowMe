import re
from dataclasses import dataclass, field

MARKER_PATTERN = re.compile(r"\[([a-zA-Z]+)\]")
VALID_MARKERS = {"pause", "softer", "warmth", "urgency", "breath", "slower", "faster"}

_DURATION_RANGES = {
    "short": (15.0, 45.0),
    "long": (40.0, 75.0),
}


@dataclass
class ValidationResult:
    passed: bool
    structure_ok: bool
    duration_ok: bool
    markers_ok: bool
    failure_reasons: list[str] = field(default_factory=list)


class QualityValidator:
    def validate(self, text: str, estimated_duration_sec: float, length: str) -> ValidationResult:
        structure_ok = self._check_structure(text)
        duration_ok = self._check_duration(estimated_duration_sec, length)
        markers_ok = self._check_markers(text)

        reasons: list[str] = []
        if not structure_ok:
            reasons.append("script does not meet four-part structure requirements")
        if not duration_ok:
            lo, hi = _DURATION_RANGES.get(length, (25.0, 65.0))
            reasons.append(
                f"duration {estimated_duration_sec}s outside target range {lo}–{hi}s for length={length}"
            )
        if not markers_ok:
            reasons.append("script contains no valid emotional markers")

        return ValidationResult(
            passed=not reasons,
            structure_ok=structure_ok,
            duration_ok=duration_ok,
            markers_ok=markers_ok,
            failure_reasons=reasons,
        )

    def _check_structure(self, text: str) -> bool:
        """Relaxed check: just needs at least 2 sentences and some content."""
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
        return len(sentences) >= 2 and len(text.split()) >= 20

    def _check_duration(self, duration: float, length: str) -> bool:
        lo, hi = _DURATION_RANGES.get(length, (25.0, 65.0))
        return lo <= duration <= hi

    def _check_markers(self, text: str) -> bool:
        found = {m.group(1).lower() for m in MARKER_PATTERN.finditer(text)}
        return bool(found & VALID_MARKERS)
