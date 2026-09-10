---
feature: niche-recipe
files_read:
  - niche_recipe.py
  - gap_report.py
  - account_posts.py
  - settings.py
  - engagement_tier.py
traced: 2026-09-10
stale: false
---


## What

niche-recipe — traced from `services/niche_recipe.py` through 5 source file(s).

## Entry Points

- `services/niche_recipe.py` (tracing origin)

## Related Issues

_No related issues found in snapshot._

## Flowchart

```mermaid
flowchart LR
  niche_recipe_py[niche_recipe.py]
  gap_report_py[gap_report.py]
  account_posts_py[account_posts.py]
  settings_py[settings.py]
  engagement_tier_py[engagement_tier.py]
  niche_recipe_py --> gap_report_py
  gap_report_py --> account_posts_py
  account_posts_py --> settings_py
  settings_py --> engagement_tier_py
```

## Key Files

- `niche_recipe.py` — traced during import walk
- `gap_report.py` — traced during import walk
- `account_posts.py` — traced during import walk
- `settings.py` — traced during import walk
- `engagement_tier.py` — traced during import walk
