import React from "react";
import { DurationDisplay } from "./DurationDisplay";
import { RegenerateControls } from "./RegenerateControls";
import { ScriptDisplay } from "./ScriptDisplay";
import { DialogueScript, LengthVariant } from "./types";
import { useScriptEditor } from "./useScriptEditor";

interface Props {
  personaId: string;
  scenarioId: string;
  initialScript?: DialogueScript;
  apiBase?: string;
}

export const ScriptEditor: React.FC<Props> = ({
  personaId,
  scenarioId,
  initialScript,
  apiBase,
}) => {
  const {
    script,
    length,
    toneOverride,
    isLoading,
    error,
    handleTextChange,
    handleLengthChange,
    handleToneOverrideChange,
    handleRegenerate,
  } = useScriptEditor({ initialPersonaId: personaId, initialScenarioId: scenarioId, initialScript, apiBase });

  return (
    <div className="flex flex-col gap-6 p-6 max-w-2xl mx-auto">
      <h2 className="text-xl font-semibold text-gray-900">Script Editor</h2>

      {error && (
        <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {script ? (
        <>
          <div className="flex items-center justify-between">
            <DurationDisplay estimatedDurationSec={script.estimated_duration_sec} />
            <span className="text-xs text-gray-400 font-mono">ID: {script.script_id}</span>
          </div>

          {/* Highlighted read view */}
          <div className="border rounded p-4 bg-gray-50 min-h-[120px]">
            <ScriptDisplay text={script.text} />
          </div>

          {/* Editable textarea */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Edit script
            </label>
            <textarea
              value={script.text}
              onChange={(e) => handleTextChange(e.target.value)}
              disabled={isLoading}
              rows={8}
              className="w-full border rounded px-3 py-2 text-sm font-mono disabled:opacity-50 resize-y"
            />
          </div>

          {/* Active markers */}
          {script.emotional_markers.length > 0 && (
            <div className="text-xs text-gray-500">
              Active markers:{" "}
              {script.emotional_markers.map((m) => (
                <code key={m} className="bg-gray-100 rounded px-1 mr-1">[{m}]</code>
              ))}
            </div>
          )}
        </>
      ) : (
        <p className="text-gray-500 text-sm">No script yet. Click Regenerate to generate one.</p>
      )}

      <RegenerateControls
        length={length as LengthVariant}
        toneOverride={toneOverride}
        isLoading={isLoading}
        onLengthChange={handleLengthChange}
        onToneOverrideChange={handleToneOverrideChange}
        onRegenerate={handleRegenerate}
      />
    </div>
  );
};

export default ScriptEditor;
