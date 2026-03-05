<!-- This project was developed with assistance from AI tools. -->

# Personas and Workflows

Summit Cap Financial demonstrates a complete mortgage lending lifecycle across five distinct personas. Each persona has a role-specific experience with access to different data, functionality, and AI agent capabilities.

## Overview

The application supports the following personas, listed in the order a loan typically flows through the system:

1. **Prospect** - Anonymous visitor exploring mortgage options
2. **Borrower** - Authenticated customer applying for a loan
3. **Loan Officer** - Internal staff managing a pipeline of applications
4. **Underwriter** - Reviews applications for approval
5. **CEO** - Executive dashboard for portfolio analytics and audit

## Prospect

Anonymous visitors to Summit Cap Financial's public website.

### Role

The Prospect persona represents potential customers who are exploring mortgage options before creating an account or starting a formal application.

### Access

No authentication required. Navigate to the home page:

```
http://localhost:5173/
```

### Capabilities

| Feature | Description |
|---------|-------------|
| Browse mortgage products | View details on six product types: 30-year fixed, 15-year fixed, ARM, jumbo, FHA, and VA loans |
| Affordability calculator | Estimate maximum loan amount, monthly payment, and purchase price based on income, debts, and down payment |
| Chat with AI assistant | Ask questions about mortgage products, the lending process, and pre-qualification basics |
| Start pre-qualification | The chat assistant can guide prospects through initial pre-qualification questions |

### Agent: Public Assistant

The public assistant uses a tightly scoped agent with strict guardrails:

- **Tools:** `product_info`, `affordability_calc`
- **Scope:** Product information and basic calculations only - no access to customer data
- **Guardrails:** Refuses questions about competitor rates, investment advice, or topics outside mortgage products

**Example interactions:**

```
Prospect: What mortgage products do you offer?
Agent: [Returns list of 6 products with rates and requirements]

Prospect: How much house can I afford with $80,000 income?
Agent: [Uses affordability_calc tool to estimate]

Prospect: What's the process for getting pre-qualified?
Agent: [Walks through steps conversationally]

Prospect: What about your competitor's rates?
Agent: I can only discuss Summit Cap Financial's products.
```

## Borrower

Authenticated customers who have started a mortgage application.

### Role

The Borrower persona represents customers actively applying for a mortgage. They can provide application data conversationally, upload documents, track progress, and respond to underwriter conditions.

### Access

Requires authentication via Keycloak. After signing in, navigate to:

```
http://localhost:5173/borrower
```

### Capabilities

| Feature | Description |
|---------|-------------|
| Start new application | Initiate a formal mortgage application through conversational chat |
| Provide application data | Supply income, employment, property details, and other required information via the chat interface |
| Upload documents | Submit pay stubs, W-2s, tax returns, bank statements through chat or form upload |
| Track application status | View current stage, pending requirements, and timeline estimates |
| View document status | Check which documents are uploaded, processing, accepted, or flagged for resubmission |
| Respond to conditions | Answer underwriter questions and upload additional documents to satisfy conditions |
| Acknowledge disclosures | Review and acknowledge required regulatory disclosures (Loan Estimate, Closing Disclosure) |
| Check rate lock status | View current rate lock and expiration date |
| View regulatory deadlines | See upcoming TRID deadlines and required waiting periods |

### Agent: Borrower Assistant

The borrower assistant has 15 tools scoped to the authenticated borrower's own data:

**Tools:**

- `product_info` - Browse mortgage products
- `affordability_calc` - Calculate affordability
- `list_my_applications` - List borrower's applications
- `start_application` - Initiate a new application
- `update_application_data` - Provide or update application data fields
- `get_application_summary` - View application details
- `document_completeness` - Check which documents are still needed
- `document_processing_status` - Check document upload/processing status
- `application_status` - Get current application stage and next steps
- `regulatory_deadlines` - View TRID and other regulatory timelines
- `acknowledge_disclosure` - Acknowledge required disclosures
- `disclosure_status` - Check which disclosures have been acknowledged
- `rate_lock_status` - View rate lock expiration
- `list_conditions` - View underwriter conditions
- `respond_to_condition_tool` - Respond to a condition
- `check_condition_satisfaction` - Check if condition documents satisfy requirements
- `prequalification_estimate` - Get pre-qualification estimate

**RBAC enforcement:** Borrowers can only access their own applications. Queries for other borrower data return 403 Forbidden.

**Example interactions:**

```
Borrower: I'd like to start an application for a $400,000 loan.
Agent: [Uses start_application, prompts for property address and loan type]

Borrower: Here's my W-2 [uploads file]
Agent: [Document upload processed, confirms receipt and processing status]

Borrower: What documents do I still need to provide?
Agent: [Uses document_completeness tool, lists missing items]

Borrower: What stage is my application in?
Agent: [Uses application_status, returns stage and next steps]

Borrower: The underwriter asked for proof of down payment funds.
Agent: [Uses list_conditions, shows condition details, prompts for upload]
```

