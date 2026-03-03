# Pre-UI Tech Lead Review

Scope: `packages/api/src/agents/`, `packages/api/src/services/`, `packages/api/src/inference/`

Items in `plans/reviews/pre-ui/known-deferred.md` are excluded.

---

## Critical

### TL-01: `decision_proposals` stored in state but not declared in AgentState

**File:** `packages/api/src/agents/decision_tools.py:211-213`
**Also:** `packages/api/src/agents/base.py:102-112`

The `uw_render_decision` tool writes `decision_proposals` to the LangGraph state dict (lines 211-213), but `AgentState` in `base.py` does not declare this field. LangGraph's `MessagesState` uses typed state channels -- writing to an undeclared field means the data is silently dropped after the tool node returns. The proposal_id validation on phase 2 (line 241) will always fail because `state["decision_proposals"]` never persists between graph steps.

This breaks the entire two-phase human-in-the-loop decision flow. When `confirmed=true`, the tool cannot find the proposal and returns an error, forcing the underwriter to manually re-specify all parameters without the safety check that the proposal_id provides.

**Suggested fix:** Add `decision_proposals: dict` to `AgentState` with a default of `{}`. This ensures the field survives between graph nodes:

```python
class AgentState(MessagesState):
    model_tier: str
    safety_blocked: bool
    escalated: bool
    user_role: str
    user_id: str
    user_email: str
    user_name: str
    tool_allowed_roles: dict[str, list[str]]
    decision_proposals: dict  # Two-phase decision proposal storage
```

### TL-02: `build_agent_graph` creates ChatOpenAI for embedding tier

**File:** `packages/api/src/agents/base.py:366-373`

`get_model_tiers()` returns all tiers from `models.yaml`, including `embedding`. The loop at line 367 creates a `ChatOpenAI` instance for every tier. For the embedding tier, this creates a chat client pointing at an embedding model endpoint. While currently harmless (the embedding LLM is never referenced by the graph), it will fail if the embedding model is served on a different endpoint than the chat models, or if a future refactor accidentally references `llms["embedding"]`.

**Suggested fix:** Filter to only chat tiers:

```python
_CHAT_TIERS = {"fast_small", "capable_large"}

for tier in get_model_tiers():
    if tier not in _CHAT_TIERS:
        continue
    model_cfg = get_model_config(tier)
    llms[tier] = ChatOpenAI(...)
```

---

## Warning

### TL-03: `session_id` read from state but never populated

**File:** `packages/api/src/agents/compliance_tools.py:51`
**Also:** `packages/api/src/agents/base.py:102-112` (AgentState), `packages/api/src/routes/_chat_handler.py:170-176` (graph invocation)

The `kb_search` tool reads `state.get("session_id")` and passes it to `write_audit_event`. However, `session_id` is not a field in `AgentState` and is not included in the graph invocation payload (line 170-176 of `_chat_handler.py`). The value is always `None`, meaning KB search audit events cannot be correlated with the WebSocket session they originated from.

**Suggested fix:** Either add `session_id: str` to `AgentState` and pass it from the chat handler, or remove the `session_id` parameter from `kb_search`'s audit calls and accept that tool-level audits don't carry session correlation.

### TL-04: CEO model monitoring tools call `get_model_monitoring_summary` redundantly

**File:** `packages/api/src/agents/ceo_tools.py:486-517, 533-567, 583-613, 629-656`

The four model monitoring tools (`ceo_model_latency`, `ceo_model_token_usage`, `ceo_model_errors`, `ceo_model_routing`) each independently call `get_model_monitoring_summary()` which fetches all observations from LangFuse and computes all four metric types. If the LLM calls all four tools in a single turn (likely for "give me a model health overview"), this fetches and processes the same data 4 times. The 60-second cache in `langfuse_client.py` helps only if the parameters match exactly.

**Suggested fix:** For MVP, the 60-second TTL cache mitigates this adequately since the parameters will typically match. Document this as a known inefficiency. For a future optimization, create a single `ceo_model_health` tool that returns all four metrics in one call.

### TL-05: `tool_auth` node returns AIMessage for denial, confusing agent context

**File:** `packages/api/src/agents/base.py:248-258`

When tool auth denies a tool call, the `tool_auth` node injects an `AIMessage` with denial text. This gets added to the conversation history as if the assistant said it. In the next turn, the LLM sees this AI message in history but didn't produce it -- this can confuse the model's understanding of what it has already communicated to the user, especially if the user then asks "why did you say that?"

**Suggested fix:** Use a `SystemMessage` instead of `AIMessage` for tool auth denials, or use a `ToolMessage` with an error status. This keeps the assistant's message history clean:

