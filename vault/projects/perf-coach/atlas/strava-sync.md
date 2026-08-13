---
feature: Strava sync
files_read:
  - db.py
traced: 2026-08-13
stale: false
---


## What

Strava sync — traced from `tests/test_strava_sync.py` through 1 source file(s).

## Entry Points

- `tests/test_strava_sync.py` (tracing origin)

## Related Issues

- #1656 — [follow-up] has_strava uses strava_activity_url, not strava_activity_pk, after isStravaWorkout refactor

## Flowchart

```mermaid
flowchart LR
  db_py[db.py]
```

## Key Files

- `db.py` — traced during import walk


## Open Questions

<!-- OPEN QUESTION: `pytest` imported in `test_strava_sync.py` but `pytest.py` not found in source — handler unresolved -->
<!-- OPEN QUESTION: `sqlalchemy` imported in `test_strava_sync.py` but `sqlalchemy.py` not found in source — handler unresolved -->
<!-- OPEN QUESTION: `sqlalchemy` imported in `db.py` but `sqlalchemy.py` not found in source — handler unresolved -->
<!-- OPEN QUESTION: `dotenv` imported in `db.py` but `dotenv.py` not found in source — handler unresolved -->
