# Lookout M2 — Gather pipeline

- Date: 2026-08-07
- Sprint label: sprint-2
- Default labels: enhancement, backend
- Status: draft

## Context

Milestone M2 (DESIGN.md section 3). Goal: gather.py collects all seven read-only sources for a target into a timestamped raw/ snapshot with per-source graceful degradation. Purely deterministic, no LLM anywhere. Invariants: GET and query calls only; gh read verbs only; the Notion token is scoped to the todos database; a failing source is recorded as absent in the manifest and never raises; targets are never a working directory. Prerequisite before ticket 3: the Notion todos database exists with a Project select property and the integration token is in .env.

## Prompts

```
Build the snapshot core of gather.py in .claude/skills/lookout/scripts/. CLI: python gather.py <target-name>. Resolve the target from targets.yaml, create vault/projects/<name>/raw/<ISO-timestamp>/, write manifest.json listing every source with status ok or absent plus an error string, and document the manifest shape in the module docstring. Implement the commander collectors: GET {commander_api}/api/projects/{slug}/brief into brief.json, GET /api/sprints/history filtered to the project appended into brief.json, GET /api/health summary into the manifest header. Timeout 10s per call. AC: live commander produces ok statuses; commander stopped produces absent statuses and exit code 0; grep of the module shows no HTTP method other than GET; unit tests cover both paths with mocked HTTP.
---
Add local collectors to gather.py. gh: shell out to gh issue list and gh pr list with json output for the target github slug, read verbs only, into issues.json. git: git -C <target-path> log --oneline -30 plus current branch and porcelain status into gitlog.txt. docs manifest: for README.md PRODUCT.md DESIGN.md SCHEMA.md and every file under docs/ in the target, record path, sha256, first markdown heading, mtime into docs_manifest.json, and when a previous snapshot exists include a changed_files diff list. Each collector degrades to absent like the commander ones. AC: a perf-coach snapshot contains all three files with real data; a missing target path aborts that run with a clear message touching nothing; grep shows no git or gh write verbs; unit tests cover the diff logic with two fixture manifests.
---
Add the Notion todos collector. Read NOTION_TOKEN from .env and the database id from targets.yaml sources. POST /v1/databases/{id}/query filtered to the target name in the Project property plus Global, paginate fully, normalize each todo to id, title, status, project, url, last_edited into notion_todos.json. Query calls only — assert no page create or update endpoint exists in the module. Rate-limit aware: max 3 requests per second with backoff on 429. AC: a live query returns normalized todos for perf-coach; invalid token records the source absent with the API error string; unit tests with mocked Notion responses cover pagination and 429 backoff.
---
Add the journal delta collector. Read journal_entries path from targets.yaml. List entries/*.md newer than the previous snapshot timestamp (all entries on first run, capped at 30 newest); for each, copy frontmatter plus any line mentioning a registered target name and any line under a Concerns heading into journal_delta.json with the entry date and relative path. Never copy full entry bodies. AC: a fixture entries dir with three files where one mentions perf-coach produces a delta containing only that extract; missing journal path records the source absent; second run against unchanged entries produces an empty delta; unit tests cover all three cases.
---
Wire gather into the run wrapper and finish degradation behavior. bin/lookout now runs gather.py, prints a snapshot summary table (source, status, item counts) to the terminal, runs lint.py, and commits once with message lookout(<target>): snapshot <timestamp>. Add a lint check: newest snapshot per registered target older than 7 days emits a staleness warning. AC: one invocation end to end produces snapshot, summary table, lint report, single commit; a second immediate invocation appends a new snapshot only (raw/ is append-only); running with commander, Notion, and journal all unavailable still exits 0 with three absent sources visible in the summary.
```

## Posted issues

| # | Title | Issue |
|---|---|---|
| 1 | Snapshot core + commander collectors | |
| 2 | Local collectors (gh, git, docs manifest) | |
| 3 | Notion todos collector | |
| 4 | Journal delta collector | |
| 5 | Run wrapper integration + staleness lint | |
