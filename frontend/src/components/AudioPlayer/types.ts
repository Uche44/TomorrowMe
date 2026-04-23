export interface AudioJob {
  job_id: string;
  status: "queued" | "processing" | "done" | "failed";
  output_url: string | null;
  duration_sec: number | null;
}

export interface AudioPlayerProps {
  jobId: string;
  apiBase?: string;
}

export function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}
