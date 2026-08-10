# Design System

**Register:** _product (the design serves the product) or brand (design IS the product)._

**Scene:** _one sentence: who uses this, where, under what light, in what mood._

## Intent

_The aesthetic direction in a sentence or two, and the anti-references (what it
is deliberately NOT)._

## Tokens

_Define the palette light and dark. Run `/impeccable init` to generate a real
token set; the table below is a placeholder._

| Role | Light | Dark |
|------|-------|------|
| `--bg` | | |
| `--surface` | | |
| `--border` | | |
| `--text` | | |
| `--accent` | | |

## Typography

_Body plus optional display/mono families; hierarchy via scale + weight contrast._

> Starter system stamped by scaffold_project so sprints can run (the design-docs
> guard requires this file). Refine with `/impeccable init`, then
> `/impeccable critique` on the first real screen.

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
