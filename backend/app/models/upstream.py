from pydantic import BaseModel


class Persona(BaseModel):
    persona_id: str
    summary: str
    tone: str
    key_life_events: list[str]
    life_outcome: str
    key_message: str
    scenario_type: str  # "success" | "regret" | "neutral"


class Scenario(BaseModel):
    scenario_id: str
    title: str
    context: str
    emotional_target: str
    trigger: str
