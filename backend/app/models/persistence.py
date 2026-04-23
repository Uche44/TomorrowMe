from datetime import datetime
from pydantic import BaseModel


class PersistedScript(BaseModel):
    script_id: str
    text: str
    estimated_duration_sec: float
    emotional_markers: list[str]
    persona_id: str
    scenario_id: str
    length: str
    created_at: datetime
    quality_pass: bool
    quality_detail: str  # JSON string: {"structure_ok": bool, "duration_ok": bool, "markers_ok": bool}
