# commander — Capability Card

## What it is

Commander automates the solo development workflow (BA → Coder → Tester → UAT) by dispatching Claude Code agents coordinated through a GitHub Issues sprint board and live dashboard. It supports concurrent agent dispatch with pipeline parallelization (coders and testers working simultaneously), multi-coder execution, and automated sprint effort estimation.

## Data it owns

- Snapshot artifacts under `vault/projects/commander/raw/`
- Situation summary at `vault/projects/commander/situation.md`
- Drift flags at `vault/projects/commander/drift.md`
- Todo view at `vault/projects/commander/todo-view.md`

## Read surfaces

- `GET /api/health` — Health check
  - Example: `curl http://localhost:8000/api/health`
- `GET /api/status` — Domain-grouped local-only status snapshot, zero GitHub calls
  - Example: `curl http://localhost:8000/api/status`
- `GET /api/status/sprints` — Just the sprints slice of `/api/status
  - Example: `curl http://localhost:8000/api/status/sprints`
- `GET /api/status/health` — Just the health slice of `/api/status
  - Example: `curl http://localhost:8000/api/status/health`
- `GET /api/status/queue` — Just the queue slice of `/api/status
  - Example: `curl http://localhost:8000/api/status/queue`
- `GET /api/environment` — Current environment (`prd`/`uat`) and version
  - Example: `curl http://localhost:8000/api/environment`
- `GET /api/version` — App version string
  - Example: `curl http://localhost:8000/api/version`
- `GET /api/doctor` — Run install-time host doctor checks, return pass/fail results
  - Example: `curl http://localhost:8000/api/doctor`
- `GET /api/backup/status` — Backup subsystem status
  - Example: `curl http://localhost:8000/api/backup/status`
- `GET /api/gh-auth-status` — GitHub CLI auth status
  - Example: `curl http://localhost:8000/api/gh-auth-status`
- `GET /api/gh-auth/login/status` — Poll the in-progress login flow
  - Example: `curl http://localhost:8000/api/gh-auth/login/status`
- `GET /api/repo/config` — Repository configuration (labels, sprint prefix)
  - Example: `curl http://localhost:8000/api/repo/config`
- `GET /api/github/labels` — List GitHub labels for the repo
  - Example: `curl http://localhost:8000/api/github/labels`
- `GET /api/agents` — List active agents with last-seen timestamp
  - Example: `curl http://localhost:8000/api/agents`
- `GET /api/events` — List recent agent events (paginated)
  - Example: `curl http://localhost:8000/api/events`
- `GET /events` — SSE stream — pushed to the Agents tab in real time
  - Example: `curl http://localhost:8000/events`
- `GET /api/projects/{slug}/events` — Recent events for one project
  - Example: `curl http://localhost:8000/api/projects/{slug}/events`
- `GET /api/projects` — List all tracked projects
  - Example: `curl http://localhost:8000/api/projects`
- `GET /api/projects/{project}/running-sprint` — The running sprint for one project, if any
  - Example: `curl http://localhost:8000/api/projects/{project}/running-sprint`
- `GET /api/project-details` — Full project detail: tickets grouped by status, sprint label, assignee
  - Example: `curl http://localhost:8000/api/project-details`
- `GET /api/running` — Running-sprint snapshot for a project (`?project=`), mirror/DB only
  - Example: `curl http://localhost:8000/api/running`
- `GET /api/brief` — Home rollup brief across all projects
  - Example: `curl http://localhost:8000/api/brief`
- `GET /api/projects/{slug}/brief` — Deterministic per-project brief (DB-only, no LLM)
  - Example: `curl http://localhost:8000/api/projects/{slug}/brief`
- `GET /api/brief/summary` — Home brief one-line recap (cached/generated)
  - Example: `curl http://localhost:8000/api/brief/summary`
- `GET /api/projects/{slug}/brief/summary` — Per-project brief recap (cached/generated)
  - Example: `curl http://localhost:8000/api/projects/{slug}/brief/summary`
- `GET /api/brief/daily` — Home daily artifact
  - Example: `curl http://localhost:8000/api/brief/daily`
- `GET /api/projects/{slug}/brief/daily` — Per-project daily artifact
  - Example: `curl http://localhost:8000/api/projects/{slug}/brief/daily`
- `GET /api/dev-report` — Per-project dev report: shipped, stale, waiting, and run-ready sprints
  - Example: `curl http://localhost:8000/api/dev-report`
- `GET /api/agent-guide` — Canonical agent operate guide as `{content, version}`; `version` is a 16-hex SHA-256 fingerprint
  - Example: `curl http://localhost:8000/api/agent-guide`
