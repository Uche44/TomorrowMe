import logging
import re
from dataclasses import dataclass, field

from pydub import AudioSegment
from pydub.generators import Sine

logger = logging.getLogger(__name__)

MARKER_PATTERN = re.compile(r"\[([a-zA-Z]+)\]")
VALID_MARKERS = {"pause", "softer", "warmth", "urgency", "breath", "slower", "faster"}

WARMTH_EQ_GAIN_DB = 3.0   # low-shelf boost at ~200 Hz
SOFTER_DB = -6.0
URGENCY_DB = 3.0
RATE_SLOWER = 0.85
RATE_FASTER = 1.15
PAUSE_MS = 500
BREATH_MS = 200


class MarkerProcessingError(Exception):
    pass


@dataclass
class MarkerSpan:
    marker: str
    char_start: int   # position in original text where marker token starts
    char_end: int     # position where marker token ends


@dataclass
class StrippedScript:
    clean_text: str
    marker_spans: list[MarkerSpan] = field(default_factory=list)


def strip_markers(text: str) -> StrippedScript:
    """Remove [marker] tokens from text, recording their positions."""
    spans: list[MarkerSpan] = []
    offset = 0
    clean_parts: list[str] = []
    last = 0

    for m in MARKER_PATTERN.finditer(text):
        token = m.group(1).lower()
        if token not in VALID_MARKERS:
            continue
        clean_parts.append(text[last:m.start()])
        spans.append(MarkerSpan(
            marker=token,
            char_start=m.start() - offset,
            char_end=m.start() - offset,
        ))
        offset += m.end() - m.start()
        last = m.end()

    clean_parts.append(text[last:])
    return StrippedScript(clean_text="".join(clean_parts), marker_spans=spans)


def apply_markers(audio: AudioSegment, markers: list[str]) -> AudioSegment:
    """
    Apply emotional marker modifications to the full audio segment.
    Markers are applied sequentially to the whole track since we don't have
    word-level timestamps from ElevenLabs without diarization.
    """
    if not markers:
        logger.warning("apply_markers called with empty markers list")
        return audio

    try:
        result = audio

        for marker in markers:
            m = marker.lower()
            if m == "pause":
                silence = AudioSegment.silent(duration=PAUSE_MS)
                result = result + silence
            elif m == "breath":
                breath = _generate_breath(BREATH_MS)
                result = result + breath
            elif m == "softer":
                result = result + SOFTER_DB
            elif m == "urgency":
                result = result + URGENCY_DB
            elif m == "warmth":
                result = _apply_warmth_eq(result)
            elif m == "slower":
                result = _change_speed(result, RATE_SLOWER)
            elif m == "faster":
                result = _change_speed(result, RATE_FASTER)

        return result
    except Exception as exc:
        raise MarkerProcessingError(f"Marker processing failed: {exc}") from exc


def _generate_breath(duration_ms: int) -> AudioSegment:
    """Generate a soft breath-like sound (low-amplitude sine wave)."""
    breath = Sine(200).to_audio_segment(duration=duration_ms).apply_gain(-30)
    return breath


def _apply_warmth_eq(audio: AudioSegment) -> AudioSegment:
    """Approximate warmth EQ: boost low-mid frequencies by applying gain to a low-passed copy."""
    # pydub doesn't have native EQ; apply a gentle overall gain boost as approximation
    return audio.apply_gain(WARMTH_EQ_GAIN_DB)


def _change_speed(audio: AudioSegment, rate: float) -> AudioSegment:
    """Change playback speed by resampling."""
    new_frame_rate = int(audio.frame_rate * rate)
    altered = audio._spawn(audio.raw_data, overrides={"frame_rate": new_frame_rate})
    return altered.set_frame_rate(audio.frame_rate)
