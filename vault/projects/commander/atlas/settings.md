---
feature: Settings
files_read:
  - settings.py
traced: 2026-08-13
stale: false
---


## What

Settings — traced from `apps/dashboard/routers/settings.py` through 1 source file(s).

## Entry Points

- `apps/dashboard/routers/settings.py` (tracing origin)
- Route: `/api/projects/{slug}/settings`
- Route: `/api/settings`
- Route: `/api/projects/{slug}/deploy-config`
- Route: `/api/projects/{slug}/environments/{env}/deploy-config/validate`
- Route: `/api/fs/list`
- Route: `/api/projects/{slug}/environments/{env}/env-vars`
- Route: `/api/projects/{slug}/docs/scaffold/check`
- Route: `/api/projects/{slug}/docs/scaffold/apply`
- Route: `/api/projects/notes`

## Related Issues

_No related issues found in snapshot._

## Flowchart

```mermaid
flowchart LR
  settings_py[settings.py]
  _api_projects__slug__settings[/api/projects/{slug}/settings]
  _api_settings[/api/settings]
  _api_projects__slug__deploy_config[/api/projects/{slug}/deploy-config]
  _api_projects__slug__environments__env__deploy_config_validate[/api/projects/{slug}/environments/{env}/deploy-config/validate]
  _api_fs_list[/api/fs/list]
  _api_projects__slug__environments__env__env_vars[/api/projects/{slug}/environments/{env}/env-vars]
  _api_projects__slug__docs_scaffold_check[/api/projects/{slug}/docs/scaffold/check]
  _api_projects__slug__docs_scaffold_apply[/api/projects/{slug}/docs/scaffold/apply]
  _api_projects_notes[/api/projects/notes]
  settings_py --> _api_projects__slug__settings
  settings_py --> _api_settings
  settings_py --> _api_projects__slug__deploy_config
  settings_py --> _api_projects__slug__environments__env__deploy_config_validate
  settings_py --> _api_fs_list
  settings_py --> _api_projects__slug__environments__env__env_vars
  settings_py --> _api_projects__slug__docs_scaffold_check
  settings_py --> _api_projects__slug__docs_scaffold_apply
  settings_py --> _api_projects_notes
```

## Key Files

- `settings.py` — traced during import walk


## Open Questions

<!-- OPEN QUESTION: `fastapi` imported in `settings.py` but `fastapi.py` not found in source — handler unresolved -->
<!-- OPEN QUESTION: `pydantic` imported in `settings.py` but `pydantic.py` not found in source — handler unresolved -->
