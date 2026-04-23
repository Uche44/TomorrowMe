import json
import logging
from datetime import datetime, timezone

import aiosqlite

from app.models.audio_persistence import PersistedAudioJob

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS audio_jobs (
    job_id          TEXT PRIMARY KEY,
    status          TEXT NOT NULL,
    script_id       TEXT NOT NULL,
    voice_id        TEXT NOT NULL,
    emotion_type    TEXT NOT NULL,
    effects         TEXT NOT NULL,
    output_url      TEXT,
    duration_sec    REAL,
    created_at      TEXT NOT NULL,
    quality_pass    INTEGER,
    quality_detail  TEXT
);
"""


class AudioStoreError(Exception):
    pass


async def init_audio_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.commit()


class AudioJobStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def save(self, job: PersistedAudioJob) -> None:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    INSERT INTO audio_jobs
                        (job_id, status, script_id, voice_id, emotion_type, effects,
                         output_url, duration_sec, created_at, quality_pass, quality_detail)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job.job_id,
                        job.status,
                        job.script_id,
                        job.voice_id,
                        job.emotion_type,
                        json.dumps(job.effects),
                        job.output_url,
                        job.duration_sec,
                        job.created_at.astimezone(timezone.utc).isoformat(),
                        int(job.quality_pass) if job.quality_pass is not None else None,
                        job.quality_detail,
                    ),
                )
                await db.commit()
        except Exception as exc:
            logger.error("AudioJobStore.save failed: %s", exc)
            raise AudioStoreError(str(exc)) from exc

    async def get(self, job_id: str) -> PersistedAudioJob | None:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM audio_jobs WHERE job_id = ?", (job_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row is None:
                        return None
                    return _row_to_job(row)
        except AudioStoreError:
            raise
        except Exception as exc:
            logger.error("AudioJobStore.get failed: %s", exc)
            raise AudioStoreError(str(exc)) from exc

    async def update_status(
        self,
        job_id: str,
        status: str,
        output_url: str | None = None,
        duration_sec: float | None = None,
        quality_pass: bool | None = None,
        quality_detail: str | None = None,
    ) -> None:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    UPDATE audio_jobs
                    SET status = ?, output_url = ?, duration_sec = ?,
                        quality_pass = ?, quality_detail = ?
                    WHERE job_id = ?
                    """,
                    (
                        status,
                        output_url,
                        duration_sec,
                        int(quality_pass) if quality_pass is not None else None,
                        quality_detail,
                        job_id,
                    ),
                )
                await db.commit()
        except Exception as exc:
            logger.error("AudioJobStore.update_status failed: %s", exc)
            raise AudioStoreError(str(exc)) from exc


def _row_to_job(row: aiosqlite.Row) -> PersistedAudioJob:
    qp = row["quality_pass"]
    return PersistedAudioJob(
        job_id=row["job_id"],
        status=row["status"],
        script_id=row["script_id"],
        voice_id=row["voice_id"],
        emotion_type=row["emotion_type"],
        effects=json.loads(row["effects"]),
        output_url=row["output_url"],
        duration_sec=row["duration_sec"],
        created_at=datetime.fromisoformat(row["created_at"]),
        quality_pass=bool(qp) if qp is not None else None,
        quality_detail=row["quality_detail"],
    )