## Loan Officer

Internal staff who manage a pipeline of active applications.

### Role

Loan Officers originate and manage mortgage applications through the pre-approval and submission stages. They review documents, assess completeness, pull credit reports, issue pre-qualifications, and submit ready applications to underwriting.

### Access

Requires authentication with `loan_officer` role. After signing in, navigate to:

```
http://localhost:5173/loan-officer
```

The pipeline view shows all applications assigned to the logged-in loan officer, grouped by stage.

### Capabilities

| Feature | Description |
|---------|-------------|
| View pipeline | See all assigned applications grouped by stage with urgency indicators |
| Application detail | View comprehensive application summary including borrower info, financials, documents, and conditions |
| Document review | Inspect uploaded documents and extraction results |
| Quality assessment | View document quality flags (blurry, incomplete, wrong type) |
| Completeness check | Verify all required documents are present |
| Request resubmission | Flag documents for borrower resubmission |
| Pull credit report | Fetch credit data from credit bureau simulation |
| Pre-qualification | Issue pre-qualification decisions with approval amounts |
| Submit to underwriting | Transition ready applications to underwriting review |
| Draft communications | Generate borrower communications with application context |
| Send messages | Deliver messages to borrowers with audit trail |
| Search compliance KB | Query the 3-tier compliance knowledge base for guidance |

### Agent: Loan Officer Assistant

The loan officer assistant has 14 tools with scoped access to the LO's own pipeline:

**Tools:**

- `product_info` - Browse mortgage products
- `affordability_calc` - Calculate affordability
- `lo_pipeline_summary` - Get pipeline overview grouped by stage
- `lo_application_detail` - View detailed application summary
- `lo_document_review` - Inspect a specific document
- `lo_document_quality` - Check quality flags across all documents
- `lo_completeness_check` - Verify document completeness
- `lo_mark_resubmission` - Flag document for borrower resubmission
- `lo_underwriting_readiness` - Check if application is ready for underwriting
- `lo_submit_to_underwriting` - Submit application to underwriting
- `lo_draft_communication` - Generate borrower message with context
- `lo_send_communication` - Send message and record in audit trail
- `lo_pull_credit` - Fetch credit bureau data
- `lo_prequalification_check` - Evaluate pre-qualification criteria
- `lo_issue_prequalification` - Issue pre-qualification decision
- `kb_search` - Search compliance knowledge base

**Data scope:** Loan officers see only applications assigned to them. CEO and underwriter data is not accessible.

**Example interactions:**

```
LO: Show me my pipeline.
Agent: [Uses lo_pipeline_summary, returns grouped list]

LO: What's the status of application #1234?
Agent: [Uses lo_application_detail, returns comprehensive summary]

LO: Are all documents present for #1234?
Agent: [Uses lo_completeness_check, returns checklist]

LO: Pull credit for #1234.
Agent: [Uses lo_pull_credit, returns credit summary and flags any issues]

LO: Is this application ready for underwriting?
Agent: [Uses lo_underwriting_readiness, checks documents + credit + data]

LO: Submit #1234 to underwriting.
Agent: [Uses lo_submit_to_underwriting, transitions stage, confirms]

LO: Draft a message asking for updated paystubs.
Agent: [Uses lo_draft_communication, generates message with app context]

LO: What's the ATR rule for debt-to-income?
Agent: [Uses kb_search, returns regulatory guidance]
```

## Underwriter

Reviews applications for approval or denial.

### Role

Underwriters perform risk assessment, compliance checks, and make final lending decisions. They issue conditions (additional documentation or clarifications required), review condition responses, and render approval, conditional approval, or denial decisions.

### Access

Requires authentication with `underwriter` role. After signing in, navigate to:

```
http://localhost:5173/underwriter
```

The underwriter queue shows all applications in underwriting stage.

### Capabilities

| Feature | Description |
|---------|-------------|
| View underwriting queue | See all applications submitted for underwriting |
| Application detail | View comprehensive application data including borrower, financials, documents, credit, and conditions |
| Risk assessment | Calculate risk indicators: DTI, LTV, credit score factors, fraud signals |
| Preliminary recommendation | Get AI-generated recommendation (approve/conditional/deny) with rationale |
| Compliance checks | Run ECOA, ATR/QM, and TRID regulatory checks |
| Search compliance KB | Query federal regulations, agency guidelines, and internal policies |
| Issue conditions | Request additional documentation or clarifications from borrower |
| Review conditions | View borrower responses to issued conditions |
| Clear conditions | Mark satisfied conditions as cleared |
| Waive conditions | Waive conditions with documented justification |
| Return conditions | Send conditions back to borrower for additional information |
| Render decision | Issue approval, conditional approval, or denial |
| Draft adverse action | Generate adverse action notice for denials (required by ECOA) |
| Generate disclosures | Produce Loan Estimate and Closing Disclosure documents |

