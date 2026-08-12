# Architecture

System map for lookout: the major components, how they talk to each other,
and where data lives. The documentor maintains the auto-managed region below;
discuss changes with it via the documentor command.

> **Run order, stage inputs and outputs, and what is deliberately not wired live
> in [pipeline.md](pipeline.md).** Read that first. This file covers layout and
> boundaries; pipeline.md covers execution.

## Layers

| Layer | Where | Role |
|---|---|---|
| Registry | `targets.yaml` | The only place a target is defined. Schema frozen by `contract_version`; see [hermes-contract.md](hermes-contract.md). |
| Collection | `gather.py`, `collectors/` | Reads the outside world, writes evidence. The only layer that touches a network or another repository. |
| Evidence | `vault/projects/<t>/raw/<ts>/` | Immutable per-run JSON. Sole source of truth for machine notes (`vault/agents.md`). Gitignored but force-added, so it is committed. |
| Derivation | `derive.py` + the stage modules | Reads evidence, writes notes. Never reaches the network. |
| Notes | `vault/` | What a human or agent reads. Machine-owned and human-owned files are separated by sentinel comments. |
| Validation | `.claude/skills/lookout/scripts/lint.py` | Ten check families over the whole vault. Gates the commit. |
| Model access | `llm.py` | The single gate for any LLM call. `claude -p` only. See [llm-usage.md](llm-usage.md). |

## Boundaries

**Nothing below the collection layer reaches the network.** A derive stage that
needs external data is a design error — the collector should have captured it.
`_collect_endpoints` parses documented tables rather than calling a target's API
for exactly this reason.

**Nothing writes outside this repository.** `vault/agents.md` states the
read-only invariant: no tool here may modify a target project, GitHub, Notion,
or the journal repo. `scripts/publish_digest.py` is the one Notion writer and is
deliberately outside the automatic path.

**Machine notes are regenerated, human notes are preserved.** Every generator
that touches a mixed file extracts the human region first and re-injects it
verbatim: `## Notes for AI` in capability cards, the Pipelines section of
`map.md`, the human section of an atlas index, the freeform top of an idea note.

## Module layout

Flat: every stage module is a single file at the repository root, standard
library plus `requests`/`pyyaml` only. `bin/lookout` is the CLI front door;
`all_runner.py` is the fleet sweep; `derive.py` sequences the derive stages.
Per-module API reference lives in `SKILL.md`.

<!-- Anything above this line is hand-maintained. -->

<!-- AUTO:architecture START -->
<!-- The documentor manages everything between these markers. Do not edit by hand. -->

_No architecture recorded yet. The documentor populates this after the next
sprint that touches structure._

<!-- AUTO:architecture END -->
