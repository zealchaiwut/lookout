# Lookout M5 — Multi-project + AI knowledge layer

- Date: 2026-08-07
- Sprint label: sprint-5
- Default labels: enhancement, backend
- Status: draft

## Context

Milestone M5 (DESIGN.md sections 7 and 8). Goal: register crux, viral-radar, and asset-studio alongside perf-coach and commander; cross-project map; deterministic pack builder for context packs and discussion packs; full lint; the 4-project pack exit test. pack.py is deliberately LLM-free — pure concatenation — so packs are cheap and never invent an endpoint. Prerequisite: local checkouts exist for the three new targets at the paths registered in ticket 1.

## Prompts

```
Register crux, viral-radar, and asset-studio in targets.yaml with their real local paths, github slugs, and commander slugs, then run gather and synthesis for each and fix whatever breaks on repos with different shapes (missing SCHEMA.md, no docs folder, different README structure). Seeding and collectors must tolerate absent files by recording them absent, never failing. AC: all five targets produce complete snapshots and situation notes plus capability cards; vault index shows five rows with real one-liners; no collector raises on any of the five repos.
---
Add cross-project map generation to SKILL.md per DESIGN.md section 7. map.md has two marked sections: Edges, machine-drafted each run from the five capability cards as producer to consumer lines naming the concrete surface (for example viral-radar produces post performance patterns via its export, perf-coach exposes read-only training data via its GET endpoints); and Pipelines, human-owned, never machine-edited, linked from the index. AC: generated edges name only surfaces that appear in capability cards; a sentinel pipeline entry in the human section survives three runs; the index links to map.md.
---
Build pack.py with the context pack command. lookout pack <target...> writes vault/packs/<date>-<slug>.md containing: header with generated date, targets, and staleness warnings for any card older than 7 days; the selected capability cards in order; each target situation one-liner plus capacity line only; map.md both sections; footer with the read-only ground rules from agents.md. Pure concatenation, no LLM. AC: a 4-project pack assembles in under a second; a stale card produces a visible warning line in the header; content is byte-for-byte traceable to its source files.
---
Add the discussion pack command to pack.py per DESIGN.md section 10. lookout discuss <target-or-idea> writes vault/packs/<date>-discuss-<name>.md containing: all open questions with their IDs, evidence links, and options; the capability card; situation one-liner plus capacity; and only the drift or atlas excerpts each question cites. AC: a target with three open questions yields a pack containing exactly those three with IDs; a resolved question never appears; an idea argument pulls the idea note plus assessments of its affected targets.
---
Full lint pass and M5 UAT. Finish lint.py: all registered checks run across the whole vault (wikilinks, index sync, ownership warnings, snapshot age, card token budget, question ID rules) with a summary table. UAT checklist recorded in the issue: paste a fresh 4-project context pack (perf-coach, viral-radar, crux, asset-studio) into a new claude.ai session and confirm it can propose a workable content-loop composition without any correction of facts; perform a cold context switch on two projects using only their situation notes and record time under 10 minutes each. AC: lint summary clean on the full vault; both UAT results recorded with evidence in issue comments.
```

## Posted issues

| # | Title | Issue |
|---|---|---|
| 1 | Register 3 new targets + shape hardening | |
| 2 | Cross-project map generation | |
| 3 | pack.py context packs | |
| 4 | Discussion pack command | |
| 5 | Full lint + M5 UAT (4-project pack test) | |