```python
from langchain_core.messages import SystemMessage
return {
    "messages": [
        SystemMessage(content=f"Tool authorization denied for role '{user_role}': {denied_list}")
    ]
}
```

### TL-06: Audit events written outside the tool's session scope in CEO model monitoring tools

**File:** `packages/api/src/agents/ceo_tools.py:490-498, 538-551, 588-596, 634-642`

The CEO model monitoring tools (`ceo_model_latency`, etc.) call `get_model_monitoring_summary()` outside of any session context, then open a separate `SessionLocal()` context solely to write the audit event. If `get_model_monitoring_summary()` raises an exception (lines 487-488), the audit event for the failed query is never written. Meanwhile, successful queries write the audit event in a separate session from the data fetch, breaking any transactional correlation.

This is different from the other CEO tools where the business logic and audit both happen inside the same `async with SessionLocal()` block.

**Suggested fix:** Wrap the entire operation (LangFuse fetch + audit write) in a single try/except, and always write an audit event (with error info on failure):

```python
async with SessionLocal() as session:
    try:
        summary = await get_model_monitoring_summary(hours=hours, model=model)
    except Exception as e:
        await write_audit_event(session, ..., event_data={"tool": "...", "error": str(e)})
        await session.commit()
        return f"Error: {e}"
    await write_audit_event(session, ..., event_data={"tool": "...", "hours": hours})
    await session.commit()
```

### TL-07: `lo_performance` issues N+1 queries per loan officer

**File:** `packages/api/src/services/analytics.py:422-518`

The `get_lo_performance` function first queries all distinct `assigned_to` values, then for each LO runs 6 separate queries (active count, closed count, initiated count, decided count, denied count, avg conditions time) plus a turn time subquery. For 10 LOs, this is 70+ queries. Each is a simple count/avg, so individual query time is low, but the round-trip overhead adds up.

**Suggested fix:** For MVP this is acceptable given the small data volume. For the UI phase, if the CEO dashboard calls this on page load, consider consolidating into 2-3 queries with GROUP BY `assigned_to` and window functions.

### TL-08: `ceo_application_lookup` borrower name search is SQL-injectable via ILIKE

**File:** `packages/api/src/agents/ceo_tools.py:228-229`

The `borrower_name` parameter is interpolated into an ILIKE pattern:
```python
.where((Borrower.first_name + " " + Borrower.last_name).ilike(f"%{borrower_name}%"))
```

While SQLAlchemy's `.ilike()` parameterizes the value (so this is NOT a SQL injection), the `%` and `_` characters in `borrower_name` are interpreted as LIKE wildcards. A user searching for "John_" would match "Johns", "Johna", etc. This is a minor correctness issue, not a security issue.

**Suggested fix:** Escape LIKE wildcards in the input:
```python
escaped = borrower_name.replace("%", "\\%").replace("_", "\\_")
.where(...ilike(f"%{escaped}%"))
```

### TL-09: `InjectedState` default value inconsistency across tool modules

**File:** Multiple tool files

Some tools use `state: Annotated[dict, InjectedState]` (no default), some use `= None`, and the CEO tools use `= {}`. This inconsistency means:
- `= None`: State is optional. If LangGraph doesn't inject it, `state` is `None` and `_user_context_from_state(state)` will fail with a `TypeError` when calling `state.get()`.
- `= {}`: State defaults to an empty dict. `_user_context_from_state(state)` will raise `ValueError("user_id is required")`.
- No default: LangGraph always injects the state.

The `InjectedState` annotation tells LangGraph to always inject state, so the default value is never actually used in normal graph execution. But the inconsistency makes it unclear which pattern is intended and could matter for unit testing.

| Pattern | Files |
|---------|-------|
| No default | `borrower_tools.py`, `loan_officer_tools.py` |
| `= None` | `condition_tools.py`, `decision_tools.py`, `compliance_check_tool.py` |
| `= {}` | `ceo_tools.py` |

**Suggested fix:** Standardize on no default (the correct pattern since `InjectedState` guarantees injection). Update `condition_tools.py`, `decision_tools.py`, `compliance_check_tool.py`, and `ceo_tools.py` to match `borrower_tools.py` and `loan_officer_tools.py`.

### TL-10: `ceo_audit_search` fetches more events than it displays but counts all

**File:** `packages/api/src/agents/ceo_tools.py:412, 438-448`

The tool passes `limit=100` to `search_events` (line 412), fetches up to 100 events, but only formats the first 50 (line 438). The header says "Audit search results (N events)" where N could be up to 100, but only 50 are shown. If the user sees "100 events" but only 50 are displayed plus "... and 50 more events", this is accurate but wastes a query fetching 50 events that are never shown.

