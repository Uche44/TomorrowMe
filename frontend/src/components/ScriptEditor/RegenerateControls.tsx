import React from "react";
import { LengthVariant } from "./types";

interface Props {
  length: LengthVariant;
  toneOverride: string;
  isLoading: boolean;
  onLengthChange: (l: LengthVariant) => void;
  onToneOverrideChange: (t: string) => void;
  onRegenerate: () => void;
}

export const RegenerateControls: React.FC<Props> = ({
  length,
  toneOverride,
  isLoading,
  onLengthChange,
  onToneOverrideChange,
  onRegenerate,
}) => (
  <div className="flex flex-col gap-3">
    <div className="flex items-center gap-3">
      <label className="text-sm font-medium text-gray-700">Length</label>
      <select
        value={length}
        onChange={(e) => onLengthChange(e.target.value as LengthVariant)}
        disabled={isLoading}
        className="border rounded px-2 py-1 text-sm disabled:opacity-50"
      >
        <option value="short">Short (~30s)</option>
        <option value="long">Long (~60s)</option>
      </select>
    </div>

    <div className="flex items-center gap-3">
      <label className="text-sm font-medium text-gray-700">Tone override</label>
      <input
        type="text"
        value={toneOverride}
        onChange={(e) => onToneOverrideChange(e.target.value)}
        disabled={isLoading}
        placeholder="e.g. gentle, urgent…"
        maxLength={100}
        className="border rounded px-2 py-1 text-sm flex-1 disabled:opacity-50"
      />
    </div>

    <button
      onClick={onRegenerate}
      disabled={isLoading}
      className="self-start bg-indigo-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-2"
    >
      {isLoading && (
        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
        </svg>
      )}
      {isLoading ? "Generating…" : "Regenerate"}
    </button>
  </div>
);
