# lookout

Lookout is a personal intelligence layer over a fleet of projects. It
periodically inspects each registered target — reading local files, GitHub
activity, Commander sprint state, and structured notes — and maintains a markdown
vault describing what each project is, what changed, what is queued, and what
contradicts itself. Everything stays local; every run commits a deterministic
audit trail to this repository and validates vault integrity before doing so.

## Start here

| Doc | What it answers |
|---|---|
| **[docs/pipeline.md](docs/pipeline.md)** | What runs, in what order, reading what, writing what. **Read this first.** |
| [PRODUCT.md](PRODUCT.md) | What lookout is for and who uses it |
| [docs/architecture.md](docs/architecture.md) | Layers and boundaries |
| [SKILL.md](SKILL.md) | Per-module API reference for every stage |
| [docs/llm-usage.md](docs/llm-usage.md) | When a model may be called, and how cost is bounded |
| [docs/hermes-contract.md](docs/hermes-contract.md) | Schema of every file the pipeline reads |
| [DESIGN.md](DESIGN.md) | Capability-map (§7) and assessment (§9) contracts |

## Running a lookout

```bash
bin/lookout <target>          # snapshot + derive + lint + commit for one target
bin/lookout --all             # the same for every target in targets.yaml
```

`<target>` is a key defined in `targets.yaml` (e.g. `perf-coach`, `asset-studio`).

Each run:

1. **Gathers** a point-in-time snapshot into
   `vault/projects/<target>/raw/<timestamp>/` from the Commander API, GitHub
   issues/PRs, local git log, documented API endpoints, and tracked doc files.
2. **Derives** the notes a reader actually opens — `capability.md`, `drift.md`,
   `situation.md`, `todo-view.md`, then the vault-wide `map.md` and ideas ledger.
3. **Lints** the vault — ten check families, exits non-zero on failure.
4. **Commits** with the message `lookout(<target>): snapshot <ISO-8601>`.

Source availability is non-fatal: if Commander is unreachable or the GitHub CLI
is absent, the run still exits 0 and records `"absent"` in `manifest.json`.

The full stage table — every module, its inputs, its outputs, and which stages
are deliberately left manual — is in [docs/pipeline.md](docs/pipeline.md).

## Other commands

```bash
python derive.py <target>              # re-derive notes without a new snapshot
bin/lookout pack <target...>           # context pack for a working session
python discuss_pack.py <target-or-idea>  # discussion pack for one topic
bin/lookout promote <file> --type idea|sprint
python atlas_seed.py <target>          # bootstrap a target's atlas from its README
python atlas_trace.py <target> <slug>  # trace one feature through real source
python llm.py --status                 # check LLM configuration (spends nothing)
python3 render_site.py                 # render the vault to a browsable HTML site
python scripts/smoke_contract.py       # validate the vault against the reader contract
```

Each is documented in [SKILL.md](SKILL.md); how they fit together is in
[docs/pipeline.md](docs/pipeline.md).

## Adding a target

See **First run on a new target** in [docs/pipeline.md](docs/pipeline.md). Short
version: register it in `targets.yaml`, add it to `vault/index.md`, run
`bin/lookout <target>`, then `atlas_seed.py <target>`.

## Nightly runner

`lookout --all` iterates every registered target, tolerates per-target failures,
and prints a status summary. Exit code is non-zero if any target failed.

Install the launchd job (fires 06:15 local, `StartOnMount` for wake catch-up):

```bash
scripts/install.sh                 # idempotent; nightly sweep
scripts/install.sh --with-digest   # also the weekly Notion digest
scripts/install.sh --uninstall     # remove both
launchctl list | grep lookout      # col 2 is the last exit code
```

The plists under `launchd/` are **templates** — `install.sh` substitutes the
repo path, interpreter, and PATH for the installing machine. Do not copy them
into `~/Library/LaunchAgents/` by hand. The PATH substitution is required:
launchd's default PATH has no `gh`, so a run would collect zero GitHub issues
and still report success. See [docs/pipeline.md](docs/pipeline.md#nightly-job).

If a run is interrupted while holding the lock:

```bash
rmdir /tmp/lookout-all.lock
```

The nightly sweep is deterministic — it spends no tokens. See
[docs/llm-usage.md](docs/llm-usage.md).

### Environment

The job sources `<repo>/.env` before invoking the runner:

```bash
GITHUB_TOKEN=...
NOTION_TOKEN=...
LOOKOUT_LLM=1        # optional — enables model-backed enrichment
```

No API key is ever needed: the only model backend is the `claude` CLI, billed
against the Claude.ai subscription.

## Roadmap status

| Sprint | Scope |
|--------|-------|
| sprint-1 | Repo scaffold, vault linter, run wrapper |
| sprint-2 | Collectors — gather.py (Commander, GitHub, git, docs), journal delta, staleness lint |
| sprint-3 | Synthesis — situation.md, drift detection, todo-view, journal cross-linking, capability cards, question registry |
| sprint-4 | Atlas — seeding bootstrap, stale-feature tracing, staleness detection and trace-cap, atlas lint path check |
| sprint-5 | Fleet expansion — crux/viral-radar/asset-studio targets, capability map, `lookout pack`, discussion packs, lint hardening |
| sprint-6 | Idea pipeline — note conventions and ledger, assessment pass, ship tracking, todo-view effort annotation |
| sprint-7 | Hermes reader contract, vault inbox capture and promote, smoke contract validation |
| — | Pipeline wiring (derive.py), endpoint collection, subscription-only LLM gate, machine-independent launchd install |
