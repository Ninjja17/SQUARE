"""
Compliance RAG — stores industry-specific regulatory requirement snippets in ChromaDB
and retrieves the most relevant ones to ground the Risk Analysis Engine.

Collection: `compliance_docs`  (separate from agent_registry)
"""
from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)

# ─── Seed corpus ──────────────────────────────────────────────────────────────
# Each doc: id, industries (list), framework, snippet (what the rule says)
COMPLIANCE_DOCS = [
    # ── GDPR ──────────────────────────────────────────────────────────────────
    {
        "id": "gdpr-001",
        "industries": ["Healthcare", "BFSI", "HR", "Education", "Retail", "Telecom", "Government", "Manufacturing", "Other"],
        "framework": "GDPR",
        "snippet": (
            "GDPR Art. 5 — Personal data must be processed lawfully, fairly, and transparently. "
            "Automated processing of personal data requires explicit consent or a legitimate legal basis. "
            "Data subjects have the right to explanation of automated decisions (Art. 22)."
        ),
    },
    {
        "id": "gdpr-002",
        "industries": ["Healthcare", "BFSI", "HR", "Education", "Retail", "Telecom", "Government", "Manufacturing", "Other"],
        "framework": "GDPR",
        "snippet": (
            "GDPR Art. 32 — Data controllers must implement appropriate technical measures: "
            "encryption of personal data, ability to ensure ongoing confidentiality, integrity, "
            "availability and resilience of processing systems, and a process for regular testing."
        ),
    },
    # ── HIPAA ─────────────────────────────────────────────────────────────────
    {
        "id": "hipaa-001",
        "industries": ["Healthcare"],
        "framework": "HIPAA",
        "snippet": (
            "HIPAA Security Rule §164.312 — Covered entities must implement technical safeguards "
            "to guard against unauthorized access to ePHI. AI systems that process patient records "
            "must enforce role-based access control and audit logging for all access events."
        ),
    },
    {
        "id": "hipaa-002",
        "industries": ["Healthcare"],
        "framework": "HIPAA / HITECH",
        "snippet": (
            "HITECH Act §13402 — Breach notification requirements apply when unsecured PHI is "
            "exposed. AI automation that stores or transmits patient data must have breach detection, "
            "notification workflows, and encryption-at-rest to qualify as 'secured' PHI."
        ),
    },
    # ── PCI-DSS ───────────────────────────────────────────────────────────────
    {
        "id": "pci-001",
        "industries": ["BFSI", "Retail"],
        "framework": "PCI-DSS v4.0",
        "snippet": (
            "PCI-DSS Requirement 6 — All software (including AI agents) that stores, processes, or "
            "transmits cardholder data must follow secure development practices, undergo code review, "
            "and be tested for injection vulnerabilities before deployment."
        ),
    },
    {
        "id": "pci-002",
        "industries": ["BFSI", "Retail"],
        "framework": "PCI-DSS v4.0",
        "snippet": (
            "PCI-DSS Requirement 10 — Log and monitor all access to system components and cardholder "
            "data. AI agents in payment workflows must generate tamper-evident audit logs and alert "
            "on anomalous decision patterns that could indicate fraud or data exfiltration."
        ),
    },
    # ── SOX ───────────────────────────────────────────────────────────────────
    {
        "id": "sox-001",
        "industries": ["BFSI", "Government", "HR"],
        "framework": "SOX Section 302 / 404",
        "snippet": (
            "SOX §404 requires management to assess internal controls over financial reporting. "
            "AI agents involved in financial approval or reporting workflows must have human-in-the-loop "
            "checkpoints, full audit trails, and change-management documentation for model updates."
        ),
    },
    # ── FERPA ─────────────────────────────────────────────────────────────────
    {
        "id": "ferpa-001",
        "industries": ["Education"],
        "framework": "FERPA",
        "snippet": (
            "FERPA (20 U.S.C. § 1232g) — Educational institutions may not disclose student "
            "education records without written consent. AI agents processing admission data, "
            "transcripts, or academic records must enforce strict access controls and consent logging."
        ),
    },
    {
        "id": "ferpa-002",
        "industries": ["Education"],
        "framework": "FERPA / COPPA",
        "snippet": (
            "COPPA applies when educational platforms serve users under 13. Automated systems "
            "must not collect unnecessary personal information, must provide parental consent flows, "
            "and must be able to delete collected data upon request."
        ),
    },
    # ── FedRAMP / NIST ────────────────────────────────────────────────────────
    {
        "id": "fedramp-001",
        "industries": ["Government"],
        "framework": "FedRAMP / NIST 800-53",
        "snippet": (
            "NIST SP 800-53 Rev 5 Control SI-7 — Software and information integrity. "
            "Government AI deployments must verify integrity of agent model artifacts, "
            "detect unauthorized changes, and maintain continuous monitoring with automated alerts."
        ),
    },
    {
        "id": "fedramp-002",
        "industries": ["Government"],
        "framework": "FedRAMP / NIST 800-53",
        "snippet": (
            "NIST SP 800-53 AC-2 / AC-17 — Account management and remote access controls. "
            "AI agents in government workflows must use multi-factor authentication, "
            "enforce least-privilege access, and terminate sessions after inactivity."
        ),
    },
    # ── ISO 27001 ─────────────────────────────────────────────────────────────
    {
        "id": "iso27001-001",
        "industries": ["Manufacturing", "Telecom", "Other"],
        "framework": "ISO/IEC 27001:2022",
        "snippet": (
            "ISO 27001 Annex A 8.28 — Secure coding. AI systems and agents must follow secure "
            "development lifecycle practices: threat modeling, input validation, output sanitization, "
            "and dependency scanning before production deployment."
        ),
    },
    # ── Basel III ─────────────────────────────────────────────────────────────
    {
        "id": "basel-001",
        "industries": ["BFSI"],
        "framework": "Basel III / EBA Guidelines on AI",
        "snippet": (
            "EBA Guidelines on Internal Governance — AI models used in credit decisions, "
            "fraud detection, or AML must be explainable, subject to model risk management frameworks, "
            "and independently validated. Autonomous decision agents require human override capability."
        ),
    },
    # ── CCPA ──────────────────────────────────────────────────────────────────
    {
        "id": "ccpa-001",
        "industries": ["Retail", "Telecom"],
        "framework": "CCPA / CPRA",
        "snippet": (
            "CCPA §1798.100 — California consumers have the right to know what personal data is "
            "collected, to opt out of sale, and to request deletion. AI automation pipelines must "
            "honor deletion requests within 45 days and propagate them to all downstream agents and stores."
        ),
    },
    # ── EEOC (HR) ─────────────────────────────────────────────────────────────
    {
        "id": "eeoc-001",
        "industries": ["HR"],
        "framework": "EEOC / Algorithmic Accountability",
        "snippet": (
            "EEOC guidance on AI in hiring — employers who use AI tools for resume screening, "
            "scoring, or interview scheduling must audit for adverse impact on protected classes "
            "at least annually and be able to explain decision logic to candidates."
        ),
    },
]


