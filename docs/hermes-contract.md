# Hermes Reader Contract

Version: **1** (matches `contract_version` in `targets.yaml`)

This document is the single source of truth for every file path and frontmatter
field that Hermes (the Lookout pipeline) may read. Any breaking change to the
schema (removing a required field, renaming a path, changing a type) **must**
be accompanied by a bump of the `contract_version` integer in `targets.yaml`
and an update to this document.

---

## Stable Read Paths

### 1. `targets.yaml`

**Path pattern:** `targets.yaml` (repository root)

**Purpose:** Top-level registry of all tracked projects and data sources.
Hermes reads this file on every run to discover target configurations and
global source endpoints.

**Top-level fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `contract_version` | integer | required | Schema version sentinel. Increment on any breaking change. |
| `sources` | mapping | required | Named data source endpoints (Commander API URL, journal path, Notion IDs). |
| `targets` | mapping | required | Named project entries. Each key is a target slug. |

**Per-target fields (under `targets.<name>`):**

| Field | Type | Required | Description |
|---|---|---|---|
| `commander_slug` | string | required | Slug used to query the Commander API. |
| `github` | string | required | GitHub repository in `owner/repo` form. |
| `local` | string | required | Absolute or `~`-prefixed path to the local checkout. |

**Minimal example:**

```yaml
contract_version: 1
sources:
  commander_api: http://localhost:8000
  journal_entries: ~/dev/journal/entries
  notion_todos_db: <placeholder>
targets:
  my-project:
    commander_slug: my-project
    github: owner/my-project
    local: ~/dev/my-project/uat
```

---

### 2. `vault/projects/<target>/situation.md`

**Path pattern:** `vault/projects/<target>/situation.md`

**Purpose:** Machine-generated point-in-time situation card for a project.
Read by `pack.py` and `discuss_pack.py` to extract the one-liner and capacity
verdict. Written by `synthesize.py`.

**Frontmatter fields:**

| Field | Type | Required | Example |
|---|---|---|---|
| `target` | string | required | `perf-coach` |
| `run` | string (ISO-8601 UTC) | required | `"2026-08-10T06:15:00Z"` |
| `sources_ok` | boolean | required | `true` |

**Body sections** (in order):

- `## One-liner` — single sentence summarising current state
- `## Capacity` — verdict from brief + health
- `## Since last run` — changed fields vs prior snapshot
- `## What to do next` — up to 5 ordered items
- `## From the journal` — entries from journal snapshot
- `## Open questions` — unresolved question items
- `## Drift` — top 3 drift signals

**Minimal example:**

```markdown
---
target: perf-coach
run: "2026-08-10T06:15:00Z"
sources_ok: true
---

## One-liner

Commander reachable; sprint idle.

## Capacity

Clear to start
```

---

### 3. `vault/projects/<target>/capability.md`

**Path pattern:** `vault/projects/<target>/capability.md`

**Purpose:** Machine-generated capability card describing a project's API
surfaces and constraints. Read by `capability_map.py` to derive the
cross-project edge map, and by `discuss_pack.py` for discussion packs.
Written by `capability_card.py`.

**No YAML frontmatter.** The entire file is structured body sections.

**Required sections** (in order):

| Section header | Purpose |
|---|---|
| `## What it is` | ≤2 sentences describing the target |
| `## Data it owns` | datasets, files, or stores managed by the target |
| `## Read surfaces` | every real GET endpoint with one example call each |
| `## How to make it do things` | commander slug, bulk-create path, CLI entries |
| `## Constraints` | known limitations and invariants |
| `## Notes for AI` | preserved verbatim across regenerations |

**Minimal example:**

```markdown
## What it is

Perf Coach is a coaching assistant that tracks athlete metrics and surfaces
improvement recommendations.

## Data it owns

- `metrics.json` — raw sensor readings per session

## Read surfaces

`GET /api/health` — health check
`GET /api/projects/perf-coach/brief` — project brief

## How to make it do things

Commander slug: `perf-coach`

## Constraints

Read-only snapshot; no writes via Hermes.

## Notes for AI

No special notes.
```

---

### 4. Ideas Ledger — `vault/ideas/<YYYY-MM-DD>-<slug>.md`

**Path pattern:** `vault/ideas/<YYYY-MM-DD>-<slug>.md` (one file per idea)

**Purpose:** Human-editable idea notes. Read and validated by
`ideas_ledger.py`, enriched by `assessment_pass.py`, and tracked for
completion by `ship_pass.py`.

**Frontmatter fields:**

| Field | Type | Required | Example |
|---|---|---|---|
| `slug` | string | required | `dark-mode` |
| `created` | string (ISO date) | required | `2026-01-10` |
| `status` | string (enum) | required | `idea` |
| `targets` | list of strings | required | `[perf-coach]` |
| `issues` | list of integers | required | `[42]` |
| `assessed` | string (ISO date) or null | required | `null` |

Valid `status` values: `idea`, `assessed`, `promoted`, `shipped`, `parked`.

**Body structure:**

- Freeform top section — human-written, never machine-edited
- `<!-- BEGIN MACHINE ASSESSMENT -->` delimiter
- `## Assessment` — machine-written, regenerated by `assessment_pass.py`

**Minimal example:**

```markdown
---
slug: dark-mode
created: 2026-01-10
status: idea
targets: []
issues: []
assessed: null
---

Add a dark mode theme to the dashboard.

<!-- BEGIN MACHINE ASSESSMENT -->
## Assessment

**Effort:** S
```

---

## Schema Versioning Policy

The `contract_version` field in `targets.yaml` is a breaking-change sentinel.

**Rules:**
- **Increment** `contract_version` whenever a required field is removed or
  renamed, a type changes incompatibly, or a stable read path is relocated.
- **Do not increment** for purely additive changes (new optional fields, new
  path patterns that don't replace existing ones).
- Update this document in the same commit as the `contract_version` bump.

---

## Smoke Validation

Run `scripts/smoke_contract.py` to validate the live vault against this
contract:

```bash
python scripts/smoke_contract.py
```

The script exits `0` when all checks pass and non-zero when any violation is
found, printing a `VIOLATION:` line that names the field and file for each
failure.
