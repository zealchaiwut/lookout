---
feature: paste
files_read:
  - __init__.py
  - features.py
  - settings.py
traced: 2026-09-10
stale: false
---


## What

paste — traced from `tests/test_paste_batch_parser_models__3.py` through 3 source file(s).

## Entry Points

- `tests/test_paste_batch_parser_models__3.py` (tracing origin)

## Related Issues

_No related issues found in snapshot._

## Flowchart

```mermaid
flowchart LR
  __init___py[__init__.py]
  features_py[features.py]
  settings_py[settings.py]
  __init___py --> features_py
  features_py --> settings_py
```

## Key Files

- `__init__.py` — traced during import walk
- `features.py` — traced during import walk
- `settings.py` — traced during import walk


## Open Questions

<!-- OPEN QUESTION: `pytest` imported in `test_paste_batch_parser_models__3.py` but `pytest.py` not found in source — handler unresolved -->
<!-- OPEN QUESTION: `httpx` imported in `test_paste_batch_parser_models__3.py` but `httpx.py` not found in source — handler unresolved -->
