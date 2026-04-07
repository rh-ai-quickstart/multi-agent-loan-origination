# This project was developed with assistance from AI tools.
"""Prometheus metrics for AI agent observability.

This module defines custom Prometheus metrics for monitoring the multi-agent
loan origination system. These metrics complement the automatic HTTP metrics
provided by prometheus-fastapi-instrumentator.

Metric Categories:
- LLM metrics: Token usage, inference latency
- Agent metrics: Routing decisions, tool calls
- Session metrics: Active WebSocket connections

Usage:
    from src.core.metrics import llm_tokens_total, llm_inference_duration_seconds

    # Record token usage
    llm_tokens_total.labels(model="gpt-4", direction="input", persona="borrower").inc(150)

    # Record inference duration
    with llm_inference_duration_seconds.labels(model="gpt-4", persona="borrower").time():
        response = await llm.invoke(prompt)
"""

from prometheus_client import Counter, Gauge, Histogram

# =============================================================================
# LLM Token Usage Metrics
# =============================================================================

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Total LLM tokens used",
    ["model", "direction", "persona"],
)
"""Counter for LLM token usage.

Labels:
    model: The LLM model name (e.g., "qwen3-30b-a3b", "gpt-4")
    direction: "input" for prompt tokens, "output" for completion tokens
    persona: The agent persona (e.g., "public", "borrower", "loan_officer", "underwriter", "ceo")
"""

# =============================================================================
# LLM Inference Latency Metrics
# =============================================================================

llm_inference_duration_seconds = Histogram(
    "llm_inference_duration_seconds",
    "LLM inference duration in seconds",
    ["model", "persona"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
)
"""Histogram for LLM inference latency.

Labels:
    model: The LLM model name
    persona: The agent persona

Buckets are optimized for typical LLM response times:
- 0.1-0.5s: Fast cached responses
- 1-5s: Typical streaming responses
- 10-60s: Complex reasoning or tool use
- 120s: Timeout threshold
"""

# =============================================================================
# Agent Routing Metrics
# =============================================================================

agent_routing_total = Counter(
    "agent_routing_total",
    "Agent routing decisions",
    ["persona", "complexity"],
)
"""Counter for agent routing decisions.

Labels:
    persona: The agent persona handling the request
    complexity: "simple" for fast model routing, "complex" for capable model with tools
"""

agent_escalation_total = Counter(
    "agent_escalation_total",
    "Agent escalation events (simple to complex)",
    ["persona", "reason"],
)
"""Counter for agent escalation events.

Labels:
    persona: The agent persona
    reason: Reason for escalation (e.g., "low_confidence", "tool_required", "explicit_request")
"""

# =============================================================================
# Tool Call Metrics
# =============================================================================

tool_calls_total = Counter(
    "tool_calls_total",
    "Tool call attempts",
    ["tool_name", "persona", "status"],
)
"""Counter for agent tool calls.

Labels:
    tool_name: Name of the tool being called
    persona: The agent persona making the call
    status: "success" or "error"
"""

tool_call_duration_seconds = Histogram(
    "tool_call_duration_seconds",
    "Tool call duration in seconds",
    ["tool_name", "persona"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)
"""Histogram for tool call latency.

Labels:
    tool_name: Name of the tool
    persona: The agent persona
"""

# =============================================================================
# WebSocket Session Metrics
# =============================================================================

active_chat_sessions = Gauge(
    "active_chat_sessions",
    "Number of active WebSocket chat sessions",
    ["persona"],
)
"""Gauge for active WebSocket connections.

Labels:
    persona: The agent persona (public, borrower, loan_officer, underwriter, ceo)
"""

chat_messages_total = Counter(
    "chat_messages_total",
    "Total chat messages processed",
    ["persona", "direction"],
)
"""Counter for chat messages.

Labels:
    persona: The agent persona
    direction: "inbound" for user messages, "outbound" for agent responses
"""

# =============================================================================
# Business Metrics
# =============================================================================

loan_applications_total = Counter(
    "loan_applications_total",
    "Total loan applications by status",
    ["status", "loan_type"],
)
"""Counter for loan application status transitions.

Labels:
    status: Application status (e.g., "submitted", "approved", "denied", "withdrawn")
    loan_type: Type of loan (e.g., "conventional", "fha", "va")
"""

compliance_checks_total = Counter(
    "compliance_checks_total",
    "Compliance check results",
    ["check_type", "result"],
)
"""Counter for compliance check outcomes.

Labels:
    check_type: Type of compliance check (e.g., "hmda", "ecoa", "trid")
    result: "pass" or "fail"
"""
