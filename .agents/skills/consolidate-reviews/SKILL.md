---
description: Consolidate multiple review files into a single de-duplicated triage table. Reads review files, merges overlapping findings, surfaces disagreements, and outputs a structured document for user triage.
user_invocable: true
---

# Review Consolidation

You are running the review consolidation skill. Your job is to read multiple review files for a single artifact, de-duplicate findings, surface disagreements, and produce a compact triage table for the user.

## Usage

```
/consolidate-reviews plans/reviews/requirements-review-*.md
/consolidate-reviews plans/reviews/technical-design-phase-1-review-*.md
```

The argument is a glob pattern or space-separated list of review file paths.

## Process

### 1. Read All Review Files

Read every file matching the provided pattern. For each file, extract:
- Reviewer name (from filename: `*-review-<reviewer>.md`)
- Verdict (APPROVE, REQUEST_CHANGES, NEEDS_DISCUSSION)
- Individual findings with their severity (Critical, Warning, Suggestion, Positive)
- For each finding: the description, affected location (file/section), and suggested resolution

### 2. De-duplicate Findings

Two findings are duplicates when they:
- Reference the same file, section, or concept
- Describe the same root cause or concern
- Suggest the same or compatible resolutions

When merging duplicates:
- Keep the highest severity across reviewers
- Note all reviewers who flagged the issue
- Merge suggested resolutions (if compatible) or note the variations

### 3. Identify Disagreements

Flag findings where reviewers disagree on:
- **Severity** — one reviewer says Critical, another says Suggestion for the same issue
- **Resolution** — reviewers propose conflicting fixes for the same issue
- **Verdict** — one reviewer approves, another requests changes

### 4. Produce Consolidated Output

Write the consolidated review to `plans/reviews/<artifact>-review-consolidated.md`.

Determine the artifact name from the input pattern:
- `requirements-review-*.md` -> artifact is `requirements`
- `technical-design-phase-1-review-*.md` -> artifact is `technical-design-phase-1`
- `product-plan-review-*.md` -> artifact is `product-plan`
- `architecture-review-*.md` -> artifact is `architecture`
- `work-breakdown-phase-N-review-*.md` -> artifact is `work-breakdown-phase-N`

## Output Format

```markdown
# Consolidated Review: <Artifact Name>

**Reviews consolidated:** <comma-separated list of review files>
**Date:** <current date>
**Verdicts:** <reviewer: verdict, reviewer: verdict, ...>

## Summary

- Total findings across all reviews: N
- De-duplicated findings: M
- Reviewer disagreements: K
- Breakdown: X Critical, Y Warning, Z Suggestion, W Positive

## Triage Required

### Critical (must fix before proceeding)

| # | Finding | Flagged By | Location | Suggested Resolution | Disposition |
|---|---------|-----------|----------|---------------------|-------------|
| C-1 | <description> | Architect, Orchestrator | <section/file> | <resolution> | _pending_ |
| C-2 | ... | ... | ... | ... | _pending_ |

### Warning (should fix)

| # | Finding | Flagged By | Location | Suggested Resolution | Disposition |
|---|---------|-----------|----------|---------------------|-------------|
| W-1 | ... | ... | ... | ... | _pending_ |

### Reviewer Disagreements

| # | Issue | Location | Reviewer A | Reviewer B | Disposition |
|---|-------|----------|-----------|-----------|-------------|
| D-1 | <issue description> | <location> | <reviewer>: <position + severity> | <reviewer>: <position + severity> | _pending_ |

### Suggestions (improve if approved)

| # | Finding | Flagged By | Location | Suggested Resolution | Disposition |
|---|---------|-----------|----------|---------------------|-------------|
| S-1 | ... | ... | ... | ... | _pending_ |

### Positive (no action needed)

- <positive finding 1> — <reviewer>
- <positive finding 2> — <reviewer>
```

## Disposition Values

The `Disposition` column is left as `_pending_` for the user to fill in during triage. Valid dispositions:

| Disposition | Meaning |
|-------------|---------|
| **Fix** | Must be addressed before proceeding |
| **Improvement** | Would make the artifact better but not blocking |
| **Defer** | Valid concern but out of scope for this artifact |
| **Dismiss** | Disagree with finding — document rationale |

## Guidelines

- **Compact output.** Target ~100-200 lines for a typical 3-reviewer gate. The point is to reduce what the orchestrator needs to read, not to produce another long document.
- **Preserve attribution.** Every finding must note which reviewer(s) flagged it. This matters for the "Explain It to Me" protocol.
- **Higher severity wins.** When de-duplicating, if one reviewer says Critical and another says Warning, the consolidated finding is Critical.
- **Don't editorialize.** Present the findings as-is. The skill consolidates — the user decides.
- **Omit empty sections.** If there are no disagreements, skip the Disagreements section. If there are no Critical findings, skip that section.
