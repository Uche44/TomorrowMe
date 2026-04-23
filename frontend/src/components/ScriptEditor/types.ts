export interface DialogueScript {
  script_id: string;
  text: string;
  estimated_duration_sec: number;
  emotional_markers: string[];
}

export type LengthVariant = "short" | "long";

export const MARKER_COLORS: Record<string, string> = {
  pause: "bg-slate-200 text-slate-800",
  softer: "bg-sky-200 text-sky-800",
  warmth: "bg-amber-200 text-amber-800",
  urgency: "bg-red-200 text-red-800",
  breath: "bg-teal-200 text-teal-800",
  slower: "bg-violet-200 text-violet-800",
  faster: "bg-orange-200 text-orange-800",
};

export const VALID_MARKERS = new Set(Object.keys(MARKER_COLORS));

export function extractMarkers(text: string): string[] {
  const pattern = /\[([a-z]+)\]/gi;
  const found = new Set<string>();
  let match;
  while ((match = pattern.exec(text)) !== null) {
    const token = match[1].toLowerCase();
    if (VALID_MARKERS.has(token)) found.add(token);
  }
  return Array.from(found).sort();
}

export function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}m ${String(s).padStart(2, "0")}s`;
}

export function httpErrorMessage(status: number, detail?: string): string {
  const map: Record<number, string> = {
    404: "Persona or scenario not found. Please check your selection.",
    422: "Invalid request. Please check your inputs.",
    502: "Script generation failed. Please try again.",
    504: "The request timed out. Please try again.",
    500: "An unexpected error occurred. Please try again.",
  };
  return map[status] ?? detail ?? "An error occurred. Please try again.";
}
