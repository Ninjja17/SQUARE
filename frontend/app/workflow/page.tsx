"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, type Industry } from "@/lib/api";
import { setSession } from "@/lib/session";
import { Spinner } from "@/components/Spinner";
import { ErrorBox } from "@/components/ErrorBox";

const INDUSTRIES: Industry[] = [
  "HR", "BFSI", "Retail", "Manufacturing", "Telecom",
  "Healthcare", "Education", "Government", "Other",
];

const PLACEHOLDER = `Example: We run a university admissions department. Current process:
1. Applicant submits form online
2. Staff manually verifies documents (transcripts, ID)
3. Finance confirms fee payment
4. Admissions committee reviews and decides
5. Staff sends acceptance or rejection letter

We want to automate Document Verification and the notification step.`;

export default function WorkflowPage() {
  const router = useRouter();
  const [description, setDescription] = useState("");
  const [industry, setIndustry] = useState<Industry>("Education");
  const [volume, setVolume] = useState<number>(500);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!description.trim()) return;
    setLoading(true);
    setStatus("Analyzing your workflow with AI...");
    setError(null);
    try {
      const wf = await api.analyzeWorkflow({ industry, monthly_volume: volume, description });
      setSession({ workflowId: wf.workflow_id });
      router.push("/agents");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
      setStatus(null);
    }
  }

  return (
    <div className="max-w-2xl mx-auto py-8 space-y-8">
      <div>
        <Link href="/" className="text-[#555] text-sm hover:text-white transition-colors">
          ← Back
        </Link>
        <h1 className="text-3xl font-bold mt-4">Workflow Input</h1>
        <p className="text-[#666] mt-2 text-sm">
          Describe your current workflow and what you want to automate. SQUARE will extract tasks,
          stakeholders, and automation candidates.
        </p>
        <div className="mt-3 p-3 rounded-lg border border-yellow-400/20 bg-yellow-400/5 text-yellow-300 text-xs">
          ⚠️ Do not enter confidential, personal, or sensitive company data — this is a demonstration environment.
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-[#aaa] mb-2">
            Industry
          </label>
          <select
            value={industry}
            onChange={(e) => setIndustry(e.target.value as Industry)}
            className="w-full bg-[#0a0a0a] border border-[#222] rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-white/40 transition-colors"
          >
            {INDUSTRIES.map((i) => (
              <option key={i} value={i}>{i}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-[#aaa] mb-2">
            Expected Monthly Volume
          </label>
          <input
            type="number"
            min={1}
            value={volume}
            onChange={(e) => setVolume(Number(e.target.value))}
            className="w-full bg-[#0a0a0a] border border-[#222] rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-white/40 transition-colors"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-[#aaa] mb-2">
            Workflow Description
            <span className="text-[#555] font-normal ml-2">({description.length}/2000)</span>
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value.slice(0, 2000))}
            placeholder={PLACEHOLDER}
            rows={10}
            required
            className="w-full bg-[#0a0a0a] border border-[#222] rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-white/40 transition-colors resize-y leading-relaxed placeholder:text-[#333]"
          />
        </div>

        {error && <ErrorBox message={error} onRetry={() => setError(null)} />}

        {loading ? (
          <Spinner>{status || "Processing..."}</Spinner>
        ) : (
          <div className="flex justify-between">
            <Link href="/" className="btn-secondary">← Back</Link>
            <button
              type="submit"
              disabled={!description.trim() || volume < 1}
              className="btn-primary"
            >
              Analyze Workflow →
            </button>
          </div>
        )}
      </form>
    </div>
  );
}
