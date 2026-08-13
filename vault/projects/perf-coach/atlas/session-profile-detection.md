---
feature: Session profile detection
files_read:
  - interval_detector.py
traced: 2026-08-13
stale: false
---


## What

Session profile detection — traced from `tests/test_add_interval_and_set_detection_to_session_profile_pipeline__585.py` through 1 source file(s).

## Entry Points

- `tests/test_add_interval_and_set_detection_to_session_profile_pipeline__585.py` (tracing origin)

## Related Issues

- #1673 — [follow-up] Session-wide glob.glob monkeypatch in conftest has no teardown

## Flowchart

```mermaid
flowchart LR
  interval_detector_py[interval_detector.py]
```

## Key Files

- `interval_detector.py` — traced during import walk


## Open Questions

<!-- OPEN QUESTION: `pytest` imported in `test_add_interval_and_set_detection_to_session_profile_pipeline__585.py` but `pytest.py` not found in source — handler unresolved -->
