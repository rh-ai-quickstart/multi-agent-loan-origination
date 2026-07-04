---
description: Interactive project setup wizard. Has a natural conversation to learn about your project, then configures the entire agent scaffold automatically.
user_invocable: true
---

# Project Setup Wizard

You are running the project setup wizard. Your job is to learn about the user's project through natural conversation, then configure the agent scaffold to match.

## Interaction Model

**Do NOT use AskUserQuestion.** Communicate with the user as plain text in your responses. They reply naturally. You parse their answers and ask follow-ups only when needed.

The conversation should feel like talking to a colleague, not filling out a form.

## Phase 1: The Brain Dump

Start with a single open-ended prompt. Say something like:

> Tell me about your project. Say as much or as little as you want — I'll ask follow-ups for anything I need.
>
> Helpful things to mention: what it does, who it's for, what tech stack you're using, how mature it is, any constraints, what you're building toward, and what's explicitly out of scope.

Let the user write freely. They might give you everything in one message, or just a sentence. Both are fine.

## Phase 2: Auto-Detection

While waiting for (or immediately after) the user's brain dump, scan the project for existing stack indicators:

- `pyproject.toml` or `setup.py` → Python (read for framework, dependencies, versions)
- `package.json` → Node.js/JavaScript/TypeScript (read for framework, dependencies, versions)
- `go.mod` → Go
- `Cargo.toml` → Rust
- `pom.xml` or `build.gradle` → Java/Kotlin
- Existing directory structure (run `ls` on project root)

Use auto-detected information to fill gaps the user didn't mention. If auto-detected info conflicts with what the user said, trust the user.

## Phase 3: Parse & Identify Gaps

After the brain dump, map what you learned to this checklist. Track internally which items are **resolved**, **inferred**, or **missing**:

| # | Item | Required | Notes |
|---|------|----------|-------|
| 1 | Project name & description | Yes | Can infer from directory name if not given |
| 2 | Maturity level (poc / mvp / production) | Yes | Critical — drives convention strictness |
| 3 | Domain | No | e.g., fintech, healthcare, developer tooling |
| 4 | Primary users | No | e.g., internal devs, end customers |
| 5 | Compliance requirements | No | e.g., SOC 2, HIPAA, none |
| 6 | Goals (2-4) | Yes | What the project is trying to achieve |
| 7 | Non-goals | No | What's explicitly out of scope |
| 8 | Constraints | No | Technical, business, or organizational |
| 9 | Technology stack | Yes | Language, framework, DB, etc. — auto-detect helps |
| 10 | Project commands | No | build, test, lint, typecheck |
| 11 | Directory structure | No | Can auto-detect or use defaults |
| 12 | Agents to remove | No | Default: keep all |
| 13 | Convention rule preferences | No | Default: use scaffold defaults |
| 14 | Domain-specific rules | No | e.g., HIPAA data handling, financial precision |
| 15 | Org-specific settings | No | Default: strip Red Hat domains |
| 16 | Secrets / .env setup | No | Default: skip .env.example |
| 17 | Agent model tier | No | Default: expanded hybrid (see 5g) |

Items marked "No" in the Required column have sensible defaults. Don't ask about them unless the user's brain dump hints at something relevant (e.g., they mention healthcare → ask about HIPAA compliance rules).

## Phase 4: Targeted Follow-Ups

After parsing the brain dump, do ONE of the following:

**If all required items are resolved:** Summarize what you understood and what you'll configure. Ask "Does this look right? Anything you'd change before I start editing?" Then proceed to Phase 5.

**If only a few gaps remain:** Ask about them in a single concise message. Group related gaps together. For example:

> Got it — sounds like a FastAPI backend for internal developer tooling. A couple things I didn't catch:
> - How mature is this? Proof-of-concept, MVP, or production-ready?
> - Any specific goals you want documented, or should I derive them from what you described?

**If the brain dump was very sparse:** Ask one focused follow-up that targets the biggest gaps. Don't ask about everything at once — keep it conversational. Prioritize: maturity level, tech stack, and goals.

Repeat Phase 4 until all **required** items are resolved. This should take at most 2-3 exchanges total. If the user says "just use defaults" or "figure it out" for anything, respect that and move on.

## Phase 5: Apply Edits

