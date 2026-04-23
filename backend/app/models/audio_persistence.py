from datetime import datetime
from pydantic import BaseModel


class PersistedAudioJob(BaseModel):
    job_id: str
    status: str                   # "queued" | "processing" | "done" | "failed"
    script_id: str
    voice_id: str
    emotion_type: str
    effects: list[str]            # stored as JSON string in SQLite
    output_url: str | None
    duration_sec: float | None
    created_at: datetime          # UTC ISO 8601
    quality_pass: bool | None     # None until quality check runs
    quality_detail: str | None    # JSON: {"duration_ok": bool, "size_ok": bool, "snr_ok": bool}
