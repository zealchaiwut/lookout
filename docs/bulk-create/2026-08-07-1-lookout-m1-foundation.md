# Lookout M1 — Vault foundation

- Date: 2026-08-07
- Sprint label: sprint-1
- Default labels: enhancement, backend
- Status: draft

## Context

Milestone M1 of lookout (see PRODUCT.md milestones and DESIGN.md sections 1-2). Goal: the vault container everything later writes into — repo scaffold, registry, control note, lint skeleton, run wrapper stub. No LLM, no collectors yet. Hard invariants for every ticket: lookout never writes outside its own repo; the vault under vault/ is the only write surface; machine-owned vs human-owned convention per DESIGN.md section 1. Supersedes the earlier combined sprint file.

## Prompts

```
Scaffold the lookout repo per DESIGN.md section 1. Folder tree: vault/index.md, vault/agents.md, vault/map.md, vault/decisions.md, vault/journal/index.md, vault/ideas/index.md, vault/learning/global.md, vault/packs/.gitkeep, vault/projects/.gitkeep, .claude/skills/lookout/scripts/. Create targets.yaml at repo root with perf-coach (~/dev/perf-coach/uat, github zealchaiwut/perf-coach, commander_slug perf-coach) and commander (~/dev/commander/uat, github zealchaiwut/commander, commander_slug commander) plus a sources block (commander_api http://localhost:8000, notion_todos_db placeholder, journal_entries ~/dev/journal/entries). Create .env.example with NOTION_TOKEN and COMMANDER_API. AC: tree matches DESIGN.md section 1 exactly; targets.yaml parses with pyyaml; no file outside the repo is created or modified.
---
Write vault/agents.md as the control note per DESIGN.md section 1. It must: list every machine-owned file type (situation, capability body, drift, todo-view, atlas, index, journal index, ideas ledger and assessment blocks, packs) and every human-owned file type (notes, learning, decisions, agents.md, idea freeform tops); state the read-only invariant that no tool run from this repo may write to any target project, GitHub, Notion, or the journal repo; state that raw/ snapshots are the only source of truth for machine notes. Also write vault/index.md as an empty markdown table with columns target, one-liner, capacity, todos, last run. AC: agents.md names every file type from DESIGN.md section 1 with correct ownership; index.md renders as a valid markdown table.
---
Build lint.py skeleton in .claude/skills/lookout/scripts/. v1 checks: every [[wikilink]] under vault/ resolves to an existing file; every row in vault/index.md has a matching vault/projects/<name>/ folder and vice versa. Output a human-readable report; exit 1 on any failure, 0 otherwise. Structure the module so later checks (ownership warnings, snapshot age, question IDs) register into a check list. AC: passes on the freshly scaffolded vault; a fixture vault with one broken wikilink exits 1 naming the file and link; unit tests cover both checks with fixture vaults under tests/.
---
Build the run wrapper stub and README. bin/lookout (or lookout.sh at root) takes a target name, validates it against targets.yaml, prints a stub message that gather is not yet built, runs lint.py, and makes exactly one git commit in the lookout repo with message lookout(<target>): scaffold run <timestamp> only when something changed. Write README.md: what lookout is in three sentences, the run command, pointers to PRODUCT.md and DESIGN.md, and a status line saying collectors arrive in sprint-2 and synthesis in sprint-3. AC: invoking with a valid target runs lint and commits once; invoking with an unknown target exits nonzero listing valid targets; the script never touches any path outside the lookout repo.
```

## Posted issues

| # | Title | Issue |
|---|---|---|
| 1 | Repo scaffold + registry + env example | |
| 2 | Control note agents.md + empty index | |
| 3 | lint.py skeleton (wikilinks + index sync) | |
| 4 | Run wrapper stub + README | |
