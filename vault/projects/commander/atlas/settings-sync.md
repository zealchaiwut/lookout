---
feature: Settings sync
files_read:
  - settings_sync.py
traced: 2026-08-13
stale: false
---


## What

Settings sync — traced from `apps/dashboard/routers/settings_sync.py` through 1 source file(s).

## Entry Points

- `apps/dashboard/routers/settings_sync.py` (tracing origin)
- Route: `/api/settings/sync/status`
- Route: `/api/settings/sync/diff`
- Route: `/api/settings/sync/commit`

## Related Issues

_No related issues found in snapshot._

## Flowchart

```mermaid
flowchart LR
  settings_sync_py[settings_sync.py]
  _api_settings_sync_status[/api/settings/sync/status]
  _api_settings_sync_diff[/api/settings/sync/diff]
  _api_settings_sync_commit[/api/settings/sync/commit]
  settings_sync_py --> _api_settings_sync_status
  settings_sync_py --> _api_settings_sync_diff
  settings_sync_py --> _api_settings_sync_commit
```

## Key Files

- `settings_sync.py` — traced during import walk


## Open Questions

<!-- OPEN QUESTION: `fastapi` imported in `settings_sync.py` but `fastapi.py` not found in source — handler unresolved -->
<!-- OPEN QUESTION: `pydantic` imported in `settings_sync.py` but `pydantic.py` not found in source — handler unresolved -->
