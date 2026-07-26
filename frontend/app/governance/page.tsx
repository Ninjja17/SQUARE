"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, type GovernanceReport } from "@/lib/api";
import { getSession, setSession } from "@/lib/session";
import { Spinner } from "@/components/Spinner";
import { ErrorBox } from "@/components/ErrorBox";
import { Badge } from "@/components/Badge";

const DECISION_BADGE: Record<string, "passed" | "warning" | "critical" | "new" | "reused"> = {
  Keep: "passed",
  Dismiss: "critical",
  "Promote to Registry": "new",
};

export default function GovernancePage() {
  const router = useRouter();
  const [report, setReport] = useState<GovernanceReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const { workflowId, simulationDone } = getSession();
    if (!workflowId || !simulationDone) {
      router.push("/simulation");
      return;
    }
    api
      .runGovernance(workflowId)
      .then((r) => {
        setReport(r);
        setSession({ governanceDone: true });
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [router]);

  return (
    <div className="py-8 space-y-8">
      <div>
        <Link href="/simulation" className="text-[#555] text-sm hover:text-white transition-colors">
          ← Back
        </Link>
        <h1 className="text-3xl font-bold mt-4">Core Control Agent Report</h1>
        <p className="text-[#666] mt-2 text-sm">
          The governance supervisor validates every agent was created correctly, is healthy,
          and decides which agents to keep, prune, or promote to the registry.
        </p>
      </div>

      {loading && <Spinner>Core Control Agent validating your team...</Spinner>}
      {error && <ErrorBox message={error} />}

      {report && (
        <>
          {/* Summary callout */}
          <div className="card border-white/10 bg-white/[0.02]">
            <p className="text-sm text-[#aaa] leading-relaxed">{report.summary}</p>
          </div>

          {/* Agent table */}
          <div className="card p-0 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#1a1a1a] text-xs text-[#555] uppercase tracking-wider">
                  <th className="text-left px-5 py-3">Agent</th>
                  <th className="text-center px-4 py-3">Created</th>
                  <th className="text-center px-4 py-3">Health</th>
                  <th className="text-left px-5 py-3">Decision</th>
                </tr>
              </thead>
              <tbody>
                {report.agents.map((agent, i) => (
                  <tr
                    key={agent.agent_id}
                    className={`border-b border-[#111] ${i % 2 === 0 ? "bg-transparent" : "bg-white/[0.01]"}`}
                  >
                    <td className="px-5 py-3 font-medium">{agent.agent_name}</td>
                    <td className="px-4 py-3 text-center">
                      {agent.created ? (
                        <span className="text-green-400 font-semibold">✓</span>
                      ) : (
                        <span className="text-red-400 font-semibold">✗</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {agent.healthy ? (
                        <span className="text-green-400 font-semibold">✓</span>
                      ) : (
                        <span className="text-red-400 font-semibold">✗</span>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      <Badge variant={DECISION_BADGE[agent.decision] ?? "default"}>
                        {agent.decision}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-between pt-2">
            <Link href="/simulation" className="btn-secondary">← Back</Link>
            <Link href="/report" className="btn-primary">Generate Executive Report →</Link>
          </div>
        </>
      )}
    </div>
  );
}
