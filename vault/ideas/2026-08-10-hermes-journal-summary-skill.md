---
slug: hermes-journal-summary-skill
created: 2026-08-10
status: assessed
targets: []
issues: []
assessed: 2026-08-12
---

Build a Hermes journal summary skill that reads raw journal entries and produces
a structured narrative summary — surfacing recurring themes, decision threads,
and open loops across a rolling window of entries. This addresses the high
cognitive cost of manually scanning the journal to find context before starting
a new work session.

The skill would work similarly to the existing `gather.py` collectors but
operate on the journal corpus rather than GitHub/Notion snapshots. Output would
be a single synthesis note written to `vault/journal/` with wikilinks back to
source entries.

Key questions: how to handle journal entries that span multiple sessions, and
whether to use a fixed window (last 7 days) or a semantic boundary (last
completed project phase).

<!-- BEGIN MACHINE ASSESSMENT -->
## Assessment

**Already exists:** —
**Must be built:** —
**Effort:** S
**Dependencies:** —
**Suggested first slice:** (Q1: What is the first independently testable step?)

Q1: What is the first independently testable step?

<!-- END MACHINE ASSESSMENT -->
