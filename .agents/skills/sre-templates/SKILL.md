---
description: Operational document templates for SRE artifacts — SLO definitions, alerting rules, runbooks, capacity plans, and post-incident reviews. Referenced by the SRE Engineer agent.
user_invocable: false
---

# SRE Templates

Templates for SRE operational documents. All output goes to `docs/sre/`.

## SLO/SLI Definition

Write to `docs/sre/slos.md`:

```markdown
# Service Level Objectives

## Service: [Name]

### SLI: Availability
- **Definition:** Proportion of successful requests (HTTP 2xx/3xx) over total requests
- **Measurement:** `count(status < 500) / count(total)` over rolling 30-day window
- **SLO Target:** 99.9% (43.8 minutes/month error budget)
- **Data Source:** Load balancer access logs / Prometheus metrics

### SLI: Latency
- **Definition:** Proportion of requests served within threshold
- **Measurement:** `count(duration < 200ms) / count(total)` over rolling 30-day window
- **SLO Target:** 95% of requests < 200ms, 99% < 1000ms
- **Data Source:** Application metrics (histogram)

### SLI: Correctness
- **Definition:** Proportion of responses that return the expected result
- **Measurement:** Synthetic probe success rate
- **SLO Target:** 99.99%
- **Data Source:** Synthetic monitoring / canary checks

## Error Budget Policy

| Budget Remaining | Action |
|-----------------|--------|
| > 50% | Normal development velocity |
| 25-50% | Prioritize reliability work alongside features |
| 10-25% | Halt non-critical feature work; focus on reliability |
| < 10% | Freeze all changes except reliability fixes |
```

## Alerting Rules

Write alert configurations to `docs/sre/alerts.md` or directly to monitoring config files:

```markdown
# Alert: [Name]

**Severity:** critical / warning / info
**Condition:** [metric] [operator] [threshold] for [duration]
**Description:** What this alert means in plain language
**Impact:** What users experience when this fires
**Runbook:** docs/sre/runbooks/[name].md

## Examples

### High Error Rate
- **Condition:** `error_rate > 1%` for 5 minutes
- **Severity:** critical
- **Runbook:** docs/sre/runbooks/high-error-rate.md

### Elevated Latency
- **Condition:** `p99_latency > 2s` for 10 minutes
- **Severity:** warning
- **Runbook:** docs/sre/runbooks/elevated-latency.md
```

## Runbook Format

Write runbooks to `docs/sre/runbooks/<incident-type>.md`:

```markdown
# Runbook: [Incident Type]

## Overview
What this incident looks like and what typically causes it.

## Detection
How this incident is detected (alert name, dashboard, user report).

## Impact
What users experience during this incident.

## Severity Assessment
| Condition | Severity |
|-----------|----------|
| [condition] | SEV1 — critical |
| [condition] | SEV2 — major |
| [condition] | SEV3 — minor |

## Diagnosis Steps
1. Check [metric/dashboard] for [what to look for]
2. Run `[command]` to verify [condition]
3. Check [log source] for [pattern]

## Remediation Steps

### Immediate (Stop the Bleeding)
1. [Step with exact commands]
2. [Step with exact commands]

### Root Cause Fix
1. [Investigation steps]
2. [Fix steps]

## Escalation
- **If not resolved in 15 minutes:** Escalate to [team/person]
- **If customer-facing data loss:** Notify [stakeholder]

## Post-Incident
- [ ] Update incident timeline
- [ ] Create post-incident review document
- [ ] File follow-up tickets for permanent fixes
```

## Capacity Plan

Write to `docs/sre/capacity.md`:

```markdown
# Capacity Plan: [Service]

## Current Baseline
| Resource | Current Usage | Capacity | Utilization |
|----------|--------------|----------|-------------|
| CPU | ... | ... | ...% |
| Memory | ... | ... | ...% |
| Storage | ... | ... | ...% |
| Network | ... | ... | ...% |
| DB connections | ... | ... | ...% |

## Growth Projections
| Metric | Current | +3 months | +6 months | +12 months |
|--------|---------|-----------|-----------|------------|
| Requests/sec | ... | ... | ... | ... |
| Storage (GB) | ... | ... | ... | ... |
| Users | ... | ... | ... | ... |

## Scaling Thresholds
| Resource | Scale-Up Trigger | Scale-Down Trigger | Action |
|----------|-----------------|-------------------|--------|
| CPU | > 70% for 10min | < 30% for 30min | Add/remove instance |
| Memory | > 80% | < 40% for 30min | Add/remove instance |
| DB connections | > 80% pool | < 20% pool | Adjust pool size |

## Recommendations
[Specific actions to take based on projections]
```

## Post-Incident Review

Write to `docs/sre/post-incident/YYYY-MM-DD-<title>.md`:

```markdown
# Post-Incident Review: [Title]

**Date:** YYYY-MM-DD
**Duration:** [start time] — [end time] ([total duration])
**Severity:** SEV[1-4]
**Author:** [name]

## Summary
[1-2 sentence description of what happened]

## Impact
- **Users affected:** [number or percentage]
- **Duration of impact:** [time]
- **Data loss:** [yes/no, details]

## Timeline
| Time | Event |
|------|-------|
| HH:MM | [event] |
| HH:MM | [event] |

## Root Cause
[What actually broke and why]

## Contributing Factors
- [Factor 1]
- [Factor 2]

## What Went Well
- [Thing that helped]

## What Went Poorly
- [Thing that hurt]

## Action Items
| Action | Owner | Priority | Ticket |
|--------|-------|----------|--------|
| [action] | [owner] | P0/P1/P2 | [link] |

## Lessons Learned
[What we learned that applies beyond this incident]
```

## Incident Severity Levels

Write to `docs/sre/incident-process.md`:

| Severity | Impact | Response Time | Communication | Example |
|----------|--------|---------------|---------------|---------|
| SEV1 | Complete outage or data loss | Immediate page | Status page + stakeholder notification | API returning 500 for all users |
| SEV2 | Major feature degraded | 15 minutes | Status page update | Search is down but CRUD works |
| SEV3 | Minor feature degraded | 1 hour | Internal notification | Slow image uploads |
| SEV4 | Cosmetic or low-impact | Next business day | Ticket filed | Dashboard chart rendering glitch |
