---
feature: Economy contribution in projection
files_read:
  - ceiling_bonus.py
  - economy_config.py
  - economy_stimulus.py
traced: 2026-08-13
stale: false
---


## What

Economy contribution in projection — traced from `tests/test_economy_contribution_projection__1150.py` through 3 source file(s).

## Entry Points

- `tests/test_economy_contribution_projection__1150.py` (tracing origin)

## Related Issues

- #1545 — [follow-up] Remove out-of-sprint test file test_race_time_projection__1503.py

## Flowchart

```mermaid
flowchart LR
  ceiling_bonus_py[ceiling_bonus.py]
  economy_config_py[economy_config.py]
  economy_stimulus_py[economy_stimulus.py]
  ceiling_bonus_py --> economy_config_py
  economy_config_py --> economy_stimulus_py
```

## Key Files

- `ceiling_bonus.py` — traced during import walk
- `economy_config.py` — traced during import walk
- `economy_stimulus.py` — traced during import walk


## Open Questions

<!-- OPEN QUESTION: `pytest` imported in `test_economy_contribution_projection__1150.py` but `pytest.py` not found in source — handler unresolved -->
