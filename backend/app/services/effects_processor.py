import logging
import os

from pydub import AudioSegment

from app.config import settings

logger = logging.getLogger(__name__)

# Effects chain order: reverb → warmth EQ → ambient noise
CHAIN_EFFECTS = ["reverb", "warmth", "ambient"]

# Sound effect dBFS mixing levels
EFFECT_LEVELS_DBFS: dict[str, float] = {
    "wind":      -35.0,
    "city":      -35.0,
    "room_tone": -40.0,
    "ambient":   -30.0,
}


class EffectsChainError(Exception):
    pass


def apply_effects(audio: AudioSegment, effects: list[str]) -> AudioSegment:
    """
    Apply effects in strict order: reverb → warmth EQ → ambient → sound effects.
    Raises EffectsChainError with the failing effect name on any failure.
    """
    if not effects:
        return audio

    result = audio

    # Apply chain effects in defined order
    for effect in CHAIN_EFFECTS:
        if effect not in effects:
            continue
        try:
            if effect == "reverb":
                result = _apply_reverb(result)
            elif effect == "warmth":
                result = _apply_warmth_eq(result)
            elif effect == "ambient":
                result = _mix_layer(result, _sfx_path("ambient.mp3"), EFFECT_LEVELS_DBFS["ambient"])
        except Exception as exc:
            logger.error("EffectsChain failed: effect=%s error=%s", effect, exc)
            raise EffectsChainError(f"Effect '{effect}' failed: {exc}") from exc

    # Apply optional sound effects
    for effect in ["wind", "city", "room_tone"]:
        if effect not in effects:
            continue
        try:
            sfx_file = _sfx_path(f"{effect}.mp3")
            result = _mix_layer(result, sfx_file, EFFECT_LEVELS_DBFS[effect])
        except Exception as exc:
            logger.error("EffectsChain failed: effect=%s error=%s", effect, exc)
            raise EffectsChainError(f"Effect '{effect}' failed: {exc}") from exc

    return result


def _apply_reverb(audio: AudioSegment) -> AudioSegment:
    """Simulate short room reverb by overlaying a delayed, attenuated copy."""
    delay_ms = 80
    attenuation_db = -12
    delayed = AudioSegment.silent(duration=delay_ms) + audio.apply_gain(attenuation_db)
    # Overlay delayed copy onto original
    if len(delayed) > len(audio):
        audio = audio + AudioSegment.silent(duration=len(delayed) - len(audio))
    return audio.overlay(delayed)


def _apply_warmth_eq(audio: AudioSegment) -> AudioSegment:
    """Low-shelf EQ boost at ~200 Hz (+3 dB) — approximated via gentle gain."""
    return audio.apply_gain(3.0)


def _mix_layer(audio: AudioSegment, sfx_path: str, target_dbfs: float) -> AudioSegment:
    """Mix an audio file layer beneath the main audio at the specified dBFS level."""
    if not os.path.exists(sfx_path):
        logger.warning("SFX file not found, skipping: %s", sfx_path)
        return audio

    sfx = AudioSegment.from_file(sfx_path)

    # Loop sfx to match audio length
    while len(sfx) < len(audio):
        sfx = sfx + sfx
    sfx = sfx[: len(audio)]

    # Normalize sfx to target dBFS
    if sfx.dBFS > -float("inf"):
        sfx = sfx.apply_gain(target_dbfs - sfx.dBFS)

    return audio.overlay(sfx)


def _sfx_path(filename: str) -> str:
    return os.path.join(settings.assets_dir, "sfx", filename)
