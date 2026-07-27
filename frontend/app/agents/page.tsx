"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, type Agent } from "@/lib/api";
import { getSession, setSession } from "@/lib/session";
import { Spinner } from "@/components/Spinner";
import { ErrorBox } from "@/components/ErrorBox";
import { Badge } from "@/components/Badge";
import { MotionDiv } from "@/components/MotionDiv";

const AGENT_ICONS: Record<string, string> = {
  Analyzer: "🔍",
  Verification: "✅",
  Decision: "⚖️",
  Communication: "📨",
  Risk: "🛡️",
  Planner: "🗺️",
};

/** Renders a Mermaid diagram by injecting mermaid.js from CDN once. */
function MermaidDiagram({ definition }: { definition: string }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!definition || !containerRef.current) return;

    const render = () => {
      if (!containerRef.current) return;
      // @ts-expect-error mermaid is loaded as global via CDN script
      window.mermaid?.run({ nodes: [containerRef.current] });
    };

    // @ts-expect-error mermaid is loaded as global via CDN script
    if (typeof window !== "undefined" && window.mermaid) {
      render();
    } else {
      // Inject CDN script once
      const existing = document.getElementById("mermaid-cdn");
      if (!existing) {
        const script = document.createElement("script");
        script.id = "mermaid-cdn";
        script.src = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js";
        script.onload = () => {
          // @ts-expect-error mermaid is loaded as global via CDN script
          window.mermaid?.initialize({ startOnLoad: false, theme: "dark", darkMode: true });
          render();
        };
        document.head.appendChild(script);
      } else {
        // Script loading — retry after short delay
        setTimeout(render, 800);
      }
    }
  }, [definition]);

  return (
    <div
      ref={containerRef}
      className="mermaid w-full overflow-x-auto text-sm"
      style={{ background: "transparent" }}
    >
      {definition}
    </div>
  );
}

export default function AgentsPage() {
  const router = useRouter();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [mermaidDef, setMermaidDef] = useState<string | null>(null);
  const [showGraph, setShowGraph] = useState(false);

  useEffect(() => {
    const { workflowId: wfId } = getSession();
    if (!wfId) {
      // No session yet — redirect to workflow input
      router.push("/workflow");
      return;
    }
    setWorkflowId(wfId);

    // Only generate agents once per workflow — if already generated, just fetch
    api
      .generateAgents(wfId)
      .then((a) => {
        setAgents(a);
        setSession({ agentsGenerated: true });
        // Fetch graph after agents are ready
        return api.getAgentGraph(wfId);
      })
      .then((g) => setMermaidDef(g.mermaid))
      .catch((e) => {
        // Try fetching already-generated agents as fallback
        api
          .getAgents(wfId)
          .then((a) => {
            setAgents(a);
            return api.getAgentGraph(wfId);
          })
          .then((g) => setMermaidDef(g.mermaid))
          .catch(() => setError(e.message));
      })
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const reused = agents.filter((a) => a.source === "reused").length;
  const created = agents.filter((a) => a.source === "new").length;

  const loadGraph = useCallback(async () => {
    if (!workflowId) return;
    try {
      const g = await api.getAgentGraph(workflowId);
      setMermaidDef(g.mermaid);
      setShowGraph(true);
    } catch { /* ignore */ }
  }, [workflowId]);

  return (
    <div className="py-8 space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <Link href="/workflow" className="text-[#555] text-sm hover:text-white transition-colors">
            ← Back
          </Link>
          <h1 className="text-3xl font-bold mt-4">Your Generated Agent Team</h1>
          {!loading && !error && agents.length > 0 && (
            <p className="text-[#666] mt-2 text-sm">
              {agents.length} agents generated
              {reused > 0 && ` — ${reused} reused from registry`}
              {created > 0 && `, ${created} newly created`}
            </p>
          )}
        </div>
      </div>

      {loading && <Spinner>Building your AI agent team — checking registry for reusable agents...</Spinner>}
      {error && <ErrorBox message={error} onRetry={() => {
        if (workflowId) {
          setError(null);
          setLoading(true);
          api.generateAgents(workflowId)
            .then((a) => { setAgents(a); setSession({ agentsGenerated: true }); })
            .catch((e) => setError(e.message))
            .finally(() => setLoading(false));
        }
      }} />}

      {!loading && !error && agents.length > 0 && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {agents.map((agent, i) => (
              <MotionDiv key={agent.agent_id} delay={i * 0.1} blur>
                <div className="card space-y-4 hover:scale-[1.01] transition-transform">
                  <div className="flex items-start gap-3">
                    <span className="text-2xl">{AGENT_ICONS[agent.agent_type] ?? "🤖"}</span>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-white">{agent.agent_type} Agent</h3>
                      <Badge variant={agent.source === "reused" ? "reused" : "new"}>
                        {agent.source === "reused" ? "🔁 Reused from Registry" : "✨ Newly Generated"}
                      </Badge>
                    </div>
                  </div>
                  <p className="text-sm text-[#888] leading-relaxed">{agent.responsibility}</p>
                  <div className="flex flex-wrap gap-4 text-xs text-[#555]">
                    <span>Accuracy <strong className="text-white">{(agent.metrics.accuracy * 100).toFixed(1)}%</strong></span>
                    <span>Response <strong className="text-white">{agent.metrics.processing_time_s.toFixed(1)}s</strong></span>
                    <span>Uptime <strong className="text-white">{(agent.metrics.uptime * 100).toFixed(2)}%</strong></span>
                  </div>
                </div>
              </MotionDiv>
            ))}
          </div>

          {/* Agent Dependency Graph */}
          {mermaidDef && (
            <MotionDiv delay={0.4}>
              <div className="card space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="font-semibold text-sm text-[#aaa] uppercase tracking-wider">
                      Agent Dependency Graph
                    </h2>
                    <p className="text-xs text-[#555] mt-0.5">
                      Visualises handoff order between agents in the pipeline.
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      setShowGraph((v) => !v);
                      if (!showGraph) loadGraph();
                    }}
                    className="text-xs text-[#555] hover:text-white transition-colors border border-[#333] rounded px-3 py-1"
                  >
                    {showGraph ? "Hide" : "Show"} Graph
                  </button>
                </div>
                {showGraph && (
                  <div className="rounded-lg border border-[#222] bg-[#080808] p-4 min-h-[120px]">
                    <MermaidDiagram definition={mermaidDef} />
                  </div>
                )}
              </div>
            </MotionDiv>
          )}

          <div className="flex justify-between pt-2">
            <Link href="/workflow" className="btn-secondary">← Back</Link>
            <Link href="/simulation" className="btn-primary">Run Simulation →</Link>
          </div>
        </>
      )}

      {!loading && !error && agents.length === 0 && (
        <div className="card text-center py-12 text-[#555]">
          <p className="text-sm">No agents generated yet.</p>
          <Link href="/workflow" className="btn-secondary mt-4 inline-flex">
            Start from Workflow →
          </Link>
        </div>
      )}
    </div>
  );
}
