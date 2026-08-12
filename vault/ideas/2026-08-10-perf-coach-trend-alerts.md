---
slug: perf-coach-trend-alerts
created: 2026-08-10
status: promoted
targets: [perf-coach]
issues: [62]
assessed: 2026-08-12
---

Add a trend-alert layer to perf-coach that detects statistically significant
changes in key training metrics — EWMA bodyweight drift, CTL/ATL ratio shifts,
and per-run speed signals — and surfaces them as actionable push notifications.

Currently the user must manually scan the dashboard for trend changes. An alert
system grounded in the existing Banister model and EWMA calculations would
eliminate the need for daily dashboard checks and surface important signals
during the session where they are most actionable.

This builds directly on the existing `bodyweight-ewma-trend`, `running-tss`,
and `ctl-atl-calibration-loop-closed` atlas features. The main open question is
the notification delivery mechanism (push vs. email digest).

<!-- BEGIN MACHINE ASSESSMENT -->
## Assessment

**Already exists:** [[projects/perf-coach/atlas/accept-suggestion-flow]]; [[projects/perf-coach/atlas/activity-streams]]; [[projects/perf-coach/atlas/acwr-training-load-guidance]]
**Must be built:** —
**Effort:** S
**Dependencies:** [[projects/perf-coach]]
**Suggested first slice:** Verify scope against [[projects/perf-coach/atlas/accept-suggestion-flow]].

<!-- BEGIN ISSUE STATE TABLE -->
## Linked Issues

| # | Title | State |
|---|-------|-------|
| #62 | [follow-up] /api/suggest slides field has no server-side upper bound | open |
<!-- END ISSUE STATE TABLE -->
<!-- END MACHINE ASSESSMENT -->
