import React, { useState } from "react";
import { AudioPlayerProps, formatDuration } from "./types";
import { useAudioJob } from "./useAudioJob";
import { WaveformDisplay } from "./WaveformDisplay";

export const AudioPlayer: React.FC<AudioPlayerProps> = ({ jobId, apiBase = "" }) => {
  const { job, isLoading, error } = useAudioJob(jobId, apiBase);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadMsg, setDownloadMsg] = useState<string | null>(null);

  const handleDownload = async () => {
    setIsDownloading(true);
    setDownloadMsg(null);
    try {
      const res = await fetch(`${apiBase}/audio/download/${jobId}`);
      if (res.status === 202) {
        setDownloadMsg("File is not ready yet. Please wait.");
        return;
      }
      if (!res.ok) {
        setDownloadMsg(`Download failed (HTTP ${res.status})`);
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${jobId}.mp3`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setDownloadMsg("Network error during download.");
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="flex flex-col gap-4 p-6 max-w-xl mx-auto border rounded-lg bg-white shadow-sm">
      {/* Job ID reference */}
      <div className="text-xs text-gray-400 font-mono">Job: {jobId}</div>

      {/* Error state */}
      {error && (
        <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {/* Loading / processing state */}
      {!error && job && (job.status === "queued" || job.status === "processing") && (
        <div className="flex items-center gap-3 text-gray-600">
          <svg className="animate-spin h-5 w-5 text-indigo-500" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <span className="text-sm capitalize">{job.status}…</span>
        </div>
      )}

      {/* Initial loading before first poll */}
      {isLoading && !job && !error && (
        <div className="text-sm text-gray-500">Checking job status…</div>
      )}

      {/* Failed state */}
      {job?.status === "failed" && (
        <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded px-4 py-3 text-sm">
          Synthesis failed. Please try again.
        </div>
      )}

      {/* Done state */}
      {job?.status === "done" && job.output_url && (
        <>
          {/* Duration */}
          {job.duration_sec != null && (
            <div className="text-sm text-gray-500">
              Duration: <strong>{formatDuration(job.duration_sec)}</strong>
            </div>
          )}

          {/* Waveform / audio player */}
          <WaveformDisplay audioUrl={`${apiBase}${job.output_url}`} />

          {/* Download */}
          <div className="flex flex-col gap-1">
            <button
              onClick={handleDownload}
              disabled={isDownloading}
              className="flex items-center gap-2 self-start bg-indigo-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
            >
              {isDownloading && (
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
              )}
              {isDownloading ? "Downloading…" : "Download MP3"}
            </button>
            {downloadMsg && (
              <p className="text-xs text-amber-600">{downloadMsg}</p>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default AudioPlayer;