Once you have enough information, apply ALL edits. Do not ask for confirmation before each individual edit — apply them in bulk. Show the user a brief running commentary as you work (e.g., "Updating AGENTS.md with your project details...").

### 5a. Project Identity & Context

- Edit `AGENTS.md`: Replace `# Project Name` with `# <project name>`
- Edit `AGENTS.md`: Replace the placeholder description line with their description
- Edit `AGENTS.md`: Fill in the Project Context table (Maturity, Domain, Primary Users, Compliance)
- Edit `.Codex/rules/maturity-expectations.md`: **Keep only the column for the selected maturity level** and delete the other two columns. Keep the Concern column. Then update `AGENTS.md`'s Maturity Expectations section to reference the selected level.

### 5b. Goals, Non-Goals, Constraints

- Edit `AGENTS.md`: Replace the `## Goals` stub (`<!-- Run /setup to configure. -->`) with actual goals (numbered list)
- Edit `AGENTS.md`: Replace the `## Non-Goals` stub with actual non-goals (bulleted), or `- None identified yet` if none provided
- Edit `AGENTS.md`: Replace the `## Constraints` stub with actual constraints, or `- None identified yet`

### 5c. Technology Stack

- Edit `AGENTS.md`: Replace the `## Key Decisions` stub with their stack choices in this format:
  ```markdown
  ## Key Decisions
  - **Language:** TypeScript 5.x
  - **Runtime:** Node.js 22 LTS
  ...
  ```
- Edit `.Codex/skills/project-conventions/SKILL.md`: Replace the Technology Stack table with actual choices and versions

**Style rules** — The scaffold ships with two style rule files:
- `.Codex/rules/code-style.md` (globally imported) — Merged TypeScript + Python conventions. Default for full-stack projects.
- `.Codex/rules/python-style.md` (auto-loads via glob for `**/*.py`) — Python-only alternative. Not globally imported.

Based on their stack:
- **Python + JS/TS:** Keep `code-style.md` (the merged version). Delete `python-style.md` entirely since `code-style.md` covers Python.
- **Python-only:** Keep `python-style.md`. Remove `code-style.md` and its `@` import from `AGENTS.md`.
- **JS/TS-only:** Keep `code-style.md`. Delete `python-style.md`.
- **Other language (Go, Rust, Java, etc.):** Delete both style files and create a new one (e.g., `go-style.md` with `globs: "**/*.go"`). Add its `@` import to `AGENTS.md`.

**Bash permissions** — `settings.json` already includes commands for both Python and Node.js toolchains. Based on their stack:
- **Python + JS/TS:** No changes needed.
- **Python-only or JS/TS-only:** Optionally clean up commands for the unused toolchain.
- **Other language:** Add language-appropriate Bash commands (e.g., `Bash(go test *)`, `Bash(cargo test *)`, `Bash(./gradlew *)`).
- **All stacks:** Add WebFetch domains for their framework documentation sites.

### 5d. Project Commands

- Edit `AGENTS.md`: Replace the `## Project Commands` stub with actual commands in a fenced code block:
  ```markdown
  ## Project Commands
  ```bash
  make setup              # Install all dependencies
  make test               # Run tests across all packages
  ...
  ```
  ```
- If not provided, leave the stub

### 5e. Project Structure

- Edit `.Codex/skills/project-conventions/SKILL.md`: Replace the Project Structure directory tree with their actual layout
- If not provided, auto-detect from the filesystem or leave defaults

### 5f. Agent Pruning

Based on the project description, **proactively suggest** agents to remove. For example:
- No frontend mentioned → suggest removing Frontend Developer
- PoC maturity → suggest removing Security Engineer, Performance Engineer, Technical Writer, SRE Engineer, Product Manager, Project Manager
- No database → suggest removing Database Engineer
- No production deployment yet → suggest removing SRE Engineer
- Requirements already well-defined → suggest removing Product Manager
- Small scope / no PM tooling needed → suggest removing Project Manager

Include your suggestions in the confirmation message (Phase 4). **Do not remove any agents unless the user explicitly confirms which ones to remove.** Silence or a generic "looks good" about the overall setup is not confirmation for pruning — the user must specifically acknowledge the agent removal list.

For each agent the user confirms for removal:
- Delete the agent file from `.Codex/agents/`
- Edit `.Codex/AGENTS.md`: Remove the agent's row from the Routing Decision Matrix and Agent Capabilities Matrix tables
- Edit `AGENTS.md`: Remove the agent's row from the Quick Reference table

