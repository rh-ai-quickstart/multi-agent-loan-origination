# Kagenti + A2A: How It All Works

## The Problem: Agents Can't Talk to Each Other

You build an AI agent. Your colleague builds another. A third team builds a third. Each one is great at its job -- but they're islands. There's no standard way for Agent A to discover Agent B exists, ask it what it can do, and then send it a task. Every integration is bespoke glue code.

That's our situation: 5 LangGraph agents (Public, Borrower, Loan Officer, Underwriter, CEO), each doing specialized mortgage work, but trapped inside a single web app.

---

## Part 1: A2A (Agent-to-Agent Protocol)

### What it is

A2A is an **open protocol** (originally from Google) that standardizes how AI agents find and talk to each other. Think "HTTP for agents" -- just as HTTP standardized browsers talking to servers, A2A standardizes agents talking to agents.

### The three key concepts

**1. Agent Card** -- "Here's who I am and what I can do"

Every A2A agent publishes a JSON file at a well-known URL (`/.well-known/agent-card.json`). This is the agent's business card:

```
"I'm the Underwriter Assistant.
 I can do: risk assessment, compliance verification, decision making.
 Talk to me at: http://host:8083/
 I speak: JSON-RPC over HTTP."
```

Any system that knows the agent's URL can fetch this card and immediately know what the agent does, what skills it has, and how to call it. No documentation needed, no API keys to figure out, no custom integration.

**2. JSON-RPC Messages** -- "Here's a task for you"

Once you know an agent exists (from its card), you talk to it using JSON-RPC 2.0 -- a simple request/response format over HTTP:

```
Client:  "message/send" -> { text: "Run risk assessment for application 12345" }
Agent:   { status: "working", artifact: "DTI ratio is 32%, LTV is 78%..." }
```

The protocol defines a few standard methods:
- `message/send` -- send a message to the agent
- `message/stream` -- send a message and stream the response
- `tasks/get` -- check on a task's status

**3. Task Lifecycle** -- "Here's the status of your request"

Every message creates a **Task** that goes through states:

```
submitted -> working -> completed
                    \-> input_required (agent needs more info)
                    \-> failed
```

If the agent needs clarification, it moves the task to `input_required` and sends back a question. The caller answers, and the task resumes. This is how our LangGraph interrupt mechanism (human-in-the-loop confirmations) maps naturally to A2A.

### What A2A is NOT

- It's **not an agent framework** -- it doesn't build agents, it connects them
- It's **not a message queue** -- it's synchronous HTTP request/response (with optional streaming)
- It's **not authentication** -- it defines no auth mechanism (that's where Kagenti comes in)

---

## Part 2: Kagenti

### What it is

Kagenti is a **Kubernetes-native A2A orchestrator**. If A2A is the protocol, Kagenti is the platform that manages A2A agents running on OpenShift/Kubernetes. It handles the things A2A deliberately leaves out: discovery at scale, authentication, authorization, and lifecycle management.

### The three things Kagenti adds

**1. Agent Discovery** -- "I know about all agents on this cluster"

