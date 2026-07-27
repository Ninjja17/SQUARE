"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getSession } from "@/lib/session";
import { Spinner } from "@/components/Spinner";
import { ErrorBox } from "@/components/ErrorBox";
import { BASE } from "@/lib/api";

interface TimelineStep {
  timestamp: string;
  agent: string;
  action: string;
  status: "success" | "processing" | "error" | "handoff";
  detail: string;
  target_agent: string | null;
}

interface NarrativeResult {
  timeline: TimelineStep[];
  outcome: string;
  total_time: string;
}

const SCENARIOS = [
  { key: "happy_path", label: "Happy Path", icon: "✅" },
  { key: "agent_failure", label: "Agent Failure", icon: "💥" },
  { key: "wrong_decision", label: "Wrong Decision", icon: "❌" },
  { key: "high_workload", label: "High Workload", icon: "📈" },
  { key: "external_failure", label: "External Failure", icon: "🔌" },
  { key: "human_override", label: "Human Override", icon: "🧑‍💼" },
];

const STATUS_COLORS: Record<string, string> = {
  success: "border-green-500/50 bg-green-500/5",
  processing: "border-blue-500/50 bg-blue-500/5",
  error: "border-red-500/50 bg-red-500/5",
  handoff: "border-yellow-500/50 bg-yellow-500/5",
};

const STATUS_DOT: Record<string, string> = {
  success: "bg-green-400",
  processing: "bg-blue-400",
  error: "bg-red-400",
  handoff: "bg-yellow-400",
};

const AGENT_COLORS: Record<string, string> = {
  Analyzer: "text-purple-400",
  Verification: "text-green-400",
  Decision: "text-blue-400",
  Communication: "text-cyan-400",
  Risk: "text-red-400",
  Planner: "text-yellow-400",
};

