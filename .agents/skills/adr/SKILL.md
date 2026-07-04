---
description: Create a new Architecture Decision Record (ADR). Walks through the decision context, options, and rationale interactively, then writes a numbered ADR file.
user_invocable: true
---

# Create ADR

Create a new Architecture Decision Record in `plans/adr/`.

## Process

### 1. Determine Next ADR Number

Check `plans/adr/` for existing ADRs. The next number is the highest existing number + 1, zero-padded to 4 digits (e.g., `0001`, `0002`). If `plans/adr/` doesn't exist, create it and start at `0001`.

### 2. Gather Decision Details

If the user provided a topic in their prompt (e.g., `/adr choose database`), use that as the starting context. Otherwise, use AskUserQuestion:

> **What architectural decision do you need to document?**

Then ask:

> **What context or constraints led to this decision? What options did you consider?**

### 3. Write the ADR

Create the file at `plans/adr/NNNN-<kebab-case-title>.md` using this template:

```markdown
# ADR-NNNN: <Title>

## Status

Accepted

## Context

<What is the issue or question that motivates this decision? Include constraints, requirements, and forces at play.>

## Options Considered

### Option 1: <Name>
- **Pros:** ...
- **Cons:** ...

### Option 2: <Name>
- **Pros:** ...
- **Cons:** ...

### Option 3: <Name> (if applicable)
- **Pros:** ...
- **Cons:** ...

## Decision

<What is the change we are making? State the decision clearly.>

## Consequences

### Positive
- ...

### Negative
- ...

### Neutral
- ...
```

Fill in as much as possible from the user's input. For sections where information is incomplete, add `<!-- TODO: fill in -->` markers.

### 4. Confirm

Show the user the file path and a summary:

```
Created: plans/adr/NNNN-<title>.md
Decision: <one-line summary>
Status: Accepted

Review the ADR and update any TODO sections.
```

Also remind them to reference this ADR in `AGENTS.md` Key Decisions if it affects technology choices.
