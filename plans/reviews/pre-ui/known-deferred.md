# Known Deferred Items -- DO NOT RE-FLAG

These items were identified in previous reviews (pre-phase-3, pre-phase-5, phase-1) and
explicitly deferred by the team. Do NOT flag these again in your review. If you encounter
one of these, skip it silently.

## Security / Rate Limiting / WebSocket Hardening
- D2: No WebSocket rate limits, message size limits, or connection limits
- D4: No rate limiting on any REST endpoint (slowapi or equivalent)
- D7: Unbounded conversation history in WebSocket (no sliding window)
- C-4: No WebSocket message size or rate limits on any WS endpoint
- C-5: SSN stored as plaintext (demo data, MVP -- not real PII)
- C-6: No rate limiting on REST or WebSocket endpoints
- W-27: `_resolve_role` raises HTTPException in WebSocket context
- S-26: PII masking only covers ssn and dob (not email, phone, employer)
- S-27: Validation error responses expose Pydantic internals
- S-29: BorrowerSummary exposes full SSN in list responses

## Auth / Admin
- C-1: AUTH_DISABLED defaults to true in compose.yml (dev convenience)
- C-2: SQLAdmin default credentials admin/admin
- C-7: SQLAdmin session secret regenerated on restart
- W-21: Bare except Exception in chat handler outer loop
- W-22: Silent audit write failures in chat handler

## Architecture / Code Structure
- W-1: `_user_context_from_state()` copy-pasted across tool modules
- W-2: Primary borrower name lookup duplicated in decision_tools.py
- W-3: Monthly payment amortization formula duplicated
- W-4: Outstanding conditions count duplicated in 3 locations
- W-5: Chat endpoint boilerplate duplicated across authenticated chat files
- W-6: Agent tools bypass service layer with raw SQLAlchemy queries
- W-7: `transition_stage()` raises HTTPException from service layer
- W-8: `_chat_handler._audit` uses generator protocol for session
- W-9: Tool modules 700+ lines each
- W-10: Service return type conventions inconsistent
- W-16: `quality_flags` parsing logic repeated 3 ways
- W-19: `add_borrower`/`remove_borrower` business logic in route layer
- W-20: `build_data_scope` imported from middleware by agent tools
- S-1: `_TIER_LABELS` dict duplicated in KB search and compliance tools
- S-2: Private-prefixed exports imported across module boundary
- S-3: `_compute_risk_factors` returns untyped nested dict
- S-4: `.replace('_', ' ').title()` enum formatting repeated ~15 times
- S-5: InjectedState tool params use `= None` default
- S-7: `DOCUMENT_REQUIREMENTS` dict redundancy
- S-8: Urgency sort compares StrEnum values alphabetically
- S-13: Deferred imports inside tool function bodies
- S-14: `uw_application_detail` is 152-line god function
- S-15: Session sourcing difference undocumented (tools vs routes)
- S-16: Compliance gate belongs in service layer not tool layer

## Database / Audit
- W-11: Audit hash chain global advisory lock serializes all writes
- W-12: `verify_audit_chain` loads entire audit table into memory
- W-13: Audit hash chain missing fields in hash computation
- W-14: N+1 query in `check_condition_documents`
- W-15: `denial_reasons` stored as JSON-encoded Text column
- W-24: Condition lifecycle operations have no SELECT FOR UPDATE
- W-25: `lo_submit_to_underwriting` two-step transition not atomic
- W-26: Audit hash chain interleaving across concurrent sessions
- S-9: `get_latest_decision` docstring contradicts implementation
- S-10: `_business_days_between` uses day-by-day loop
- S-11: Adverse action audit stores param decision_id instead of dec.id
- S-19: `HmdaLoanData.snapshot_at` has `onupdate=func.now()`
- S-20: `RateLock` model missing `updated_at` column

## API Design
- W-28: Conversation history endpoints return raw dicts with no response_model
- W-29: Products endpoint returns bare array (not standard envelope)
- W-30: Conditions endpoint has fake pagination
- S-21: Condition/Decision schema fields typed as str instead of enums
- S-22: ErrorResponse missing RFC 7807 instance field
- S-23: Verb-based URL paths
- S-24: Audit endpoints use non-standard envelope
- S-25: All POST-create endpoints missing Location header
- S-12: Unused import DocumentType in decision_tools.py

## DevOps / Deployment
- W-31: Deploy script missing env var overrides
- W-32: Containerfile installs dev dependencies, unpinned base images
- W-33: compose.yml uses latest tag for MinIO and LlamaStack
- W-34: Helm values contain plaintext secrets as defaults
- W-35: Liveness and readiness probes use same endpoint
- W-36: Multiple config settings absent from compose and Helm
- S-32: Containerfile copies uv into runtime but doesn't use it
- S-33: Helm chart placeholder URLs/emails
- D17: Fragile Path(__file__).parents[4] resolution

## Documentation
- C-10: Root README is still the AI QuickStart template
- C-11: API README missing Phase 3-4 endpoints
- W-37: Technical debt items not fully reconciled
- W-38: Architecture document uses "PoC" 16 times
- W-42: No .env.example file
- S-34: Planning doc path references still use old names
- P-8: No interface contracts for Phases 3-4

## Test Quality
- W-39: Test coverage gaps (chat handler auth, data scope, extraction prompts)
- W-40: Decision service test mocks override return values
- W-41: Test mock helpers duplicated across files

## Business Logic
- W-17: closing_date in CD generation fabricated as today
- W-18: LE/CD tools mutate ORM before commit
- W-23: S3 upload failure leaves phantom Document row
- S-6: Agent registry checkpointer not in cache key
- S-17: document_metadata_only flag not enforced
- S-28: LLM extraction output stored without validation
- S-30: ECOA compliance check hardcodes has_demographic_query=False
- S-31: LLM can set confirmed=true on first call

## Deferred Features
- F26: Agent Adversarial Defenses (4 stories)
- F38: TrustyAI Fairness Metrics (4 stories)
