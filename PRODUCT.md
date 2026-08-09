# Lookout — Product Overview

Lookout is a read-only second brain for a solo developer running multiple
commander-driven projects. It maintains a plain-markdown vault that answers,
per project: **where are we, what changed, what should happen next, what has
drifted** — and, across projects: **what can each project do for the others,
and how do they compose**. Context-switching between projects should cost
minutes, not an afternoon of re-reading; and any AI session should be able to
load a project's — or a project *combination's* — working knowledge from one
stable place.

## Problem

- Running 5+ projects (commander, perf-coach, crux, viral-radar,
  asset-studio, nerdysteps tooling) through commander sprints works, but
  *switching* between them does not. Each switch requires re-deriving "where
  was I" from GitHub issues, git log, and memory.
- Context-switch fatigue leads to lazy delegation — one-line prompts to LLM
  agents — which produces spec mismatch and rework.
- Cross-project work (e.g. viral-radar insights → perf-coach data → crux
  probe → asset-studio content) requires re-explaining every project to the
  LLM in every session. There is no single place an AI can read to understand
  what the projects are and how they connect.
- Project knowledge (decisions, feature internals, tutorials, todos, journal
  reflections) is scattered across repos, Notion, a Kindle Scribe pipeline,
  chats, and heads.

## What Lookout is

- A **Claude Code skill** (`lookout <project>`) run manually when sitting
  down to work; nightly automation is v2. It reads a target's state and
  synthesizes/updates notes in the vault.
- A **vault**: one git-versioned folder of plain markdown at `~/dev/lookout`,
  one project space per target, cross-linked with `[[wikilinks]]`. Any
  editor works; Obsidian is an optional overlay (graph view, backlinks, iPad)
  with zero migration cost — **not a dependency**.
- A **mirror, not a front door.** Tickets are born in commander. Todos are
  managed in Notion. Journal entries are produced by the existing journal
  pipeline. Lookout reflects and connects; it never originates or edits any
  of them.
- An **AI knowledge layer**: per-project capability cards, a cross-project
  map, and a context-pack builder that assembles paste-ready briefings for
  fresh Claude sessions or Claude Code runs.

## What Lookout is not (invariants)

- **Never writes to target projects.** No file writes, no GitHub writes, no
  commander/Notion API writes. The only writable surface is the vault.
- **No database, no vector store, no server, no web UI.** Markdown + git.
- **No re-derivation of what other tools already derive** (borrow, don't
  build): sprint state and briefs come from commander's APIs; journal entries
  come from the existing Scribe→Gmail→OCR pipeline; deep code graphs remain
  Understand-Anything's job (run on demand, linked out).

## Features

1. **Target registry** — `targets.yaml`: name, local path, GitHub slug,
   commander slug. Registered once per project. Special entries for the
   commander API base URL, the Notion todos database, and the journal
   entries path.
2. **Read-only gather** — commander HTTP API (brief, sprint history, health)
   + `gh` (issues/PRs, read verbs only) + `git log` + docs manifest + Notion
   todos + journal entries → a timestamped `raw/` snapshot. Every source
   degrades gracefully when down.
