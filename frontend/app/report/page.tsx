"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, type ExecutiveReport } from "@/lib/api";
import { getSession, setSession } from "@/lib/session";
import { Spinner } from "@/components/Spinner";
import { ErrorBox } from "@/components/ErrorBox";
import { MetricCard } from "@/components/MetricCard";
import { Badge } from "@/components/Badge";
import { MotionDiv } from "@/components/MotionDiv";

const RISK_COLOR = (score: number) => {
  if (score < 30) return "bg-green-500";
  if (score < 55) return "bg-yellow-400";
  if (score < 75) return "bg-orange-400";
  return "bg-red-500";
};

const GO_BADGE: Record<string, "go" | "pilot" | "changes"> = {
  GO: "go",
  PILOT_FIRST: "pilot",
  NEEDS_CHANGES: "changes",
};

const GO_LABEL: Record<string, string> = {
  GO: "✅ GO",
  PILOT_FIRST: "⚠️ PILOT FIRST",
  NEEDS_CHANGES: "🚫 NEEDS CHANGES",
};

export default function ReportPage() {
  const router = useRouter();
  const [report, setReport] = useState<ExecutiveReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const { workflowId, governanceDone } = getSession();
    if (!workflowId || !governanceDone) {
      router.push("/governance");
      return;
    }
    // Run risk + ROI analyses in parallel, then generate report
    Promise.all([
      api.analyzeRisk(workflowId),
      api.analyzeROI(workflowId),
    ])
      .then(async () => {
        const r = await api.generateReport(workflowId);
        setReport(r);
        setSession({ reportDone: true });
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [router]);

  const { workflowId } = getSession();

  return (
    <div className="py-8 space-y-10">
      <div>
        <Link href="/governance" className="text-[#555] text-sm hover:text-white transition-colors">
          ← Back
        </Link>
        <h1 className="text-3xl font-bold mt-4">Executive Readiness Report</h1>
        <p className="text-[#666] mt-2 text-sm">
          Your complete pre-deployment analysis — automation score, risk, ROI, and deployment recommendation.
        </p>
      </div>

      {loading && <Spinner>Generating your Executive Report...</Spinner>}
      {error && <ErrorBox message={error} />}

      {report && (
        <>
          {/* Key Metrics */}
          <MotionDiv delay={0.1}>
          <section className="space-y-3">
            <h2 className="text-xs uppercase tracking-widest text-[#555]">Key Metrics at a Glance</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <MetricCard label="Automation Score" value={`${report.automation_score.toFixed(1)}%`} highlight />
              <MetricCard
                label="Year 1 ROI"
                value={`${report.roi_report.roi_percent_year1.toFixed(0)}%`}
                highlight
              />
              <MetricCard
                label="Annual Savings"
                value={`$${(report.roi_report.annual_savings / 1000).toFixed(0)}k`}
              />
              <MetricCard
                label="Payback Period"
                value={`${report.roi_report.payback_period_months.toFixed(1)} mo`}
              />
              <MetricCard
                label="FTE Reduction"
                value={report.roi_report.fte_reduction.toFixed(1)}
                sub="full-time equivalents"
              />
              <MetricCard
                label="Overall Risk Score"
                value={`${report.risk_report.overall_score.toFixed(0)}/100`}
                sub={report.risk_report.overall_score < 50 ? "Low-Medium" : "High"}
              />
            </div>
          </section>
          </MotionDiv>

          {/* ROI Sensitivity Analysis */}
          {report.roi_report.sensitivity && report.roi_report.sensitivity.best_case && (
            <MotionDiv delay={0.25}>
            <section className="space-y-3">
              <h2 className="text-xs uppercase tracking-widest text-[#555]">ROI Sensitivity Analysis</h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="card border border-green-500/30 bg-green-500/5">
                  <p className="text-xs uppercase tracking-widest text-green-400 mb-2">Best Case</p>
                  <p className="text-2xl font-bold text-green-400">{report.roi_report.sensitivity.best_case.roi_percent.toFixed(0)}%</p>
                  <p className="text-xs text-[#666] mt-1">ROI</p>
                  <p className="text-lg font-semibold text-green-400 mt-2">{report.roi_report.sensitivity.best_case.payback_months.toFixed(1)} mo</p>
                  <p className="text-xs text-[#666]">Payback Period</p>
                </div>
                <div className="card border border-[#333]">
                  <p className="text-xs uppercase tracking-widest text-[#888] mb-2">Expected</p>
                  <p className="text-2xl font-bold text-white">{report.roi_report.sensitivity.expected.roi_percent.toFixed(0)}%</p>
                  <p className="text-xs text-[#666] mt-1">ROI</p>
                  <p className="text-lg font-semibold text-white mt-2">{report.roi_report.sensitivity.expected.payback_months.toFixed(1)} mo</p>
                  <p className="text-xs text-[#666]">Payback Period</p>
                </div>
                <div className="card border border-orange-500/30 bg-orange-500/5">
                  <p className="text-xs uppercase tracking-widest text-orange-400 mb-2">Worst Case</p>
                  <p className="text-2xl font-bold text-orange-400">{report.roi_report.sensitivity.worst_case.roi_percent.toFixed(0)}%</p>
                  <p className="text-xs text-[#666] mt-1">ROI</p>
                  <p className="text-lg font-semibold text-orange-400 mt-2">{report.roi_report.sensitivity.worst_case.payback_months.toFixed(1)} mo</p>
                  <p className="text-xs text-[#666]">Payback Period</p>
                </div>
              </div>
            </section>
            </MotionDiv>
          )}

          {/* Go / No-Go */}
          <section className="card flex items-center gap-5">
            <div className="flex-1">
              <p className="text-xs uppercase tracking-widest text-[#555] mb-2">Deployment Recommendation</p>
              <Badge
                variant={GO_BADGE[report.go_no_go] ?? "default"}
                className="text-base px-4 py-1.5"
              >
                {GO_LABEL[report.go_no_go]}
              </Badge>
              <p className="text-sm text-[#666] mt-3 leading-relaxed">
                {report.deployment_plan.justification}
              </p>
            </div>
          </section>

          {/* Risk Breakdown */}
          <section className="space-y-3">
            <h2 className="text-xs uppercase tracking-widest text-[#555]">Risk Breakdown</h2>
            <div className="card space-y-4">
              {report.risk_report.categories.map((cat) => (
                <div key={cat.name} className="space-y-1.5">
                  <div className="flex justify-between text-sm">
                    <span className="text-[#aaa]">{cat.name}</span>
                    <span
                      className={
                        cat.score < 30
                          ? "text-green-400"
                          : cat.score < 55
                          ? "text-yellow-400"
                          : cat.score < 75
                          ? "text-orange-400"
                          : "text-red-400"
                      }
                    >
                      {cat.score}/100
                    </span>
                  </div>
                  <div className="score-bar-track">
                    <div
                      className={`h-2 rounded-full ${RISK_COLOR(cat.score)} transition-all`}
                      style={{ width: `${cat.score}%` }}
                    />
                  </div>
                  <p className="text-xs text-[#555]">{cat.justification}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Recommendations */}
          <section className="space-y-3">
            <h2 className="text-xs uppercase tracking-widest text-[#555]">Recommendations</h2>
            <div className="card space-y-2">
              {report.risk_report.recommendations.map((rec, i) => (
                <div key={i} className="flex items-start gap-3 text-sm text-[#888]">
                  <span className="text-white mt-0.5">•</span>
                  <span>{rec}</span>
                </div>
              ))}
            </div>
          </section>

          {/* Deployment Timeline */}
          <section className="space-y-3">
            <h2 className="text-xs uppercase tracking-widest text-[#555]">Deployment Timeline</h2>
            <div className="space-y-3">
              {report.deployment_plan.phases.map((phase, i) => (
                <div key={i} className="card space-y-2">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-sm">{phase.name}</h3>
                    <div className="flex gap-2 text-xs text-[#555]">
                      <span>Scope <strong className="text-white">{phase.scope_percent}%</strong></span>
                      <span>Human oversight <strong className="text-white">{phase.human_oversight_percent}%</strong></span>
                    </div>
                  </div>
                  <p className="text-xs text-[#666]">{phase.success_criteria}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Actions */}
          <div className="flex items-center justify-between pt-2">
            <Link href="/governance" className="btn-secondary">← Back</Link>
            {workflowId && (
              <a
                href={api.downloadPDF(workflowId)}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-primary"
              >
                📄 Download Report
              </a>
            )}
          </div>
        </>
      )}
    </div>
  );
}
