import json
import logging
from datetime import datetime, timezone

import aiosqlite

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS personas (
    persona_id          TEXT PRIMARY KEY,
    summary             TEXT NOT NULL,
    tone                TEXT NOT NULL,
    key_life_events     TEXT NOT NULL,
    life_outcome        TEXT NOT NULL,
    key_message         TEXT NOT NULL,
    scenario_type       TEXT NOT NULL,
    current_age         INTEGER,
    years_ahead         INTEGER,
    goals               TEXT,
    current_state       TEXT,
    personality_traits  TEXT,
    narrative_coherence INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL
);
"""


async def init_persona_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.commit()


class PersonaStoreError(Exception):
    pass


class PersonaStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def save(self, persona: dict) -> None:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """INSERT INTO personas
                       (persona_id, summary, tone, key_life_events, life_outcome, key_message,
                        scenario_type, current_age, years_ahead, goals, current_state,
                        personality_traits, narrative_coherence, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        persona["persona_id"],
                        persona["summary"],
                        persona["tone"],
                        json.dumps(persona["key_life_events"]),
                        persona["life_outcome"],
                        persona["key_message"],
                        persona["scenario_type"],
                        persona.get("current_age"),
                        persona.get("years_ahead"),
                        json.dumps(persona.get("goals", [])),
                        persona.get("current_state"),
                        json.dumps(persona.get("personality_traits", [])),
                        int(persona.get("narrative_coherence", True)),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                await db.commit()
        except Exception as exc:
            raise PersonaStoreError(str(exc)) from exc

    async def get(self, persona_id: str) -> dict | None:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM personas WHERE persona_id = ?", (persona_id,)) as cur:
                    row = await cur.fetchone()
                    if row is None:
                        return None
                    d = dict(row)
                    d["key_life_events"] = json.loads(d["key_life_events"])
                    d["goals"] = json.loads(d.get("goals") or "[]")
                    d["personality_traits"] = json.loads(d.get("personality_traits") or "[]")
                    return d
        except Exception as exc:
            raise PersonaStoreError(str(exc)) from exc
