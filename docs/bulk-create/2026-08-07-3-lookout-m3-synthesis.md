# Lookout M3 — Synthesis brain

- Date: 2026-08-07
- Sprint label: sprint-3
- Default labels: enhancement, ai
- Status: draft

## Context

Milestone M3 (DESIGN.md sections 4 and 10). Goal: SKILL.md turns a raw/ snapshot plus previous notes into the situation note, drift flags, todo view, journal cross-links, capability card, decision-ready questions, and decision read-back — for perf-coach first. Core rule everywhere: LLM narrates, snapshots are the facts; no claim in a machine note without a snapshot source. Machine-owned files are regenerated whole; the human Notes for AI section in capability.md and everything human-owned is preserved verbatim. This is the quality-critical sprint — review the SKILL.md drafts in UAT carefully before accepting.

## Prompts

```
Write the core of .claude/skills/lookout/SKILL.md: the synthesis contract and the situation note generator. The skill reads the newest snapshot, the previous situation.md, and notes.md, then regenerates situation.md following the template in DESIGN.md section 4 exactly: frontmatter with target, run timestamp, sources_ok; one-liner; Capacity verdict derived from brief and health (clear to start, sprint running so wait, or N blocked first); Since last run delta vs the previous snapshot; What to do next as at most five wikilinked ordered items from brief plus Notion todos plus docs todo forward items; From the journal; Open questions; Drift top 3. State the grounding rule: every claim must trace to a snapshot file, and absent sources must be named in the note. AC: running the skill on a real perf-coach snapshot produces a situation.md matching the template; a snapshot with commander absent yields a capacity line saying commander unreachable state unverified; human notes.md is byte-identical after the run.
---
Add drift flag and todo view generation to SKILL.md. Drift: compare docs_manifest against gitlog and brief — docs claiming features git contradicts, todo items commander marks done, SCHEMA mentions diverging from migration file names; each flag is claim plus evidence path plus suggested fix as text, written to drift.md, top three summarized into situation.md. Todo view: todo-view.md section one renders Notion todos for this project with a banner naming Notion as the write home; section two mirrors the target docs/todo.md with a banner naming commander as its maintainer; annotations belong in notes. AC: a seeded contradiction fixture (doc says endpoint X, git shows it removed) produces a drift flag citing both paths; todo-view.md contains both banners and never any instruction to edit it directly.
---
Add journal cross-links and the capability card to SKILL.md. Journal: from journal_delta.json, write the From the journal section (date links plus one-line gists) and append dated rows to vault/journal/index.md tagged with mentioned projects; never copy full entries. Capability card: regenerate capability.md per the DESIGN.md section 4 template — what it is in two sentences, data it owns, read surfaces with one concrete example call each, how to make it do things (commander slug, bulk-create path, CLI entry points), constraints — within roughly 1500 tokens, preserving the human Notes for AI section verbatim across regens. AC: a delta mentioning perf-coach on two dates yields two dated links in the situation note and two rows in the journal index; the card for perf-coach lists its real read-only GET endpoints from the snapshot evidence; a sentinel string placed in Notes for AI survives three consecutive runs.
---
Add question generation and decision read-back to SKILL.md per DESIGN.md section 10. Questions: unresolved drift flags, blocked or stalled work, and human-note carry-overs become decision-ready questions with stable IDs (two-letter project prefix plus Q plus increment, never reused), each with evidence links and two or three options when the snapshot supports them, written into the Open questions section. Read-back: parse vault decisions.md and the project decisions.md; any question ID appearing in a decision entry is marked resolved and drops from the open list, the decision is cross-linked from the situation note, and a target doc contradicting a logged decision raises a drift flag with suggested edit text. Extend lint.py: decision entries referencing unknown question IDs warn; open questions older than 14 days info. AC: a stalled fixture produces a question with ID and options; adding a five-line decision entry for that ID makes the next run drop it from open questions and link the decision; a doc contradicting the decision fixture raises the drift flag; both new lint rules covered by tests.
---
End to end UAT ticket: run bin/lookout perf-coach twice on consecutive days of real data and review outputs against the M3 exit criteria in PRODUCT.md. Checklist to verify and record in the issue: situation note is trustworthy after a week away (spot check five claims against snapshots); capability card endpoints are real; a logged decision changes the second run output; no human-owned file changed; exactly one commit per run with the one-liner as message. Fix anything failing the checklist within this ticket. AC: all checklist items pass and are recorded with evidence in the issue comments.
```

## Posted issues

| # | Title | Issue |
|---|---|---|
| 1 | SKILL.md core + situation note generator | |
| 2 | Drift flags + todo view generation | |
| 3 | Journal cross-links + capability card | |
| 4 | Question generation + decision read-back + lint rules | |
| 5 | M3 end-to-end UAT on perf-coach | |
