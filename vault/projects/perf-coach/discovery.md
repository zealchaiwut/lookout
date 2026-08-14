# perf-coach — Discovery

Start-here page for this project: product flow, API map, shallow module map, and atlas. Machine-generated from docs, the latest snapshot, and the local clone. Lookout does not invent edges.

## One-liner

Perf-coach is a personal performance dashboard for athletes and fitness enthusiasts tracking bodyweight, body composition, and power-to-weight trends within structured weight-loss or muscle-gain phases. It smooths daily measurements into actionable trends via exponential-weighted moving averages, monitors energy availability relative to training load, and recommends caloric adjustments when progress diverges from the active plan.

## Product flow

_No product flow extracted. See [[projects/perf-coach/flow]] once PRODUCT.md or docs/workflow.md has numbered steps._

## API map

Documented GET surfaces from the latest snapshot. Atlas / Handler columns fill when an atlas note cites the path (deterministic join — no live server calls).

| API name | API | Example | Atlas | Handler |
|---|---|---|---|---|
| Service health status | `GET /api/health` | `curl -sS http://localhost:8000/api/health` → `200 JSON — Service health status` | — | — |
| Current environment (short) | `GET /api/env` | `curl -sS http://localhost:8000/api/env` → `200 JSON — Current environment (short)` | — | — |
| Current environment (alias) | `GET /api/environment` | `curl -sS http://localhost:8000/api/environment` → `200 JSON — Current environment (alias)` | — | — |
| List all users | `GET /api/users` | `curl -sS http://localhost:8000/api/users` → `200 JSON — List all users` | — | — |
| List weight entries for a user | `GET /api/weight` | `curl -sS http://localhost:8000/api/weight` → `200 JSON — List weight entries for a user` | — | — |
| List active habits for a user | `GET /api/habits` | `curl -sS http://localhost:8000/api/habits` → `200 JSON — List active habits for a user` | — | — |
| Get habit logs for a date range | `GET /api/habits/logs` | `curl -sS http://localhost:8000/api/habits/logs` → `200 JSON — Get habit logs for a date range` | — | — |
| Get habit statistics | `GET /api/habits/stats` | `curl -sS http://localhost:8000/api/habits/stats` → `200 JSON — Get habit statistics` | — | — |
| Get cross-resource active streak | `GET /api/stats/active-streak` | `curl -sS http://localhost:8000/api/stats/active-streak` → `200 JSON — Get cross-resource active streak` | — | — |
| Get per-day summary for a calendar month | `GET /api/calendar/month` | `curl -sS http://localhost:8000/api/calendar/month` → `200 JSON — Get per-day summary for a calendar month` | — | — |
| List workouts for a date range | `GET /api/workouts` | `curl -sS http://localhost:8000/api/workouts` → `200 JSON — List workouts for a date range` | — | — |
| Get a single workout with exercises | `GET /api/workouts/{workout_id}` | `curl -sS http://localhost:8000/api/workouts/example` → `200 JSON — Get a single workout with exercises` | — | — |
| Get splits for a workout | `GET /api/workouts/{workout_id}/splits` | `curl -sS http://localhost:8000/api/workouts/example/splits` → `200 JSON — Get splits for a workout` | — | — |
| List daily metrics for a date range | `GET /api/daily-metrics` | `curl -sS http://localhost:8000/api/daily-metrics` → `200 JSON — List daily metrics for a date range` | — | — |
| Get a single daily metric | `GET /api/daily-metrics/{user_id}/{metric_date}` | `curl -sS http://localhost:8000/api/daily-metrics/example/example` → `200 JSON — Get a single daily metric` | — | — |
| Get trend values for the last N days | `GET /api/daily-metrics/trend` | `curl -sS http://localhost:8000/api/daily-metrics/trend` → `200 JSON — Get trend values for the last N days` | — | — |
| Get trends summary with series and deltas | `GET /trends/summary` | `curl -sS http://localhost:8000/trends/summary` → `200 JSON — Get trends summary with series and deltas` | — | — |
| Get today's readiness record | `GET /api/readiness/today` | `curl -sS http://localhost:8000/api/readiness/today` → `200 JSON — Get today's readiness record` | — | — |
| Get readiness scores for a date range | `GET /api/readiness` | `curl -sS http://localhost:8000/api/readiness` → `200 JSON — Get readiness scores for a date range` | — | — |
| Get training log grouped by week | `GET /api/training-log` | `curl -sS http://localhost:8000/api/training-log` → `200 JSON — Get training log grouped by week` | — | — |
| List personal records for a user | `GET /api/personal-records` | `curl -sS http://localhost:8000/api/personal-records` → `200 JSON — List personal records for a user` | — | — |
| Initiate Strava OAuth flow | `GET /api/strava/connect` | `curl -sS http://localhost:8000/api/strava/connect` → `200 JSON — Initiate Strava OAuth flow` | — | — |
| Strava OAuth redirect callback | `GET /api/strava/callback` | `curl -sS http://localhost:8000/api/strava/callback` → `200 JSON — Strava OAuth redirect callback` | — | — |
| Get Strava connection status | `GET /api/strava/status` | `curl -sS http://localhost:8000/api/strava/status` → `200 JSON — Get Strava connection status` | — | — |
| Get Stryd connection status | `GET /api/stryd/status` | `curl -sS http://localhost:8000/api/stryd/status` → `200 JSON — Get Stryd connection status` | — | — |
| Poll SyncJob by job_id | `GET /api/sync/strava/status` | `curl -sS http://localhost:8000/api/sync/strava/status` → `200 JSON — Poll SyncJob by job_id` | — | — |
| Most recent Strava sync info | `GET /api/sync/strava/latest` | `curl -sS http://localhost:8000/api/sync/strava/latest` → `200 JSON — Most recent Strava sync info` | — | — |
| Read-only reconcile preview | `GET /api/sync/strava/dry-run` | `curl -sS http://localhost:8000/api/sync/strava/dry-run` → `200 JSON — Read-only reconcile preview` | — | — |
| Data quality counts for Strava/workout sync state | `GET /api/sync/strava/data-quality` | `curl -sS http://localhost:8000/api/sync/strava/data-quality` → `200 JSON — Data quality counts for Strava/workout sync state` | — | — |
| Paginated SyncJob history for session user | `GET /api/sync/history` | `curl -sS http://localhost:8000/api/sync/history` → `200 JSON — Paginated SyncJob history for session user` | — | — |

