---
feature: Visual Sourcing
files_read:
  - sourcing.py
  - library.py
  - mystic.py
traced: 2026-08-13
stale: false
---


## What

Visual Sourcing — traced from `tests/test_visual_sourcing.py` through 3 source file(s).

## Entry Points

- `tests/test_visual_sourcing.py` (tracing origin)

## Related Issues

_No related issues found in snapshot._

## Flowchart

```mermaid
flowchart LR
  sourcing_py[sourcing.py]
  library_py[library.py]
  mystic_py[mystic.py]
  sourcing_py --> library_py
  library_py --> mystic_py
```

## Key Files

- `sourcing.py` — traced during import walk
- `library.py` — traced during import walk
- `mystic.py` — traced during import walk


## Open Questions

<!-- OPEN QUESTION: `pytest` imported in `test_visual_sourcing.py` but `pytest.py` not found in source — handler unresolved -->
<!-- OPEN QUESTION: `requests` imported in `mystic.py` but `requests.py` not found in source — handler unresolved -->
