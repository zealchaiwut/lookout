# Lookout Skills

Agent-facing reference for the routines that Lookout exposes. Each routine is
a Python module at the repo root that can be called from a snapshot pipeline
or run directly from the CLI.

> This file documents **each module in isolation**. For how they connect — run
> order, which stages are wired into `bin/lookout`, and which are deliberately
> manual — see [docs/pipeline.md](docs/pipeline.md).

---

## `derive` — Derive Stage Runner

**Module:** `derive.py`
**Public API:**
- `derive_target(target, vault_dir)` → `list[dict]`
- `derive_vault(vault_dir)` → `list[dict]`
- `print_summary(title, results)` → `None`
- `any_error(results)` → `bool`

### What it does

Sequences the stages that turn a raw snapshot into vault notes. `gather` writes
evidence; these stages read that evidence and write the notes a human or agent
actually opens.

**Per target**, in dependency order:

| # | Stage | Writes |
|---|-------|--------|
| 1 | `capability_card` | `capability.md` |
| 2 | `drift` | `drift.md` |
| 3 | `synthesize` | `situation.md` |
| 4 | `todo_view` | `todo-view.md` |

**Vault-wide**, once per run after every target:

| # | Stage | Writes |
|---|-------|--------|
| 5 | `capability_map` | `vault/map.md` |
| 6 | `ideas_ledger` | `vault/ideas/index.md` |
| 7 | `assessment_pass` | idea `## Assessment` blocks |
| 8 | `ship_pass` | idea `status:` frontmatter |

Order matters: `capability.md` must exist before `synthesize` reads its
description for the one-liner, and `drift.md` must exist before `situation.md`
cites it.

### Result records

Each stage returns `{"stage", "status", "detail"}` where status is one of
`ok` / `skipped` / `error`. A stage that raises is caught, its traceback printed
to stderr, and the remaining stages still run — the same tolerance `gather`
applies to an unreachable source.

`derive_target` returns a single `skipped` record when the target has no
snapshot yet.

### CLI

```
python derive.py <target> [--vault <dir>] [--skip-vault-wide]
python derive.py --vault-only
```

Exits 1 if any stage errored.

---

## `llm` — Model Access Gate

**Module:** `llm.py`
**Public API:**
- `ask(prompt, *, fallback, model=None, purpose="", cache_dir=None, timeout=None, use_cache=True)` → `str`
- `enabled()` → `bool`, `available()` → `bool`, `status()` → `dict`

### What it does

The single point through which any Lookout stage may call a language model.
The only backend is `claude -p` (subscription-funded). No module imports an SDK
or reads an API key, and a test enforces that.

| Guarantee | Behaviour |
|---|---|
| Subscription only | Always `["claude", "-p", prompt, "--model", model]` |
| Cached | Keyed by `sha256(model + prompt)` under `vault/.llm-cache/` |
| Never fatal | Missing binary, non-zero exit, timeout, or empty response → `fallback` |
| Off by default | Returns `fallback` without spawning anything unless `LOOKOUT_LLM=1` |

| Variable | Default | Meaning |
|---|---|---|
| `LOOKOUT_LLM` | unset | `1`/`true`/`yes`/`on` enables calls |
| `LOOKOUT_LLM_MODEL` | `haiku` | passed to `claude --model` |
| `LOOKOUT_LLM_TIMEOUT` | `120` | seconds before abandoning a call |

### Callers

Three, each with a deterministic fallback: the capability card description
(`capability_card._build_what_it_is`), which is preserved across deterministic
runs; the situation one-liner, which **reuses** that description rather than
making its own call; and atlas-note relevance ranking in the assessment pass,
whose picks are intersected with the real slug list so a hallucinated note can
never reach an assessment.

Full policy and the reasoning behind each choice:
[docs/llm-usage.md](docs/llm-usage.md).

### CLI

```
python llm.py --status
LOOKOUT_LLM=1 python llm.py --ask "prompt" [--model haiku]
```

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

`endpoints.json` is produced by `gather._collect_endpoints`, which parses
Markdown method/path tables out of the target's `README.md` and `docs/*.md` and
keeps the GET rows. Documentation is the evidence source rather than live
introspection because Lookout is read-only against targets and must not start or
call a target's server. Schema:

```json
{
  "get_endpoints": [
    {"path": "/api/jobs", "description": "List all jobs",
     "example": "curl http://localhost:8000/api/jobs", "source": "README.md"}
  ],
  "source_files": ["README.md"]
}
```

### `## What it is` and LLM enrichment

