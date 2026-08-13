---
feature: Pipeline mode
files_read:
  - pipeline.py
  - failures.py
  - github_client.py
  - logging.py
  - config.py
  - serialization.py
  - state.py
  - timekeeping.py
  - events.py
  - paths.py
  - alerts.py
  - worktree.py
  - gates.py
  - model_routing.py
traced: 2026-08-13
stale: false
---


## What

Pipeline mode — traced from `tests/test_737__concurrent_pipeline_mode.py` through 14 source file(s).

## Entry Points

- `tests/test_737__concurrent_pipeline_mode.py` (tracing origin)

## Related Issues

- #2245 — Extract list_backlog_issues out of the dispatch pipeline

## Flowchart

```mermaid
flowchart LR
  pipeline_py[pipeline.py]
  failures_py[failures.py]
  github_client_py[github_client.py]
  logging_py[logging.py]
  config_py[config.py]
  serialization_py[serialization.py]
  state_py[state.py]
  timekeeping_py[timekeeping.py]
  events_py[events.py]
  paths_py[paths.py]
  alerts_py[alerts.py]
  worktree_py[worktree.py]
  gates_py[gates.py]
  model_routing_py[model_routing.py]
  pipeline_py --> failures_py
  failures_py --> github_client_py
  github_client_py --> logging_py
  logging_py --> config_py
  config_py --> serialization_py
  serialization_py --> state_py
  state_py --> timekeeping_py
  timekeeping_py --> events_py
  events_py --> paths_py
  paths_py --> alerts_py
  alerts_py --> worktree_py
  worktree_py --> gates_py
  gates_py --> model_routing_py
```

## Key Files

- `pipeline.py` — traced during import walk
- `failures.py` — traced during import walk
- `github_client.py` — traced during import walk
- `logging.py` — traced during import walk
- `config.py` — traced during import walk
- `serialization.py` — traced during import walk
- `state.py` — traced during import walk
- `timekeeping.py` — traced during import walk
- `events.py` — traced during import walk
- `paths.py` — traced during import walk
- `alerts.py` — traced during import walk
- `worktree.py` — traced during import walk
- `gates.py` — traced during import walk
- `model_routing.py` — traced during import walk


## Open Questions

<!-- OPEN QUESTION: `pytest` imported in `test_737__concurrent_pipeline_mode.py` but `pytest.py` not found in source — handler unresolved -->
