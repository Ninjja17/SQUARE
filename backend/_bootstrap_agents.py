"""
One-shot bootstrap: create all 6 SQUARE core agents in Orchestrate.
Uses the same logic as bootstrap_core_agents() from orchestrate_client.py.
"""
import json
import urllib.request
import urllib.error
from datetime import datetime

API_KEY      = "kpXlh6v3jGTZSdfXzjz_DWXr765X-73jd5ONHcIkgX46"
INSTANCE_URL = "https://api.eu-de.watson-orchestrate.cloud.ibm.com/instances/7d62dfb2-5efa-421b-9ae3-80b98438b235"
# Use the same LLM the default AskOrchestrate agent uses — confirmed from live API inspection
GRANITE_LLM  = "groq/openai/gpt-oss-120b"

CORE_AGENTS = [
    {
        "name":         "square_core_analyzer",
        "display_name": "SQUARE Analyzer Agent",
        "description":  "Analyzes business workflows and extracts structured insights from unstructured input. Core persistent agent - lifecycle: core.",
        "instructions": (
            "You are the SQUARE Analyzer Agent - a core, persistent AI agent for the "
            "SQUARE Enterprise Agent Engineering Platform. "
            "Your primary responsibility: Analyzes business workflows and extracts structured insights from unstructured input. "
            "You operate across all enterprise workflows with a target accuracy of 96%. "
            "Always apply enterprise compliance, governance, and data-handling standards. "
            "Never expose sensitive user data. Follow the SQUARE agent protocol at all times."
        ),
    },
    {
        "name":         "square_core_verification",
        "display_name": "SQUARE Verification Agent",
        "description":  "Validates documents, records, and data quality against defined business rules. Core persistent agent - lifecycle: core.",
        "instructions": (
            "You are the SQUARE Verification Agent - a core, persistent AI agent for the "
            "SQUARE Enterprise Agent Engineering Platform. "
            "Your primary responsibility: Validates documents, records, and data quality against defined business rules. "
            "You operate across all enterprise workflows with a target accuracy of 98%. "
            "Always apply enterprise compliance, governance, and data-handling standards. "
            "Never expose sensitive user data. Follow the SQUARE agent protocol at all times."
        ),
    },
    {
        "name":         "square_core_decision",
        "display_name": "SQUARE Decision Agent",
        "description":  "Makes accept, reject, or approve recommendations based on verified workflow data. Core persistent agent - lifecycle: core.",
        "instructions": (
            "You are the SQUARE Decision Agent - a core, persistent AI agent for the "
            "SQUARE Enterprise Agent Engineering Platform. "
            "Your primary responsibility: Makes accept, reject, or approve recommendations based on verified workflow data. "
            "You operate across all enterprise workflows with a target accuracy of 95%. "
            "Always apply enterprise compliance, governance, and data-handling standards. "
            "Never expose sensitive user data. Follow the SQUARE agent protocol at all times."
        ),
    },
    {
        "name":         "square_core_communication",
        "display_name": "SQUARE Communication Agent",
        "description":  "Sends notifications, status updates, and manages user interactions across channels. Core persistent agent - lifecycle: core.",
        "instructions": (
            "You are the SQUARE Communication Agent - a core, persistent AI agent for the "
            "SQUARE Enterprise Agent Engineering Platform. "
            "Your primary responsibility: Sends notifications, status updates, and manages user interactions across channels. "
            "You operate across all enterprise workflows with a target accuracy of 99%. "
            "Always apply enterprise compliance, governance, and data-handling standards. "
            "Never expose sensitive user data. Follow the SQUARE agent protocol at all times."
        ),
    },
    {
        "name":         "square_core_risk",
        "display_name": "SQUARE Risk Agent",
        "description":  "Identifies operational, compliance, and security risks in automated workflows. Core persistent agent - lifecycle: core.",
        "instructions": (
            "You are the SQUARE Risk Agent - a core, persistent AI agent for the "
            "SQUARE Enterprise Agent Engineering Platform. "
            "Your primary responsibility: Identifies operational, compliance, and security risks in automated workflows. "
            "You operate across all enterprise workflows with a target accuracy of 92%. "
            "Always apply enterprise compliance, governance, and data-handling standards. "
            "Never expose sensitive user data. Follow the SQUARE agent protocol at all times."
        ),
    },
    {
        "name":         "square_core_planner",
        "display_name": "SQUARE Planner Agent",
        "description":  "Generates phased rollout strategies and implementation plans for AI deployments. Core persistent agent - lifecycle: core.",
        "instructions": (
            "You are the SQUARE Planner Agent - a core, persistent AI agent for the "
            "SQUARE Enterprise Agent Engineering Platform. "
            "Your primary responsibility: Generates phased rollout strategies and implementation plans for AI deployments. "
            "You operate across all enterprise workflows with a target accuracy of 92%. "
            "Always apply enterprise compliance, governance, and data-handling standards. "
            "Never expose sensitive user data. Follow the SQUARE agent protocol at all times."
        ),
    },
]

# ── Step 1: Get IAM token ──────────────────────────────────────────────────────
print("=== Getting IAM token ===")
iam_data = f"grant_type=urn%3Aibm%3Aparams%3Aoauth%3Agrant-type%3Aapikey&apikey={API_KEY}"
req = urllib.request.Request(
    "https://iam.cloud.ibm.com/identity/token",
    data=iam_data.encode(),
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=30) as resp:
    token = json.loads(resp.read().decode())["access_token"]
print(f"Token obtained: {token[:40]}...\n")

# ── Step 2: List existing agents ───────────────────────────────────────────────
base = INSTANCE_URL.rstrip("/")
list_req = urllib.request.Request(
    f"{base}/v1/orchestrate/agents",
    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    method="GET",
)
with urllib.request.urlopen(list_req, timeout=30) as resp:
    body = json.loads(resp.read().decode())
existing_agents = body if isinstance(body, list) else (body.get("agents") or body.get("items") or [])
existing_names  = {a.get("name") for a in existing_agents}
print(f"Existing agents: {sorted(existing_names)}\n")

# ── Step 3: Create missing agents ──────────────────────────────────────────────
print("=== Creating SQUARE core agents ===")
results = []
for spec in CORE_AGENTS:
    name = spec["name"]
    if name in existing_names:
        agent = next(a for a in existing_agents if a.get("name") == name)
        aid   = agent.get("id") or agent.get("agent_id", "?")
        print(f"  [SKIP already exists] {name}  (id={aid})")
        results.append({"name": name, "status": "already_exists", "id": aid})
        continue

    payload = {
        "name":          name,
        "display_name":  spec["display_name"],
        "description":   spec["description"],
        "instructions":  spec["instructions"],
        "llm":           GRANITE_LLM,
        "style":         "default",
        "tools":         [],
        "collaborators": [],
        "knowledge_base": [],
    }

    post_req = urllib.request.Request(
        f"{base}/v1/orchestrate/agents",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(post_req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
        aid = result.get("id") or result.get("agent_id", "?")
        print(f"  [CREATED]  {name}  (id={aid})")
        results.append({"name": name, "status": "created", "id": aid})
    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else ""
        print(f"  [FAILED]   {name}  -> HTTP {e.code}: {err_body}")
        results.append({"name": name, "status": "failed", "error": err_body})

# ── Summary ────────────────────────────────────────────────────────────────────
print()
created  = sum(1 for r in results if r["status"] == "created")
existing = sum(1 for r in results if r["status"] == "already_exists")
failed   = sum(1 for r in results if r["status"] == "failed")
print(f"=== Bootstrap complete: {created} created, {existing} already existed, {failed} failed ===")
