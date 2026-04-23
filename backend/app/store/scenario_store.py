import json
import logging
from datetime import datetime, timezone

import aiosqlite

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id     TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    context         TEXT NOT NULL,
    emotional_target TEXT NOT NULL,
    trigger         TEXT NOT NULL,
    scenario_type   TEXT NOT NULL,
    is_preset       INTEGER NOT NULL DEFAULT 0,
    plausibility_ok INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL
);
"""


async def init_scenario_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.commit()


class ScenarioStoreError(Exception):
    pass


class ScenarioStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def save(self, scenario: dict) -> None:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """INSERT OR REPLACE INTO scenarios
                       (scenario_id, title, context, emotional_target, trigger,
                        scenario_type, is_preset, plausibility_ok, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        scenario["scenario_id"],
                        scenario["title"],
                        scenario["context"],
                        scenario["emotional_target"],
                        scenario["trigger"],
                        scenario.get("scenario_type", "neutral"),
                        int(scenario.get("is_preset", False)),
                        int(scenario.get("plausibility_ok", True)),
                        scenario.get("created_at", datetime.now(timezone.utc).isoformat()),
                    ),
                )
                await db.commit()
        except Exception as exc:
            raise ScenarioStoreError(str(exc)) from exc

    async def get(self, scenario_id: str) -> dict | None:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM scenarios WHERE scenario_id = ?", (scenario_id,)) as cur:
                    row = await cur.fetchone()
                    return dict(row) if row else None
        except Exception as exc:
            raise ScenarioStoreError(str(exc)) from exc
