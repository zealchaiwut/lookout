---
slug: offline-sync
created: 2026-03-04
status: assessed
targets: []
issues: []
assessed: 2026-08-10
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

**Already exists:** —
**Must be built:** —
**Effort:** S
**Dependencies:** —
**Suggested first slice:** (Q1: What is the first independently testable step?)

Q1: What is the first independently testable step?

<!-- END MACHINE ASSESSMENT -->
