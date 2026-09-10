# Pipeline

What runs, in what order, reading what, writing what. This is the file to read
before touching Lookout — it should answer "what happens when I run this"
without opening a `.py`.

`SKILL.md` documents each module's API in depth. This documents how they connect.

---

## The shape

```
targets.yaml ─┐
              │
              ▼
         ┌─────────┐   raw/<timestamp>/*.json     ┌──────────┐   vault notes
         │ gather  │ ───────────────────────────► │  derive  │ ─────────────►
         └─────────┘   (evidence, machine-only)   └──────────┘  (what you read)
              │                                         │
       Commander API                              ┌─────┴─────┐
       GitHub (gh)                                │   lint    │
       local git                                  └─────┬─────┘
       local docs                                       │
       Notion                                     ┌─────┴─────┐
       journal                                    │  commit   │
                                                  └───────────┘
```

**gather writes evidence. derive writes notes.** `lookout --all` also writes
`vault/sweep-status.md` after the fleet run so a repeating per-target failure
is visible without opening the log.

Evidence lives under `vault/projects/<target>/raw/<timestamp>/` and is the sole
source of truth for machine notes (`vault/agents.md`). Derived notes sit one
level up, in `vault/projects/<target>/`.

---

## Stage table

### Per target — `derive.derive_target()`

