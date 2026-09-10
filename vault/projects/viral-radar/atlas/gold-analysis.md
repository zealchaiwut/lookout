---
feature: gold-analysis
files_read:
  - __init__.py
  - features.py
  - settings.py
  - gold_analysis.py
  - gold_analysis.py
  - local_time.py
traced: 2026-09-10
stale: false
---


## What

gold-analysis — traced from `tests/test_gold_analysis__18.py` through 6 source file(s).

## Entry Points

- `tests/test_gold_analysis__18.py` (tracing origin)

## Related Issues

- #176 — [review] Gold-analysis cost estimate shown to user doesn't match the batch actually executed
- #150 — Persist gold-analysis job state in SQLite

## Flowchart

```mermaid
flowchart LR
  __init___py[__init__.py]
  features_py[features.py]
  settings_py[settings.py]
  gold_analysis_py[gold_analysis.py]
  local_time_py[local_time.py]
  __init___py --> features_py
  features_py --> settings_py
  settings_py --> gold_analysis_py
  gold_analysis_py --> gold_analysis_py
  gold_analysis_py --> local_time_py
```

## Key Files

- `__init__.py` — traced during import walk
- `features.py` — traced during import walk
- `settings.py` — traced during import walk
- `gold_analysis.py` — traced during import walk
- `gold_analysis.py` — traced during import walk
- `local_time.py` — traced during import walk


## Open Questions

<!-- OPEN QUESTION: `pytest` imported in `test_gold_analysis__18.py` but `pytest.py` not found in source — handler unresolved -->
