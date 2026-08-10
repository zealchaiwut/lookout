---
slug: offline-sync
created: 2026-03-04
status: assessed
targets: []
issues: []
assessed: 2026-03-10
---

Allow Lookout to cache the last snapshot locally and surface it when the
remote collector cannot reach the target. This would improve resilience
during network outages and enable use on flights or in areas with poor
connectivity.

The key challenge is cache invalidation — how do we signal to the agent
that the data is stale? A prominent banner with the snapshot timestamp
is probably sufficient.

<!-- BEGIN MACHINE ASSESSMENT -->
## Assessment

**Effort:** M  
**Blocked-by:** —  
**Summary:** Feasible. The snapshot pipeline already writes raw/ files
locally; the main work is updating the UI layer to detect missing network
and fall back to the cached raw/ directory. No external dependencies required.
<!-- END MACHINE ASSESSMENT -->
