---
slug: crux-conversation-digest
created: 2026-08-10
status: assessed
targets: [crux]
issues: []
assessed: 2026-08-12
---

Generate a weekly conversation digest for Crux that summarizes active discussion
threads, surfaces unresolved decisions, and highlights messages that received
high engagement but no follow-up action. This reduces the overhead of staying
current with Crux conversations during periods of low availability.

The digest would be modeled on the existing `discuss_pack.py` pattern: read
raw conversation snapshots, apply a summarization template, and output a
structured Markdown note to `vault/`. Unlike discuss_pack, this would operate
across multiple channels and thread hierarchies rather than a single discussion
bundle.

The primary risk is relevance scoring — determining which threads actually need
attention versus which can be safely skipped requires either heuristics based
on participation patterns or a lightweight classification layer.

<!-- BEGIN MACHINE ASSESSMENT -->
## Assessment

**Already exists:** —
**Must be built:** capability card for `crux`
**Effort:** L
**Dependencies:** —
**Suggested first slice:** Add capability card for `crux`.

Q1: What capabilities does `crux` expose? (registered but no capability card or atlas found)

<!-- END MACHINE ASSESSMENT -->