### Agent: Underwriter Assistant

The underwriter assistant has 19 tools with read access to all applications in underwriting:

**Tools:**

- `current_date` - Get today's date for timeline calculations
- `product_info` - Browse mortgage products
- `affordability_calc` - Calculate affordability
- `uw_queue_view` - View underwriting queue
- `uw_application_detail` - View detailed application summary
- `uw_risk_assessment` - Calculate risk metrics (DTI, LTV, credit factors)
- `uw_preliminary_recommendation` - Get AI recommendation with rationale
- `compliance_check` - Run ECOA, ATR/QM, TRID checks
- `kb_search` - Search compliance knowledge base
- `uw_issue_condition` - Issue new condition to borrower
- `uw_review_condition` - View condition and borrower response
- `uw_clear_condition` - Mark condition as satisfied
- `uw_waive_condition` - Waive condition with justification
- `uw_return_condition` - Return condition to borrower
- `uw_condition_summary` - View all conditions for an application
- `uw_render_decision` - Issue approval/conditional/denial decision
- `uw_draft_adverse_action` - Generate adverse action notice
- `uw_generate_le` - Generate Loan Estimate disclosure
- `uw_generate_cd` - Generate Closing Disclosure

**HMDA isolation:** The underwriter agent has NO access to demographic data. HMDA data is isolated in a separate database schema with role-based access control. If asked about protected characteristics, the agent explicitly refuses.

**Compliance guard:** If `compliance_check` returns a critical failure (e.g., ECOA violation), the agent refuses to proceed with approval and requires the issue to be resolved first.

**Example interactions:**

```
UW: Show me the underwriting queue.
Agent: [Uses uw_queue_view, returns list of applications]

UW: What's the risk profile for application #1234?
Agent: [Uses uw_risk_assessment, returns DTI, LTV, credit score, fraud flags]

UW: What's your preliminary recommendation for #1234?
Agent: [Uses uw_preliminary_recommendation, returns approve/conditional/deny with rationale]

UW: Run compliance checks for #1234.
Agent: [Uses compliance_check, returns ECOA/ATR/TRID pass/fail results]

UW: What's the TRID 3-day rule for closing disclosure?
Agent: [Uses kb_search, returns regulatory guidance with citations]

UW: Issue a condition requesting updated bank statements.
Agent: [Uses uw_issue_condition, creates condition record, notifies borrower]

UW: Has the borrower responded to condition #567?
Agent: [Uses uw_review_condition, shows borrower response and uploaded docs]

UW: Clear condition #567.
Agent: [Uses uw_clear_condition, marks cleared, records in audit trail]

UW: Approve application #1234.
Agent: [Uses uw_render_decision, records approval, generates Loan Estimate]

UW: Deny application #1234 due to high DTI.
Agent: [Uses uw_render_decision + uw_draft_adverse_action, creates denial and notice]
```

## CEO

Executive dashboard for portfolio analytics and audit.

### Role

The CEO persona provides a high-level view of business performance, fair lending metrics, and comprehensive audit capabilities. All personally identifiable information (PII) is masked in CEO views: SSNs, dates of birth, and account numbers are redacted or partially obscured.

### Access

Requires authentication with `ceo` role. After signing in, navigate to:

```
http://localhost:5173/ceo
```

The dashboard shows portfolio analytics. The audit tab provides access to the complete audit trail.

### Capabilities

| Feature | Description |
|---------|-------------|
| Pipeline summary | View application counts by stage, average processing times, volume trends |
| Denial trends | Track denial rates over time with reason breakdown |
| LO performance | View loan officer metrics: applications, approvals, processing times |
| Application lookup | Search for any application by ID or borrower name |
| Audit trail query | Search audit events by application, decision, time range, or event type |
| Decision trace | Follow the full audit chain for a specific decision |
| Model monitoring | View LLM latency, token usage, error rates, and routing distribution |
| Chat with AI assistant | Ask analytical questions about portfolio performance |

### Agent: CEO Assistant

The CEO assistant has 12 tools with read-only access to all data, subject to PII masking:

**Tools:**

- `ceo_pipeline_summary` - Portfolio overview by stage and time period
- `ceo_denial_trends` - Denial rate trends with reason categories
- `ceo_lo_performance` - Loan officer performance metrics
- `ceo_application_lookup` - Find application by ID or borrower name
- `ceo_audit_trail` - Query audit events by application
- `ceo_decision_trace` - Trace decision audit chain
- `ceo_audit_search` - Search audit by event type and time range
- `ceo_model_latency` - LLM latency percentiles by model
- `ceo_model_token_usage` - Token consumption by model and persona
- `ceo_model_errors` - LLM error rates and failure types
- `ceo_model_routing` - Model routing distribution across agents
- `product_info` - Browse mortgage products

