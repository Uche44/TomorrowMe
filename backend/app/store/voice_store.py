import json
import logging
from datetime import datetime, timezone

import aiosqlite

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS voice_profiles (
    voice_id            TEXT PRIMARY KEY,
    provider            TEXT NOT NULL DEFAULT 'elevenlabs',
    sample_duration_sec REAL NOT NULL,
    similarity_score    REAL,
    created_at          TEXT NOT NULL
);
"""


async def init_voice_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.commit()


class VoiceStoreError(Exception):
    pass


class VoiceStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def save(self, voice_id: str, sample_duration_sec: float, similarity_score: float | None) -> None:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    "INSERT INTO voice_profiles (voice_id, provider, sample_duration_sec, similarity_score, created_at) VALUES (?, 'elevenlabs', ?, ?, ?)",
                    (voice_id, sample_duration_sec, similarity_score, datetime.now(timezone.utc).isoformat()),
                )
                await db.commit()
        except Exception as exc:
            raise VoiceStoreError(str(exc)) from exc

    async def get(self, voice_id: str) -> dict | None:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM voice_profiles WHERE voice_id = ?", (voice_id,)) as cur:
                    row = await cur.fetchone()
                    if row is None:
                        return None
                    return dict(row)
        except Exception as exc:
            raise VoiceStoreError(str(exc)) from exc

    async def delete(self, voice_id: str) -> None:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute("DELETE FROM voice_profiles WHERE voice_id = ?", (voice_id,))
                await db.commit()
        except Exception as exc:
            raise VoiceStoreError(str(exc)) from exc