**Suggested fix:** Either reduce the default limit to 50, or display all fetched events. The current behavior is not incorrect but is confusing.

---

## Suggestion

### TL-11: `build_langfuse_config` creates a new `CallbackHandler` per message

**File:** `packages/api/src/observability.py:53-55`

Every incoming WebSocket message creates a new `CallbackHandler()`. LangFuse's `CallbackHandler` internally initializes the SDK client on construction. While the LangFuse SDK handles this gracefully (reusing a singleton client), the handler object itself carries per-trace state and is lightweight. This is acceptable but could be documented to prevent someone from trying to cache the handler (which would mix traces).

### TL-12: `_low_confidence` strips `<think>` tags but doesn't handle partial tags

**File:** `packages/api/src/agents/base.py:80`

The regex `<think>.*?</think>` handles complete think blocks but not unclosed ones (e.g., if the model starts `<think>` and the response is truncated). An unclosed `<think>` tag would leave the thinking content in the text, which could inflate the hedging phrase count and cause unnecessary escalation. This is a marginal edge case since truncation during `ainvoke` (non-streaming) is rare.

### TL-13: `format_enum_label` in `shared.py` duplicates logic that exists inline elsewhere

**File:** `packages/api/src/agents/shared.py:41-46`

The `format_enum_label` function was extracted to `shared.py`, but several tools still use `.replace('_', ' ').title()` inline (e.g., `ceo_tools.py:71`, `ceo_tools.py:82-83`). The shared function is used by most tools via import, but the CEO tools were added later and missed it. Not a bug, but a consistency issue.

**Suggested fix:** Replace inline `.replace('_', ' ').title()` calls in `ceo_tools.py` with `format_enum_label()` from `shared.py`.

### TL-14: `safety.py` docstring says "fail-closed" but `base.py` comment says "fail-open"

**File:** `packages/api/src/inference/safety.py:11` vs `packages/api/src/agents/base.py:14`

The `safety.py` module docstring (line 11) says: "Both input and output checks fail-closed (block on error)." The `base.py` module docstring (line 14) says: "On any safety-model error the check is skipped (fail-open)."

Looking at the actual code: `safety.py` returns `is_safe=False` on exception (fail-closed). However, `base.py`'s `input_shield` and `output_shield` nodes call the checker, and if the checker returns `is_safe=False`, they block. So the actual behavior is fail-closed, and the `base.py` docstring is stale/wrong.

**Suggested fix:** Update the `base.py` module docstring to reflect the actual fail-closed behavior.

### TL-15: `_HEDGING_PHRASES` list may cause false escalations for mortgage domain

**File:** `packages/api/src/agents/base.py:49-60`

Phrases like "you should consult" and "please check" are common in mortgage assistant responses when the agent correctly advises the user to consult their loan officer or check documentation. This could cause the fast model to escalate unnecessarily on legitimate responses. The threshold of 2+ hedging phrases mitigates this somewhat, but a response like "you should consult your loan officer and please check your application status" would trigger escalation despite being a confident, correct answer.

**Suggested fix:** Consider domain-tuning the hedging list or adding an allow-list of domain-specific phrases that should not count as hedging.

### TL-16: LangFuse observation fetch lacks pagination guard

**File:** `packages/api/src/services/langfuse_client.py:100-118`

The `fetch_observations` function paginates through all pages of LangFuse observations. There is no upper bound on the number of pages fetched. For a busy system with months of data, requesting `hours=2160` (90 days) could return thousands of pages. The `httpx.AsyncClient` has a 15-second timeout per request, but no overall timeout or max-pages guard.

**Suggested fix:** Add a `max_pages` parameter (default 50) to prevent unbounded pagination:

```python
MAX_PAGES = 50
while page <= MAX_PAGES:
    ...
    if page >= total_pages or page >= MAX_PAGES:
        break
```

### TL-17: `get_model_monitoring_summary` re-raises `httpx` exceptions without wrapping

**File:** `packages/api/src/services/model_monitoring.py:299-304`

The function catches `httpx.HTTPStatusError` and `httpx.RequestError`, logs a warning, then re-raises. The CEO tools catch `Exception` broadly (e.g., `ceo_tools.py:487`). This works but leaks `httpx` as an implementation detail. If the LangFuse fetch mechanism changes (e.g., to use the SDK directly), callers would need updating.

**Suggested fix:** For MVP, the current behavior is acceptable. Consider wrapping in a domain-specific exception (e.g., `MonitoringUnavailableError`) if the monitoring backend is expected to change.
