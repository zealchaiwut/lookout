# Lookout Skills

Agent-facing reference for the routines that Lookout exposes. Each routine is
a Python module at the repo root that can be called from a snapshot pipeline
or run directly from the CLI.

---

## `drift` — Drift Detection

**Module:** `drift.py`  
**Public API:** `detect_drift(docs_manifest, gitlog, brief)` → `list[dict]`  
**Writer:** `emit_drift_md(flags, output_path)`

### What it does

Reads three sources and surfaces contradictions before they silently mislead
the agent:

| Source | Key consumed |
|--------|-------------|
| `docs_manifest` | `files[].path`, `files[].content`, `migration_files` |
| `gitlog` | Free-text git log (e.g. `git log --oneline`) |
| `brief` | `completed_todos` list |

### Output — `drift.md`

Each flag in the output file contains:

- **Claim** — verbatim excerpt from the documentation that may be wrong
- **Evidence** — the path(s) and/or git ref that contradict the claim
- **Suggested fix** — plain-text action the agent (or human) can take

Only the top three highest-confidence flags are written (one per signal type).

### Signal types

**`removed_feature`** — A doc asserts an endpoint or feature that git history
shows was removed.  
Detection: any doc file whose content mentions a `METHOD /path` pattern that
also appears in a commit message containing removal verbs (remove, delete,
drop, deprecate, strip, disable).

**`todo_still_open`** — A todo item that commander has recorded as completed
still appears as unchecked (`- [ ]`) in a documentation file.  
Detection: compares `brief.completed_todos` against open checkboxes in any
`docs/` file tracked in `docs_manifest`.

**`schema_name_diverges`** — A `## heading` in `SCHEMA.md` does not match any
migration file name exactly (after stripping numeric prefixes and extensions).  
Detection: headings in files whose path contains `SCHEMA` are compared against
`docs_manifest.migration_files`.

### Integration with `situation.md`

When `drift.md` exists in `vault/projects/<target>/`, `synthesize.py` reads
its top three claim lines and surfaces them in the `## Drift` section of
`situation.md` in place of the default manifest-diff signals.

### CLI

```
python drift.py <target-name> [--vault <vault_dir>]
```

Reads the latest snapshot from `vault/projects/<target>/raw/`, runs detection,
and writes `vault/projects/<target>/drift.md`.

### Fixture

A seeded contradiction fixture lives at `tests/fixtures/drift/`:

| File | Purpose |
|------|---------|
| `api-docs.md` | Doc stub claiming `GET /v1/widgets` exists |
| `gitlog.txt` | Simulated git log showing commit `abc1234` removing that endpoint |
| `docs_manifest.json` | Manifest describing the fixture files |

Running drift detection against this fixture produces a `removed_feature` flag
citing both the doc path and the git ref — used by tests to verify the
detection logic end-to-end.

---

## `todo-view` — Todo View Generation

**Module:** `todo_view.py`  
**Public API:** `generate_todo_view(notion_todos, docs_todo_content)` → `str`  
**Writer:** `write_todo_view(notion_todos, docs_todo_content, output_path)`

### What it does

Consolidates two todo sources into a single read-only file
(`todo-view.md`) so contributors have one place to see all outstanding work
without risk of editing the wrong source.

### Output — `todo-view.md`

The file always contains **exactly two sections**:

#### Section 1 — Notion Todos

Renders Notion todos scoped to this project. Each item is shown with its
current status rendered as a Markdown checkbox (`[x]` or `[ ]`).

A banner is always present:

> **Source: Notion** — This section is a read-only mirror of Notion todos
> scoped to this project. Notion is the authoritative write home for these items.

The banner appears even when Notion returns zero todos for the project.

#### Section 2 — Commander Todos

Mirrors `docs/todo.md` verbatim. No content is transformed or filtered.

A banner is always present:

> **Source: commander** — This section mirrors `docs/todo.md` verbatim.
> Commander is the maintainer of that file.

The banner appears even when `docs/todo.md` is empty.

### Invariants

- `todo-view.md` contains **no instruction** telling contributors to edit it
  directly; annotations and commentary belong only in a `notes` block.
- Both banners are present in every generated file, regardless of whether
  either source is empty.
- The file is fully regenerated on each run; it must not be edited by hand.

### CLI

```
python todo_view.py <target-name> [--vault <vault_dir>] [--docs-todo <path>]
```

Reads Notion todos from the latest snapshot and `docs/todo.md` from `<path>`
(default: `docs/todo.md` in the repo root), then writes
`vault/projects/<target>/todo-view.md`.

---

## `journal-crosslink` — Journal Cross-Link Writer

**Module:** `journal_crosslink.py`  
**Public API:** `crosslink(delta, vault_dir, targets)` → `None`

### What it does

Reads `journal_delta.json` and for each registered target that has mentions
in the delta:

1. Updates `vault/projects/<target>/SKILL.md` with a `## From the journal`
   section containing one dated link per distinct date — no full entry text
   is copied.
2. Appends new rows to `vault/journal/index.md`, one per distinct date,
   tagged with the target name.

### Dated link format

```
[2026-03-12](../../journal/entries/2026-03-12.md) — one-line gist
```

Each gist is the first `target_lines` entry mentioning the target, truncated
to 100 characters. If the delta has zero mentions of a target, that target's
SKILL.md and `vault/journal/index.md` are left completely unchanged.

### CLI

```
python journal_crosslink.py [--delta <path>] [--vault <dir>]
```

Reads `journal_delta.json` (default: repo root) and writes to the vault.

---

## `capability-card` — Capability Card Generator

**Module:** `capability_card.py`  
**Public API:** `generate_capability_card(target, vault_dir)` → `Path`  
**Token counter:** `count_tokens(text)` → `int`

