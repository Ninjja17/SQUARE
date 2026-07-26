"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { RotatingWords } from "@/components/RotatingWords";
import { MotionDiv } from "@/components/MotionDiv";

const HOW_IT_WORKS = [
  {
    step: "01",
    title: "Describe",
    desc: "Enter your current business workflow in plain English — what the process is, who's involved, and what you want automated.",
    icon: "📝",
  },
  {
    step: "02",
    title: "Generate",
    desc: "SQUARE builds a team of specialized AI agents mapped to your workflow tasks. Reusable agents are pulled from the cross-sector registry.",
    icon: "🤖",
  },
  {
    step: "03",
    title: "Simulate",
    desc: "Every agent is stress-tested across 6 scenarios — Happy Path, Agent Failure, Wrong Decision, High Workload, and more.",
    icon: "⚡",
  },
  {
    step: "04",
    title: "Analyze",
    desc: "Get an Executive Readiness Report: Risk Score, ROI, Payback Period, and a Go / Pilot First / Needs Changes deployment recommendation.",
    icon: "📊",
  },
];

export default function HomePage() {
  return (
    <div className="space-y-24 py-8">
      {/* Background gradient orb */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden -z-10">
        <div
          className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full opacity-[0.07]"
          style={{
            background: "radial-gradient(circle, rgba(255,255,255,0.4) 0%, transparent 70%)",
            animation: "float 20s ease-in-out infinite",
          }}
        />
        <div
          className="absolute bottom-1/4 right-1/4 w-[400px] h-[400px] rounded-full opacity-[0.05]"
          style={{
            background: "radial-gradient(circle, rgba(100,200,255,0.3) 0%, transparent 70%)",
            animation: "float 25s ease-in-out infinite reverse",
          }}
        />
      </div>

      {/* Hero */}
      <section className="text-center space-y-8 pt-16 relative">
        <MotionDiv delay={0} blur>
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/[0.05] border border-white/10 text-xs text-[#aaa] mb-6">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            Enterprise Agent Engineering Platform
          </div>
        </MotionDiv>

        <MotionDiv delay={0.15} blur>
          <h1 className="text-5xl sm:text-6xl font-bold tracking-tight leading-[1.1]">
            Describe your workflow.
            <br />
            <span className="text-[#888]">
              {"We'll build the AI "}
              <RotatingWords
                words={["workforce", "agents", "team", "system"]}
                className="text-white"
              />
            </span>
          </h1>
        </MotionDiv>

        <MotionDiv delay={0.3} blur>
          <p className="text-lg text-[#666] max-w-xl mx-auto">
            Turn a plain-English workflow description into a validated, cost/risk-scored, reusable AI agent team — before a single agent touches production.
          </p>
        </MotionDiv>

        <MotionDiv delay={0.45}>
          <div className="flex items-center justify-center gap-4 pt-4">
            <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
              <Link href="/workflow" className="btn-primary text-base px-8 py-3">
                Get Started →
              </Link>
            </motion.div>
            <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
              <Link href="/simulation/live" className="btn-secondary text-base px-8 py-3">
                ▶ Watch Demo
              </Link>
            </motion.div>
          </div>
        </MotionDiv>
      </section>

      {/* How It Works */}
      <section className="space-y-10">
        <MotionDiv delay={0.2} className="text-center">
          <h2 className="text-xs uppercase tracking-[0.2em] text-[#555] mb-3">How It Works</h2>
          <p className="text-2xl font-semibold">Four steps to AI-ready</p>
        </MotionDiv>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {HOW_IT_WORKS.map((item, i) => (
            <MotionDiv key={item.step} delay={0.3 + i * 0.12} blur>
              <motion.div
                whileHover={{ y: -4, scale: 1.01 }}
                transition={{ type: "spring", stiffness: 300, damping: 20 }}
                className="card relative overflow-hidden group"
              >
                <div className="absolute top-0 right-0 text-[80px] font-black text-white/[0.03] leading-none select-none">
                  {item.step}
                </div>
                <div className="relative z-10 space-y-3">
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">{item.icon}</span>
                    <div>
                      <span className="text-[10px] uppercase tracking-wider text-[#555]">Step {item.step}</span>
                      <h3 className="text-lg font-semibold">{item.title}</h3>
                    </div>
                  </div>
                  <p className="text-sm text-[#666] leading-relaxed">{item.desc}</p>
                </div>
              </motion.div>
            </MotionDiv>
          ))}
        </div>
      </section>

      {/* Footer */}
      <MotionDiv delay={0.3} className="text-center pb-16 space-y-4">
        <h2 className="text-6xl sm:text-8xl font-black tracking-tighter text-white/[0.08] select-none">
          SQUARE
        </h2>
        <p className="text-sm text-[#555]">
          Built by Shibani With IBM BoB
        </p>
      </MotionDiv>
    </div>
  );
}
