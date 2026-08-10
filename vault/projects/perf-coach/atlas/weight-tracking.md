---
feature: Weight tracking
files_read:
  - weight_stats.py
  - weight_ewma.py
  - weight_trend_rate.py
traced: 2026-08-10
stale: false
---


## What

Weight tracking — traced from `weight_stats.py` through 3 source file(s).

## Entry Points

- `weight_stats.py` (tracing origin)

## Related Issues

_No related issues found in snapshot._

## Flowchart

```mermaid
flowchart LR
  weight_stats_py[weight_stats.py]
  weight_ewma_py[weight_ewma.py]
  weight_trend_rate_py[weight_trend_rate.py]
  weight_stats_py --> weight_ewma_py
  weight_stats_py --> weight_trend_rate_py
```

## Key Files

- `weight_stats.py` — traced during import walk
- `weight_ewma.py` — traced during import walk
- `weight_trend_rate.py` — traced during import walk
