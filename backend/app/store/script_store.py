import json
import logging
from datetime import datetime, timezone

import aiosqlite

from app.exceptions import StoreError
from app.models.persistence import PersistedScript

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS scripts (
    script_id               TEXT PRIMARY KEY,
    text                    TEXT NOT NULL,
    estimated_duration_sec  REAL NOT NULL,
    emotional_markers       TEXT NOT NULL,
    persona_id              TEXT NOT NULL,
    scenario_id             TEXT NOT NULL,
    length                  TEXT NOT NULL,
    created_at              TEXT NOT NULL,
    quality_pass            INTEGER NOT NULL,
    quality_detail          TEXT NOT NULL
);
"""


async def init_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.commit()


class ScriptStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def save(self, script: PersistedScript) -> None:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    INSERT INTO scripts
                        (script_id, text, estimated_duration_sec, emotional_markers,
                         persona_id, scenario_id, length, created_at, quality_pass, quality_detail)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        script.script_id,
                        script.text,
                        script.estimated_duration_sec,
                        json.dumps(script.emotional_markers),
                        script.persona_id,
                        script.scenario_id,
                        script.length,
                        script.created_at.astimezone(timezone.utc).isoformat(),
                        int(script.quality_pass),
                        script.quality_detail,
                    ),
                )
                await db.commit()
        except Exception as exc:
            logger.error("ScriptStore.save failed: %s", exc)
            raise StoreError(str(exc)) from exc

    async def get(self, script_id: str) -> PersistedScript | None:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM scripts WHERE script_id = ?", (script_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row is None:
                        return None
                    return PersistedScript(
                        script_id=row["script_id"],
                        text=row["text"],
                        estimated_duration_sec=row["estimated_duration_sec"],
                        emotional_markers=json.loads(row["emotional_markers"]),
                        persona_id=row["persona_id"],
                        scenario_id=row["scenario_id"],
                        length=row["length"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        quality_pass=bool(row["quality_pass"]),
                        quality_detail=row["quality_detail"],
                    )
        except StoreError:
            raise
        except Exception as exc:
            logger.error("ScriptStore.get failed: %s", exc)
            raise StoreError(str(exc)) from exc
