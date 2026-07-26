"""
Common Agent Registry — in-memory fallback when ChromaDB is not installed.
Automatically upgrades to ChromaDB if the package is available.
"""
from __future__ import annotations

import json
import math
import uuid as _uuid

from app.config import get_settings

settings = get_settings()

SEED_AGENTS = [
    {
        "id": "reg-001",
        "agent_type": "Verification",
        "responsibility": "Validates documents, records, and data quality",
        "accuracy": 0.98,
        "industries": ["University", "BFSI", "HR", "Healthcare"],
    },
    {
        "id": "reg-002",
        "agent_type": "Decision",
        "responsibility": "Makes accept/reject/approve recommendations",
        "accuracy": 0.95,
        "industries": ["BFSI", "HR", "University"],
    },
    {
        "id": "reg-003",
        "agent_type": "Communication",
        "responsibility": "Sends notifications and manages user interactions",
        "accuracy": 0.998,
        "industries": ["All sectors"],
    },
    {
        "id": "reg-004",
        "agent_type": "Risk",
        "responsibility": "Identifies operational, compliance and security risks",
        "accuracy": 0.92,
        "industries": ["BFSI", "Healthcare", "Government"],
    },
    {
        "id": "reg-005",
        "agent_type": "Planner",
        "responsibility": "Suggests rollout strategy and implementation plans",
        "accuracy": 0.92,
        "industries": ["All sectors"],
    },
    {
        "id": "reg-006",
        "agent_type": "Analyzer",
        "responsibility": "Extracts insights from unstructured workflow input",
        "accuracy": 0.96,
        "industries": ["All sectors"],
    },
]

# ─── In-memory registry (always available) ───────────────────────────────────

_registry: list[dict] = list(SEED_AGENTS)  # mutable copy


def _simple_similarity(query: str, doc: str) -> float:
    """Very simple word-overlap similarity — no ML required."""
    q_words = set(query.lower().split())
    d_words = set(doc.lower().split())
    if not q_words or not d_words:
        return 0.0
    intersection = q_words & d_words
    return len(intersection) / math.sqrt(len(q_words) * len(d_words))


def find_similar_agents(task_description: str, top_k: int = 3) -> list[dict]:
    """Return registry agents most similar to the task description."""
    # Try ChromaDB first; fall back to in-memory similarity
    try:
        return _chroma_find(task_description, top_k)
    except Exception:
        pass

    scored = []
    for agent in _registry:
        doc = f"{agent['agent_type']} agent: {agent['responsibility']}"
        sim = _simple_similarity(task_description, doc)
        scored.append({
            "registry_id": agent["id"],
            "agent_type": agent["agent_type"],
            "responsibility": agent["responsibility"],
            "accuracy": agent["accuracy"],
            "distance": 1.0 - sim,  # convert similarity → distance
        })
    scored.sort(key=lambda x: x["distance"])
    return scored[:top_k]


def find_agent_by_type(agent_type: str) -> dict | None:
    """Find an existing agent in the registry by exact type match."""
    for agent in _registry:
        if agent["agent_type"].lower() == agent_type.lower():
            return agent
    return None


def add_agent_to_registry(agent_type: str, responsibility: str, industries: list[str]) -> str:
    """Promote a new agent into the registry."""
    new_id = f"reg-{str(_uuid.uuid4())[:8]}"
    _registry.append({
        "id": new_id,
        "agent_type": agent_type,
        "responsibility": responsibility,
        "accuracy": 0.90,
        "industries": industries,
    })
    # Also try ChromaDB if available
    try:
        _chroma_add(new_id, agent_type, responsibility, 0.90, industries)
    except Exception:
        pass
    return new_id


# ─── Optional ChromaDB upgrade ───────────────────────────────────────────────

_chroma_collection = None


def _get_chroma():
    global _chroma_collection
    if _chroma_collection is not None:
        return _chroma_collection
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    if settings.CHROMA_DB_URL:
        client = chromadb.HttpClient(host=settings.CHROMA_DB_URL)
    else:
        client = chromadb.PersistentClient(
            path=settings.CHROMA_DB_PATH,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    col = client.get_or_create_collection(
        "agent_registry", metadata={"hnsw:space": "cosine"}
    )
    # seed if empty
    if col.count() < len(SEED_AGENTS):
        col.add(
            documents=[f"{a['agent_type']} agent: {a['responsibility']}. Used in: {', '.join(a['industries'])}" for a in SEED_AGENTS],
            metadatas=[{"agent_type": a["agent_type"], "responsibility": a["responsibility"], "accuracy": a["accuracy"], "industries": json.dumps(a["industries"])} for a in SEED_AGENTS],
            ids=[a["id"] for a in SEED_AGENTS],
        )
    _chroma_collection = col
    return col


def _chroma_find(task_description: str, top_k: int) -> list[dict]:
    col = _get_chroma()
    results = col.query(query_texts=[task_description], n_results=min(top_k, col.count()))
    out = []
    for i, meta in enumerate(results["metadatas"][0]):
        out.append({
            "registry_id": results["ids"][0][i],
            "agent_type": meta["agent_type"],
            "responsibility": meta["responsibility"],
            "accuracy": meta["accuracy"],
            "distance": results["distances"][0][i],
        })
    return out


def _chroma_add(new_id: str, agent_type: str, responsibility: str, accuracy: float, industries: list[str]):
    col = _get_chroma()
    doc = f"{agent_type} agent: {responsibility}. Used in: {', '.join(industries)}"
    col.add(
        documents=[doc],
        metadatas=[{"agent_type": agent_type, "responsibility": responsibility, "accuracy": accuracy, "industries": json.dumps(industries)}],
        ids=[new_id],
    )
