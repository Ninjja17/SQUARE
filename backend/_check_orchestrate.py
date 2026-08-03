"""One-shot script to check what agents currently exist in Orchestrate."""
import json
import urllib.request
import urllib.error

API_KEY      = "kpXlh6v3jGTZSdfXzjz_DWXr765X-73jd5ONHcIkgX46"
INSTANCE_URL = "https://api.eu-de.watson-orchestrate.cloud.ibm.com/instances/7d62dfb2-5efa-421b-9ae3-80b98438b235"

CORE_AGENT_NAMES = [
    "square_core_analyzer",
    "square_core_verification",
    "square_core_decision",
    "square_core_communication",
    "square_core_risk",
    "square_core_planner",
]

# ── Step 1: IAM token ──────────────────────────────────────────────────────────
print("=== Step 1: Getting IAM token ===")
iam_url  = "https://iam.cloud.ibm.com/identity/token"
iam_data = f"grant_type=urn%3Aibm%3Aparams%3Aoauth%3Agrant-type%3Aapikey&apikey={API_KEY}"
req = urllib.request.Request(
    iam_url, data=iam_data.encode(),
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode())
    token = body["access_token"]
    print(f"IAM token obtained: {token[:40]}...")
except urllib.error.HTTPError as e:
    print(f"IAM ERROR {e.code}: {e.read().decode()}")
    raise SystemExit(1)
except Exception as e:
    print(f"IAM EXCEPTION: {e}")
    raise SystemExit(1)

# ── Step 2: List agents ────────────────────────────────────────────────────────
print("\n=== Step 2: Listing existing Orchestrate agents ===")
base = INSTANCE_URL.rstrip("/")
url  = f"{base}/v1/orchestrate/agents"
req2 = urllib.request.Request(
    url,
    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    method="GET",
)
agents = []
try:
    with urllib.request.urlopen(req2, timeout=30) as resp:
        body2 = json.loads(resp.read().decode())
    if isinstance(body2, list):
        agents = body2
    else:
        agents = body2.get("agents") or body2.get("items") or []
    print(f"Total agents in Orchestrate: {len(agents)}")
    for a in agents:
        name = a.get("name", "(no name)")
        aid  = a.get("id") or a.get("agent_id", "(no id)")
        disp = a.get("display_name", "")
        print(f"  • {name}  |  id={aid}  |  display={disp}")
    if not agents:
        print("  (no agents found yet)")
except urllib.error.HTTPError as e:
    body_err = e.read().decode() if e.fp else ""
    print(f"AGENTS LIST ERROR {e.code}: {body_err}")
    agents = []
except Exception as e:
    print(f"AGENTS LIST EXCEPTION: {e}")
    agents = []

# ── Step 3: Cross-check against SQUARE core names ─────────────────────────────
print("\n=== Step 3: SQUARE core agents status ===")
existing_names = {a.get("name") for a in agents}
all_present = True
for name in CORE_AGENT_NAMES:
    if name in existing_names:
        agent = next(a for a in agents if a.get("name") == name)
        aid   = agent.get("id") or agent.get("agent_id", "?")
        print(f"  [OK]     {name}  (id={aid})")
    else:
        print(f"  [MISSING] {name}")
        all_present = False

print()
if all_present:
    print("All 6 SQUARE core agents are live in Orchestrate.")
else:
    missing = [n for n in CORE_AGENT_NAMES if n not in existing_names]
    print(f"{len(missing)} agent(s) still need to be created: {missing}")
    print("-> Run POST /api/orchestrate/bootstrap-core-agents to create them.")