# ─── In-memory fallback ───────────────────────────────────────────────────────

def _simple_similarity(query: str, doc: str) -> float:
    q_words = set(query.lower().split())
    d_words = set(doc.lower().split())
    if not q_words or not d_words:
        return 0.0
    intersection = q_words & d_words
    return len(intersection) / math.sqrt(len(q_words) * len(d_words))


def retrieve_compliance_context(industry: str, workflow_summary: str, top_k: int = 4) -> str:
    """
    Retrieve the most relevant compliance snippets for the given industry + workflow.
    Returns a formatted string ready to inject into the risk analysis prompt.
    Tries ChromaDB first; falls back to in-memory TF-IDF-style overlap.
    """
    try:
        return _chroma_retrieve(industry, workflow_summary, top_k)
    except Exception as exc:
        logger.debug("ChromaDB compliance retrieve failed (%s) — using in-memory fallback", exc)
        return _memory_retrieve(industry, workflow_summary, top_k)


def _memory_retrieve(industry: str, workflow_summary: str, top_k: int) -> str:
    query = f"{industry} {workflow_summary}"
    scored: list[tuple[float, dict]] = []
    for doc in COMPLIANCE_DOCS:
        # Boost docs that are tagged for this industry
        industry_boost = 0.3 if industry in doc["industries"] else 0.0
        text = f"{doc['framework']} {doc['snippet']}"
        sim = _simple_similarity(query, text) + industry_boost
        scored.append((sim, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]
    return _format_snippets([d for _, d in top])


def _format_snippets(docs: list[dict]) -> str:
    if not docs:
        return ""
    lines = ["Relevant compliance requirements (retrieved from regulatory knowledge base):"]
    for doc in docs:
        lines.append(f"[{doc['framework']}] {doc['snippet']}")
    return "\n".join(lines)


# ─── ChromaDB integration ─────────────────────────────────────────────────────

_compliance_collection = None


def _get_compliance_collection():
    global _compliance_collection
    if _compliance_collection is not None:
        return _compliance_collection

    from app.config import get_settings
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    settings = get_settings()
    if settings.CHROMA_DB_URL:
        client = chromadb.HttpClient(host=settings.CHROMA_DB_URL)
    else:
        client = chromadb.PersistentClient(
            path=settings.CHROMA_DB_PATH,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    col = client.get_or_create_collection(
        "compliance_docs", metadata={"hnsw:space": "cosine"}
    )

    # Seed if empty
    if col.count() < len(COMPLIANCE_DOCS):
        col.add(
            documents=[f"[{d['framework']}] {d['snippet']}" for d in COMPLIANCE_DOCS],
            metadatas=[{
                "framework": d["framework"],
                "industries": ",".join(d["industries"]),
                "snippet": d["snippet"],
            } for d in COMPLIANCE_DOCS],
            ids=[d["id"] for d in COMPLIANCE_DOCS],
        )
        logger.info("Compliance RAG: seeded %d documents into ChromaDB", len(COMPLIANCE_DOCS))

    _compliance_collection = col
    return col


def _chroma_retrieve(industry: str, workflow_summary: str, top_k: int) -> str:
    col = _get_compliance_collection()
    query = f"{industry} compliance regulations: {workflow_summary[:300]}"
    results = col.query(query_texts=[query], n_results=min(top_k, col.count()))
    docs = []
    for i, meta in enumerate(results["metadatas"][0]):
        docs.append({
            "framework": meta["framework"],
            "industries": meta["industries"].split(","),
            "snippet": meta["snippet"],
        })
    return _format_snippets(docs)