## Module map

Shallow map of entry points and top-level packages under the `perf-coach` clone (deterministic import skim, capped at 15 nodes). Not a full call graph.

Top-level modules:

- `services/`
- `scripts/`

## Feature atlas

[[projects/perf-coach/atlas/index|Atlas index]] — **34** traced / **119** features.

Sample features:

- [[projects/perf-coach/atlas/accept-suggestion-flow|accept-suggestion-flow]]
- [[projects/perf-coach/atlas/activity-streams|activity-streams]]
- [[projects/perf-coach/atlas/acwr-training-load-guidance|acwr-training-load-guidance]]
- [[projects/perf-coach/atlas/auto-threshold-suggestions|auto-threshold-suggestions]]
- [[projects/perf-coach/atlas/banister-held-out-mse-validation|banister-held-out-mse-validation]]
- [[projects/perf-coach/atlas/banister-parameter-fitting|banister-parameter-fitting]]
- [[projects/perf-coach/atlas/body-composition-modifier|body-composition-modifier]]
- [[projects/perf-coach/atlas/body-measurements|body-measurements]]

## Read next

- [[projects/perf-coach/situation|Situation]] — current state

- [[projects/perf-coach/capability|Capability]] — full API card

- [[projects/perf-coach/flow|Flow]] — product lifecycle + how work ships

- [[projects/perf-coach/changelog|Changelog]] — PRs and git history

- [[projects/perf-coach/todo-view|Todo view]] — open work

