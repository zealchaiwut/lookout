# Lookout M7 — v2 automation

- Date: 2026-08-07
- Sprint label: sprint-7
- Default labels: enhancement, ops
- Status: draft

## Context

Milestone M7 (DESIGN.md section 13). Goal: nightly refresh on zeal-server, the Notion weekly digest, inbox/promote, and the Hermes reader contract. Each ticket is independent — run this sprint whole or cherry-pick after the manual habit has proven itself. The Notion digest is the single sanctioned write in the entire system: one derived digest page, nothing else; the read-only invariant on targets, GitHub, and the journal repo is untouched. Reuse the journal repo launchd patterns (env token, wake catchup, mkdir lock) rather than reinventing.

## Prompts

```
Build the nightly runner. Add lookout --all iterating every registered target through gather, synthesis, lint, and the single-commit convention, continuing past per-target failures and summarizing at the end. Create a launchd plist for zeal-server scheduling it nightly after the journal pipeline completes (it runs at 05:45, so schedule 06:15), following the journal repo patterns: environment tokens loaded from .env, catch-up on wake, and an mkdir-based lock preventing overlap with a manual run. Include an install script and README section. AC: lookout --all on five targets survives one target being broken and says so in the summary; the plist loads and fires on schedule in a test window; a manual run while the lock is held exits gracefully telling the user.
---
Build the Notion weekly digest publisher. A publish script reads vault/index.md, each situation one-liner and capacity line, and the ideas ledger table, then writes ONE dedicated Notion page (page id in targets.yaml sources) replacing its content — strictly derived, never a source, and the only write endpoint permitted in the repo, enforced by a test asserting no other Notion write call exists anywhere. Schedule weekly via the same launchd patterns. AC: the digest page renders index rows, five one-liners, and the ideas table after a run; deleting the page content and re-running restores it; the single-write-endpoint test passes.
---
Build inbox and promote. vault/inbox/ is human-owned freeform capture; lookout promote <inbox-file> converts a triaged inbox item into either a new idea note in vault/ideas/ or a bulk-create sprint file in the standard format (date, sprint label, default labels, status header, context section, prompts in a fenced block separated by --- with inline AC, posted issues table) written to vault/packs/ for the human to paste into commander. Promote never calls any commander or GitHub API — it only writes files in the vault. AC: an inbox note promotes to a valid idea note with correct frontmatter; a promote to sprint file produces a file that parses in commander bulk create; grep shows no commander or GitHub write call in the module.
---
Define and ship the Hermes reader contract. Write docs/hermes-contract.md in the lookout repo specifying the stable read paths (targets.yaml, per-project situation.md and capability.md, ideas ledger) and the frontmatter fields Hermes may rely on, with a version field in targets.yaml bumped on breaking changes. Add a smoke script that validates the current vault against the documented contract shape. AC: the contract documents every path and field with an example; the smoke script passes on the current vault and fails with a named violation when a required frontmatter field is removed in a fixture.
```

## Posted issues

| # | Title | Issue |
|---|---|---|
| 1 | Nightly lookout --all + launchd on zeal-server | |
| 2 | Notion weekly digest publisher | |
| 3 | Inbox + promote to idea or sprint file | |
| 4 | Hermes reader contract + smoke check | |
