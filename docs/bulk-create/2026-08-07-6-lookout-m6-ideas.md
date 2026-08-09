# Lookout M6 — Idea ledger + feasibility triage

- Date: 2026-08-07
- Sprint label: sprint-6
- Default labels: enhancement, ai
- Status: draft

## Context

Milestone M6 (DESIGN.md section 9). Goal: the ideas ledger with machine assessment blocks, lifecycle tracking to shipped, and todo enrichment — closing v1. Assessments must be grounded in atlas notes, capability cards, and snapshots built in M2 through M5; every claim cites its evidence. Mirror-only holds: promotion to commander tickets is manual; lookout assesses, the human dispatches.

## Prompts

```
Build the idea note conventions and ledger. Define in SKILL.md and agents.md: one note per idea at vault/ideas/<date>-<slug>.md with frontmatter (idea slug, created, status one of idea assessed promoted shipped parked, targets, issues list, assessed date), a human freeform top never machine-edited, and a machine Assessment section. vault/ideas/index.md is regenerated each run as the ledger table (idea, status, effort, blocked-by, age). AC: two fixture idea notes render into a correct ledger table; a hand edit to a freeform top survives regeneration byte-identical; an unknown status value fails lint with a clear message.
---
Add the assessment pass to SKILL.md per the DESIGN.md section 9 template. For ideas that are new or human-edited since their assessed date, capped at 3 per run, regenerate the Assessment section: already exists (citing atlas notes and capability cards by wikilink), must be built, effort S M or L, dependencies naming concrete blockers, suggested first slice as one small testable step. Grounding rule identical to section 4: no claim without a cited source; unknowns become open questions with IDs instead of guesses. AC: a fixture idea touching perf-coach and viral-radar produces an assessment citing at least one real atlas or capability note per claim; an idea about an unregistered project yields an assessment saying so plus a question, not invented facts; the cap and the assessed-date skip logic are covered by tests.
---
Build lifecycle tracking. When an idea frontmatter issues list is non-empty, each run checks those issue numbers against the snapshots of the affected targets: all closed advances status to shipped; otherwise status stays promoted with per-issue state shown in the Assessment. Extend lint.py: status promoted with an empty issues list warns; status shipped with any open issue errors. AC: a fixture idea with two issues where one closes shows mixed state; closing both flips status to shipped on the next run; both lint rules covered by tests.
---
Add todo enrichment to the todo view generation. For each Notion todo in todo-view.md, the assessment pass appends effort S M or L and blocked-by annotations derived from the same grounded evidence, marked clearly as lookout annotations; the Notion write home is untouched and no Notion API write exists anywhere. AC: a fixture todo matching a known atlas feature gains an effort and a blocked-by line citing evidence; grep across the repo shows no Notion write or update endpoint; annotations regenerate without duplicating.
---
M6 UAT: write three real ideas from the current backlog into vault/ideas/ (for example the Hermes journal summary skill), run the assessment pass, and review against the M6 exit criteria: each assessment names what exists, what is missing, and what blocks it, grounded in citations you spot-check by hand; promote one idea manually into commander tickets, record the issue numbers in the note, and verify tracking picks them up next run. Record all evidence in the issue. AC: three assessed ideas pass the spot check; the promoted idea shows per-issue state on the following run; findings recorded in issue comments.
```

## Posted issues

| # | Title | Issue |
|---|---|---|
| 1 | Idea note conventions + ledger index | |
| 2 | Grounded assessment pass | |
| 3 | Lifecycle tracking to shipped + lint | |
| 4 | Todo enrichment annotations | |
| 5 | M6 UAT: three real ideas assessed + one promoted | |
