"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, type ScenarioKey, type SimulationResult } from "@/lib/api";
import { getSession, setSession } from "@/lib/session";
import { Spinner } from "@/components/Spinner";
import { ErrorBox } from "@/components/ErrorBox";
import { Badge } from "@/components/Badge";

const ALL_SCENARIOS: { key: ScenarioKey; label: string; desc: string }[] = [
  { key: "happy_path", label: "Happy Path", desc: "All agents perform under normal conditions" },
  { key: "agent_failure", label: "Agent Failure", desc: "One agent goes down — test fallback path" },
  { key: "wrong_decision", label: "Wrong Decision Scenario", desc: "Incorrect output from Decision Agent" },
  { key: "high_workload", label: "High Workload Scenario", desc: "3× expected monthly volume" },
  { key: "external_failure", label: "External System Failure", desc: "Downstream API / DB timeout" },
  { key: "human_override", label: "Human Override Scenario", desc: "Manual escalation path" },
];

const STATUS_BADGE: Record<string, "passed" | "warning" | "critical"> = {
  passed: "passed",
  warning: "warning",
  critical: "critical",
};

const STATUS_ICON: Record<string, string> = {
  passed: "✓",
  warning: "⚠",
  critical: "✗",
};

export default function SimulationPage() {
  const router = useRouter();
  const [selected, setSelected] = useState<ScenarioKey[]>(["happy_path"]);
  const [results, setResults] = useState<SimulationResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggle(key: ScenarioKey) {
    setSelected((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  }

  async function runSimulation() {
    const { workflowId, agentsGenerated } = getSession();
    if (!workflowId || !agentsGenerated) {
      router.push("/agents");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await api.runSimulation(workflowId, selected);
      setResults(res);
      setSession({ simulationDone: true });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Simulation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="py-8 space-y-8">
      <div>
        <Link href="/agents" className="text-[#555] text-sm hover:text-white transition-colors">
          ← Back
        </Link>
        <h1 className="text-3xl font-bold mt-4">Simulation Dashboard</h1>
        <p className="text-[#666] mt-2 text-sm">
          Stress-test your agent team across realistic and adverse scenarios before deployment.
        </p>
      </div>

      {/* Scenario selector */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-sm text-[#aaa] uppercase tracking-wider">Select Scenarios</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {ALL_SCENARIOS.map(({ key, label, desc }) => (
            <label
              key={key}
              className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                selected.includes(key)
                  ? "border-white/30 bg-white/5"
                  : "border-[#222] hover:border-[#333]"
              }`}
            >
              <input
                type="checkbox"
                checked={selected.includes(key)}
                onChange={() => toggle(key)}
                className="mt-0.5 accent-white"
              />
              <div>
                <p className="text-sm font-medium text-white">{label}</p>
                <p className="text-xs text-[#555]">{desc}</p>
              </div>
            </label>
          ))}
        </div>

        {!loading && (
          <div className="flex gap-2">
            <button
              onClick={runSimulation}
              disabled={selected.length === 0}
              className="btn-primary flex-1 justify-center"
            >
              Run Simulation →
            </button>
            <Link href="/simulation/live" className="btn-secondary text-center">
              ▶ Live View
            </Link>
          </div>
        )}
        {loading && <Spinner>Running simulation scenarios...</Spinner>}
        {error && <ErrorBox message={error} onRetry={() => setError(null)} />}
      </div>

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-3">
          <h2 className="font-semibold text-sm text-[#aaa] uppercase tracking-wider">Results</h2>
          {results.map((r) => {
            const label = ALL_SCENARIOS.find((s) => s.key === r.scenario)?.label ?? r.scenario;
            return (
              <div key={r.scenario} className="card flex items-start gap-4">
                <div className="text-xl mt-0.5">{STATUS_ICON[r.status]}</div>
                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm">{label}</span>
                    <Badge variant={STATUS_BADGE[r.status]}>
                      {r.status.toUpperCase()}
                    </Badge>
                  </div>
                  <div className="flex gap-5 text-xs text-[#555]">
                    <span>Success rate <strong className="text-white">{(r.success_rate * 100).toFixed(1)}%</strong></span>
                    <span>Avg response <strong className="text-white">{r.avg_response_time_s.toFixed(2)}s</strong></span>
                  </div>
                  <p className="text-xs text-[#666] mt-1">{r.notes}</p>
                </div>
              </div>
            );
          })}

          <div className="flex justify-between pt-2">
            <Link href="/agents" className="btn-secondary">← Back</Link>
            <Link href="/governance" className="btn-primary">Check Agent Health →</Link>
          </div>
        </div>
      )}

      {results.length === 0 && !loading && (
        <div className="flex justify-between pt-2">
          <Link href="/agents" className="btn-secondary">← Back</Link>
        </div>
      )}
    </div>
  );
}
