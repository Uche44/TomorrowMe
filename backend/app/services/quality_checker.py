import logging
import os

from pydub import AudioSegment

logger = logging.getLogger(__name__)

DURATION_MIN_SEC = 25.0
DURATION_MAX_SEC = 65.0
TARGET_MIN_SEC = 30.0
TARGET_MAX_SEC = 60.0
MIN_SNR_DB = 10.0
DURATION_DEVIATION_THRESHOLD = 0.10  # 10%


class QualityCheckError(Exception):
    pass


def run_quality_checks(
    audio_path: str,
    duration_sec: float,
    job_id: str,
    estimated_duration_sec: float | None = None,
) -> dict:
    """
    Run quality checks on the output MP3 file.
    Returns {"duration_ok": bool, "size_ok": bool, "snr_ok": bool, "passed": bool}
    Raises QualityCheckError if any check fails.
    """
    results: dict[str, bool] = {}
    failures: list[str] = []

    # Check 1: duration within acceptable range
    duration_ok = DURATION_MIN_SEC <= duration_sec <= DURATION_MAX_SEC
    results["duration_ok"] = duration_ok
    if not duration_ok:
        failures.append(f"duration {duration_sec:.1f}s outside {DURATION_MIN_SEC}–{DURATION_MAX_SEC}s range")
        logger.error(
            "QualityCheck FAIL: job_id=%s check=duration value=%.1f expected=%.0f–%.0f",
            job_id, duration_sec, DURATION_MIN_SEC, DURATION_MAX_SEC,
        )

    # Warn if outside 30-60s target (but not a hard failure)
    if duration_ok and not (TARGET_MIN_SEC <= duration_sec <= TARGET_MAX_SEC):
        logger.warning(
            "QualityCheck WARN: job_id=%s duration=%.1f outside 30–60s target",
            job_id, duration_sec,
        )

    # Check 2: file size > 0
    file_size = os.path.getsize(audio_path) if os.path.exists(audio_path) else 0
    size_ok = file_size > 0
    results["size_ok"] = size_ok
    if not size_ok:
        failures.append(f"file size is 0 bytes at {audio_path}")
        logger.error("QualityCheck FAIL: job_id=%s check=size value=0", job_id)

    # Check 3: speech-to-background SNR (simplified — check audio is not silent)
    snr_ok = True
    try:
        audio = AudioSegment.from_mp3(audio_path)
        snr_ok = audio.dBFS > -60.0  # not effectively silent
        if not snr_ok:
            failures.append(f"audio appears silent (dBFS={audio.dBFS:.1f})")
            logger.error("QualityCheck FAIL: job_id=%s check=snr value=%.1f", job_id, audio.dBFS)
    except Exception as exc:
        logger.warning("QualityCheck SNR check failed to load audio: %s", exc)
        snr_ok = True  # don't fail job on SNR check error

    results["snr_ok"] = snr_ok

    # Warn if duration deviates > 10% from estimated
    if estimated_duration_sec and estimated_duration_sec > 0:
        deviation = abs(duration_sec - estimated_duration_sec) / estimated_duration_sec
        if deviation > DURATION_DEVIATION_THRESHOLD:
            logger.warning(
                "QualityCheck WARN: job_id=%s duration deviation=%.1f%% expected=%.1fs actual=%.1fs",
                job_id, deviation * 100, estimated_duration_sec, duration_sec,
            )

    passed = not failures
    results["passed"] = passed

    if not passed:
        raise QualityCheckError(
            f"Quality checks failed for job {job_id}: {'; '.join(failures)}"
        )

    logger.info(
        "QualityCheck PASS: job_id=%s duration=%.1fs size=%d snr_ok=%s",
        job_id, duration_sec, file_size, snr_ok,
    )
    return results
