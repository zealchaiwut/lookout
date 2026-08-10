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

## `atlas-trace` — Stale Feature Tracing

**Module:** `atlas_trace.py`  
**Public API:** `generate_note(feature_name, source_dir, entry_point_file, issues)` → `str`  
**Helpers:** `extract_mermaid_block(note_text)` → `str | None`, `get_node_names(mermaid_text)` → `list[str]`

### When to run

Run this step only for features where the atlas stub has `stale: true`. Features
traced recently (`stale: false`) do not need re-tracing unless their source has
changed.

### What it does

Traces a stale feature end-to-end through real source code before writing any
diagram or description. The step prevents hallucinated edges and invented file
paths from reaching atlas notes by grounding every node in an artifact that
exists in the repository.

**Phase 1 — discover entry points.**  
Read `docs/features.md` (or equivalent documentation) to find the entry point
file named for the feature. Never prompt for file names not present in docs or
observed imports.

**Phase 2 — traverse imports.**  
Starting from the entry point file, follow each `import` and `from … import`
statement recursively. For each local module name encountered:

- If the corresponding `.py` file exists in `source_dir`, read it and continue
  traversal.
- If the file does not exist, record an `OPEN QUESTION` for that unresolved
  handler — do **not** invent a node connecting the two endpoints.

**Phase 3 — collect routes and tables.**  
While reading each file, extract:
- Route decorators (e.g. `@router.get('/api/…')`) → route nodes
- Table name assignments (`table = 'name'`, `__tablename__ = 'name'`) → table
  nodes

**Phase 4 — write the atlas note.**  
Produce a note whose structure matches the six-section template below.

### Note template (six required sections)

```
---
feature: <name>
files_read:
  - <file1.py>
  - <file2.py>
traced: null
stale: true
---

## What

<one-sentence description of what the feature does>

## Entry Points

- `<entry_point_file>` (tracing origin)
- Route: `<route_path>`

## Related Issues

- #<N> — <title>  (pulled from snapshot issues.json)

## Flowchart

```mermaid
flowchart LR
  <node definitions — every label is a real filename, route, or table>
  <edge definitions>
```

## Key Files

- `<file.py>` — <one-line description of role in the feature>

## Open Questions

<!-- OPEN QUESTION: <module> imported in <file> but <module>.py not found — handler unresolved -->
```

The `## Open Questions` section (and its `<!-- OPEN QUESTION: … -->` callouts)
must appear whenever any import cannot be resolved to a real source file.

### Invariants

- **No fabricated edges.** A node may only appear in the Mermaid diagram if it
  names a file read during tracing, a route string extracted from source, or a
  table name found in source. Inferred or guessed nodes are forbidden.
- **Unresolved handlers → OPEN QUESTION, not a node.** When a flow cannot be
  fully resolved, the note records an explicit
  `<!-- OPEN QUESTION: … -->` callout in the `## Open Questions` section
  instead of connecting the two endpoints with a speculative edge.
- **Every node is independently verifiable.** Reviewers can `grep` or `find`
  each named file, route, or table in the repository and get a hit.
- **Frontmatter lists every file read.** The `files_read:` key in the YAML
  frontmatter must enumerate every `.py` file traversed during import tracing.

### CLI

```
python atlas_trace.py <target-name> <feature-slug> [--vault <vault_dir>] [--source-dir <path>]
```

Reads the atlas stub from `vault/projects/<target>/atlas/<feature-slug>.md`,
traces imports starting from the entry point discovered in docs, and writes the
completed note back to the same path.

**Example — trace perf-coach today-recommendation:**

```
python atlas_trace.py perf-coach today-recommendation --source-dir /path/to/perf-coach
```

### Fixture

Tracing fixtures live at `tests/fixtures/trace-src/`:

| File | Purpose |
|------|---------|
| `app.py` | Entry point importing `routes` and `db` |
| `routes.py` | Route definitions importing `db` and `models` |
| `db.py` | Database class with table name |
| `models.py` | Domain model |
| `docs/features.md` | Entry point documentation stub |

Running tracing against this fixture with `entry_point_file="app.py"` produces
a four-node diagram (`app.py → routes.py → /api/recommendations → coaching_sessions`)
with no open questions, used by tests to verify end-to-end tracing correctness.

---

## `atlas-seed` — Atlas Seeding Bootstrap

**Module:** `atlas_seed.py`  
**Public API:** `extract_features(readme_text, docs_features_text)` → `list[dict]`  
**Seeder:** `seed(target, vault_dir, readme_text, docs_features_text)` → `None`

### What it does

Derives the initial feature list for a named target from two source texts and
bootstraps the atlas directory so tracing can begin from a single command
rather than a blank page:

| Source | How parsed |
|--------|-----------|
| README `## Features` section | Bold `**Feature name**` bullet lines |
| `docs/features/` headings | `## Heading` lines (skips generic titles like "Overview") |

Features appearing in both sources are deduplicated by their kebab-case slug.

### Output

**`vault/projects/<target>/atlas/index.md`** — two clearly delimited sections:

1. **Machine-managed table** (fenced between sentinel comments) with columns:

   | column | meaning |
   |--------|---------|
   | `feature` | display name |
   | `files` | `pending` when unknown |
   | `traced` | ISO date or `null` |
   | `stale` | boolean flag (`true` for new features) |

2. **Human section** (fenced between sentinel comments) where maintainers add
   or remove features by hand. Features listed here are picked up on the next
   seed run and added to the machine table + a stub file.

**`vault/projects/<target>/atlas/<feature-slug>.md`** — per-feature stub with
YAML frontmatter:

```yaml
---
feature: <name>
files: []
traced: null
stale: true
---
```

### Idempotency rules

- Re-running never duplicates machine-table rows.
- Human-section content is never overwritten.
- A feature **added** to the human section gets a new stub file on the next run.
- A feature **removed** from the human section is dropped from the machine table;
  its stub file stays on disk (no automated deletion).

### CLI

```
python atlas_seed.py <target-name> [--vault <vault_dir>]
```

Fetches the target's README and `docs/features/` index via `gh api`, then
seeds `vault/projects/<target>/atlas/`.

**Example — seed perf-coach:**

```
python atlas_seed.py perf-coach
```

---

## Notes

All skill modules are pure Python with no external dependencies beyond the
standard library. Test coverage lives in `tests/test_drift.py`,
`tests/test_todo_view.py`, `tests/test_journal_crosslink.py`,
`tests/test_capability_card.py`, `tests/test_questions.py`, and
`tests/test_atlas_seed.py`. The fixture for end-to-end testing of drift
detection is committed under `tests/fixtures/drift/`.
