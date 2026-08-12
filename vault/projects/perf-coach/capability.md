# perf-coach — Capability Card

## What it is

Perf-coach is a personal performance dashboard for athletes and fitness enthusiasts tracking bodyweight, body composition, and power-to-weight trends within structured weight-loss or muscle-gain phases. It smooths daily measurements into actionable trends via exponential-weighted moving averages, monitors energy availability relative to training load, and recommends caloric adjustments when progress diverges from the active plan.

## Data it owns

- Snapshot artifacts under `vault/projects/perf-coach/raw/`
- Situation summary at `vault/projects/perf-coach/situation.md`
- Drift flags at `vault/projects/perf-coach/drift.md`
- Todo view at `vault/projects/perf-coach/todo-view.md`

## Read surfaces

- `GET /api/health` — Service health status
  - Example: `curl http://localhost:8000/api/health`
- `GET /api/env` — Current environment (short)
  - Example: `curl http://localhost:8000/api/env`
- `GET /api/environment` — Current environment (alias)
  - Example: `curl http://localhost:8000/api/environment`
- `GET /api/users` — List all users
  - Example: `curl http://localhost:8000/api/users`
- `GET /api/weight` — List weight entries for a user
  - Example: `curl http://localhost:8000/api/weight`
- `GET /api/habits` — List active habits for a user
  - Example: `curl http://localhost:8000/api/habits`
- `GET /api/habits/logs` — Get habit logs for a date range
  - Example: `curl http://localhost:8000/api/habits/logs`
- `GET /api/habits/stats` — Get habit statistics
  - Example: `curl http://localhost:8000/api/habits/stats`
- `GET /api/stats/active-streak` — Get cross-resource active streak
  - Example: `curl http://localhost:8000/api/stats/active-streak`
- `GET /api/calendar/month` — Get per-day summary for a calendar month
  - Example: `curl http://localhost:8000/api/calendar/month`
- `GET /api/workouts` — List workouts for a date range
  - Example: `curl http://localhost:8000/api/workouts`
- `GET /api/workouts/{workout_id}` — Get a single workout with exercises
  - Example: `curl http://localhost:8000/api/workouts/{workout_id}`
- `GET /api/workouts/{workout_id}/splits` — Get splits for a workout
  - Example: `curl http://localhost:8000/api/workouts/{workout_id}/splits`
- `GET /api/daily-metrics` — List daily metrics for a date range
  - Example: `curl http://localhost:8000/api/daily-metrics`
- `GET /api/daily-metrics/{user_id}/{metric_date}` — Get a single daily metric
  - Example: `curl http://localhost:8000/api/daily-metrics/{user_id}/{metric_date}`
- `GET /api/daily-metrics/trend` — Get trend values for the last N days
  - Example: `curl http://localhost:8000/api/daily-metrics/trend`
- `GET /trends/summary` — Get trends summary with series and deltas
  - Example: `curl http://localhost:8000/trends/summary`
- `GET /api/readiness/today` — Get today's readiness record
  - Example: `curl http://localhost:8000/api/readiness/today`
- `GET /api/readiness` — Get readiness scores for a date range
  - Example: `curl http://localhost:8000/api/readiness`
- `GET /api/training-log` — Get training log grouped by week
  - Example: `curl http://localhost:8000/api/training-log`
- `GET /api/personal-records` — List personal records for a user
  - Example: `curl http://localhost:8000/api/personal-records`
- `GET /api/strava/connect` — Initiate Strava OAuth flow
  - Example: `curl http://localhost:8000/api/strava/connect`
- `GET /api/strava/callback` — Strava OAuth redirect callback
  - Example: `curl http://localhost:8000/api/strava/callback`
- `GET /api/strava/status` — Get Strava connection status
  - Example: `curl http://localhost:8000/api/strava/status`
- `GET /api/stryd/status` — Get Stryd connection status
  - Example: `curl http://localhost:8000/api/stryd/status`
- `GET /api/sync/strava/status` — Poll SyncJob by job_id
  - Example: `curl http://localhost:8000/api/sync/strava/status`
- `GET /api/sync/strava/latest` — Most recent Strava sync info
  - Example: `curl http://localhost:8000/api/sync/strava/latest`
- `GET /api/sync/strava/dry-run` — Read-only reconcile preview
  - Example: `curl http://localhost:8000/api/sync/strava/dry-run`
- `GET /api/sync/strava/data-quality` — Data quality counts for Strava/workout sync state
  - Example: `curl http://localhost:8000/api/sync/strava/data-quality`
- `GET /api/sync/history` — Paginated SyncJob history for session user
  - Example: `curl http://localhost:8000/api/sync/history`

## How to make it do things

- **Commander slug:** `perf-coach`
- **Bulk-create path:** `POST /api/briefs` with `{"slug": "perf-coach"}`
- **CLI:** `python gather.py perf-coach` (snapshot), `python synthesize.py perf-coach` (situation.md)
- **Lookout runner:** `bin/lookout perf-coach`

## Constraints

- Snapshot data is read-only; Lookout never writes to the target repository.
- Commander API must be reachable at `sources.commander_api` for live data.
- Journal cross-links are populated only when `journal_entries` source is configured.
- GitHub repository: `zealchaiwut/perf-coach`

## Notes for AI

_Add notes here to preserve across regenerations._
