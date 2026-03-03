# Technical Writer Review -- Pre-UI

**Reviewer:** Technical Writer
**Date:** 2026-03-02
**Scope:** README files, `plans/`, docstrings in `packages/api/src/`, `packages/db/src/`

Known-deferred items from `plans/reviews/pre-ui/known-deferred.md` were skipped. All
findings below are new.

---

## Critical

### TW-01: API README missing Phase 5 routes (CEO chat, analytics, model monitoring)

**File:** `packages/api/README.md`

The API README documents four agents but the codebase now has five. The CEO assistant
(`ceo_assistant.py`, `ceo_chat.py`) was added in Phase 5 (F13) and is entirely absent
from the README. Three related route groups are also missing:

- **CEO WebSocket chat:** `ws://host/api/ceo/chat?token=<jwt>` (authenticated)
- **CEO conversation history:** `GET /api/ceo/conversations/history`
- **Analytics endpoints (F12, admin + CEO):**
  - `GET /api/analytics/pipeline?days=`
  - `GET /api/analytics/denial-trends?days=&product=`
  - `GET /api/analytics/lo-performance?days=&product=`
- **Model monitoring endpoints (F39, admin + CEO):**
  - `GET /api/analytics/model-monitoring?hours=&model=`
  - `GET /api/analytics/model-monitoring/latency`
  - `GET /api/analytics/model-monitoring/tokens`
  - `GET /api/analytics/model-monitoring/errors`
  - `GET /api/analytics/model-monitoring/routing`

The agents table (`packages/api/README.md:152-160`) states "Four LangGraph agents" but there
are now five. The CEO agent has 12 tools (pipeline summary, denial trends, LO performance,
application lookup, audit trail, decision trace, audit search, model latency, model token usage,
model errors, model routing, product info).

The Conversation History section (`packages/api/README.md:97-100`) lists borrower, loan officer,
and underwriter history endpoints but omits CEO (`GET /api/ceo/conversations/history`).

**Fix:** Add a CEO agent row to the agents table, add CEO chat + history WebSocket entries,
add Analytics and Model Monitoring REST sections, update "Four LangGraph agents" to five.

---

### TW-02: Root README is still the AI QuickStart template (not a Summit Cap readme)

**File:** `README.md:1-4, 472-609`

The root README opens with "A ready-made template for creating new AI Quickstarts" and closes
with "Generated with [AI QuickStart CLI]". The entire "Extending the Template" section
(`README.md:474-560`) instructs readers to rename the project -- which is the opposite of what
a Quickstart adopter needs. This document is the first thing any developer, Summit attendee, or
AI BU evaluator reads.

This was deferred in pre-Phase 3 (C-10 in known-deferred) but the context has changed: Phase 5
is now complete and the demo is targeting Red Hat Summit. The project has five personas, an agent
system, a compliance KB, and a full deployment story -- none of which appear in the root README.

**Fix:** Replace the root README with a Summit Cap Financial README following the standard
structure: one-line project description, Quick Start (3-5 steps), Prerequisites, Architecture
overview with Mermaid diagram, Personas section, and links to package READMEs.

---

### TW-03: Root README development environment example uses wrong database port

**File:** `README.md:132, 398`

The Development URLs section states:
```
- **Database**: postgresql://localhost:5432
```

And the Environment Configuration section shows:
```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/summit-cap
```

The compose.yml maps host port **5433** to container port 5432 (`compose.yml:65`). A developer
following the README will attempt to connect on 5432 and fail. The API package README
(`packages/api/README.md:233`) and DB package README (`packages/db/README.md:402-424`) both
correctly state 5433.

**Fix:** Change all `localhost:5432` references in the root README to `localhost:5433`.
Affected lines: 132, 204, 238, 398.

---

## Warning

### TW-04: UI README directory listing references `quick-stats/` component that does not exist

**File:** `packages/ui/README.md:45`

The directory structure listing shows:
```
│   ├── quick-stats/           # Quick stats component
```

The component does not exist at `packages/ui/src/components/quick-stats/`. The actual
components directory contains: atoms, footer, header, hero, logo, mode-toggle, service-card,
service-list, stat-card, status-panel, theme-provider.

The same non-existent component is referenced in the component organization list
(`README.md:86, 250`): "Logo, Hero, **QuickStats**, StatCard, ..." -- QuickStats does not exist.

**Fix:** Remove `quick-stats/` from the directory listing. Remove `QuickStats` from both
component organization lists at lines 86 and 250. Keep `stat-card` which does exist.

---

### TW-05: UI README `pnpm dev` description omits Storybook (it launches both dev servers)

**File:** `packages/ui/README.md:604`

The Essential Scripts section states:
```
pnpm dev                # Start dev server + Storybook
```

