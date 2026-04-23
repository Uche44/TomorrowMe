import { useCallback, useEffect, useRef, useState } from "react";
import { AudioJob } from "./types";

const POLL_INTERVAL_MS = 3000;
const TERMINAL_STATUSES = new Set(["done", "failed"]);

interface UseAudioJobResult {
  job: AudioJob | null;
  isLoading: boolean;
  error: string | null;
}

export function useAudioJob(jobId: string, apiBase = ""): UseAudioJobResult {
  const [job, setJob] = useState<AudioJob | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const poll = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/audio/status/${jobId}`);
      if (!res.ok) {
        if (res.status === 404) {
          setError("Job not found.");
          stopPolling();
          return;
        }
        setError(`Status check failed (HTTP ${res.status})`);
        return;
      }
      const data: AudioJob = await res.json();
      setJob(data);
      setIsLoading(false);
      if (TERMINAL_STATUSES.has(data.status)) {
        stopPolling();
      }
    } catch {
      setError("Network error while checking job status.");
    }
  }, [jobId, apiBase]);

  const stopPolling = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  useEffect(() => {
    poll();
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);
    return () => stopPolling();
  }, [poll]);

  return { job, isLoading, error };
}
