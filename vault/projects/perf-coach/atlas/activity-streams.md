---
feature: Activity streams
files_read:
  - activity_streams.py
traced: 2026-08-13
stale: false
---


## What

Activity streams — traced from `backend/services/activity_streams.py` through 1 source file(s).

## Entry Points

- `backend/services/activity_streams.py` (tracing origin)

## Related Issues

- #1656 — [follow-up] has_strava uses strava_activity_url, not strava_activity_pk, after isStravaWorkout refactor
- #617 — [follow-up] Move write_activity_stream out of activity_streams.py into the caller layer

## Flowchart

```mermaid
flowchart LR
  activity_streams_py[activity_streams.py]
```

## Key Files

- `activity_streams.py` — traced during import walk