This is accurate (`package.json:10` runs `concurrently "npm run dev:vite" "npm run dev:storybook"`).
However, Storybook launches on port 6006 and this port is never documented anywhere in the UI
README. A developer running `pnpm dev` will see two servers start and not know the Storybook
URL.

Additionally, the root README (`README.md:130`) lists:
```
- **Frontend App**: http://localhost:3000
```
But the Vite dev server defaults to port 5173 (as confirmed by `ALLOWED_HOSTS` in config.py
defaulting to `http://localhost:5173`). The root README development URL for the frontend
is wrong.

**Fix:** Add `http://localhost:6006` as the Storybook URL to the UI README. Correct the
root README Development URLs section: frontend is `http://localhost:5173`, not 3000.

---

### TW-06: API README missing several environment variables from config.py

**File:** `packages/api/README.md:204-214`

The Configuration section documents 14 environment variables but `src/core/config.py` defines
20. Missing from the README:

- `DB_ECHO` - SQL query logging toggle (referenced in root README but not API README)
- `APP_NAME` - Application name
- `UPLOAD_MAX_SIZE_MB` - Maximum upload size in MB (default 50)
- `S3_REGION` - S3/MinIO region (default us-east-1)
- `SAFETY_API_KEY` - Safety model API key (separate from LLM API key)
- `JWKS_CACHE_TTL` - JWKS cache lifetime in seconds

These are not critical blockers but a developer configuring a non-default setup (e.g., enabling
safety shields, tuning upload limits) will not find these in the README.

**Fix:** Add the missing six variables to the Configuration section with their descriptions
and default values, matching the format of existing entries.

---

### TW-07: API README agents section references `config/agents/` with ambiguous path

**File:** `packages/api/README.md:35, 152`

The directory listing says `registry.py  # Agent config loading from config/agents/*.yaml`
and the agents section says "YAML config (`config/agents/`)". The `config/agents/` directory
is at the **project root**, not inside `packages/api/`. A developer reading the API package
README will look for it relative to `packages/api/` and not find it.

The actual path is `/home/jary/redhat/git/mortgage-ai/config/agents/` containing five YAML files
(borrower-assistant.yaml, ceo-assistant.yaml, loan-officer-assistant.yaml, public-assistant.yaml,
underwriter-assistant.yaml).

**Fix:** Clarify the path as `../../config/agents/` or `config/agents/` (relative to project
root) in both the directory listing and the agents section.

---

### TW-08: Demo walkthrough does not mention CEO model monitoring capability

**File:** `plans/demo-walkthrough.md:40-48`

The CEO section of the demo walkthrough mentions pipeline data and PII masking but omits
the model monitoring overlay (F39), which is a significant demo talking point for AI BU
stakeholders. The model monitoring story -- LangFuse-backed latency percentiles, token usage,
error rates, and routing distribution -- is directly relevant to showcasing OpenShift AI
capabilities.

This is a planning doc gap, not a code gap: the endpoints exist (`/api/analytics/model-monitoring/*`)
but are not scripted into the demo flow.

**Fix:** Add a bullet to the CEO section: "Inspect model monitoring metrics (latency percentiles,
token usage, routing distribution across fast/capable tiers)" to make the F39 capability
discoverable during demos.

---

## Suggestion

### TW-09: UI README "Generated with AI QuickStart CLI" footer should be removed

**File:** `packages/ui/README.md:663`

The UI README ends with:
```
Generated with [AI QuickStart CLI](https://github.com/TheiaSurette/quickstart-cli)
```

This is template attribution from the scaffolding tool. It is confusing for Summit
attendees and adopters who will see it as documentation for a CLI tool they don't need.

**Fix:** Remove line 663. The DB README has the same footer at line 448 and should
also be cleaned up.

---

### TW-10: DB README project structure listing is incomplete

**File:** `packages/db/README.md:55-70`

The project structure shows only `database.py` in `src/db/`. The actual `src/db/` directory
contains models, enums, and other modules that adopters need to find. While the DB README
is template-level and a full rewrite is the correct long-term fix, the minimal gap here
is that the structure listing actively misleads readers about what the package contains.

This is a lower priority than TW-01 through TW-08 since the DB README is used less
frequently during development than the API README.

**Fix:** Verify and update the `src/db/` directory listing to match actual files.

---

## Notes on Deferred Items

Items C-10 (root README is template), C-11 (API README missing Phase 3-4 endpoints), W-38
(architecture PoC vs MVP), W-42 (no .env.example), and S-34 (path references wrong names)
from the known-deferred list were not re-flagged. TW-02 and TW-03 above are related but
distinct: TW-02 specifically targets the template framing that is now a Summit credibility
risk, while TW-03 is a factual error (wrong port) that breaks developer setup.
