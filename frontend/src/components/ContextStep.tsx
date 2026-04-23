import React, { useState } from "react";
import { runPipeline } from "../api";
import type { PipelineResult, ScenarioType, LengthVariant } from "../types";

interface Props {
  voiceId: string;
  onDone: (result: PipelineResult) => void;
  onBack: () => void;
}

export const ContextStep: React.FC<Props> = ({ voiceId, onDone, onBack }) => {
  const [currentAge, setCurrentAge] = useState(28);
  const [yearsAhead, setYearsAhead] = useState(7);
  const [currentState, setCurrentState] = useState("");
  const [goalInput, setGoalInput] = useState("");
  const [goals, setGoals] = useState<string[]>([]);
  const [traitInput, setTraitInput] = useState("");
  const [traits, setTraits] = useState<string[]>([]);
  const [scenarioType, setScenarioType] = useState<ScenarioType>("success");
  const [length, setLength] = useState<LengthVariant>("short");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addGoal = () => {
    const g = goalInput.trim();
    if (g && goals.length < 10) {
      setGoals([...goals, g]);
      setGoalInput("");
    }
  };

  const addTrait = () => {
    const t = traitInput.trim();
    if (t && traits.length < 5) {
      setTraits([...traits, t]);
      setTraitInput("");
    }
  };

  const handleSubmit = async () => {
    if (!currentState.trim() || goals.length === 0 || traits.length === 0) {
      setError("Please fill in all fields and add at least one goal and trait.");
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const result = await runPipeline({
        voice_id: voiceId,
        current_age: currentAge,
        years_ahead: yearsAhead,
        goals,
        current_state: currentState,
        personality_traits: traits,
        scenario_type: scenarioType,
        length,
        effects: ["reverb", "warmth"],
      });
      onDone(result);
    } catch (err: any) {
      setError(err.message ?? "Generation failed");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Tell Us About You</h2>
        <p className="text-sm text-gray-400">
          This shapes your future self's message.
        </p>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-500/50 text-red-200 rounded px-4 py-3 text-sm">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-5">
        {/* Age */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Current Age: <span className="text-indigo-400">{currentAge}</span>
          </label>
          <input type="range" min={18} max={100} value={currentAge} onChange={(e) => setCurrentAge(+e.target.value)}
            className="w-full accent-indigo-500" />
        </div>

        {/* Years ahead */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Years into the future: <span className="text-indigo-400">{yearsAhead}</span>
          </label>
          <input type="range" min={5} max={10} value={yearsAhead} onChange={(e) => setYearsAhead(+e.target.value)}
            className="w-full accent-indigo-500" />
        </div>

        {/* Current state */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">Where are you right now?</label>
          <textarea
            value={currentState}
            onChange={(e) => setCurrentState(e.target.value)}
            placeholder="e.g. I'm a junior developer feeling stuck in my career, unsure if I should take a risk..."
            rows={3}
            maxLength={500}
            className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
          />
        </div>

        {/* Goals */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">Goals ({goals.length}/10)</label>
          <div className="flex gap-2 mb-2">
            <input
              value={goalInput}
              onChange={(e) => setGoalInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addGoal()}
              placeholder="Add a goal and press Enter"
              maxLength={200}
              className="flex-1 bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
            />
            <button onClick={addGoal} className="bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-2 rounded text-sm">Add</button>
          </div>
          <div className="flex flex-wrap gap-2">
            {goals.map((g, i) => (
              <span key={i} className="bg-indigo-900/50 border border-indigo-700 text-indigo-200 text-xs px-2 py-1 rounded-full flex items-center gap-1">
                {g}
                <button onClick={() => setGoals(goals.filter((_, j) => j !== i))} className="text-indigo-400 hover:text-white">×</button>
              </span>
            ))}
          </div>
        </div>

        {/* Personality traits */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">Personality traits ({traits.length}/5)</label>
          <div className="flex gap-2 mb-2">
            <input
              value={traitInput}
              onChange={(e) => setTraitInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addTrait()}
              placeholder="e.g. ambitious, anxious, creative"
              maxLength={50}
              className="flex-1 bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
            />
            <button onClick={addTrait} className="bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-2 rounded text-sm">Add</button>
          </div>
          <div className="flex flex-wrap gap-2">
            {traits.map((t, i) => (
              <span key={i} className="bg-purple-900/50 border border-purple-700 text-purple-200 text-xs px-2 py-1 rounded-full flex items-center gap-1">
                {t}
                <button onClick={() => setTraits(traits.filter((_, j) => j !== i))} className="text-purple-400 hover:text-white">×</button>
              </span>
            ))}
          </div>
        </div>

        {/* Scenario type */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">How does your future turn out?</label>
          <div className="grid grid-cols-3 gap-3">
            {(["success", "regret", "neutral"] as ScenarioType[]).map((s) => (
              <button
                key={s}
                onClick={() => setScenarioType(s)}
                className={`py-3 rounded-lg border text-sm font-medium capitalize transition ${
                  scenarioType === s
                    ? "bg-indigo-600 border-indigo-500 text-white"
                    : "bg-gray-900 border-gray-700 text-gray-400 hover:border-gray-500"
                }`}
              >
                {s === "success" ? "🌟 Success" : s === "regret" ? "💭 Regret" : "⚖️ Neutral"}
              </button>
            ))}
          </div>
        </div>

        {/* Length */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">Message length</label>
          <div className="flex gap-3">
            {(["short", "long"] as LengthVariant[]).map((l) => (
              <button
                key={l}
                onClick={() => setLength(l)}
                className={`px-4 py-2 rounded-lg border text-sm font-medium transition ${
                  length === l
                    ? "bg-indigo-600 border-indigo-500 text-white"
                    : "bg-gray-900 border-gray-700 text-gray-400 hover:border-gray-500"
                }`}
              >
                {l === "short" ? "~30 seconds" : "~60 seconds"}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex justify-between pt-2">
        <button onClick={onBack} className="text-sm text-gray-400 hover:text-white underline">
          ← Back
        </button>
        <button
          onClick={handleSubmit}
          disabled={isLoading}
          className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-6 py-3 rounded-lg font-medium transition flex items-center gap-2"
        >
          {isLoading && (
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          )}
          {isLoading ? "Generating your message…" : "Generate Message"}
        </button>
      </div>
    </div>
  );
};
