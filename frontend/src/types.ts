export type ScenarioType = "success" | "regret" | "neutral";
export type LengthVariant = "short" | "long";
export type JobStatus = "queued" | "processing" | "done" | "failed";

export interface VoiceProfile {
  voice_id: string;
  provider: string;
  sample_duration_sec: number;
}

export interface Persona {
  persona_id: string;
  summary: string;
  tone: string;
  key_life_events: string[];
  life_outcome: string;
  key_message: string;
  scenario_type: ScenarioType;
}

export interface Scenario {
  scenario_id: string;
  title: string;
  context: string;
  emotional_target: string;
  trigger: string;
  scenario_type: ScenarioType;
}

export interface DialogueScript {
  script_id: string;
  text: string;
  estimated_duration_sec: number;
  emotional_markers: string[];
}

export interface AudioJob {
  job_id: string;
  status: JobStatus;
  output_url: string | null;
  duration_sec: number | null;
}

export interface PipelineResult {
  session_id: string;
  persona_id: string;
  scenario_id: string;
  script_id: string;
  job_id: string;
}

// App-level wizard step
export type Step = "voice" | "context" | "result";