- `GET /api/projects/{slug}/docs` — List allowed `.md` files in the project's clone root as `[{path, size, mtime}]`. Nested layout resolves the clone root in `uat`→`main`→`prd` order, preferring the develop-tracking `uat` clone so docs reflect the most current (unmerged) state (issue #2052)
  - Example: `curl http://localhost:8000/api/projects/{slug}/docs`
- `GET /api/projects/{slug}/docs/{path}` — Fetch one doc's content as `{path, content}
  - Example: `curl http://localhost:8000/api/projects/{slug}/docs/{path}`
- `GET /api/projects/{slug}/docs/scaffold/check` — Check for missing standard docs files
  - Example: `curl http://localhost:8000/api/projects/{slug}/docs/scaffold/check`
- `GET /api/docs-freshness/warnings` — List open docs-freshness warnings
  - Example: `curl http://localhost:8000/api/docs-freshness/warnings`
- `GET /api/board` — Board columns snapshot for a project
  - Example: `curl http://localhost:8000/api/board`
- `GET /api/issues` — List open issues with label/state filters
  - Example: `curl http://localhost:8000/api/issues`
- `GET /api/open-issues` — Open issues including body, for conflict detection
  - Example: `curl http://localhost:8000/api/open-issues`
- `GET /api/issues/{issue_id}/test-report` — Fetch the test report comment for an issue
  - Example: `curl http://localhost:8000/api/issues/{issue_id}/test-report`
- `GET /api/sprint-planning/issues` — Issues available for sprint assignment, with size estimate
  - Example: `curl http://localhost:8000/api/sprint-planning/issues`
- `GET /api/sprint-management/issues` — Sprint Mgmt panel view (issues grouped by sprint)
  - Example: `curl http://localhost:8000/api/sprint-management/issues`
- `GET /api/sprints` — List all sprint labels in the repo
  - Example: `curl http://localhost:8000/api/sprints`
- `GET /api/sprints/goal` — Get the current sprint goal
  - Example: `curl http://localhost:8000/api/sprints/goal`
- `GET /api/sprints/order` — Get the sprint ordering list
  - Example: `curl http://localhost:8000/api/sprints/order`
- `GET /api/sprints/running-all` — All currently-running sprints across projects
  - Example: `curl http://localhost:8000/api/sprints/running-all`
- `GET /api/sprints/{sprint_label}/branch-status` — Branch status for a sprint's tickets
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/branch-status`
- `GET /api/sprints/{sprint_label}/rerun-preview` — Preview what a rerun would do
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/rerun-preview`
- `GET /api/sprints/{sprint_label}/rerun/preview` — Alias preview route
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/rerun/preview`
- `GET /api/sprints/{sprint_label}/state` — plan.json` payload
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/state`
- `GET /api/sprints/{sprint_label}/state-full` — Full `state.json` + outcome
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/state-full`
- `GET /api/sprints/{sprint_label}/state-timing` — Timing data from `state.json
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/state-timing`
- `GET /api/sprints/{sprint_label}/live` — Live snapshot — counts, current ticket, active agent, last 50 log lines, locked `issues[]` (see below)
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/live`
- `GET /api/sprints/{sprint_label}/live/stream` — SSE stream of live sprint log lines
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/live/stream`
- `GET /api/sprints/{sprint_label}/finish-card` — Finish-report card data — always HTTP 200 (see below)
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/finish-card`
- `GET /api/sprints/{sprint_label}/dispatch-log` — Tail of the most recent sprint run log file. `?tail_lines=N` (max 2000)
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/dispatch-log`
- `GET /api/sprints/{sprint_label}/issue/{issue_num}/log` — Tail of the most recent per-issue log. `?tail_lines=N` (max 2000)
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/issue/{issue_num}/log`
- `GET /api/sprints/{sprint_label}/timeline` — Structured per-issue segment data for the running-sprint pane (DB-sourced, no disk reads)
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/timeline`
- `GET /api/logs/runs` — Paginated sprint run history
  - Example: `curl http://localhost:8000/api/logs/runs`
