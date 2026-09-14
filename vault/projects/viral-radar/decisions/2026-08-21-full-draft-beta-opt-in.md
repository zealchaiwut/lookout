---
id: VR-D2
date: 2026-08-21
status: active
targets:
  - viral-radar
issues:
  - 109
prs: []
sprints:
  - sprint-14
supersedes: null
superseded_by: null
questions: []
---

# VR-D2 — Full-draft beta stays opt-in only

## Context

PRODUCT allows an opt-in "Generate full draft (beta)" path (issue #109 /
M12.4 checkpoint). Voice protection is a hard job: structure-only is the
default. Shipping beta prose as the default would violate Protect the voice.

## Decision

Keep full-draft generation **opt-in and labelled beta**. It must never be the
default, never feed templates or diagnosis, and remains subject to the M12.4
keep/shrink/drop review on #109.

## Consequences

- UI must show beta labelling on that path.
- Closing or shrinking #109 may supersede this decision later.

## Links

- Issue: #109
- Sprint: `sprint-14`
