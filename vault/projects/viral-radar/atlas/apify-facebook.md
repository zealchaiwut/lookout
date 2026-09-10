---
feature: apify-facebook
files_read:
  - apify_facebook.py
  - __init__.py
  - features.py
  - settings.py
traced: 2026-09-10
stale: false
---


## What

apify-facebook — traced from `tests/test_apify_facebook.py` through 4 source file(s).

## Entry Points

- `tests/test_apify_facebook.py` (tracing origin)

## Related Issues

_No related issues found in snapshot._

## Flowchart

```mermaid
flowchart LR
  apify_facebook_py[apify_facebook.py]
  __init___py[__init__.py]
  features_py[features.py]
  settings_py[settings.py]
  apify_facebook_py --> __init___py
  __init___py --> features_py
  features_py --> settings_py
```

## Key Files

- `apify_facebook.py` — traced during import walk
- `__init__.py` — traced during import walk
- `features.py` — traced during import walk
- `settings.py` — traced during import walk


## Open Questions

<!-- OPEN QUESTION: `pytest` imported in `test_apify_facebook.py` but `pytest.py` not found in source — handler unresolved -->
