import type { AudioJob, Persona, PipelineResult, Scenario, ScenarioType, LengthVariant } from "./types";

const BASE = "";

async function req<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(BASE + url, options);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json();
}

export async function uploadVoice(files: File[]): Promise<{ voice_id: string }> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const res = await fetch("/voice/upload", { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Upload failed (${res.status})`);
  }
  return res.json();
}

export async function getPresets(): Promise<Scenario[]> {
  return req("/scenario/presets");
}

export async function runPipeline(payload: {
  voice_id: string;
  current_age: number;
  years_ahead: number;
  goals: string[];
  current_state: string;
  personality_traits: string[];
  scenario_type: ScenarioType;
  length: LengthVariant;
  effects: string[];
  preset_id?: string;
}): Promise<PipelineResult> {
  return req("/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function pollAudioStatus(job_id: string): Promise<AudioJob> {
  return req(`/audio/status/${job_id}`);
}
