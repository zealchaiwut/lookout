---
feature: candidate-sampler
files_read:
  - __init__.py
  - features.py
  - settings.py
  - cost_guard.py
  - candidate_sampler.py
  - engagement_tier.py
traced: 2026-09-10
stale: false
---


## What

candidate-sampler — traced from `tests/test_candidate_sampler__24.py` through 6 source file(s).

## Entry Points

- `tests/test_candidate_sampler__24.py` (tracing origin)

## Related Issues

_No related issues found in snapshot._

## Flowchart

```mermaid
flowchart LR
  __init___py[__init__.py]
  features_py[features.py]
  settings_py[settings.py]
  cost_guard_py[cost_guard.py]
  candidate_sampler_py[candidate_sampler.py]
  engagement_tier_py[engagement_tier.py]
  __init___py --> features_py
  features_py --> settings_py
  settings_py --> cost_guard_py
  cost_guard_py --> candidate_sampler_py
  candidate_sampler_py --> engagement_tier_py
```

## Key Files

- `__init__.py` — traced during import walk
- `features.py` — traced during import walk
- `settings.py` — traced during import walk
- `cost_guard.py` — traced during import walk
- `candidate_sampler.py` — traced during import walk
- `engagement_tier.py` — traced during import walk


## Open Questions

<!-- OPEN QUESTION: `pytest` imported in `test_candidate_sampler__24.py` but `pytest.py` not found in source — handler unresolved -->
