# ▣ SQUARE — Enterprise Agent Engineering Platform

> **"Describe your workflow. We'll build the AI workforce."**

SQUARE is an Enterprise Agent Engineering Platform that turns a plain-English workflow description into a validated, cost/risk-scored, reusable AI agent team — before a single agent touches production.

---

## What SQUARE Does

Enterprises want to automate workflows but can't confidently answer:
- Which tasks should actually be automated?
- Which AI agents are required, and which are redundant?
- What happens if an agent fails or makes a wrong decision?
- What are the security/compliance risks?
- What is the expected ROI and payback period?

**SQUARE answers all of these before production deployment.**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                         │
│  Home → Workflow Input → Agents → Simulation → Governance    │
│         → Live View → Risk/ROI → Executive Report            │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST API
┌──────────────────────────▼──────────────────────────────────┐
│                    Backend (FastAPI)                          │
│                                                              │
│  ┌─────────────────┐  ┌──────────────────┐                 │
│  │ Workflow Engine  │  │ Agent Generation │                  │
│  │ (Parses input)  │  │ (Creates agents) │                  │
│  └────────┬────────┘  └────────┬─────────┘                 │
│           │                     │                            │
│  ┌────────▼─────────────────────▼─────────┐                │
│  │         Common Agent Registry           │                 │
│  │    (ChromaDB — vector similarity)       │                 │
│  │  Reusable agents across industries      │                 │
│  └────────────────────┬───────────────────┘                 │
│                       │                                      │
│  ┌────────────────────▼───────────────────┐                 │
│  │        Simulation Engine               │                  │
│  │  6 scenarios: Happy Path, Agent        │                  │
│  │  Failure, Wrong Decision, High         │                  │
│  │  Workload, External Failure,           │                  │
│  │  Human Override                        │                  │
│  └────────────────────┬───────────────────┘                 │
│                       │                                      │
│  ┌────────────────────▼───────────────────┐                 │
│  │     Core Control Agent (Governance)     │                 │
│  │  Keep / Dismiss / Promote to Registry   │                 │
│  └────────────────────┬───────────────────┘                 │
│                       │                                      │
│  ┌──────────┐  ┌──────▼─────┐  ┌────────────────┐         │
│  │Risk Engine│  │ ROI Engine │  │Deployment Advisor│         │
│  │(0-100)   │  │(Savings,%) │  │(Go/Pilot/Change)│          │
│  └──────────┘  └────────────┘  └────────────────┘          │
│                                                              │
│  ┌──────────────────────────────────────────┐               │
│  │         LLM Provider (Groq/Llama 3.3)    │               │
│  └──────────────────────────────────────────┘               │
│                                                              │
│  ┌──────────────────────────────────────────┐               │
│  │    IBM watsonx Orchestrate (Agent Coord)  │              │
│  └──────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

---

## Agent Types

SQUARE generates agents from a fixed template set:

| Agent Type | Role |
|-----------|------|
| 🔍 **Analyzer** | Extracts insights from unstructured workflow input |
| ✅ **Verification** | Validates documents, records, and data quality |
| ⚖️ **Decision** | Makes accept/reject/approve recommendations |
| 📨 **Communication** | Sends notifications and manages user interactions |
| 🛡️ **Risk** | Identifies operational, compliance, and security risks |
| 🗺️ **Planner** | Generates rollout strategy and implementation plans |

Agents are **reusable across industries**. The Common Agent Registry stores promoted agents and retrieves them via vector similarity matching for future workflows.

---

## IBM Integration

### IBM Bob (Development IDE)
SQUARE was built using **IBM Bob IDE** as the primary development environment for building, testing, and deploying the application.

### IBM watsonx Orchestrate
SQUARE integrates with **IBM watsonx Orchestrate** for enterprise-grade agent coordination and execution:
- **Instance**: Frankfurt (eu-de) region
- **Role**: Orchestrates multi-agent workflows and manages digital employee interactions
- **API**: RESTful endpoint integration for agent lifecycle management

The platform uses watsonx Orchestrate to coordinate how generated agents communicate and hand off tasks between each other during simulation and deployment.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, React 18, Tailwind CSS, Framer Motion |
| Backend | Python, FastAPI, Pydantic |
| LLM | Groq (Llama 3.3 70B) — fast, free inference |
| Vector DB | ChromaDB (embedded, for Agent Registry) |
| Agent Orchestration | IBM watsonx Orchestrate |
| IDE | IBM Bob |

---

## Core Flow

1. **Input** → Enterprise describes workflow + what to automate
2. **Workflow Engine** → Parses tasks, stakeholders, automation candidates
3. **Agent Generation** → Creates/reuses agents from registry
4. **Simulation** → Stress-tests agents across 6 scenarios
5. **Governance** → Core Control Agent validates, prunes, promotes agents
6. **Risk + ROI** → Compliance-aware scoring + financial analysis
7. **Report** → Executive Readiness Report with Go/Pilot/Needs Changes recommendation

---

## Local Setup

```bash
# Backend
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

Copy `.env.example` to `backend/.env` and fill in your API keys.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Groq API key for LLM inference |
| `GROQ_MODEL` | Model name (default: `llama-3.3-70b-versatile`) |
| `ORCHESTRATE_INSTANCE_URL` | IBM watsonx Orchestrate endpoint |
| `ORCHESTRATE_API_KEY` | IBM Cloud API key for Orchestrate |
| `DEMO_MODE` | `True` for mock data, `False` for real AI |

---

## Built By

**Shibani** — Built with IBM BoB

---
