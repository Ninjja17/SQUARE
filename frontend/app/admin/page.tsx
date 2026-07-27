"use client";

/**
 * /admin — Internal backend operations dashboard.
 * NOT in client navigation. Access directly via URL.
 *
 * Requires the ADMIN_DASHBOARD_TOKEN set in backend/.env.
 */

import { useState, useCallback } from "react";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ─── Types ────────────────────────────────────────────────────────────────────

interface OverviewCounts {
  workflows: number;
  agents_generated: number;
  simulations_run: number;
  governance_reports: number;
  risk_reports: number;
  roi_reports: number;
  executive_reports: number;
}

interface OverviewConfig {
  rate_limit_per_hour: number;
  chroma_db_path: string;
  orchestrate_configured: boolean;
  groq_key_set: boolean;
}

interface Overview {
  timestamp: string;
  uptime_seconds: number;
  demo_mode: boolean;
  model: string;
  provider: string;
  counts: OverviewCounts;
  config: OverviewConfig;
}

interface HealthCheck {
  status: "ok" | "degraded" | string;
  timestamp: string;
  uptime_seconds: number;
  demo_mode: boolean;
  chroma_agent_registry?: { status: string; doc_count?: number; detail?: string };
  compliance_rag?: { status: string; doc_count?: number; detail?: string };
  cache_sizes?: Record<string, number>;
  modules?: Record<string, string>;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function adminFetch<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "X-Admin-Token": token, "Content-Type": "application/json" },
  });
  if (res.status === 401) throw new Error("Invalid or missing admin token (401)");
  if (!res.ok) throw new Error(`HTTP ${res.status} from ${path}`);
  return res.json();
}

function fmt(n: number | undefined) {
  return n?.toLocaleString() ?? "—";
}

