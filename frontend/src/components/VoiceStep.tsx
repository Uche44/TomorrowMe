import React, { useRef, useState } from "react";
import { uploadVoice } from "../api";

interface Props {
  onDone: (voiceId: string) => void;
}

export const VoiceStep: React.FC<Props> = ({ onDone }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [duration, setDuration] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];
      setDuration(0);
      setError(null);

      recorder.ondataavailable = (e) => chunksRef.current.push(e.data);
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setRecordedBlob(blob);
        stream.getTracks().forEach((t) => t.stop());
      };

      recorder.start();
      setIsRecording(true);

      timerRef.current = setInterval(() => {
        setDuration((d) => {
          const next = d + 1;
          if (next >= 15) {
            // Auto-stop at 15s max
            mediaRecorderRef.current?.stop();
            setIsRecording(false);
            if (timerRef.current) clearInterval(timerRef.current);
          }
          return next;
        });
      }, 1000);
    } catch (err) {
      setError("Microphone access denied or unavailable.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setRecordedBlob(file);
      setError(null);
    }
  };

  const handleSubmit = async () => {
    if (!recordedBlob) return;
    setIsUploading(true);
    setError(null);
    try {
      const file = new File([recordedBlob], "voice.webm", { type: recordedBlob.type });
      const { voice_id } = await uploadVoice([file]);
      onDone(voice_id);
    } catch (err: any) {
      setError(err.message ?? "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Record Your Voice</h2>
        <p className="text-sm text-gray-400">
          Record up to 15 seconds of clear audio. This will be used to clone your voice.
        </p>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-500/50 text-red-200 rounded px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {/* Recording controls */}
      <div className="bg-gray-900/50 border border-white/10 rounded-lg p-6 flex flex-col gap-4">
        {!recordedBlob && (
          <>
            <div className="flex items-center gap-4">
              <button
                onClick={isRecording ? stopRecording : startRecording}
                className={`px-6 py-3 rounded-lg font-medium transition ${
                  isRecording
                    ? "bg-red-600 hover:bg-red-700 text-white"
                    : "bg-indigo-600 hover:bg-indigo-700 text-white"
                }`}
              >
                {isRecording ? "Stop Recording" : "Start Recording"}
              </button>
              {isRecording && (
                <div className="flex items-center gap-2 text-sm text-gray-300">
                  <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                  <span>{Math.floor(duration / 60)}:{String(duration % 60).padStart(2, "0")}</span>
                  {duration >= 5 && duration < 15 && <span className="text-green-400 text-xs">✓ Good</span>}
                  {duration >= 15 && <span className="text-amber-400 text-xs">⚠ Max reached — stop now</span>}
                </div>
              )}
            </div>
            <div className="text-center text-sm text-gray-500">or</div>
            <label className="cursor-pointer">
              <input type="file" accept="audio/*" onChange={handleFileUpload} className="hidden" />
              <div className="border-2 border-dashed border-gray-700 hover:border-indigo-500 rounded-lg px-6 py-4 text-center text-sm text-gray-400 hover:text-indigo-400 transition">
                Upload an audio file (WAV, MP3, M4A, OGG)
              </div>
            </label>
          </>
        )}

        {recordedBlob && (
          <div className="flex flex-col gap-3">
            <div className="text-sm text-green-400">✓ Audio ready ({(recordedBlob.size / 1024).toFixed(0)} KB)</div>
            <button
              onClick={() => setRecordedBlob(null)}
              className="text-xs text-gray-400 hover:text-white underline self-start"
            >
              Clear and re-record
            </button>
          </div>
        )}
      </div>

      {recordedBlob && (
        <button
          onClick={handleSubmit}
          disabled={isUploading}
          className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-6 py-3 rounded-lg font-medium transition self-end"
        >
          {isUploading ? "Uploading…" : "Continue"}
        </button>
      )}
    </div>
  );
};
