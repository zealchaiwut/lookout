---
feature: Daily bodyweight upsert
files_read:
  - main.py
  - weight_ewma.py
traced: 2026-08-10
stale: false
---


## What

Daily bodyweight upsert — `PUT /api/weight-entries/by-date` route handler in `main.py` upserts one bodyweight entry per calendar date; downstream EWMA recompute triggered via `weight_ewma.py`.

## Entry Points

- `main.py` (route handler: `PUT /api/weight-entries/by-date`, line 963)
- Route: `/api/weight-entries/by-date`

## Related Issues

_No related issues found in snapshot._

## Flowchart

```mermaid
flowchart LR
  main_py[main.py]
  weight_ewma_py[weight_ewma.py]
  _api_weight_entries_by_date[/api/weight-entries/by-date]
  main_py --> _api_weight_entries_by_date
  _api_weight_entries_by_date --> weight_ewma_py
```

## Key Files

- `main.py` — contains the `PUT /api/weight-entries/by-date` route handler (upsert logic)
- `weight_ewma.py` — EWMA recompute service called after entry is stored

## Open Questions

<!-- OPEN QUESTION: `main.py` is a monolith — exact upsert function is at line 963; full import walk of main.py was skipped to avoid tracing unrelated routes -->
