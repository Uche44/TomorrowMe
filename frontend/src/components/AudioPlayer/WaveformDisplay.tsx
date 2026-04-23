import React, { useEffect, useRef } from "react";

interface Props {
  audioUrl: string;
  onReady?: () => void;
}

/**
 * Waveform visualization using the native HTML5 <audio> element.
 * For a richer waveform, replace with wavesurfer.js when available.
 */
export const WaveformDisplay: React.FC<Props> = ({ audioUrl, onReady }) => {
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.load();
    }
  }, [audioUrl]);

  return (
    <div className="w-full">
      <audio
        ref={audioRef}
        controls
        className="w-full"
        onCanPlay={onReady}
        preload="metadata"
      >
        <source src={audioUrl} type="audio/mpeg" />
        Your browser does not support the audio element.
      </audio>
    </div>
  );
};
