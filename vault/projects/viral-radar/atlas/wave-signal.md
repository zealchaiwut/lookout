---
feature: wave-signal
files_read:
  - wave_signal.py
  - settings.py
  - engagement_tier.py
  - race_calendar.py
traced: 2026-09-10
stale: false
---


## What

wave-signal — traced from `services/wave_signal.py` through 4 source file(s).

## Entry Points

- `services/wave_signal.py` (tracing origin)

## Related Issues

_No related issues found in snapshot._

## Flowchart

```mermaid
flowchart LR
  wave_signal_py[wave_signal.py]
  settings_py[settings.py]
  engagement_tier_py[engagement_tier.py]
  race_calendar_py[race_calendar.py]
  wave_signal_py --> settings_py
  settings_py --> engagement_tier_py
  engagement_tier_py --> race_calendar_py
```

## Key Files

- `wave_signal.py` — traced during import walk
- `settings.py` — traced during import walk
- `engagement_tier.py` — traced during import walk
- `race_calendar.py` — traced during import walk
