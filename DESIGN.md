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