function uptimeStr(seconds: number) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string | number;
  sub?: string;
  accent?: string;
}) {
  return (
    <div className="bg-[#0a0a0a] border border-[#222] rounded-xl p-5">
      <p className="text-[10px] uppercase tracking-widest text-[#555] mb-1">{label}</p>
      <p className={`text-3xl font-black ${accent ?? "text-white"}`}>{value}</p>
      {sub && <p className="text-xs text-[#555] mt-1">{sub}</p>}
    </div>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-[10px] uppercase tracking-[0.18em] text-[#444] mt-8 mb-3 border-t border-[#1a1a1a] pt-6">
      {children}
    </h2>
  );
}

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full mr-2 ${ok ? "bg-green-400" : "bg-orange-400"}`}
    />
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const [token, setToken]       = useState("");
  const [authed, setAuthed]     = useState(false);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [health, setHealth]     = useState<HealthCheck | null>(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);

  const load = useCallback(async (t: string) => {
    setLoading(true);
    setError(null);
    try {
      const [ov, hc] = await Promise.all([
        adminFetch<Overview>("/api/admin/overview", t),
        adminFetch<HealthCheck>("/api/admin/health", t),
      ]);
      setOverview(ov);
      setHealth(hc);
      setAuthed(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
      setAuthed(false);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (token.trim()) load(token.trim());
  };

  // ── Token gate ──────────────────────────────────────────────────────────────
  if (!authed) {
    return (
      <div className="min-h-screen bg-black text-white flex items-center justify-center px-4">
        <div className="w-full max-w-sm space-y-6">
          <div className="text-center space-y-1">
            <p className="text-[10px] uppercase tracking-[0.2em] text-[#444]">Internal use only</p>
            <h1 className="text-2xl font-bold">▣ SQUARE Admin</h1>
            <p className="text-xs text-[#555]">Backend operations dashboard</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            <input
              type="password"
              placeholder="Admin token"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="w-full bg-[#0a0a0a] border border-[#333] rounded-lg px-4 py-3 text-sm text-white placeholder-[#444] focus:border-white/30 focus:outline-none"
              autoFocus
            />
            <button
              type="submit"
              disabled={loading || !token.trim()}
              className="w-full bg-white text-black rounded-lg py-3 text-sm font-semibold disabled:opacity-40"
            >
              {loading ? "Connecting…" : "Connect →"}
            </button>
          </form>

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3">
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Dashboard ────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-black text-white">
      {/* Header */}
      <header className="border-b border-[#1a1a1a] bg-black/90 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-white">▣</span>
            <span className="font-bold">SQUARE Admin</span>
            <span className="text-[10px] uppercase tracking-wider text-[#444] border border-[#222] rounded px-2 py-0.5">
              Internal
            </span>
          </div>
          <div className="flex items-center gap-3">
            {health && (
              <span className="flex items-center text-xs text-[#555]">
                <StatusDot ok={health.status === "ok"} />
                {health.status === "ok" ? "All systems OK" : "Degraded"}
              </span>
            )}
            <button
              onClick={() => load(token)}
              disabled={loading}
              className="text-xs border border-[#333] rounded px-3 py-1.5 text-[#888] hover:text-white hover:border-[#555] transition-colors disabled:opacity-40"
            >
              {loading ? "Refreshing…" : "↺ Refresh"}
            </button>
            <button
              onClick={() => { setAuthed(false); setOverview(null); setHealth(null); }}
              className="text-xs text-[#555] hover:text-white transition-colors"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 space-y-2">

        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 mb-4">
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        )}

        {/* Server info strip */}
        {overview && (
          <div className="flex flex-wrap gap-4 text-xs text-[#555] pb-2">
            <span>Uptime <strong className="text-[#888]">{uptimeStr(overview.uptime_seconds)}</strong></span>
            <span>Model <strong className="text-[#888]">{overview.model}</strong></span>
            <span>Provider <strong className="text-[#888]">{overview.provider}</strong></span>
            <span>
              Mode{" "}
              <strong className={overview.demo_mode ? "text-yellow-400" : "text-green-400"}>
                {overview.demo_mode ? "DEMO" : "LIVE"}
              </strong>
            </span>
            <span className="ml-auto text-[#333]">
              {new Date(overview.timestamp).toLocaleTimeString()}
            </span>
          </div>
        )}

        {/* Pipeline counts */}
        <SectionHeading>Pipeline Counts</SectionHeading>
        {overview ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="Workflows"          value={fmt(overview.counts.workflows)} />
            <StatCard label="Agents Generated"   value={fmt(overview.counts.agents_generated)} />
            <StatCard label="Simulations Run"    value={fmt(overview.counts.simulations_run)} />
            <StatCard label="Governance Reports" value={fmt(overview.counts.governance_reports)} />
            <StatCard label="Risk Reports"       value={fmt(overview.counts.risk_reports)} />
            <StatCard label="ROI Reports"        value={fmt(overview.counts.roi_reports)} />
            <StatCard
              label="Executive Reports"
              value={fmt(overview.counts.executive_reports)}
              accent="text-green-400"
            />
            <StatCard
              label="Rate Limit"
              value={`${overview.config.rate_limit_per_hour}/hr`}
              sub="per IP"
            />
          </div>
        ) : (
          <div className="h-24 flex items-center justify-center text-[#444] text-sm">
            Loading…
          </div>
        )}

        {/* Config flags */}
        {overview && (
          <>
            <SectionHeading>Configuration</SectionHeading>
            <div className="bg-[#0a0a0a] border border-[#222] rounded-xl p-5 grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-[10px] uppercase tracking-widest text-[#555] mb-1">Groq API Key</p>
                <p className="flex items-center">
                  <StatusDot ok={overview.config.groq_key_set} />
                  {overview.config.groq_key_set ? "Set" : "Missing"}
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-widest text-[#555] mb-1">Orchestrate</p>
                <p className="flex items-center">
                  <StatusDot ok={overview.config.orchestrate_configured} />
                  {overview.config.orchestrate_configured ? "Configured" : "Not set"}
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-widest text-[#555] mb-1">ChromaDB Path</p>
                <p className="text-[#888] font-mono text-xs truncate">{overview.config.chroma_db_path}</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-widest text-[#555] mb-1">Rate Limit</p>
                <p className="text-[#888]">{overview.config.rate_limit_per_hour} / hour / IP</p>
              </div>
            </div>
          </>
        )}

        {/* Health diagnostics */}
        {health && (
          <>
            <SectionHeading>System Health</SectionHeading>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">

              {/* Chroma agent registry */}
              <div className="bg-[#0a0a0a] border border-[#222] rounded-xl p-5 space-y-2">
                <p className="text-[10px] uppercase tracking-widest text-[#555]">Agent Registry (ChromaDB)</p>
                <p className="flex items-center text-sm">
                  <StatusDot ok={health.chroma_agent_registry?.status === "ok"} />
                  {health.chroma_agent_registry?.status ?? "—"}
                </p>
                {health.chroma_agent_registry?.doc_count !== undefined && (
                  <p className="text-xs text-[#555]">{health.chroma_agent_registry.doc_count} seed agents</p>
                )}
                {health.chroma_agent_registry?.detail && (
                  <p className="text-xs text-orange-400 font-mono break-all">{health.chroma_agent_registry.detail}</p>
                )}
              </div>

              {/* Compliance RAG */}
              <div className="bg-[#0a0a0a] border border-[#222] rounded-xl p-5 space-y-2">
                <p className="text-[10px] uppercase tracking-widest text-[#555]">Compliance RAG</p>
                <p className="flex items-center text-sm">
                  <StatusDot ok={health.compliance_rag?.status !== "degraded"} />
                  {health.compliance_rag?.status ?? "—"}
                </p>
                {health.compliance_rag?.doc_count !== undefined && (
                  <p className="text-xs text-[#555]">{health.compliance_rag.doc_count} compliance docs</p>
                )}
                {health.compliance_rag?.detail && (
                  <p className="text-xs text-orange-400 font-mono break-all">{health.compliance_rag.detail}</p>
                )}
              </div>

              {/* Cache sizes */}
              {health.cache_sizes && (
                <div className="bg-[#0a0a0a] border border-[#222] rounded-xl p-5 space-y-2 sm:col-span-2">
                  <p className="text-[10px] uppercase tracking-widest text-[#555]">In-Memory Cache Sizes</p>
                  <div className="grid grid-cols-3 sm:grid-cols-7 gap-3 pt-1">
                    {Object.entries(health.cache_sizes).map(([k, v]) => (
                      <div key={k} className="text-center">
                        <p className="text-xl font-black text-white">{v}</p>
                        <p className="text-[9px] uppercase tracking-wider text-[#444] mt-0.5">{k}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Module status */}
            {health.modules && (
              <>
                <SectionHeading>Service Modules</SectionHeading>
                <div className="bg-[#0a0a0a] border border-[#222] rounded-xl p-5">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {Object.entries(health.modules).map(([mod, st]) => (
                      <div key={mod} className="flex items-center gap-2 text-sm">
                        <StatusDot ok={st === "ok"} />
                        <span className="text-[#888] font-mono text-xs w-40 truncate">{mod}</span>
                        <span className={st === "ok" ? "text-green-400 text-xs" : "text-orange-400 text-xs"}>
                          {st === "ok" ? "ok" : st}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </>
        )}

        {/* Footer */}
        <div className="pt-10 pb-6 text-center text-[10px] text-[#333] border-t border-[#111] mt-8">
          SQUARE Admin — Internal use only. Do not share this URL or token.
        </div>

      </main>
    </div>
  );
}