3. **Situation note** — per target: one-liner, capacity verdict ("clear to
   start new work" / "sprint N running" / "2 blocked items first"),
   since-last-run delta, next ≤5 actions, open questions.
4. **Drift flags** — places where a target's docs disagree with its code,
   schema, git history, or commander state. Each flag: claim, evidence path,
   suggested fix as text — never applied.
5. **Todo hub: Notion write, vault mirror** — todos are *managed* in one
   Notion database (a Project property per target + Global). Lookout reads
   it via a Notion integration token (read-only) and mirrors into each
   project space and the index. The target repo's auto-maintained
   `docs/todo.md` appears as a second, clearly labeled section.
6. **Feature atlas (code-level)** — one note per feature of the target:
   what it does, entry points, key files, related issues, and a **Mermaid
   flow diagram traced from actual source** (Understand-Anything-style, but
   owned and versioned in the vault). Incremental: frontmatter file-maps +
   git-diff staleness; only stale features re-traced, capped per run.
7. **Journal reader** — consumes the existing journal pipeline's
   `entries/YYYY-MM-DD.md` (Scribe → Gmail → Vision OCR, already scheduled
   on zeal-server). Lookout extracts project mentions and concerns from
   entries newer than the last snapshot and wikilinks them into situation
   notes plus a journal index. Full entries stay in the journal repo — the
   vault holds only derived cross-links. **No ingest is built here.**
8. **Capability cards + context packs (AI knowledge layer)** —
   - *Capability card* per target (`capability.md`, ~1.5K-token budget,
     machine-owned with a preserved human `## Notes for AI` section): what
     it is, data it owns, **concrete read surfaces with example calls**,
     how to make it do things (commander slug, CLI entry points), and
     constraints (localhost-only, never-writes rules).
   - *Cross-project map* — one note of producer/consumer edges between
     targets; machine-drafted, human-curated pipeline patterns (e.g.
     viral-radar → perf-coach → crux → asset-studio for content).
   - *Context pack builder* — `lookout pack <targets...>` concatenates the
     selected cards + situation one-liners + the map into one paste-ready
     markdown for a fresh Claude session; Claude Code reads the same stable
     vault paths directly.
9. **Cross-project index** — one row per target: one-liner, capacity, todo
   count, last-run staleness badge.
10. **Human spaces** — `notes.md` per project, `learning/` per project and
    global (tutorials, cert paths). Machine never writes these.
11. **Lint + journal commits** — broken-wikilink and index checks,
    hand-edit-of-machine-file warnings, one git commit per run whose message
    is the situation one-liner — the vault's git log is itself a journal.
12. **Idea ledger + feasibility triage** — `vault/ideas/`: one note per
    idea, mixed-ownership. You write the idea freeform; Lookout appends a
    machine `## Assessment`: affected targets, what already exists vs must
    be built (from the atlas and capability cards), effort S/M/L,
    dependencies ("needs X fixed first"), and a lifecycle status
    (`idea → assessed → promoted → shipped/parked`). When an idea becomes
    commander tickets (manually — mirror-only holds), issue numbers dropped
    into the note are tracked to shipped by later runs, so shipped work
    links back to its originating idea. The same assessment treatment
    enriches the Notion todos inside `todo-view.md` (difficulty, blocked-by)
    — vault-side only, Notion is never written. New/changed ideas only,
    capped per run.
13. **Discussion loop: questions out, decisions in** — synthesis phrases
    unresolved items (drift, blocked work, idea unknowns) as decision-ready
    questions with stable IDs. `lookout discuss <target|idea>` builds a
    paste-ready discussion pack (questions + minimal grounding) for a
    claude.ai session. Afterward you log outcomes in a human-owned
    `decisions.md` (ADR-lite: date, question ID, decision, why, affects).
    Later runs mark questions resolved, cross-link decisions from
    situation/idea notes, and raise a drift flag with suggested edit text
    when a target's docs contradict a logged decision — the doc fix itself
    ships as a commander ticket, so read-only holds.

## Data sources (all read-only)

| Source | Via |
|---|---|
| Commander state | HTTP API at localhost:8000 (brief, sprint history, health, analytics) |
| Issues / PRs | `gh` read verbs with existing token |
| Code & docs | Target local checkout: `git log`, README/PRODUCT/DESIGN/SCHEMA, `docs/`, source files (atlas) |
| Todos | Notion database via integration token |
| Journal | `~/dev/journal/entries/*.md` (existing pipeline's output) |

## Surfaces

- **The vault in any editor** — primary surface (Obsidian optional).
- **Terminal** — a run prints the situation summary as it writes it.
- **Context packs** — paste-ready markdown for claude.ai sessions.
- **Claude Code / commander planning sessions** — read the vault as context
  to resume a project or plan cross-project work.

## Scope

### v1 (in)

Features 1–13 above, manual runs, one target per run (`pack` takes many).
Initial targets: perf-coach first, then commander, crux, viral-radar,
asset-studio.

### v2 (deferred, in order)

1. **Nightly refresh** — launchd on zeal-server runs `lookout --all`; same
   deterministic writer as manual runs, so no conflict model needed.
2. **Notion weekly digest** — publish a cross-project digest page via Notion
   MCP for iPad reading. MD stays the source of truth.
3. **Inbox/promote** — idea intake emitting bulk-create sprint files in
   commander's format. Deferred deliberately: mirror-only keeps one front
   door for tickets until the mirror has earned trust.
4. **Hermes reader** — Hermes reads situation notes for Discord nudges.

### Out (any version)

- Writing to targets, commander, GitHub, Notion, or the journal repo.
- Journal ingest/OCR (exists), deep code-graph engines (UA on demand),
  databases, embeddings, web UIs.

## Milestones

**M1 — Vault foundation.** Scaffold `~/dev/lookout` with `targets.yaml`,
control note, index, and the machine-owned vs human-owned convention. No
intelligence yet — just the container every later milestone writes into.
Done when lint passes on the empty vault.

**M2 — Gather pipeline.** `gather.py` for perf-coach: commander API, `gh`,
git log, docs manifest, Notion todos DB, journal entries reader — all into
timestamped `raw/` snapshots with per-source graceful degradation. Purely
deterministic, no LLM anywhere. Done when a snapshot is complete,
re-derivable, and provably read-only.

**M3 — Synthesis brain.** SKILL.md turns snapshot + previous notes into the
situation note, drift flags, todo mirror, journal cross-links, the
per-project capability card, and decision-ready questions with stable IDs —
plus the `decisions.md` convention and read-back (resolve questions,
cross-link, drift on contradiction). LLM narrates snapshot facts only. Done
when `lookout perf-coach` yields a situation note you'd trust after a week
away and a logged decision changes the next run's output. Riskiest
milestone — prompt quality decides whether the whole tool is useful or
noise.

**M4 — Feature atlas.** Code-level tracing per feature with Mermaid flow
diagrams, frontmatter file-maps, git-diff staleness detection, and a
~3-refreshes-per-run cap. Seeded from README feature tables, deepened by
reading actual source — the Understand-Anything-style layer, owned by the
vault. Done when perf-coach's top 5 features have atlas notes whose diagrams
match the code.

**M5 — Multi-project + AI knowledge layer.** Register commander, crux,
viral-radar, and asset-studio; build the cross-project map, the context
pack builder (`lookout pack <targets...>`), and the discussion pack command
(`lookout discuss`); finish `lint.py` and commit-per-run. Done when pasting
a 4-project pack into a fresh Claude session produces a sensible
composition plan (the viral-radar → perf-coach → crux → asset-studio
example), and the 10-minute context switch works everywhere.

**M6 — Idea ledger + feasibility triage.** `ideas/` notes with machine
assessment blocks (feasibility, effort, dependencies, lifecycle status)
plus per-todo enrichment in the todo views — all derived from the atlas,
cards, and snapshots that M2–M5 built, which is why it slots here and not
earlier. Done when a raw idea like "Hermes summarizes my journal" gets an
assessment naming what exists, what's missing, and what blocks it — and a
promoted idea tracks through to shipped. This closes v1 and makes Lookout
the keeper of the idea backlog, not just project state.

**M7 — v2 automation.** Nightly `lookout --all` via launchd on zeal-server,
Notion weekly digest via MCP, inbox/promote if the mirror has earned trust,
and Hermes reading situation notes for Discord nudges. Each piece is
independent — ship in any order as the manual habit proves itself. Done when
the index and packs are fresh every morning without you touching anything.

## Success criteria

- Sitting down on any project after ≥1 week away: productive in under 10
  minutes using only the situation note.
- A fresh Claude session given one context pack can propose a workable
  cross-project plan without any re-explaining.
- Prompts fed to commander's BA reference situation-note and capability-card
  facts (measurably fewer spec-mismatch reworks).
- Any idea written to `ideas/` receives an assessment grounded in real
  code/doc evidence within one run, and no idea silently disappears —
  every note carries a lifecycle status.
- Every significant decision has a five-line log entry, and no question is
  discussed twice because the answer was lost — resolved questions stay
  resolved across runs.
- Vault survives deletion of everything except `raw/` + the skill
  (re-derivable), and every machine note regenerates without clobbering a
  human note.