export default function SimulationLivePage() {
  const router = useRouter();
  const [selectedScenarios, setSelectedScenarios] = useState<string[]>(["happy_path"]);
  const [narratives, setNarratives] = useState<{ scenario: string; data: NarrativeResult }[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [visibleSteps, setVisibleSteps] = useState(0);
  const [currentScenarioIdx, setCurrentScenarioIdx] = useState(0);

  function toggleScenario(key: string) {
    setSelectedScenarios((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  }

  async function runNarrative() {
    const { workflowId, agentsGenerated } = getSession();
    if (!workflowId || !agentsGenerated) {
      router.push("/agents");
      return;
    }
    if (selectedScenarios.length === 0) return;
    setLoading(true);
    setError(null);
    setNarratives([]);
    setVisibleSteps(0);
    setCurrentScenarioIdx(0);

    try {
      const allNarratives: { scenario: string; data: NarrativeResult }[] = [];

      for (let s = 0; s < selectedScenarios.length; s++) {
        setCurrentScenarioIdx(s);
        const scenario = selectedScenarios[s];
        const res = await fetch(`${BASE}/api/simulate/narrative`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ workflow_id: workflowId, scenario }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: NarrativeResult = await res.json();
        allNarratives.push({ scenario, data });
        setNarratives([...allNarratives]);

        // Animate steps for this scenario
        for (let i = 1; i <= data.timeline.length; i++) {
          await new Promise((r) => setTimeout(r, 300));
          setVisibleSteps(i);
        }
        // Pause between scenarios
        if (s < selectedScenarios.length - 1) {
          await new Promise((r) => setTimeout(r, 600));
          setVisibleSteps(0);
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to generate narrative");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="py-8 space-y-8">
      <div>
        <Link href="/simulation" className="text-[#555] text-sm hover:text-white transition-colors">
          ← Back to Simulation
        </Link>
        <h1 className="text-3xl font-bold mt-4">Agent Interaction Live View</h1>
        <p className="text-[#666] mt-2 text-sm">
          Watch how your AI agents collaborate to process a transaction — step by step, agent by agent.
        </p>
      </div>

      {/* Scenario Picker */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-sm text-[#aaa] uppercase tracking-wider">Select Scenarios</h2>
        <p className="text-xs text-[#555]">Pick one or more scenarios to simulate</p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {SCENARIOS.map(({ key, label, icon }) => (
            <button
              key={key}
              onClick={() => toggleScenario(key)}
              className={`p-3 rounded-lg border text-left transition-all ${
                selectedScenarios.includes(key)
                  ? "border-white/30 bg-white/10"
                  : "border-[#222] hover:border-[#444] bg-transparent"
              }`}
            >
              <span className="text-lg">{icon}</span>
              <p className="text-xs font-medium mt-1">{label}</p>
              {selectedScenarios.includes(key) && (
                <span className="text-[10px] text-green-400">✓ selected</span>
              )}
            </button>
          ))}
        </div>

        <button
          onClick={runNarrative}
          disabled={loading || selectedScenarios.length === 0}
          className="btn-primary w-full justify-center"
        >
          {loading ? `Simulating scenario ${currentScenarioIdx + 1}/${selectedScenarios.length}...` : `▶ Run ${selectedScenarios.length} Scenario${selectedScenarios.length > 1 ? "s" : ""}`}
        </button>
      </div>

      {loading && narratives.length === 0 && <Spinner>AI is simulating agent interactions...</Spinner>}
      {error && <ErrorBox message={error} onRetry={runNarrative} />}

      {/* Timeline — show all completed narratives */}
      {narratives.map(({ scenario, data }, nIdx) => {
        const scenarioInfo = SCENARIOS.find((s) => s.key === scenario);
        const isLast = nIdx === narratives.length - 1;
        const stepsToShow = isLast ? visibleSteps : data.timeline.length;

        return (
          <div key={`${scenario}-${nIdx}`} className="space-y-4">
            {/* Scenario header */}
            <div className="flex items-center gap-2 pt-4 border-t border-[#222]">
              <span className="text-lg">{scenarioInfo?.icon ?? "🔄"}</span>
              <h2 className="font-semibold text-sm text-white">{scenarioInfo?.label ?? scenario}</h2>
              <span className="text-xs text-[#555]">• {data.total_time}</span>
            </div>

          {/* Timeline steps */}
          <div className="relative">
            {/* Vertical line */}
            <div className="absolute left-[22px] top-0 bottom-0 w-px bg-[#222]" />

            <div className="space-y-3">
              {data.timeline.slice(0, stepsToShow).map((step, i) => (
                <div
                  key={i}
                  className={`relative pl-12 pr-4 py-3 rounded-lg border transition-all duration-300 ${STATUS_COLORS[step.status]}`}
                >
                  {/* Dot on timeline */}
                  <div className={`absolute left-[18px] top-5 w-[10px] h-[10px] rounded-full ${STATUS_DOT[step.status]}`} />

                  {/* Content */}
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`text-xs font-bold ${AGENT_COLORS[step.agent] ?? "text-white"}`}>
                        {step.agent}
                      </span>
                      <span className="text-[10px] text-[#444]">{step.timestamp}</span>
                      {step.target_agent && (
                        <span className="text-[10px] text-yellow-500/80">
                          → {step.target_agent}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-white">{step.action}</p>
                    <p className="text-xs text-[#666]">{step.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Outcome */}
          {stepsToShow >= data.timeline.length && (
            <div className="card border-white/10 bg-white/[0.02]">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-green-400">●</span>
                <span className="text-xs uppercase tracking-wider text-[#aaa]">Outcome</span>
              </div>
              <p className="text-sm text-white">{data.outcome}</p>
            </div>
          )}
          </div>
        );
      })}

      {/* Legend */}
      {narratives.length > 0 && (
        <div className="flex flex-wrap gap-4 text-[10px] text-[#555] pt-2">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-400" /> Success</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-400" /> Processing</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-yellow-400" /> Handoff</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-400" /> Error</span>
        </div>
      )}
    </div>
  );
}