### What it does

Generates or regenerates `vault/projects/<target>/capability.md` — a
machine-readable, token-bounded summary that lets AI agents introspect a
target's read surfaces, commander slug, and constraints without reading
the full snapshot.

### Output — `capability.md`

Always contains exactly five required sections plus a preserved sixth:

| Section | Content |
|---------|---------|
| `## What it is` | ≤2 sentences describing the target |
| `## Data it owns` | datasets and vault artifacts |
| `## Read surfaces` | every real GET endpoint from snapshot + one example call |
| `## How to make it do things` | commander slug, bulk-create path, CLI entry points |
| `## Constraints` | known limitations and invariants |
| `## Notes for AI` | **preserved verbatim** across regenerations |

### Sentinel preservation

The `## Notes for AI` section is extracted from any existing `capability.md`
before regeneration and re-injected verbatim, so notes and sentinel strings
placed there survive unlimited regenerations.

### Token budget

Output is capped at 1500 tokens (measured by `count_tokens()`, which counts
space-separated tokens). When the endpoint list causes the budget to be
exceeded, the lowest-priority endpoints are trimmed until the file fits.

### Snapshot evidence

GET endpoints are read from `endpoints.json` in the target's latest snapshot
directory (`vault/projects/<target>/raw/<latest>/`). If no `endpoints.json`
exists, the Read surfaces section states this explicitly; no fabricated or
placeholder endpoints are written.

### CLI

```
python capability_card.py <target> [--vault <dir>]
```

Reads the latest snapshot and writes `vault/projects/<target>/capability.md`.

---

## `question-registry` — Question Generation and Decision Read-Back

**Module:** `question_registry.py`  
**Public API:**  
- `generate_questions(project_dir, target_name, drift_flags, stalled_items, human_notes)` → `list[dict]`  
- `resolve_questions(project_dir, vault_dir, target_name)` → `list[dict]`  
- `get_open_questions(project_dir)` → `list[dict]`  
- `get_resolved_questions(project_dir)` → `list[dict]`  
- `detect_decision_contradictions(project_dir, vault_dir, docs_manifest)` → `list[dict]`  
- `parse_drift_md_flags(drift_md_path)` → `list[dict]`  
- `extract_human_note_carryovers(notes_path)` → `list[str]`  
- `extract_stalled_items(issues_data)` → `list[dict]`

### What it does

Implements automatic question generation from snapshot signals and a
decision read-back pass that marks resolved questions and cross-links
them to their decision entries.

### Question ID format

Each question receives a stable, never-reused ID:

```
<PREFIX>Q<n>
```

Where `PREFIX` is the first two letters of the target name (uppercase)
and `n` increments monotonically. Example: `SKQ1`, `CMQ3`.

IDs are persisted in `vault/projects/<target>/questions.json` so they
survive across runs and are never reissued.

### Signal sources

| Signal | Extracted from |
|--------|---------------|
| Unresolved drift flags | `drift.md` (via `parse_drift_md_flags`) |
| Blocked/stalled issues | `issues.json` (labels: blocked, stalled) |
| Human-note carry-overs | `notes.md` lines ending in `?` or starting with `> ` |

Each question includes:
- `evidence` — link to the source signal
- `options` — 2–3 resolution options derived from signal type and context

### Decision read-back

`resolve_questions()` parses both:
- `vault/decisions.md` (vault-level decisions)
- `vault/projects/<target>/decisions.md` (project-level decisions)

Any question ID (e.g. `SKQ1`) found in a decision entry is marked
`resolved` and removed from the open list. The situation note for that
question gains a cross-link to the decision heading that closed it.

### Decision-contradiction drift detection

`detect_decision_contradictions()` scans decisions.md for lines marked:

```
**Deprecated:** <item>
**Removes:** <item>
**Revokes:** <item>
```

If any tracked doc file still mentions the deprecated item, a drift flag
is raised with suggested edit text pointing at the contradiction.

### lint.py integration (AC7 + AC8)

Two new checks are wired into `lint.py`:

| Check | Level | Trigger |
|-------|-------|---------|
| Decision question refs | `[WARN]` | Decision entry references a `<PREFIX>Q<n>` ID not in any `questions.json` |
| Stale open questions | `[INFO]` | Open question with `created` date older than 14 days |

Both checks are non-fatal (exit code remains 0).

### Registry file format

`vault/projects/<target>/questions.json`:

```json
{
  "prefix": "SK",
  "next_id": 3,
  "questions": {
    "SKQ1": {
      "id": "SKQ1",
      "created": "2026-08-10",
      "signal_type": "removed_feature",
      "signal_text": "drift:GET /v1/widgets",
      "text": "How should we resolve: GET /v1/widgets?",
      "evidence": "api-docs.md (doc) + abc1234 (git)",
      "options": ["Remove the stale doc reference", "Re-introduce in a new PR"],
      "status": "open"
    },
    "SKQ2": {
      "id": "SKQ2",
      "created": "2026-08-09",
      "signal_type": "stalled_item",
      "status": "resolved",
      "resolved_by": "Migrate to Postgres (SKQ2)"
    }
  }
}
```

### CLI

Question generation is triggered automatically by `synthesize.py` on
every run. The registry can also be accessed directly:

```python
from question_registry import (
    generate_questions, resolve_questions, get_open_questions
)
```

---

## Notes

All skill modules are pure Python with no external dependencies beyond the
standard library. Test coverage lives in `tests/test_drift.py`,
`tests/test_todo_view.py`, `tests/test_journal_crosslink.py`,
`tests/test_capability_card.py`, and `tests/test_questions.py`. The fixture
for end-to-end testing of drift detection is committed under
`tests/fixtures/drift/`.
