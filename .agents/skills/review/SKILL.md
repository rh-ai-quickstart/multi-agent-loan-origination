---
description: Run a combined code quality + security review on the current branch. Analyzes the diff against the base branch and produces a unified report with findings by severity.
user_invocable: true
---

# Code Review

Run a combined code quality and security review of the current branch's changes.

## Process

Follow these steps in order:

### 1. Determine the Diff

First, detect the base branch by running `git remote show origin | grep 'HEAD branch'` (falling back to `main` if the remote is unavailable). Then run `git diff <base-branch>...HEAD` to get all changes on the current branch.

If there are also unstaged changes, include those with `git diff` as well. If on the base branch with no feature branch, review staged/unstaged changes instead.

Show the user a brief summary of what will be reviewed: number of files changed, insertions, deletions.

### 2. Code Quality Review

Analyze the diff for:

- **Correctness** — Logic errors, off-by-one, null/undefined risks, race conditions
- **Standards** — Adherence to project rules (code-style, testing, error-handling, api-conventions, observability)
- **Maintainability** — Code smells, excessive complexity, poor abstractions, duplicated logic
- **Testing** — Are changes covered by tests? Are edge cases handled?
- **Error handling** — Are errors handled at appropriate boundaries? RFC 7807 compliance?

### 3. Security Review

Analyze the diff for OWASP Top 10 issues:

- Injection risks (SQL, command, XSS, template)
- Broken access control (missing auth checks, IDOR)
- Hardcoded secrets, tokens, API keys
- Input validation gaps
- Insecure dependencies (if package files changed, run `npm audit` or equivalent)

### 4. Report

Present findings using this format:

```markdown
## Review: <branch-name>

**Files reviewed:** <count> | **Insertions:** +<n> | **Deletions:** -<n>

### Critical
- **[file:line]** — [description]
  **Fix:** [specific suggestion]

### Warning
- **[file:line]** — [description]
  **Fix:** [specific suggestion]

### Suggestion
- **[file:line]** — [description]

### Security
- **[SEVERITY] [file:line]** — [description]
  **Fix:** [specific remediation]

### Positive
- **[file:line]** — [what was done well]

---

**Verdict:** APPROVE / REQUEST_CHANGES / COMMENT
**Summary:** [1-2 sentence overall assessment]
```

If there are no findings in a severity category, omit that section. Always include the Positive section — acknowledge good work.
