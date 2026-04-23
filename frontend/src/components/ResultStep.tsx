import React, { useEffect, useRef, useState } from "react";
import { pollAudioStatus } from "../api";
import type { AudioJob, PipelineResult } from "../types";

interface Props {
  result: PipelineResult;
  onRestart: () => void;
}

function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export const ResultStep: React.FC<Props> = ({ result, onRestart }) => {
  const [job, setJob] = useState<AudioJob | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadMsg, setDownloadMsg] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const j = await pollAudioStatus(result.job_id);
        setJob(j);
        if (j.status === "done" || j.status === "failed") {
          if (intervalRef.current) clearInterval(intervalRef.current);
        }
      } catch {}
    };
    poll();
    intervalRef.current = setInterval(poll, 3000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [result.job_id]);

  const handleDownload = async () => {
    setIsDownloading(true);
    setDownloadMsg(null);
    try {
      const res = await fetch(`/audio/download/${result.job_id}`);
      if (res.status === 202) {
        setDownloadMsg("Not ready yet — please wait.");
        return;
      }
      if (!res.ok) {
        setDownloadMsg(`Download failed (${res.status})`);
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `future-self-${result.job_id.slice(0, 8)}.mp3`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setDownloadMsg("Network error during download.");
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Your Message from the Future</h2>
        <p className="text-sm text-gray-400">
          Your future self is speaking. Listen carefully.
        </p>
      </div>

      {/* Status card */}
      <div className="bg-gray-900/50 border border-white/10 rounded-lg p-6 flex flex-col gap-4">
        {(!job || job.status === "queued" || job.status === "processing") && (
          <div className="flex items-center gap-3 text-gray-300">
            <svg className="animate-spin h-5 w-5 text-indigo-400" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            <span className="text-sm capitalize">{job?.status ?? "queued"}… synthesizing your voice message</span>
          </div>
        )}

        {job?.status === "failed" && (
          <div className="text-red-400 text-sm">
            Synthesis failed. Please try again.
          </div>
        )}

        {job?.status === "done" && (
          <>
            {job.duration_sec != null && (
              <div className="text-sm text-gray-400">
                Duration: <span className="text-white font-medium">{formatDuration(job.duration_sec)}</span>
              </div>
            )}

            {/* Native audio player */}
            <audio
              controls
              className="w-full"
              src={`/audio/download/${result.job_id}`}
            >
              Your browser does not support audio playback.
            </audio>

            <div className="flex flex-col gap-1">
              <button
                onClick={handleDownload}
                disabled={isDownloading}
                className="flex items-center gap-2 self-start bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
              >
                {isDownloading && (
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                )}
                {isDownloading ? "Downloading…" : "Download MP3"}
              </button>
              {downloadMsg && <p className="text-xs text-amber-400">{downloadMsg}</p>}
            </div>
          </>
        )}

        {/* Session info */}
        <div className="text-xs text-gray-600 font-mono pt-2 border-t border-white/5">
          Job: {result.job_id}
        </div>
      </div>

      <button
        onClick={onRestart}
        className="text-sm text-gray-400 hover:text-white underline self-start"
      >
        ← Start over
      </button>
    </div>
  );
};
