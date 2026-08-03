"""Agent Generation Engine — checks Common Agent Registry first, then generates new agents."""
from __future__ import annotations

import json
import logging
import uuid

from app.db.chroma_client import find_similar_agents
from app.models.schemas import AgentMetrics, AgentResponse, AgentSourceEnum, AgentTypeEnum
from app.prompts.templates import AGENT_GENERATION_SYSTEM, AGENT_GENERATION_USER

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.60  # cosine distance — lower = more similar; 0.6 is generous to favor reuse

_FALLBACK_AGENTS = [
    {"agent_type": "Verification", "responsibility": "Validates data and document authenticity", "suggested_metrics": {"accuracy": 0.98, "processing_time_s": 1.2, "uptime": 0.999}},
    {"agent_type": "Decision", "responsibility": "Evaluates workflow rules and makes automated recommendations", "suggested_metrics": {"accuracy": 0.95, "processing_time_s": 1.8, "uptime": 0.997}},
    {"agent_type": "Communication", "responsibility": "Sends notifications and updates across stakeholders", "suggested_metrics": {"accuracy": 0.99, "processing_time_s": 0.5, "uptime": 0.999}},
    {"agent_type": "Analyzer", "responsibility": "Monitors workflow execution and flags discrepancies", "suggested_metrics": {"accuracy": 0.96, "processing_time_s": 1.5, "uptime": 0.998}},
]


async def generate_agents(workflow_id: str, automation_candidates: list[dict]) -> list[AgentResponse]:
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
        data = _FALLBACK_AGENTS

    # Group/deduplicate by agent_type to ensure unique agent types per workflow
    deduped_data: dict[str, dict] = {}
    for item in data:
        atype = item.get("agent_type", "")
        if not atype:
            continue
        if atype not in deduped_data:
            deduped_data[atype] = dict(item)
        else:
            existing_resp = deduped_data[atype].get("responsibility", "")
            new_resp = item.get("responsibility", item.get("task_name", ""))
            if new_resp and new_resp not in existing_resp:
                deduped_data[atype]["responsibility"] = f"{existing_resp}; {new_resp}"

    results: list[AgentResponse] = []

    for atype, item in deduped_data.items():
        task_desc = item.get("responsibility", item.get("task_name", ""))

        # Check semantic similarity against ChromaDB registry
        similar = find_similar_agents(task_desc, top_k=1)

        if similar and len(similar) > 0 and similar[0].get("distance", 1.0) < 0.30:
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

    # ── Create agents in WatsonX Orchestrate via the Agents API ───────────
    try:
        from app.services.orchestrate_client import create_agents_batch

        agents_for_orch = [
            {
                "agent_id": a.agent_id,
                "agent_type": a.agent_type.value,
                "responsibility": a.responsibility,
                "metrics": a.metrics.model_dump(),
            }
            for a in results
        ]
        orch_results = create_agents_batch(agents_for_orch, workflow_id)

        # Attach Orchestrate agent IDs back to the results
        orch_by_id = {r["agent_id"]: r for r in orch_results}
        for agent in results:
            orch = orch_by_id.get(agent.agent_id, {})
            agent.orchestrate_agent_id = orch.get("orchestrate_agent_id")

        created = sum(1 for r in orch_results if r.get("created"))
        logger.info(
            "Orchestrate: %d/%d agents created for workflow %s",
            created, len(results), workflow_id[:8],
        )
    except Exception as exc:
        logger.warning("Orchestrate agent creation skipped: %s", exc)

    return results

