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
        "responsibility": "Validates documents, records, and data quality for this specific workflow",
        "source": "new",
        "metrics": {"accuracy": 0.98, "processing_time_s": 1.2, "uptime": 0.999},
    },
    {
        "agent_type": "Decision",
        "responsibility": "Evaluates workflow rules and makes accept/reject/approve recommendations",
        "source": "new",
        "metrics": {"accuracy": 0.95, "processing_time_s": 2.1, "uptime": 0.997},
    },
    {
        "agent_type": "Communication",
        "responsibility": "Sends automated notifications and status updates to users",
        "source": "new",
        "metrics": {"accuracy": 0.998, "processing_time_s": 0.3, "uptime": 0.9999},
    },
    {
        "agent_type": "Analyzer",
        "responsibility": "Analyzes workflow inputs and flags missing items or discrepancies",
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
    # Group/deduplicate by agent_type to ensure unique agent types per workflow
    deduped_data: dict[str, dict] = {}
    for item in data:
        atype = item.get("agent_type", "")
        if not atype:
            continue
        if atype not in deduped_data:
            deduped_data[atype] = dict(item)
        else:
            # Combine responsibilities of duplicate types
            existing_resp = deduped_data[atype].get("responsibility", "")
            new_resp = item.get("responsibility", item.get("task_name", ""))
            if new_resp and new_resp not in existing_resp:
                deduped_data[atype]["responsibility"] = f"{existing_resp}; {new_resp}"

    results: list[AgentResponse] = []

    for atype, item in deduped_data.items():
        task_desc = item.get("responsibility", item.get("task_name", ""))

        # Check semantic similarity search against custom stored agents in ChromaDB
        # Use a strict similarity threshold (distance < 0.30) so workflow-specific agents
        # are created fresh as NEW, and only exact pre-validated store matches are reused.
        similar = find_similar_agents(task_desc, top_k=1)

        if similar and len(similar) > 0 and similar[0].get("distance", 1.0) < 0.30:
            # High semantic match — reuse stored agent from registry
            source = AgentSourceEnum.REUSED
            metrics = AgentMetrics(
                accuracy=similar[0]["accuracy"],
                processing_time_s=item.get("suggested_metrics", {}).get("processing_time_s", 1.5),
                uptime=0.999,
            )
        else:
            # Workflow-specific custom agent — created fresh for this workflow
            source = AgentSourceEnum.NEW
            sm = item.get("suggested_metrics", {})
            metrics = AgentMetrics(
                accuracy=sm.get("accuracy", 0.96),
                processing_time_s=sm.get("processing_time_s", 2.0),
                uptime=sm.get("uptime", 0.995),
            )

        results.append(
            AgentResponse(
                agent_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                agent_type=AgentTypeEnum(atype),
                responsibility=item.get("responsibility", ""),
                source=source,
                metrics=metrics,
            )
        )

    return results