### 5g. Agent Model Tiers

The scaffold defaults to **expanded hybrid** — Opus for Product Manager, Architect, Tech Lead, and Code Reviewer; Sonnet for all others.

Adjust based on the user's maturity level and budget:
- **PoC or budget-constrained:** Suggest switching to all-sonnet (cost-optimized). Set `model: sonnet` in all agent frontmatter files.
- **MVP (default):** Keep expanded hybrid. No changes needed.
- **Production or security-sensitive:** Suggest quality-optimized if budget allows, or keep expanded hybrid.

If changing model tiers:
- Edit the `model:` field in each affected agent's frontmatter (`.Codex/agents/*.md`)
- Edit `.Codex/AGENTS.md`: Update the Agent Capabilities Matrix table (Model column) and the Cost Tiers table to match

Only suggest changing model tiers if the user's maturity level or budget hints at it. Don't ask about it unprompted for MVP-maturity projects — the default is appropriate.

### 5h. Convention Rules

Use scaffold defaults unless the user mentioned specific preferences. If they mentioned things like "we use Ruff" or "Google-style docstrings", update the relevant rule files.

### 5i. Domain-Specific Rules

If the user mentioned domain-specific concerns (HIPAA, financial precision, accessibility, data residency, etc.):
- Create `.Codex/rules/domain.md` with the rules formatted clearly
- Edit `AGENTS.md`: Add `@.Codex/rules/domain.md` to the Project Conventions section

### 5j. Personal Settings

- Copy `.Codex/settings.local.json.template` to `.Codex/settings.local.json` if it doesn't exist
- Default behavior: remove Red Hat / OpenShift org-specific domains (listed in `_template.org_domains`) unless the user indicated they work in that ecosystem
- Remove the `_template` key from `settings.local.json` if present
- If the user mentioned their organization's documentation domains, add those

### 5k. Secrets & Environment Protection

After all edits, inform the user about the scaffold's secret protection layers:

> **Secrets protection note:** The scaffold already excludes `.env` files from git (`.gitignore`) and blocks Codex from reading them (`.Codex/settings.json` deny list). If you use other AI-assisted IDEs (Cursor, Windsurf), you'll need to configure their ignore files separately. If you have additional secret file patterns (`.pem`, `.key`, `credentials.json`), add them to both `.gitignore` and the deny list.

If the user mentioned environment variables or secrets during the conversation, offer to create a `.env.example` file. Otherwise, skip this silently.

## Phase 6: Completion

After all edits are applied, display:

```
Setup complete! Here's what was configured:

[x] Project identity: <project name>
[x] Maturity level: <level>
[x] Project context: <domain>, <users>, <compliance>
[x] Goals: <count> goals, <count> non-goals defined
[x] Constraints: <count> constraints defined
[x] Technology stack: <primary language/framework>
[x] Style rules: <which kept — python-style.md, code-style.md, both, or custom>
[x] Project commands: <configured or defaults>
[x] Project structure: <configured or default>
[x] Convention rules: <reviewed or defaults> (<count> active rules)
[x] Agents: <count> active (removed: <list or "none">)
[x] Model tier: <expanded hybrid (default) / cost-optimized / hybrid / quality-optimized>
[x] Domain rules: <added or skipped>
[x] Personal settings: <configured or defaults>
[x] Secrets protection: git + Codex deny rules active

Your agents are ready. Just describe what you want to do in plain
language — the system will route to the right agents automatically.

Example: "I'd like to work with our agents to build a user
authentication system" or "Help me optimize the database queries."

Available slash commands:
  /review  — Code quality + security review of current branch
  /status  — Lint, typecheck, tests, dependency audit dashboard
  /adr     — Create an Architecture Decision Record
  /setup   — Re-run this wizard anytime to reconfigure

See START_HERE.md for the full reference guide.
```

## Tone Guidelines

- Be concise. Don't over-explain what you're about to do.
- Be opinionated. If you can infer a good default, use it. Don't ask about things that don't matter.
- Be conversational. "Got it" is better than "Thank you for providing that information."
- Respect "skip" and "just use defaults" — don't push back or re-ask.
- When summarizing what you understood, be specific so the user can correct misunderstandings. Don't parrot their words back — show you parsed them.
