# Design

Lookout has no user interface. It is a CLI that writes markdown, so its design
surface is **the shape of the files it produces** — what belongs in a note, who
owns which region of it, and what a generator is allowed to assert.

The numbered sections below are contracts. Generators cite them; `lint.py`
enforces several of them. Visual/typographic design tokens do not apply to this
project and are deliberately absent.

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