Kagenti watches for pods labeled `kagenti.io/type: agent`. When it finds one, it reads the agent card and registers it. Now any other agent (or Kagenti's own UI) can find it without knowing its URL in advance.

This is why we added these labels to the Helm chart:
```yaml
labels:
  kagenti.io/type: agent     # "Hey Kagenti, I'm an agent"
```

**2. AuthBridge (Zero-Trust Security)** -- "I handle auth so you don't have to"

A2A defines no authentication. Our agents have no auth code in their A2A endpoints. But in production, you can't have unauthenticated endpoints.

Kagenti solves this with **AuthBridge** -- an envoy sidecar proxy injected into your pod:

```
Incoming request
    |
    v
[AuthBridge sidecar]  <-- validates JWT, checks SPIRE identity
    |
    v (only if auth passes)
[Your agent on port 8080]  <-- receives clean, unauthenticated request
```

The agent code stays simple -- no auth logic. AuthBridge handles it transparently. This is why we added:

```yaml
annotations:
  kagenti.io/inject: "enabled"    # "Inject the AuthBridge sidecar"
  kagenti.io/spire: "enabled"     # "Use SPIRE for workload identity"
  kagenti.io/inbound-ports-exclude: "8000"  # "Don't proxy the main FastAPI port"
```

That last annotation is important: our pod has port 8000 (FastAPI/WebSocket for the UI) AND ports 8080-8084 (A2A agents). We tell Kagenti to only proxy the A2A ports -- the UI traffic goes through its own auth (Keycloak).

**3. AgentRuntime CR** -- "This deployment contains agents"

The `AgentRuntime` is a Kubernetes Custom Resource that tells Kagenti "this Deployment is an agent runtime." It's the bridge between Kubernetes and Kagenti:

```yaml
apiVersion: agent.kagenti.dev/v1alpha1
kind: AgentRuntime
metadata:
  name: risk-assessment-backend
spec:
  targetRef:
    kind: Deployment
    name: mortgage-ai-api    # <-- points to our deployment
  type: agent
```

Kagenti then watches this deployment, injects sidecars, and registers the agents.

---

## Part 2.5: SPIRE / SPIFFE -- The Identity Layer

### What SPIFFE is

**SPIFFE** (Secure Production Identity Framework for Everyone) is a standard for identifying workloads in distributed systems. Instead of relying on network location (IP addresses) or shared secrets (API keys) to know "who is calling me," SPIFFE gives every workload a cryptographic identity -- a **SPIFFE ID**:

```
spiffe://apps.cluster-z8vkd.sandbox3324.opentlc.com/ns/team1/sa/mortgage-ai-mlflow-client
         \_______________ trust domain ______________/ \_______ workload path _________/
```

This ID is baked into X.509 certificates and JWTs. It's not a string you configure -- it's a cryptographically verifiable identity derived from the workload's Kubernetes namespace and service account.

### What SPIRE is

**SPIRE** is the runtime that implements SPIFFE. It runs on the cluster and does two things:

1. **Issues identities** -- when a pod starts, SPIRE verifies it (via Kubernetes attestation) and issues it a SPIFFE ID with short-lived X.509 certificates and JWT SVIDs (SPIFFE Verifiable Identity Documents)
2. **Rotates credentials automatically** -- certificates expire quickly (~2.5 minutes) and SPIRE continuously renews them without any application involvement

### How it works in our pod

When Kagenti sees `kagenti.io/spire: "enabled"`, it injects a **spiffe-helper** sidecar and mounts the SPIRE Agent socket:

```
+---------------------- Pod: mortgage-ai-api ----------------------+
|                                                                   |
|  [spiffe-helper]                                                  |
|       |                                                           |
|       | 1. Connects to SPIRE Agent via CSI volume                 |
|       |    (csi.spiffe.io -> /run/spire/sockets/agent.sock)       |
|       |                                                           |
|       | 2. Requests X.509 SVID + JWT SVID for this workload       |
|       |                                                           |
|       | 3. Writes certs to shared volume (svid-output/)           |
|       |       - svid.pem (X.509 cert)                             |
|       |       - svid_key.pem (private key)                        |
|       |       - svid_bundle.pem (trust bundle)                    |
|       |       - jwt_svid (JWT token)                              |
|       |                                                           |
|       | 4. Rotates every ~2.5 minutes automatically               |
|       v                                                           |
|  [envoy-proxy / AuthBridge]                                       |
|       |                                                           |
|       | Reads certs from svid-output/                             |
|       | Uses them for:                                            |
|       |   - mTLS on incoming A2A connections                      |
|       |   - JWT validation on A2A requests                        |
|       |   - Outgoing mTLS when calling other agents               |
|       v                                                           |
|  [api container]  <-- receives only authenticated traffic         |
+-------------------------------------------------------------------+
```

### Three containers, three jobs

| Container | Image | Job |
|-----------|-------|-----|
| `api` | `mortgage-ai-api:kagentiv1` | Your application code |
| `spiffe-helper` | `kagenti-extensions/spiffe-helper:v0.4.0-alpha.10` | Gets and rotates SPIFFE identity (certs + JWTs) |
| `envoy-proxy` | `kagenti-extensions/envoy-with-processor:v0.4.0-alpha.10` | AuthBridge -- uses SPIFFE certs to enforce mTLS and JWT auth |

### Why this matters

Without SPIRE/SPIFFE, you'd have to:
- Manually create and distribute TLS certificates to every agent
- Build JWT validation into every agent's code
- Rotate secrets on a schedule and handle expiry
- Trust that network policies alone keep agents safe

With SPIRE/SPIFFE:
- Identities are **automatic** -- derived from Kubernetes metadata, no configuration
- Certificates are **short-lived** -- rotated every few minutes, limiting blast radius if compromised
- Authentication is **mutual** -- both caller and callee prove their identity (mTLS)
- Your application code **touches none of this** -- the sidecars handle everything

### How to verify it's working

```bash
# Check the three containers are running
oc -n team1 get pod -l app.kubernetes.io/component=api -o jsonpath='{range .items[0].spec.containers[*]}{.name}{"\n"}{end}'
# Output: api, envoy-proxy, spiffe-helper

# Check the SPIFFE CSI volume is mounted
oc -n team1 get pod -l app.kubernetes.io/component=api -o jsonpath='{range .items[0].spec.volumes[*]}{.name}{": "}{.csi.driver}{"\n"}{end}' | grep spiffe
# Output: spire-agent-socket: csi.spiffe.io

# Check spiffe-helper is rotating certs
oc -n team1 logs deployment/mortgage-ai-api -c spiffe-helper --tail=5
# Output: "JWT SVID updated" every ~2.5 minutes
#         "X.509 certificates updated" on identity refresh
```

---

## Part 3: What We Built

### The architecture

```
                         +----- Pod: mortgage-ai-api ------+
                         |                                  |
 UI (browser) ---------> |  port 8000: FastAPI + WebSocket  |  <-- existing, unchanged
                         |                                  |
                         |  port 8080: A2A Public Agent     |
 Kagenti / other ------> |  port 8081: A2A Borrower Agent   |  <-- NEW (a2a_server.py)
 A2A agents              |  port 8082: A2A Loan Officer     |
                         |  port 8083: A2A Underwriter      |
                         |  port 8084: A2A CEO Agent        |
                         |                                  |
                         |  [AuthBridge sidecar]            |  <-- injected by Kagenti
                         +----------------------------------+
```

### The code flow

When an A2A request arrives at port 8083 (Underwriter), here's what happens:

```
1. HTTP POST to /  (JSON-RPC "message/send")
        |
2. Starlette routes -> LegacyRequestHandler
        |
3. LoanAgentExecutor.execute() is called
        |
4. Extract user's text from the A2A message
        |
5. Load the LangGraph agent: get_agent("underwriter-assistant")
        |
6. Check for LangGraph interrupts (human-in-the-loop)
   - If interrupted: send Command(resume=user_text)
   - If new: send {"messages": [HumanMessage(content=user_text)]}
        |
7. graph.ainvoke() -- runs the SAME graph as the WebSocket path
        |
8. Extract response from graph result
   - Skip ToolMessages, skip "Routing to..." messages
   - Return the last meaningful AI message
        |
9. Send back as A2A artifact -> task completes
```

The key insight: **the A2A server reuses the exact same LangGraph agents** that the WebSocket UI uses. `get_agent()` returns the same graph. The only difference is the transport: WebSocket streams tokens to a browser, A2A sends structured JSON-RPC responses to another agent.

### Feature flag

Everything is gated by `KAGENTI_ENABLED=true`. When false (default), no A2A servers start, no ports are opened, no Kagenti labels are added. Zero impact on existing functionality.

### What's on the cluster

In `team1` namespace:
- Pod running 3/3 (api container + 2 Kagenti sidecars)
- Image: `quay.io/rh-ai-quickstart/mortgage-ai-api:kagentiv1`
- 5 agent cards responding at ports 8080-8084
- AgentRuntime CR `risk-assessment-backend` active
- AuthBridge injected and handling auth

---

## Part 4: The Big Picture

### Without Kagenti + A2A

```
User -> Browser -> WebSocket -> LangGraph Agent
```

One user, one browser, one agent at a time. Agents are trapped inside the web app.

### With Kagenti + A2A

```
User -> Browser -> WebSocket -> LangGraph Agent
Other Agent -> A2A (HTTP) -> LangGraph Agent
Kagenti UI -> A2A (HTTP) -> LangGraph Agent
Voice Agent -> A2A (HTTP) -> LangGraph Agent
Any A2A client -> A2A (HTTP) -> LangGraph Agent
```

The agents become **services** that anything can invoke -- other agents, orchestrators, voice interfaces, batch processors. The web UI is just one of many possible consumers.

### Real-world example

In our case, you could have:
- A **risk orchestrator** that calls the Underwriter agent via A2A to get risk assessments
- A **Kagenti UI** that lets admins interact with any agent without using the mortgage app
- A **monitoring agent** that periodically calls the CEO agent to generate portfolio reports
- A **voice interface** that talks to the Public Assistant

All of this works because every agent speaks the same protocol and can be discovered automatically.

---

## Files Created/Modified

| File | What it does |
|------|-------------|
| `packages/api/src/a2a_server.py` | The A2A integration -- agent configs, AgentCard builder, LoanAgentExecutor, server startup |
| `packages/api/src/core/config.py` | Added `KAGENTI_ENABLED` setting |
| `packages/api/src/main.py` | Starts A2A servers as background tasks in FastAPI lifespan |
| `packages/api/tests/test_a2a_server.py` | 22 unit tests |
| `deploy/helm/mortgage-ai/values.yaml` | Added `kagenti:` config section |
| `deploy/helm/mortgage-ai/templates/api-deployment.yaml` | Conditional Kagenti labels, annotations, ports |
| `deploy/helm/mortgage-ai/templates/api-service.yaml` | Conditional A2A port exposure |
| `deploy/helm/mortgage-ai/templates/secret.yaml` | Added `KAGENTI_ENABLED` to secrets |
