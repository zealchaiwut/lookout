# lookout

Lookout is a personal intelligence layer that periodically inspects a named target project—reading local files, GitHub activity, and structured notes—and surfaces a concise digest of what has changed and what needs attention. It runs as a local CLI tool, keeping all data within your own environment and committing a deterministic audit trail to this repository. Each run validates vault integrity so the knowledge base stays internally consistent over time.

## Running a lookout

```
bin/lookout <target>
```

Where `<target>` is a key defined in `targets.yaml` (e.g. `perf-coach` or `commander`).

### Additional commands

```
bin/lookout pack <target...>
```

Generates a context pack (`vault/packs/<timestamp>-<target>.md`) bundling the situation snapshot, capability card, open questions, and cited drift excerpts for one or more targets. Useful as a focused context drop before a working session.

```
python discuss_pack.py <target-or-idea>
```

Generates a discussion pack for a target or idea note. Bundles open questions, capability card, situation snapshot, and cited drift/atlas excerpts into `vault/packs/<YYYY-MM-DD>-discuss-<slug>.md`.

```
python capability_map.py [--vault <vault_dir>]
```

Reads all `vault/projects/*/capability.md` files and regenerates the `## Edges` section of `vault/map.md`. The human-owned Pipelines section is never overwritten. See DESIGN.md §7.

Each run:
1. **Gathers** a point-in-time snapshot into `vault/projects/<target>/raw/<timestamp>/`, collecting from the Commander API, GitHub issues/PRs, local git log, and tracked doc files.
2. **Prints a summary table** showing per-source status (`ok` / `absent`) and item counts for commander, notion, and journal sources.
3. **Runs vault lint** — six check families: wikilinks, index/folder sync, ownership warnings, snapshot staleness, card token budget, and question ID rules. Prints a summary table (files scanned, warnings, errors) and exits non-zero on failures. A `[WARN]` is printed for projects missing a `targets.yaml` entry, snapshots older than 7 days, capability cards over 1500 tokens, and decision entries referencing unknown question IDs; open questions older than 14 days emit an `[INFO]` notice.
4. **Commits** the snapshot to the repository with the message `lookout(<target>): snapshot <ISO-8601-timestamp>`.

Source availability is non-fatal: if Commander is unreachable or GitHub CLI is absent, the run still exits 0 and records an `"absent"` status in `manifest.json`.

## Design and product context

- **[PRODUCT.md](PRODUCT.md)** — what lookout is, who it is for, and the core user flows.
- **[DESIGN.md](DESIGN.md)** — the design system: tokens, typography, and visual intent.
- **[SKILL.md](SKILL.md)** — agent-facing reference for all skill routines: synthesis, drift detection, todo-view, journal cross-linking, capability cards, and question registry.

## Roadmap status

| Sprint | Scope |
|--------|-------|
| sprint-1 | Repo scaffold, vault linter, run wrapper (this sprint) |
| sprint-2 | Collectors shipped — gather.py (Commander, GitHub, git, docs), journal delta collector, wired into run wrapper with staleness lint |
| sprint-3 | Synthesis pipeline — situation.md generation, drift detection, todo-view, journal cross-linking, capability cards, question registry, and E2E UAT |
| sprint-4 | Atlas pipeline — atlas seeding bootstrap (atlas_seed.py), stale-feature tracing (atlas_trace.py), atlas staleness detection and trace-cap in gather.py, atlas lint path check, and UAT M4 tracing top five perf-coach features |
| sprint-5 | Fleet expansion, capability map, pack commands, and lint hardening — registered crux/viral-radar/asset-studio targets, cross-project capability map generator (capability_map.py), pack.py context packs (`lookout pack`), discuss_pack.py discussion packs (`lookout discuss`), and M5 lint UAT with ownership warnings, card token budget checks, and summary table |
