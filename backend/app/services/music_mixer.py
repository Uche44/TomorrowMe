import logging
import os

from pydub import AudioSegment

from app.config import settings

logger = logging.getLogger(__name__)

# Background music selection by emotion type (Req 6a)
EMOTION_MUSIC_MAP: dict[str, str] = {
    "success": "success.mp3",
    "regret":  "regret.mp3",
    "neutral": "neutral.mp3",
}

# Music is mixed at -20 dBFS relative to speech to ensure ≥10 dB SNR
MUSIC_TARGET_DBFS = -30.0
MIN_SNR_DB = 10.0


def mix_music(audio: AudioSegment, emotion_type: str) -> AudioSegment:
    """
    Layer background music beneath the synthesized speech.
    Music is selected by emotion_type and mixed at a level that keeps
    speech clearly intelligible (speech-to-background ratio ≥ 10 dB).
    If the music file is not found, logs a warning and returns audio unchanged.
    """
    music_file = _music_path(emotion_type)

    if not os.path.exists(music_file):
        logger.warning(
            "Background music file not found for emotion_type=%s path=%s — proceeding without music",
            emotion_type, music_file,
        )
        return audio

    try:
        music = AudioSegment.from_file(music_file)

        # Loop music to match speech length
        while len(music) < len(audio):
            music = music + music
        music = music[: len(audio)]

        # Normalize music to target dBFS
        if music.dBFS > -float("inf"):
            music = music.apply_gain(MUSIC_TARGET_DBFS - music.dBFS)

        # Verify SNR: speech peak should be at least MIN_SNR_DB above music
        speech_peak = audio.dBFS
        music_peak = music.dBFS
        snr = speech_peak - music_peak

        if snr < MIN_SNR_DB:
            # Reduce music further to achieve required SNR
            reduction = MIN_SNR_DB - snr + 1.0  # +1 dB margin
            music = music.apply_gain(-reduction)
            logger.info(
                "Music level reduced by %.1f dB to achieve SNR ≥ %d dB (was %.1f dB)",
                reduction, MIN_SNR_DB, snr,
            )

        return audio.overlay(music)

    except Exception as exc:
        logger.warning(
            "Background music mixing failed for emotion_type=%s: %s — proceeding without music",
            emotion_type, exc,
        )
        return audio


def _music_path(emotion_type: str) -> str:
    filename = EMOTION_MUSIC_MAP.get(emotion_type, "neutral.mp3")
    return os.path.join(settings.assets_dir, "music", filename)