The deterministic description says only that the target is tracked by Lookout,
which is true of every target. With `LOOKOUT_LLM=1` the target's README plus its
documented endpoints are summarised into at most two sentences instead.

A real description already on the card **survives a deterministic run**, the
same way `## Notes for AI` does — otherwise the nightly sweep would overwrite it
and the next enriched run would have to buy it again. So this costs one call per
target, not one per run.

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
| README `## Features` — bold bullets | `- **Feature name** — …` |
| README `## Features` — subheadings | `### Feature Name (issue #N)`; the issue suffix is stripped |
| README `## Features` — table rows | `\| **Feature Name** \| what it does \| docs \|` |
| `docs/features/` headings | `## Heading` lines (skips generic titles like "Overview") |

The section ends at the next sibling `## ` heading — a `###` inside it is a
feature, not a terminator.

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

## `capability-map` — Cross-Project Capability Map Generator

**Module:** `capability_map.py`  
**Public API:** `generate_edges(cards)` → `list[str]`  
**Writer:** `generate_map(vault_dir)` → `Path`

### What it does

Reads all `vault/projects/*/capability.md` files, derives producer→consumer
relationships, and regenerates the `## Edges` section of `vault/map.md`.
The human-owned Pipelines section is always preserved byte-for-byte.

Edge detection: a project is a *producer* when a surface (GET path) appears in
its `## Read surfaces` section; a project is a *consumer* when its card text
(outside its own `## Read surfaces`) references that same path. Only surfaces
documented in a real capability card are emitted as edge endpoints. See
DESIGN.md §7 for the rationale behind this design.

### Output — `vault/map.md`

Always contains exactly two clearly delimited sections:

| Section | Managed by |
|---------|-----------|
| `<!-- BEGIN MACHINE EDGES -->` … `<!-- END MACHINE EDGES -->` | Regenerated each run |
| `<!-- BEGIN HUMAN PIPELINES -->` … `<!-- END HUMAN PIPELINES -->` | Human-owned, never overwritten |

Each edge line follows the format:

```
- <producer> → <consumer> via GET <path>
```

### Guards

- No edge is emitted for a surface that does not appear in any capability card.
- No edge references a project that does not have a capability card.
- The Human Pipelines section is preserved byte-for-byte across every run.

### CLI

```
python capability_map.py [--vault <vault_dir>]
```

Reads capability cards from `vault/projects/*/capability.md` and writes
`vault/map.md`.

---

## `ideas-ledger` — Idea Note Conventions and Ledger Regeneration

**Module:** `ideas_ledger.py`  
**Public API:** `validate_note(path)` → `list[str]`, `regenerate_ledger(ideas_dir, today)` → `Path`

### Idea note format

One file per idea, located at `vault/ideas/<YYYY-MM-DD>-<slug>.md`.

**Required frontmatter fields:**

| Field | Type | Description |
|-------|------|-------------|
| `slug` | string | Kebab-case identifier |
| `created` | ISO date | When the idea was first captured |
| `status` | enum | One of: `idea` \| `assessed` \| `promoted` \| `shipped` \| `parked` |
| `targets` | list | Target project names this idea touches |
| `issues` | list | Linked GitHub issue numbers |
| `assessed` | ISO date or null | When the idea was last assessed |

**IMPORTANT:** The frontmatter and the `## Assessment` section below the
delimiter are **machine-owned and must not be hand-edited**. Only the
freeform top section (everything above the delimiter) is human territory.

### Body structure

Each idea note has exactly two sections separated by a clearly marked delimiter:

```
---
<frontmatter>
---

<freeform top — human-written, never machine-edited>

<!-- BEGIN MACHINE ASSESSMENT -->
## Assessment

<machine-owned — do not hand-edit>
<!-- END MACHINE ASSESSMENT -->
```

The freeform top section is preserved byte-for-byte across every
regeneration run. The agent pipeline only writes `vault/ideas/index.md`
and the `## Assessment` block; it never modifies the freeform top.

### Output — `vault/ideas/index.md`

Regenerated on every run as a Markdown table:

| Column | Source |
|--------|--------|
| Idea | `slug` frontmatter field |
| Status | `status` frontmatter field |
| Effort | `effort` frontmatter field (optional, defaults to `—`) |
| Blocked-by | `blocked_by` frontmatter field (optional, defaults to `—`) |
| Age | Days since `created` |

### Validation

An idea note with an unrecognised `status` value causes the linter to exit
non-zero and print a human-readable error naming the file and the invalid
value. Valid statuses are: `idea`, `assessed`, `promoted`, `shipped`, `parked`.

