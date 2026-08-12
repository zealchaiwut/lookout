# Product Context

## What lookout Is

Lookout is a personal intelligence layer over a fleet of solo-developed projects.
It periodically inspects each registered target — reading local files, GitHub
activity, Commander sprint state, and structured notes — and maintains a markdown
vault describing what each project is, what changed, what is queued, and what
contradicts itself. Everything stays local and every run commits a deterministic
audit trail to this repository.

The problem it solves: running five projects at once means the state of four of
them is always out of working memory. Reconstructing "where was I on crux, and
does anything there block the perf-coach idea I just had" costs a morning.
Lookout keeps that reconstruction written down and current.

## Target Users

**The operator (one person).** Runs several projects through Commander, works on
one at a time, and needs to re-enter the other four quickly. Reads
`situation.md` before starting a session and `vault/map.md` before deciding
where an idea belongs.

**The agents.** Claude Code sessions working in any of these repositories. A
capability card is a token-bounded briefing on what a sibling project exposes,
so an agent can answer "does perf-coach already have this?" without cloning it.
This is why cards have a hard 1 500-token budget and a `## Notes for AI` section
that survives regeneration.

## Core User Flows

1. **Nightly sweep.** `lookout --all` snapshots every target, regenerates its
   notes, lints the vault, and commits. Runs unattended via launchd. The
   operator wakes to a current vault.
2. **Re-entry.** Open `vault/projects/<target>/situation.md` — what the project
   is, whether it is clear to start, what changed since last time, what is queued,
   what is unresolved.
3. **Idea triage.** Drop an idea into `vault/ideas/`. The assessment pass grounds
   it against the atlas and capability cards — what already exists, what must be
   built, rough effort, concrete blockers — and the ledger tracks it from `idea`
   through `shipped`.
4. **Session prep.** `lookout pack <target...>` bundles the situation snapshot,
   capability card, open questions, and cited drift excerpts into one file to
   paste as context.
5. **Feature archaeology.** `atlas_trace.py` traces a stale feature through real
   source, producing a diagram in which every node is a file, route, or table
   that actually exists.

## Design Principles

- **Grounded or absent.** Every claim cites the artifact it came from. Anything
  the vault cannot confirm becomes a numbered open question, never a guess. An
  invented edge on the map is worse than a missing one.
- **Read-only against the world.** Lookout never writes to a target repository,
  GitHub, Notion, or the journal. It commits only to itself.
- **Deterministic by default.** The nightly path spends no tokens. Model calls
  are opt-in, cached, and always have a deterministic fallback — see
  [docs/llm-usage.md](docs/llm-usage.md).
- **Degradation is not failure.** An unreachable source is recorded as `absent`
  and the run still exits 0. A broken stage does not cost the sweep.
- **Machine and human territory are separated by sentinel, not convention.**
  Regeneration must never destroy something a person wrote. See
  `vault/agents.md`.
- **Optimises for re-entry speed, not completeness.** A card that fits in context
  beats an exhaustive one that does not.
