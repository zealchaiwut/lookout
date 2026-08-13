---
feature: Model routing
files_read:
  - model_routing.py
  - paths.py
  - logging.py
traced: 2026-08-13
stale: false
---


## What

Model routing — traced from `services/sprint_manager/model_routing.py` through 3 source file(s).

## Entry Points

- `services/sprint_manager/model_routing.py` (tracing origin)

## Related Issues

_No related issues found in snapshot._

## Flowchart

```mermaid
flowchart LR
  model_routing_py[model_routing.py]
  paths_py[paths.py]
  logging_py[logging.py]
  model_routing_py --> paths_py
  paths_py --> logging_py
```

## Key Files

- `model_routing.py` — traced during import walk
- `paths.py` — traced during import walk
- `logging.py` — traced during import walk
