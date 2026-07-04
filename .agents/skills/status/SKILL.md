---
description: Run a project health check — lint, type check, tests, and dependency audit. Reports a pass/fail dashboard.
user_invocable: true
---

# Project Status Check

Run all project quality gates and report a health dashboard.

## Process

### 1. Read Project Commands

Read the "Project Commands" section of the root `AGENTS.md` to find the configured build, test, lint, and typecheck commands. If commands are still commented out or placeholder, tell the user and suggest they configure them (or run `/setup`).

### 2. Run Checks

Run each configured command and capture pass/fail status. Run them sequentially (lint and typecheck are fast; tests may be slow). For each check, capture:

- Exit code (0 = pass, non-zero = fail)
- Summary output (error count, test count/pass/fail, coverage percentage if available)
- Duration

Also run a dependency audit if a package manager lock file exists (`npm audit`, `pnpm audit`, `pip audit`, etc.).

### 3. Report Dashboard

Present results as a dashboard:

```markdown
## Project Health

| Check | Status | Details |
|-------|--------|---------|
| Lint | PASS/FAIL | <error count or "clean"> |
| Type Check | PASS/FAIL | <error count or "clean"> |
| Tests | PASS/FAIL | <passed>/<total> tests, <coverage>% coverage |
| Dependency Audit | PASS/FAIL | <vulnerability count by severity> |

**Overall: HEALTHY / NEEDS ATTENTION / FAILING**

### Issues
[List any failing checks with key error details]

### Suggestions
[Actionable next steps to fix any failures]
```

If a check is not configured (command is commented out), show it as `SKIPPED — not configured`.

### 4. Git Status

Also include a brief git status summary:

```markdown
### Git
- **Branch:** <current branch>
- **Ahead/behind:** <ahead>/<behind> vs <tracking branch>
- **Uncommitted changes:** <count> files modified, <count> untracked
```