| # | Stage | Module | Reads | Writes | LLM |
|---|-------|--------|-------|--------|-----|
| 0 | gather | `gather.py` | Commander API, `gh issue/pr list --state all`, idea frontmatter in `vault/ideas/*.md` (pinned issue numbers → `gh issue view <N>`), `git log`, target's `docs/`, Notion, journal | `raw/<ts>/{manifest,brief,issues,endpoints,docs_manifest}.json`, `gitlog.txt` | no |
| 1 | capability_card | `capability_card.py` | `endpoints.json`, `manifest.json`, target's `README.md` | `capability.md` | **yes** — the `## What it is` description |
| 2 | drift | `drift.py` | `docs_manifest.json`, `gitlog.txt`, `brief.json` | `drift.md` | no |
| 3 | synthesize | `synthesize.py` | latest + previous snapshot, `drift.md`, `capability.md`, `questions.json`, `notes.md` | `situation.md`, `questions.json` | no (reuses stage 1's description) |
| 4 | todo_view | `todo_view.py` | `notion_todos.json`, target's `docs/todo.md` | `todo-view.md` | no |
| 5 | project_flow | `project_flow.py` | target's `docs/workflow.md`, `docs/architecture.md`, atlas index, `docs_manifest.json` | `flow.md` | no |
| 6 | project_changelog | `project_changelog.py` | `issues.json` PRs, `gitlog.txt`, atlas notes | `changelog.md` | no |
| 7 | project_discovery | `project_discovery.py` | PRODUCT.md / flow helpers, `endpoints.json`, local tree, atlas notes, capability.md | `discovery.md` | no |

### Vault-wide — `derive.derive_vault()`, once per run

| # | Stage | Module | Reads | Writes | LLM |
|---|-------|--------|-------|--------|-----|
| 8 | capability_map | `capability_map.py` | every `projects/*/capability.md` | `vault/map.md` (Edges section only) | no |
| 9 | ideas_ledger | `ideas_ledger.py` | `vault/ideas/*.md` | `vault/ideas/index.md` | no |
| 10 | assessment_pass | `assessment_pass.py` | idea notes, atlas notes, capability cards | idea `## Assessment` blocks (max 3/run) | **yes** — atlas-note relevance ranking |
| 11 | ship_pass | `ship_pass.py` | idea notes, `issues.json` (per idea's `targets:`) | idea `status:` frontmatter | no |

**Order is load-bearing.** capability.md must exist before synthesize reads its
description for the one-liner, and drift.md must exist before situation.md cites
it. Vault-wide stages run after every target so `map.md` and the ledger see the
whole fleet, not a partial one.

**Failure isolation.** Each stage runs inside `derive._run_stage`. A stage that
raises is recorded as `error` and the remaining stages still run — the same
tolerance `gather` applies to an unreachable source. `derive.any_error()` decides
the exit code.

---

## Entry points

| Command | Runs | Commits |
|---|---|---|
| `bin/lookout <target>` | gather → derive (per-target + vault-wide) → lint → commit | yes |
| `bin/lookout --all` | the above for every target in `targets.yaml`, vault-wide once at the end, then `vault/sweep-status.md` | yes, per target; sweep-status committed separately |
| `python derive.py <target>` | derive only, per-target + vault-wide | no |
| `python derive.py <target> --skip-vault-wide` | per-target derive only | no |
| `python derive.py --vault-only` | vault-wide derive only | no |
| `bin/lookout pack <target...>` | context pack → `vault/packs/` | no |
| `bin/lookout promote <file> --type idea\|sprint` | inbox → idea or sprint note | no |
| `python atlas_seed.py <target>` | seeds the atlas from the target's README (see below) | no |
| `python atlas_trace.py <target> <slug>` | traces one stale atlas note through real source | no |
| `python atlas_trace.py <target> --all-stale` | batch-traces stale notes for a target (up to `--batch-size`, default 3) | no |
| `python3 render_site.py` | render the vault to a static HTML site in `site/` | no |
| `python3 atlas_coverage.py` | report atlas trace coverage and what blocks it | no |

---

## Stages that are NOT wired, and why

| Module | Status | Reason |
|---|---|---|
| `atlas_seed.py` | manual | Seeding is a bootstrap step per target, not a per-run step. Re-running is idempotent but pointless nightly. |
| `atlas_trace.py` | manual | Tracing requires the target's source checked out locally and is expensive per feature. `gather` already marks notes stale and writes a capped pending queue; `atlas_trace.py --all-stale` consumes that queue on demand (single-feature or batch, capped at 3 per run by default). Entry points are resolved per-feature from `docs/features/<slug>.md`; related issues are filtered to open, feature-matched issues capped at 10. |
| `journal_crosslink.py` | **not runnable** | It requires `journal_delta.json`, which no stage in this pipeline produces. `journal_delta.py` exists but is not invoked by `gather` or `derive`. Wire the delta producer before wiring the consumer. |
| `discuss_pack.py` | manual | On-demand, produces a working-session artifact. |
| `todo_view_assessment.py` | manual | Annotates an existing `todo-view.md`; run after stage 4 when you want effort/blocked-by comments. |
| `scripts/publish_digest.py` | manual | Writes to Notion. Deliberately outside the automatic path — see the read-only invariant below. |

---

## Discovery page

`discovery.md` is the per-project **start here** note: one-liner, product flow
(from PRODUCT.md — not the Commander sprint template), API map with atlas joins,
a shallow capped module mermaid, atlas coverage, and read-next links. It is
docs-first and static — no interactive graph, no live API introspection, no
writes into target clones. Generate alone with
`python3 project_discovery.py <target>`, or via `derive`.

---

## Invariants

**Read-only against the world.** `vault/agents.md` forbids any tool in this repo
from writing to a target project, GitHub, Notion, or the journal repo. Lookout
commits only to its own repository. `_collect_endpoints` parses documentation
tables rather than calling a target's API for exactly this reason.

**Snapshots are committed.** `.gitignore` lists `vault/projects/*/raw/`, but both
runners force-add it (`git add -f`). This is intentional — the README calls it a
deterministic audit trail — but it means the repository grows with every run of
every target. There is no retention policy yet.

**Machine vs human ownership** is defined in `vault/agents.md` and enforced by
`lint.py`. Machine-owned: situation, capability body, drift, todo-view, flow,
changelog, discovery, atlas, indexes, ideas ledger, assessment blocks, packs,
sweep-status.
Human-owned: notes, learning, decisions, `agents.md`, idea freeform tops, and
`map.md`'s Pipelines section.

**Lint gates the commit.** `lint.py` runs after derive so it validates this run's
output. Ten check families; a wikilink that cannot resolve is a hard failure.
This is why issue-sourced "What to do next" items render as plain `#N — title`
references rather than wikilinks: an issue has no page in the vault. Doc paths
and other titles that do not name a vault note stay plain text for the same
reason — `_to_wikilink` only emits `[[...]]` when the page exists.

`--all` records the per-target outcome in `vault/sweep-status.md` (and
`vault/sweep-status.json`) after every fleet run, including consecutive failure
counts, and prints a `repeating failures` block when any target has failed twice
or more in a row. A lint failure also prints the linter's own output rather
than collapsing to `lint failed (exit 1)`.

---

## First run on a new target

```bash
# 1. register it
$EDITOR targets.yaml            # commander_slug, github, local

# 2. create the vault directory
mkdir -p vault/projects/<target>

# 3. add a one-liner row + a [[<target>]] bullet to vault/index.md
$EDITOR vault/index.md          # human-owned, lint checks index/folder sync

# 4. first snapshot + derive
bin/lookout <target>

# 5. bootstrap the atlas from the target's README / docs/features/
python atlas_seed.py <target>

# 6. enrich the description once (costs one claude -p call)
LOOKOUT_LLM=1 python capability_card.py <target>

# 7. optional — trace the features that matter (per-feature or batch)
python atlas_trace.py <target> <feature-slug> --source-dir ~/dev/<target>/uat
# or batch-trace all stale features for a target (up to 3 at a time):
python atlas_trace.py <target> --all-stale --source-dir ~/dev/<target>/uat
```

Step 5 reads the target's README `## Features` section and `docs/features/`
headings. Three README conventions are recognised:

| Form | Example | Used by |
|---|---|---|
| Bold bullet | `- **Readiness Score** — daily readiness.` | perf-coach |
| Subheading | `### Brand Settings (issue #1)` | asset-studio |
| Table row | `\| **Dashboard** \| Live event feed \| [docs](…) \|` | commander |

A target whose README has no `## Features` section seeds zero features — that is
correct, not a failure. Add them by hand in the human section of
`vault/projects/<target>/atlas/index.md` and re-run; `atlas_seed` picks up human
additions and writes a stub for each. `crux` and `viral-radar` are in this state.

`local:` must point at the actual working clone. Nested-layout projects use
`~/dev/<name>/uat`; flat-layout projects (viral-radar) use `~/dev/<name>`. A
wrong path is not fatal — git, docs, and endpoints all record `absent` — so it
fails quietly. Check the gather summary on a first run.

Step 6 is worth doing once per target. The description is preserved across later
deterministic runs, so you pay for it once.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| `Read surfaces: _No read surfaces discovered_` | The target's README has no method/path table. `endpoints.json` will have `get_endpoints: []`. |
| `vault/map.md` Edges section empty | No capability card lists a GET path, or no card references another project's path. Edges need both a producer and a consumer. |
| Atlas seeded 0 features | The README has no `## Features` section, or uses a fourth format. Add features by hand to the atlas index human section. |
| Gather summary shows every local source `absent` | `local:` in `targets.yaml` points at a path that does not exist. Check nested (`~/dev/<t>/uat`) vs flat (`~/dev/<t>`) layout. |
| `situation.md` "What to do next" contains `{'text': …}` | A brief item shape with no recognised label key. Add it to `synthesize._ITEM_TITLE_KEYS`. |
| `Another run is in progress (lock: /tmp/lookout-all.lock)` | A previous `--all` died holding the lock. `rmdir /tmp/lookout-all.lock`. |
| Lint fails on an unresolved wikilink | A machine stage emitted `[[X]]` where `X` has no file under `vault/`. Machine notes must only link to real vault pages. |
| Situation one-liner reads "health is unknown" | No capability card description yet. Run `LOOKOUT_LLM=1 python capability_card.py <target>`. |

---

## Nightly job

`com.zealchaiwut.lookout-all` fires at **06:15** and runs `bin/lookout --all`
against the clone it was installed from. No other schedule trigger is active —
`StartOnMount` was removed because it fired on every volume mount (continuous on
machines with network/Tailscale mounts), not only on wake. macOS already
re-fires a missed `StartCalendarInterval` job when the machine wakes, so no
explicit catch-up trigger is needed.

```bash
scripts/install.sh                 # nightly sweep
scripts/install.sh --with-digest   # also the weekly Notion digest
scripts/install.sh --uninstall     # remove both
launchctl list | grep lookout      # verify (col 2 = last exit code)
launchctl kickstart -k gui/$(id -u)/com.zealchaiwut.lookout-all   # run now
```

Logs land in `<repo>/logs/lookout-all.log` (gitignored).

### Branch rule for commits

Every sweep writes vault output regardless of which branch is checked out, but
**commits only when the working tree is on the configured snapshot branch**.

The expected branch is set by `snapshot_branch` in `targets.yaml` (defaults to
`develop`). When the active branch differs, the runner prints a message naming
both the current branch and the expected one, records `"committed": false` in
`manifest.json`, and exits 0 — a skipped commit is not a failed run.

The runner **never switches branches**. Switching the working tree during an
unattended sweep would move a developer's checkout out from under them.

To verify commit status after a run:

```bash
cat vault/projects/<target>/raw/<latest-timestamp>/manifest.json | python3 -m json.tool | grep committed
```

### The plists are templates

`launchd/*.plist.template` carry `__REPO_ROOT__`, `__PYTHON__`, and `__PATH__`
placeholders. `install.sh` substitutes them for the installing machine and
writes the result to `~/Library/LaunchAgents/`. **Do not copy a template there
by hand** — it is not a valid plist until rendered, and `install.sh` refuses to
install one with a placeholder left in it.

This is not incidental. The plists previously hardcoded
`/Users/zeal-server/dev/lookout/.commander/runtime/worktree-pool/slot-0` — both
a specific user and a transient Commander worktree slot — so the job could not
run on any other machine and would break silently when the slot was recycled.

### PATH is set explicitly, and it matters

launchd starts jobs with `PATH=/usr/bin:/bin:/usr/sbin:/sbin`. That is enough
for `git` (macOS ships a `/usr/bin/git` shim) but **not** for `gh` or `claude`,
which normally live in `/opt/homebrew/bin` and `~/.local/bin`.

Without an explicit PATH the failure is silent in the worst way: `_collect_gh`
raises `FileNotFoundError`, no `issues.json` is written, and the run still
reports **success** for every target. Situation notes lose their "What to do
next" list and the ideas ledger loses issue titles, with nothing in the log
saying why.

`install.sh` resolves `gh`, `git`, and `claude` on the installing shell's PATH,
bakes their directories into the job, and warns if any is missing. `gather` now
also records a `github` entry in `manifest.json`, so a future PATH problem shows
up as `"status": "absent"` instead of vanishing.

**Check after installing:** `sources.github.status` should be `ok` in the newest
`manifest.json`, and `issues.json` should exist in the snapshot.

### The sweep is deterministic

`LOOKOUT_LLM` is not set by the installer, so no stage spends tokens. Add it to
`<repo>/.env` — which the job sources — to enable enrichment. Descriptions
already on a capability card survive a deterministic sweep either way. See
[llm-usage.md](llm-usage.md).
