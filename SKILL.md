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

## Notes

All skill modules are pure Python with no external dependencies beyond the
standard library. Test coverage lives in `tests/test_drift.py` and
`tests/test_todo_view.py`. The fixture for end-to-end testing of drift
detection is committed under `tests/fixtures/drift/`.
