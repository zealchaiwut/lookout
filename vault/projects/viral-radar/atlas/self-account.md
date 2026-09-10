---
feature: Self account
files_read:
  - self_account.py
traced: 2026-09-10
stale: false
---


## What

Self account — traced from `routers/self_account.py` through 1 source file(s).

## Entry Points

- `routers/self_account.py` (tracing origin)
- Route: `/posts`
- Route: `/analysis`
- Route: `/scrapes`
- Route: `/backfill`
- Route: `/accounts`
- Route: `/accounts/resolve-facebook`
- Route: `/accounts/{account_id}/posts`
- Route: `/accounts/{account_id}/scrapes`
- Route: `/accounts/{account_id}/backfill`
- Route: `/accounts/scorecard-review`
- Route: `/accounts/{account_id}/scorecard`

## Related Issues

- #134 — Wire the criteria self-audit (#105) to actually run somewhere in production
- #127 — Fix Analysis-tab empty-state check to scope to the current account/view, not the whole database

## Flowchart

```mermaid
flowchart LR
  self_account_py[self_account.py]
  _posts[/posts]
  _analysis[/analysis]
  _scrapes[/scrapes]
  _backfill[/backfill]
  _accounts[/accounts]
  _accounts_resolve_facebook[/accounts/resolve-facebook]
  _accounts__account_id__posts[/accounts/{account_id}/posts]
  _accounts__account_id__scrapes[/accounts/{account_id}/scrapes]
  _accounts__account_id__backfill[/accounts/{account_id}/backfill]
  _accounts_scorecard_review[/accounts/scorecard-review]
  _accounts__account_id__scorecard[/accounts/{account_id}/scorecard]
  self_account_py --> _posts
  self_account_py --> _analysis
  self_account_py --> _scrapes
  self_account_py --> _backfill
  self_account_py --> _accounts
  self_account_py --> _accounts_resolve_facebook
  self_account_py --> _accounts__account_id__posts
  self_account_py --> _accounts__account_id__scrapes
  self_account_py --> _accounts__account_id__backfill
  self_account_py --> _accounts_scorecard_review
  self_account_py --> _accounts__account_id__scorecard
```

## Key Files

- `self_account.py` — traced during import walk


## Open Questions

<!-- OPEN QUESTION: `fastapi` imported in `self_account.py` but `fastapi.py` not found in source — handler unresolved -->
<!-- OPEN QUESTION: `pydantic` imported in `self_account.py` but `pydantic.py` not found in source — handler unresolved -->