- `GET /api/sprints/{sprint_label}/finish-preview?project=` — Preview what "finish sprint" would do
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/finish-preview?project=`
- `GET /api/sprints/{sprint_label}/finish-stream?project=` — SSE stream of finish-sprint progress; resends current snapshot on reconnect
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/finish-stream?project=`
- `GET /api/sprints/{sprint_label}/bulk-complete-preview?project=` — Dry-run preview of bulk-complete. Returns `400` when the sprint has no child sprints (bulk-complete requires a parent sprint with at least one child) instead of a misleading `200` empty preview (issue #2160). Each `members[].merged` flag distinguishes a properly-merged-then-pruned branch from one deleted without merging: a branch absent from GitHub is reported `merged` only when a merged PR into its parent branch exists (issue #2086)
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/bulk-complete-preview?project=`
- `GET /api/sprints/{sprint_label}/conflict-status?project=` — Merge-conflict status for a sprint's branches
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/conflict-status?project=`
- `GET /api/sprints/{label}/reconcile-preview` — Dry-run: GitHub-vs-DB diff + post-sprint checks for one sprint. No writes; requires `?project=`. Unknown `project=` → `404` (issue #2069). Response now also carries `outcome_mismatch` (bool) and `outcome_derived_state` (the terminal state re-derived from stored `issues_json` ticket outcomes): a sprint stored `ready_to_merge` whose ticket outcomes show a failure/dead-letter is flagged for downgrade to `needs_rework` even when no GitHub needs-rework label exists (issue #2167)
  - Example: `curl http://localhost:8000/api/sprints/{label}/reconcile-preview`
- `GET /api/sprints/history` — List completed sprint summaries (local, GitHub-free ledger feed)
  - Example: `curl http://localhost:8000/api/sprints/history`
- `GET /api/sprints/{label}/run-stats` — Per-run stats for a finished sprint
  - Example: `curl http://localhost:8000/api/sprints/{label}/run-stats`
- `GET /api/sprints/pending-signoff` — Sprints sitting in the pending sign-off gate
  - Example: `curl http://localhost:8000/api/sprints/pending-signoff`
- `GET /api/sprints/{sprint_label}/preflight` — Full preflight health check before dispatch
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/preflight`
- `GET /api/sprints/{sprint_label}/cycle-check` — Detect dependency cycles in the sprint DAG
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/cycle-check`
- `GET /api/sprints/{sprint_label}/conflicts` — Detect file-overlap conflicts between tickets
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/conflicts`
- `GET /api/sprints/{sprint_label}/dep-order` — Resolved dependency execution order
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/dep-order`
- `GET /api/sprints/{sprint_label}/preview-dag` — Preview the ticket dependency DAG
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/preview-dag`
- `GET /api/sprints/{sprint_label}/dag-order-preview` — Preview DAG-resolved execution order
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/dag-order-preview`
- `GET /api/estimate-jobs/{job_id}` — Poll an async estimate job
  - Example: `curl http://localhost:8000/api/estimate-jobs/{job_id}`
- `GET /api/sprints/{sprint_label}/estimate` — Get saved estimates for a sprint
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/estimate`
- `GET /api/sprints/{sprint_label}/estimate-summary` — Rolled-up estimate summary for a sprint
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/estimate-summary`
- `GET /api/estimates/batch` — Batch-fetch estimates for multiple issues
  - Example: `curl http://localhost:8000/api/estimates/batch`
- `GET /api/sprints/{sprint_label}/outcome` — Actual outcome data for a finished sprint
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/outcome`
- `GET /api/sprints/{sprint_label}/estimate-vs-actual` — Estimate-vs-actual comparison
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/estimate-vs-actual`
- `GET /api/calibration` — Average actual time per size bucket (estimator calibration)
  - Example: `curl http://localhost:8000/api/calibration`
- `GET /api/projects/{slug}/analytics/calibration` — Per-project calibration view
  - Example: `curl http://localhost:8000/api/projects/{slug}/analytics/calibration`
- `GET /api/sprints/{sprint_label}/mis-sizing-flags` — Flagged tickets whose actual size diverged from estimate
  - Example: `curl http://localhost:8000/api/sprints/{sprint_label}/mis-sizing-flags`
- `GET /api/mis-sizing/history` — Historical mis-sizing flag log
  - Example: `curl http://localhost:8000/api/mis-sizing/history`
- `GET /api/mis-sizing/config` — Read mis-sizing detection config
  - Example: `curl http://localhost:8000/api/mis-sizing/config`
- `GET /api/sprint-status` — Current sprint run status (per-ticket states)
  - Example: `curl http://localhost:8000/api/sprint-status`
- `GET /api/sprint-summary` — Sprint summary for the active or last sprint
  - Example: `curl http://localhost:8000/api/sprint-summary`

## How to make it do things

- **Commander slug:** `commander`
- **Bulk-create path:** `POST /api/briefs` with `{"slug": "commander"}`
- **CLI:** `python gather.py commander` (snapshot), `python synthesize.py commander` (situation.md)
- **Lookout runner:** `bin/lookout commander`

## Constraints

- Snapshot data is read-only; Lookout never writes to the target repository.
- Commander API must be reachable at `sources.commander_api` for live data.
- Journal cross-links are populated only when `journal_entries` source is configured.
- GitHub repository: `zealchaiwut/commander`

## Notes for AI

_Add notes here to preserve across regenerations._