**PII masking:** SSNs show only last 4 digits (`***-**-1234`), DOBs show only year (`1985-**-**`), account numbers show only last 4 digits (`****5678`). Borrower names remain visible for operational context.

**Document restriction:** CEO can view document metadata (type, upload date, status, quality flags) but cannot access document content. The `/api/documents/{id}/content` endpoint returns 403 for CEO role.

**HMDA access:** CEO has access to pre-aggregated HMDA statistics through the compliance service, but NOT individual demographic records. Fair lending metrics (SPD, DIR) are computed by the compliance service and exposed as summary statistics.

**Example interactions:**

```
CEO: What's our approval rate this quarter?
Agent: [Uses ceo_pipeline_summary, calculates approval rate]

CEO: Show me denial trends over the last 6 months.
Agent: [Uses ceo_denial_trends, returns trend chart data]

CEO: How is Maria Chen performing?
Agent: [Uses ceo_lo_performance, returns metrics for that LO]

CEO: What's the audit trail for application #1234?
Agent: [Uses ceo_audit_trail, returns chronological event list]

CEO: Show me the decision rationale for application #1234.
Agent: [Uses ceo_decision_trace, follows audit chain, returns decision data]

CEO: What's our average LLM latency this week?
Agent: [Uses ceo_model_latency, returns p50/p95/p99 latencies]

CEO: Are we routing too many queries to the expensive model?
Agent: [Uses ceo_model_routing, returns distribution and cost estimate]
```

## Navigation Summary

| Persona | URL Path | Auth Required | Role |
|---------|----------|---------------|------|
| Prospect | `/` | No | (none) |
| Borrower | `/borrower` | Yes | `borrower` |
| Loan Officer | `/loan-officer` | Yes | `loan_officer` |
| Underwriter | `/underwriter` | Yes | `underwriter` |
| CEO | `/ceo` | Yes | `ceo` |

## WebSocket Chat Endpoints

All persona chat interfaces connect to WebSocket endpoints for real-time AI agent conversations:

| Persona | WebSocket URL | Auth |
|---------|---------------|------|
| Prospect | `ws://localhost:8000/api/public/chat` | None |
| Borrower | `ws://localhost:8000/api/borrower/chat?token=<jwt>` | JWT required |
| Loan Officer | `ws://localhost:8000/api/lo/chat?token=<jwt>` | JWT required |
| Underwriter | `ws://localhost:8000/api/underwriter/chat?token=<jwt>` | JWT required |
| CEO | `ws://localhost:8000/api/ceo/chat?token=<jwt>` | JWT required |

Message format for sending user queries:

```json
{
  "type": "user_message",
  "content": "Your question here"
}
```

The agent responds with streaming messages of type `agent_message` containing the response content.

## Key Architectural Patterns

### Role-Based Access Control (RBAC)

Access control is enforced at three layers:

1. **API layer:** Route-level access checks and data scope injection
2. **Service layer:** Services re-apply data scope filters for defense-in-depth
3. **Agent layer:** Tool authorization checked before each invocation

Borrowers see only their own applications. Loan officers see only their assigned pipeline. Underwriters have read access to all underwriting queue applications. CEO has read access to all data with PII masking.

### HMDA Data Isolation

Demographic data (race, ethnicity, sex, age) is collected for regulatory reporting but isolated from lending decisions through four-stage isolation:

1. **Collection:** Dedicated API endpoint writes to separate `hmda` schema
2. **Document extraction:** Demographic filter excludes detected demographic content
3. **Storage:** Separate PostgreSQL schema with role-based access control
4. **Retrieval:** Lending agents have NO tools that query the `hmda` schema

Only the compliance service can access HMDA data, and it exposes only pre-aggregated statistics.

### Agent Security

Every AI agent implements four defense layers:

1. **Input validation:** Scan for adversarial patterns, refuse injection attempts
2. **System prompt hardening:** Explicit refusal instructions for out-of-scope queries
3. **Tool authorization:** Pre-tool node checks role permissions
4. **Output filtering:** Scan responses for PII leakage and HMDA references

### Audit Trail

Every AI action is logged to an append-only audit trail:

- User queries
- Tool calls with parameters and results
- Data access operations
- Decisions (approval, denial, conditions)
- State transitions
- Security events (rejected prompts, output redactions)

Hash chain provides tamper evidence. Database trigger rejects UPDATE/DELETE on audit events.

## Next Steps

After exploring the persona experiences:

- Review the [Architecture](architecture.md) document for system design details
- See the [API Reference](api-reference.md) for endpoint documentation
