# Lookout M4 — Feature atlas

- Date: 2026-08-07
- Sprint label: sprint-4
- Default labels: enhancement, ai
- Status: draft

## Context

Milestone M4 (DESIGN.md section 5). Goal: code-level feature atlas for perf-coach — one note per feature with a Mermaid flow traced from actual source, frontmatter file-maps, git-diff staleness, and a cap of 3 traces per run. Deep whole-repo graphs remain out of scope (Understand-Anything on demand, linked out). Coder model note: consider switching the coder to Opus for this sprint only — tracing unfamiliar source into correct diagrams is the one milestone where model strength visibly matters; wrong-but-plausible diagrams are worse than none.

## Prompts

```
Build atlas seeding. Add to SKILL.md an atlas bootstrap step: derive the feature list for a target from its README feature table and docs/features/ headings, write vault/projects/<name>/atlas/index.md as a machine table (feature, files known yet or pending, traced date, stale flag) with a marked human section where features can be added or removed by hand and are respected on subsequent runs. Create empty per-feature note stubs with frontmatter (feature, files empty, traced null, stale true). AC: seeding perf-coach yields a plausible feature list from its real README; a feature added in the human section appears as a stub next run; a feature removed there is left untouched on disk but dropped from the machine table.
---
Add the tracing step to SKILL.md per the DESIGN.md section 5 note template. For a stale feature, the skill reads the relevant target source files (discovering them from entry points named in docs and imports), then writes the note: what it does, entry points, related issues from the snapshot, a Mermaid flowchart of the request or data flow, key files with one line each, and frontmatter files listing every file read. Grounding rule: every node in the diagram must correspond to a real file, route, or table seen in source; unknowns are written as open questions instead of guessed. AC: tracing one known perf-coach feature produces a diagram whose nodes all name real files or routes verifiable in the repo; an ambiguous flow yields an atlas note containing an explicit open question rather than an invented edge; the mermaid block parses with mmdc or an equivalent syntax check in tests.
---
Build staleness detection and the trace cap. In gather.py, diff gitlog changed files against each atlas note frontmatter files list and mark matching notes stale true in their frontmatter and the atlas index. In SKILL.md, each run re-traces at most 3 stale or new features, oldest traced first, leaving the rest flagged with the queue visible in the atlas index. Extend lint.py: an atlas note whose files list contains a path missing from the target warns. AC: touching one mapped file in a fixture repo marks exactly that note stale; a run with five stale notes traces three and lists two pending in the index; the new lint rule is covered by a test.
---
M4 UAT ticket: seed and trace the top five perf-coach features across however many runs the cap requires, then verify each diagram against the code by hand. Record in the issue per feature: diagram matches reality yes or no, corrections made, files list complete. Fix mismatches within this ticket. AC: five atlas notes exist whose diagrams match the code as reviewed, staleness and cap behaved as designed across the runs, and the review evidence is in the issue comments.
```

## Posted issues

| # | Title | Issue |
|---|---|---|
| 1 | Atlas seeding + index conventions | |
| 2 | Code-level tracing + Mermaid template | |
| 3 | Staleness detection + trace cap + lint | |
| 4 | M4 UAT: top-5 perf-coach features verified | |
