import React, { useState } from "react";
import type { PipelineResult, Step } from "./types";
import { VoiceStep } from "./components/VoiceStep";
import { ContextStep } from "./components/ContextStep";
import { ResultStep } from "./components/ResultStep";

export default function App() {
  const [step, setStep] = useState<Step>("voice");
  const [voiceId, setVoiceId] = useState<string>("");
  const [result, setResult] = useState<PipelineResult | null>(null);

  const steps: Step[] = ["voice", "context", "result"];
  const stepLabels = ["Record Voice", "Your Story", "Listen"];
  const currentIdx = steps.indexOf(step);

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-indigo-950 to-gray-950">
      {/* Header */}
      <header className="border-b border-white/10 px-6 py-4">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-white">TomorrowMe</h1>
            <p className="text-xs text-gray-400">Listen to who you’re becoming...</p>
          </div>
          {/* Step indicator */}
          <div className="flex items-center gap-2">
            {steps.map((s, i) => (
              <React.Fragment key={s}>
                <div className={`flex items-center gap-1.5 ${i <= currentIdx ? "text-indigo-400" : "text-gray-600"}`}>
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border ${i < currentIdx ? "bg-indigo-500 border-indigo-500 text-white" : i === currentIdx ? "border-indigo-400 text-indigo-400" : "border-gray-700 text-gray-600"}`}>
                    {i < currentIdx ? "✓" : i + 1}
                  </div>
                  <span className="text-xs hidden sm:block">{stepLabels[i]}</span>
                </div>
                {i < steps.length - 1 && <div className={`w-8 h-px ${i < currentIdx ? "bg-indigo-500" : "bg-gray-700"}`} />}
              </React.Fragment>
            ))}
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-2xl mx-auto px-6 py-10">
        {step === "voice" && (
          <VoiceStep
            onDone={(vid) => {
              setVoiceId(vid);
              setStep("context");
            }}
          />
        )}
        {step === "context" && (
          <ContextStep
            voiceId={voiceId}
            onDone={(r) => {
              setResult(r);
              setStep("result");
            }}
            onBack={() => setStep("voice")}
          />
        )}
        {step === "result" && result && (
          <ResultStep
            result={result}
            onRestart={() => {
              setVoiceId("");
              setResult(null);
              setStep("voice");
            }}
          />
        )}
      </main>
    </div>
  );
}
