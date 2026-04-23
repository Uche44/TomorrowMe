import { useState } from "react";
import {
  DialogueScript,
  LengthVariant,
  extractMarkers,
  httpErrorMessage,
} from "./types";

interface ScriptEditorState {
  script: DialogueScript | null;
  personaId: string;
  scenarioId: string;
  length: LengthVariant;
  toneOverride: string;
  isLoading: boolean;
  error: string | null;
}

interface UseScriptEditorOptions {
  initialPersonaId: string;
  initialScenarioId: string;
  initialScript?: DialogueScript;
  apiBase?: string;
}

export function useScriptEditor({
  initialPersonaId,
  initialScenarioId,
  initialScript,
  apiBase = "",
}: UseScriptEditorOptions) {
  const [state, setState] = useState<ScriptEditorState>({
    script: initialScript ?? null,
    personaId: initialPersonaId,
    scenarioId: initialScenarioId,
    length: "short",
    toneOverride: "",
    isLoading: false,
    error: null,
  });

  const handleTextChange = (newText: string) => {
    setState((prev) => {
      if (!prev.script) return prev;
      return {
        ...prev,
        script: {
          ...prev.script,
          text: newText,
          emotional_markers: extractMarkers(newText),
        },
      };
    });
  };

  const handleLengthChange = (length: LengthVariant) => {
    setState((prev) => ({ ...prev, length }));
  };

  const handleToneOverrideChange = (toneOverride: string) => {
    setState((prev) => ({ ...prev, toneOverride }));
  };

  const handleRegenerate = async () => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      const res = await fetch(`${apiBase}/dialogue/regenerate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          persona_id: state.personaId,
          scenario_id: state.scenarioId,
          length: state.length,
          tone_override: state.toneOverride || undefined,
        }),
      });

      if (!res.ok) {
        let detail: string | undefined;
        try {
          const body = await res.json();
          detail = body?.detail;
        } catch {}
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: httpErrorMessage(res.status, detail),
        }));
        return;
      }

      const script: DialogueScript = await res.json();
      setState((prev) => ({ ...prev, script, isLoading: false, error: null }));
    } catch {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: "Network error. Please try again.",
      }));
    }
  };

  return {
    ...state,
    handleTextChange,
    handleLengthChange,
    handleToneOverrideChange,
    handleRegenerate,
  };
}
