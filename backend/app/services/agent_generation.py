"""Agent Generation Engine — checks Common Agent Registry first, then generates new agents."""
from __future__ import annotations

import json
import logging
import uuid

from app.config import get_settings
from app.db.chroma_client import find_similar_agents, find_agent_by_type
from app.models.schemas import AgentMetrics, AgentResponse, AgentSourceEnum, AgentTypeEnum
from app.prompts.templates import AGENT_GENERATION_SYSTEM, AGENT_GENERATION_USER

logger = logging.getLogger(__name__)
settings = get_settings()

SIMILARITY_THRESHOLD = 0.60  # cosine distance — lower = more similar; 0.6 is generous to favor reuse

MOCK_AGENTS = [
    {
        "agent_type": "Verification",
        "responsibility": "Validates student documents including transcripts, ID, and certificates",
        "source": "reused",
        "metrics": {"accuracy": 0.98, "processing_time_s": 1.2, "uptime": 0.999},
    },
    {
        "agent_type": "Decision",
        "responsibility": "Evaluates verified applications and recommends accept/reject/waitlist",
        "source": "reused",
        "metrics": {"accuracy": 0.95, "processing_time_s": 2.1, "uptime": 0.997},
    },
    {
        "agent_type": "Communication",
        "responsibility": "Sends automated acceptance/rejection notifications and status updates",
        "source": "reused",
        "metrics": {"accuracy": 0.998, "processing_time_s": 0.3, "uptime": 0.9999},
    },
    {
        "agent_type": "Analyzer",
        "responsibility": "Analyzes application completeness and flags missing items for follow-up",
        "source": "new",
        "metrics": {"accuracy": 0.96, "processing_time_s": 1.8, "uptime": 0.998},
    },
]


async def generate_agents(workflow_id: str, automation_candidates: list[dict]) -> list[AgentResponse]:
    if settings.DEMO_MODE:
        return [
            AgentResponse(
                agent_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                agent_type=AgentTypeEnum(a["agent_type"]),
                responsibility=a["responsibility"],
                source=AgentSourceEnum(a["source"]),
                metrics=AgentMetrics(**a["metrics"]),
            )
            for a in MOCK_AGENTS
        ]

    try:
        from app.services.watsonx_client import call_granite_json

        candidates_json = json.dumps(automation_candidates)
        user_prompt = AGENT_GENERATION_USER.format(
            automation_candidates_json=candidates_json,
            industry="Unknown",
        )
        data = call_granite_json(AGENT_GENERATION_SYSTEM, user_prompt)
    except Exception as exc:
        logger.warning("Groq AI agent generation failed (%s), using dynamic fallback agents", exc)
        data = [
            {"agent_type": "Verification", "responsibility": "Validates data and document authenticity", "suggested_metrics": {"accuracy": 0.98, "processing_time_s": 1.2, "uptime": 0.999}},
            {"agent_type": "Decision", "responsibility": "Evaluates workflow rules and makes automated recommendations", "suggested_metrics": {"accuracy": 0.95, "processing_time_s": 1.8, "uptime": 0.997}},
            {"agent_type": "Communication", "responsibility": "Sends notifications and updates across stakeholders", "suggested_metrics": {"accuracy": 0.99, "processing_time_s": 0.5, "uptime": 0.999}},
            {"agent_type": "Analyzer", "responsibility": "Monitors workflow execution and flags discrepancies", "suggested_metrics": {"accuracy": 0.96, "processing_time_s": 1.5, "uptime": 0.998}},
        ]
    results: list[AgentResponse] = []

    for item in data:
        agent_type = item.get("agent_type", "")
        task_desc = item.get("responsibility", item.get("task_name", ""))

        # Strategy 1: Check if same agent_type already exists in registry (exact type match)
        type_match = find_agent_by_type(agent_type)

        # Strategy 2: Semantic similarity search
        similar = find_similar_agents(task_desc, top_k=1)

        if type_match:
            # Exact type match in registry — always reuse
            source = AgentSourceEnum.REUSED
            metrics = AgentMetrics(
                accuracy=type_match["accuracy"],
                processing_time_s=item.get("suggested_metrics", {}).get("processing_time_s", 1.5),
                uptime=0.999,
            )
        elif similar and similar[0]["distance"] < SIMILARITY_THRESHOLD:
            # Semantic match — reuse
            source = AgentSourceEnum.REUSED
            metrics = AgentMetrics(
                accuracy=similar[0]["accuracy"],
                processing_time_s=item.get("suggested_metrics", {}).get("processing_time_s", 1.5),
                uptime=0.999,
            )
        else:
            source = AgentSourceEnum.NEW
            sm = item.get("suggested_metrics", {})
            metrics = AgentMetrics(
                accuracy=sm.get("accuracy", 0.90),
                processing_time_s=sm.get("processing_time_s", 2.0),
                uptime=sm.get("uptime", 0.995),
            )

        results.append(
            AgentResponse(
                agent_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                agent_type=AgentTypeEnum(item["agent_type"]),
                responsibility=item.get("responsibility", ""),
                source=source,
                metrics=metrics,
            )
        )

    return results