### CLI

```
python ideas_ledger.py [--ideas-dir <vault/ideas>]
```

Validates all idea notes in the directory, then regenerates `index.md`.
Exits 0 on success, 1 if any note has an invalid status or missing field.

---

## `assessment-pass` — Idea Assessment Pass

**Module:** `assessment_pass.py`  
**Public API:**  
- `select_ideas_for_assessment(ideas_dir, vault_dir, today)` → `list[Path]`  
- `build_assessment(idea_path, vault_dir, today)` → `str`  
- `run_assessment_pass(ideas_dir, vault_dir, today)` → `list[Path]`

### What it does

Scans `vault/ideas/` for ideas that need assessment — those with `assessed: null`
(never assessed) or whose file was modified after their `assessed` date (human-edited).
At most three ideas are assessed per run; the cap is enforced in `select_ideas_for_assessment`
before any content-generation begins.

For each selected idea, `build_assessment` generates an `## Assessment` section
following the DESIGN.md §9 five-field template, grounded exclusively in atlas notes
and capability cards found in the vault:

| Field | Content |
|-------|---------|
| **Already exists** | Wikilinked atlas notes and capability cards that already cover the idea |
| **Must be built** | What is new and has no existing vault implementation |
| **Effort** | One of **S** / **M** / **L** |
| **Dependencies** | Concrete named blockers (wikilinked projects), not generic categories |
| **Suggested first slice** | One small, independently testable first step |

### Grounding rule (DESIGN.md §9)

Every claim cites a source by wikilink (e.g. `[[projects/perf-coach/atlas/today-recommendation]]`).
Anything unknown — an unregistered project, an empty atlas, an unresolvable claim — is recorded
as a numbered open question (`Q1: …`) rather than a guess. No capabilities or relationships
are fabricated.

### Skip logic

An idea is skipped if its `assessed` frontmatter field is not `null` and the file's
modification time falls on or before the end of the assessed date (i.e. no human edits
have occurred since assessment).

### Atomicity guarantee

No new fields are written to an idea's frontmatter — and the Assessment block is not
updated — until `build_assessment` completes without errors. A failed assessment leaves
the idea file byte-for-byte unchanged.

### Frontmatter fields written on success

| Field | Value written |
|-------|--------------|
| `assessed` | Today's ISO date |
| `status` | Changed from `idea` to `assessed` (only if currently `idea`) |

The `## Assessment` block (between `<!-- BEGIN MACHINE ASSESSMENT -->` and
`<!-- END MACHINE ASSESSMENT -->`) is fully regenerated. The freeform top section
(everything above the machine delimiter) is never touched.

### Project registry

A project is considered **registered** if `vault/projects/<target>/` exists as a
directory. An unregistered project causes the assessment to explicitly state
"not registered in vault/projects/" and to raise a numbered open question.

### CLI

```
python assessment_pass.py [--ideas-dir <vault/ideas>] [--vault <vault>]
```

Runs the pass against the specified ideas directory. Exits 0 on completion.

---

## Notes

All skill modules are pure Python with no external dependencies beyond the
standard library. Test coverage lives in `tests/test_drift.py`,
`tests/test_todo_view.py`, `tests/test_journal_crosslink.py`,
`tests/test_capability_card.py`, `tests/test_questions.py`,
`tests/test_atlas_seed.py`, `tests/test_capability_map__20.py`, and
`tests/test_assessment_pass__25.py`. The fixture for end-to-end testing of
drift detection is committed under `tests/fixtures/drift/`.

---

## `gather` — Snapshot Collector notes

`gather._collect_gh` passes `--state all` to both `gh issue list` and
`gh pr list`, so `issues.json` contains **both open and closed issues**.
Before issue #76 only open issues were collected (gh's default).

## `ship_pass` — Idea Ship Pass notes

`ship_pass.load_issue_states` returns `{project_name: {issue_number: {...}}}` —
a two-level dict keyed first by project name, then by issue number.  Issue
numbers are only unique within a repository, so the outer key prevents
cross-project collisions from overwriting each other.

`ship_pass.check_idea` resolves each linked issue **only against the idea's
own `targets:` frontmatter**.  An issue present in a different project's
snapshot (but not in any of the idea's targets) does not satisfy the closed
check and does not advance the idea to `shipped`.  Issues unresolvable from
any of the idea's targets render as `(unknown)` / `OPEN` and leave `status`
unchanged.
