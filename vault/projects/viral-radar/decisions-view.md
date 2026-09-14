# viral-radar — Decisions

History of product/architecture choices for this project. Human-authored under `decisions/`; this page joins GitHub issue/PR/sprint **status from the latest snapshot**. Lookout does not invent decisions from PR titles.

## Summary

- **2** active · **0** proposed · **0** superseded · **0** reverted (total 2)

## Contents

- [Timeline by decided date](#timeline-by-decided-date)
- [Timeline by issue created](#timeline-by-issue-created)
- [Timeline by implemented](#timeline-by-implemented)
- [Decision cards](#decision-cards)

## Timeline by decided date

Sorted by planning markdown `date:` (newest first).

| Date | ID | Decision | Status · GitHub |
|---|---|---|---|
| 2026-08-21 | [VR-D1](#vr-d1) | VR-D1 — Defer FB public groups connector | `active` · #115 closed · sprint-14 active |
| 2026-08-21 | [VR-D2](#vr-d2) | VR-D2 — Full-draft beta stays opt-in only | `active` · #109 open · sprint-14 active |

## Timeline by issue created

Sorted by earliest linked issue `createdAt` from the snapshot. Rows without a known issue date sink to the bottom.

| Date | ID | Decision | Status · GitHub |
|---|---|---|---|
| 2026-08-21 | [VR-D1](#vr-d1) | VR-D1 — Defer FB public groups connector | `active` · #115 closed · sprint-14 active |
| 2026-08-21 | [VR-D2](#vr-d2) | VR-D2 — Full-draft beta stays opt-in only | `active` · #109 open · sprint-14 active |

## Timeline by implemented

Sorted by linked PR merge/close time, else issue closed time. Unimplemented decisions sink to the bottom.

| Date | ID | Decision | Status · GitHub |
|---|---|---|---|
| 2026-08-24 | [VR-D1](#vr-d1) | VR-D1 — Defer FB public groups connector | `active` · #115 closed · sprint-14 active |
| 2026-08-21 | [VR-D2](#vr-d2) | VR-D2 — Full-draft beta stays opt-in only | `active` · #109 open · sprint-14 active |

## Decision cards

## VR-D1

**VR-D1 — Defer FB public groups connector**

**Status:** `active` · **Decided:** 2026-08-21

### GitHub links

- Issue #115: `closed` — D3 — FB public groups connector (decision needed before scoping)

- Sprint `sprint-14`: `active`

### Clocks

- Decided (planning): `2026-08-21`
- Issue created: `2026-08-21`
- Implemented: `2026-08-24`

### Context

Issue #115 asked whether viral-radar should scrape Facebook public groups
as a discovery source. That path has legal/ToS and quality risk; quarantine
sampling of page accounts already covers the "find unknown runners" job for
M12.

### Decision

**Defer** the public-groups connector. Do not scope or ticket implementation
until quarantine discovery has proven it surfaces ≥1 useful unknown account
(PRODUCT milestone 4 exit test). Prefer page watchlist + quarantine only.

### Consequences

- No Apify actor / rate budget for groups in M12.
- Discovery UI stays candidate-from-pages; groups stay out of SCHEMA.
- Revisit only with a new decision that supersedes this one.

_(source: [[projects/viral-radar/decisions/2026-08-21-defer-fb-public-groups|decisions/2026-08-21-defer-fb-public-groups.md]])_

## VR-D2

**VR-D2 — Full-draft beta stays opt-in only**

**Status:** `active` · **Decided:** 2026-08-21

### GitHub links

- Issue #109: `open` — M12.4 Beta review checkpoint: keep, shrink, or drop

- Sprint `sprint-14`: `active`

### Clocks

- Decided (planning): `2026-08-21`
- Issue created: `2026-08-21`
- Implemented: `—`

### Context

PRODUCT allows an opt-in "Generate full draft (beta)" path (issue #109 /
M12.4 checkpoint). Voice protection is a hard job: structure-only is the
default. Shipping beta prose as the default would violate Protect the voice.

### Decision

Keep full-draft generation **opt-in and labelled beta**. It must never be the
default, never feed templates or diagnosis, and remains subject to the M12.4
keep/shrink/drop review on #109.

### Consequences

- UI must show beta labelling on that path.
- Closing or shrinking #109 may supersede this decision later.

_(source: [[projects/viral-radar/decisions/2026-08-21-full-draft-beta-opt-in|decisions/2026-08-21-full-draft-beta-opt-in.md]])_

