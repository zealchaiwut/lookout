---
feature: Watchlist
files_read:
  - cost_guard.py
  - watchlist_actions.py
traced: 2026-09-10
stale: false
---


## What

Watchlist — traced from `tests/test_watchlist_actions.py` through 2 source file(s).

## Entry Points

- `tests/test_watchlist_actions.py` (tracing origin)

## Related Issues

_No related issues found in snapshot._

## Flowchart

```mermaid
flowchart LR
  cost_guard_py[cost_guard.py]
  watchlist_actions_py[watchlist_actions.py]
  cost_guard_py --> watchlist_actions_py
```

## Key Files

- `cost_guard.py` — traced during import walk
- `watchlist_actions.py` — traced during import walk


## Open Questions

<!-- OPEN QUESTION: `pytest` imported in `test_watchlist_actions.py` but `pytest.py` not found in source — handler unresolved -->
