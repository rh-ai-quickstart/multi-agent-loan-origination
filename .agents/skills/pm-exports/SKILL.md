---
description: Export format templates for project management tools (Jira, Linear, GitHub Projects, Agent Task Plan). Referenced by the Project Manager agent when generating exports.
user_invocable: false
---

# PM Export Formats

Templates for exporting work breakdown artifacts to external project management tools.

## Jira Import (JSON)

Write to `plans/exports/jira-import.json`:

```json
{
  "projects": [{
    "key": "PROJ",
    "issues": [
      {
        "issueType": "Epic",
        "summary": "Epic title",
        "description": "Epic description with acceptance criteria",
        "priority": "High",
        "labels": ["phase-1"],
        "customFields": {
          "Story Points": null
        }
      },
      {
        "issueType": "Story",
        "summary": "Story title",
        "description": "As a [role], I want [action], so that [benefit].\n\n## Acceptance Criteria\n- ...",
        "priority": "High",
        "labels": ["phase-1"],
        "epicLink": "Epic title",
        "customFields": {
          "Story Points": 5
        }
      },
      {
        "issueType": "Sub-task",
        "summary": "Task title",
        "description": "Technical description",
        "parent": "Story title",
        "customFields": {
          "Story Points": 2
        }
      }
    ]
  }]
}
```

## Linear Import (CSV)

Write to `plans/exports/linear-import.csv`:

```csv
Title,Description,Priority,Status,Estimate,Label,Parent
"Epic: Feature name","Epic description",Urgent,Backlog,,phase-1,
"Story: User action","As a user, I want...",High,Backlog,5,phase-1,"Epic: Feature name"
"Task: Technical action","Implementation details",Medium,Backlog,2,,"Story: User action"
```

## GitHub Projects (Markdown)

Write to `plans/work-breakdown.md` — a structured markdown document that can be converted to GitHub Issues via `gh issue create`:

```markdown
# Work Breakdown: [Feature Name]

## Phase 1: [Milestone Name]

### Epic: [E-001] [Title]

#### Stories

- **[S-001] [Title]** (5 pts, @backend-developer)
  - AC: Given..., when..., then...
  - Tasks:
    - [T-001] Task description (XS, @backend-developer)
    - [T-002] Task description (S, @test-engineer)
```

## Agent Task Plan

Write to `plans/agent-tasks.md` — formatted for creating TaskCreate calls with blockedBy dependencies:

```markdown
# Agent Task Plan: [Feature Name]

## Execution Order

### Phase 1: Requirements & Design
1. [@product-manager] Finalize PRD for [feature] → blockedBy: none
2. [@requirements-analyst] Write user stories for [feature] → blockedBy: [1]
3. [@architect] Design system architecture for [feature] → blockedBy: [2]
4. [@tech-lead] Technical design for phase 1 → blockedBy: [3]
5. [@project-manager] Work breakdown for phase 1 → blockedBy: [4]

### Phase 2: Implementation (parallel, per work breakdown)
WU-001: User API [@backend-developer] → blockedBy: [5]
  6. T-001: Add User model and schema
  7. T-002: Implement CRUD endpoints
  8. T-003: Write unit tests
WU-002: User UI [@frontend-developer] → blockedBy: [5]
  9. T-004: Add user list page
  10. T-005: Add user form component

### Phase 3: Quality
11. [@code-reviewer] Review implementation → blockedBy: [8, 10]
12. [@security-engineer] Security audit → blockedBy: [8, 10]

### Phase 4: Delivery
13. [@technical-writer] Write documentation → blockedBy: [11, 12]
```
