# Design

Lookout's primary output is markdown, and its contracts are about the *shape of
the files it produces* — what belongs in a note, who owns which region of it,
and what a generator may assert. The numbered sections below are those
contracts; generators cite them and `lint.py` enforces several.

Since #88 there is also one rendered surface: the static HTML site produced by
`site.py`. Its tokens are below. They apply to that site only — nothing else in
this project renders.

## Tokens

Light is defined on bare `:root`; dark overrides the same names under
`prefers-color-scheme: dark`. No colour has its only definition inside a media
query, so a viewer with no preference still gets a complete palette.

| Role | Light | Dark |
|------|-------|------|
| `--bg` | `#fdfdfc` | `#16161a` |
| `--surface` | `#f4f4f2` | `#1e1e24` |
| `--border` | `#e0e0dc` | `#2e2e36` |
| `--text` | `#22222a` | `#e6e6ea` |
| `--text-muted` | `#6a6a76` | `#9a9aa8` |
| `--accent` | `#3a5a8c` | `#7fa3d8` |
| `--code-bg` | `#f0f0ee` | `#24242c` |

## Typography

System UI stack for prose, system mono for code, tables, and file paths — the
vault is full of identifiers and paths that must stay scannable.

| Use | Family | Size | Line height |
|---|---|---|---|
| Prose | system UI | 15px | 1.55 |
| Headings | system UI | 1.6 / 1.12 / 1.0 rem | 1.25 |
| Tables, code | system mono | 13–13.5px | 1.35–1.45 |
| Provenance, breadcrumb | system mono | 12.5px | inherit |

Content is capped at `72ch`. Tables may exceed it and scroll inside their own
container, so the page body never scrolls sideways.

**Register:** product — the design serves the content. A reading tool for one
person and their agents, used at a desk beside an editor. It should read as
documentation, not as a dashboard: no cards for their own sake, no shadows, no
animation beyond the native disclosure triangle.

## Principles

**Grounded or absent.** Every claim in a machine note cites the artifact it came
from. Anything the vault cannot confirm becomes a numbered open question, never
a guess. A fabricated edge on the capability map is worse than a missing one,
because a missing edge is visibly missing.

**Sentinels, not conventions, separate ownership.** Any file with both machine
and human content is split by explicit comment markers, and the generator
extracts and re-injects the human region verbatim. A convention that says "don't
edit below here" fails the first time a regeneration is careless; a sentinel does
not.

**Regeneration is idempotent.** Running a generator twice over unchanged input
produces a byte-identical file. Anything that cannot satisfy that — a timestamp,
a run id — belongs in frontmatter, not the body.

**Expensive output is preserved, not rebuilt.** Where a section costs a model
call to produce, a later deterministic run keeps what is already there rather
than overwriting it with a placeholder. Applies to `## What it is` and
`## Notes for AI` on capability cards.

**Degradation is silent and non-fatal.** A missing source produces an explicit
"not found in snapshot evidence" line, never a plausible-looking placeholder.

## §7 Capability Map

The capability map (`vault/map.md`) surfaces producer→consumer relationships
across registered projects automatically. It separates machine-generated content
(the Edges section, rebuilt on every run) from human-curated content (the
Pipelines section, never overwritten by machines).

**Why two sections?** Machines can derive which project exposes a given surface
from capability cards, but higher-level pipeline semantics (ordering, retry
policies, business purpose) require human judgment. Separating them lets the map
stay current without destroying human annotations.

**Guard rule:** No edge is emitted for a surface that does not appear verbatim in
at least one capability card. This prevents stale or hallucinated surface names
from reaching the map.

## §9 Assessment Template

Each idea note's `## Assessment` section (the machine-owned block between
`<!-- BEGIN MACHINE ASSESSMENT -->` and `<!-- END MACHINE ASSESSMENT -->`)
follows this five-field structure:

| Field | Content |
|-------|---------|
| **Already exists** | Wikilinked atlas notes / capability cards that already implement or partly cover the idea |
| **Must be built** | What is new and has no existing implementation in the vault |
| **Effort** | One of **S** (small, hours) / **M** (medium, days) / **L** (large, week+) |
| **Dependencies** | Concrete named blockers — wikilinked project or feature names, not generic categories (e.g. `[[projects/perf-coach]]`, not "backend service") |
| **Suggested first slice** | One small, independently testable step that validates the approach |

**Grounding rule (mirrors §4):** Every claim in the Assessment section must cite
its source by wikilink (e.g. `[[projects/perf-coach/atlas/today-recommendation]]`).
Anything that cannot be confirmed in the vault — an unregistered project, an empty
atlas, a claim with no cited source — must be recorded as a numbered open question:

```
Q1: Is [[unregistered-project]] planned for the atlas?
Q2: What capabilities does [[viral-radar]] expose? (registered but no capability card or atlas found)
```

**No fabrication:** The assessment must not invent capabilities, relationships,
or atlas notes. Every `[[wikilink]]` must resolve to a real file under `vault/`.
An unregistered project's name is written in backticks, not wikilinks, and the
assessment explicitly states it is not in the registry.

**Invariant:** The freeform top section (everything above the machine delimiter)
is never modified by the assessment pass. Only the Assessment block and the
`assessed` / `status` frontmatter fields are written.
