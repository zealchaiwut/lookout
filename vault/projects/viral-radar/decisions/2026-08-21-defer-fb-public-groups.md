---
id: VR-D1
date: 2026-08-21
status: active
targets:
  - viral-radar
issues:
  - 115
prs: []
sprints:
  - sprint-14
supersedes: null
superseded_by: null
questions: []
---

# VR-D1 — Defer FB public groups connector

## Context

Issue #115 asked whether viral-radar should scrape Facebook public groups
as a discovery source. That path has legal/ToS and quality risk; quarantine
sampling of page accounts already covers the "find unknown runners" job for
M12.

## Decision

**Defer** the public-groups connector. Do not scope or ticket implementation
until quarantine discovery has proven it surfaces ≥1 useful unknown account
(PRODUCT milestone 4 exit test). Prefer page watchlist + quarantine only.

## Consequences

- No Apify actor / rate budget for groups in M12.
- Discovery UI stays candidate-from-pages; groups stay out of SCHEMA.
- Revisit only with a new decision that supersedes this one.

## Links

- Issue: #115
- Sprint: `sprint-14`
