# Changelog

Per-sprint changelog for lookout. Entries are written by the documentor when a
sprint finishes. Dated per-sprint files live under [docs/changelog/](docs/changelog/).

## Unreleased

- Wire the derive pipeline into `bin/lookout` and `lookout --all` (`derive.py`).
  Previously both ran gather → lint → commit only, so no `situation.md`,
  `capability.md`, `drift.md`, or `todo-view.md` was ever produced by a run.
- Add `llm.py`, the single gate for model calls. `claude -p` only
  (subscription-funded), cached by prompt hash, deterministic fallback on any
  failure, off unless `LOOKOUT_LLM=1`. See `docs/llm-usage.md`.
- Collect `endpoints.json` in `gather.py`. It was read by `capability_card.py`
  but written by nothing, so Read surfaces was always empty and `vault/map.md`
  could never hold an edge.
- Fix `atlas_seed.py`: the README Features section ended at the first `###`, and
  only bold-bullet feature lists were recognised. asset-studio seeded 0 features
  and now seeds 28.
- Exclude volatile host telemetry from the `situation.md` manifest diff — every
  run reported `health.uptime_seconds` and friends as changes.
- Populate "What to do next" from open GitHub issues and the brief keys the live
  Commander payload actually uses; it was empty for every target.
- Preserve an enriched capability description across deterministic runs.
- Remove six pytest leftover targets from `targets.yaml`; `--all` iterated them
  nightly against pytest tmp paths. Fix `viral-radar`'s `local:` path — it is a
  flat-layout project with no `uat/` subclone, so every local collector was
  recording `absent`.
- Read brief item labels through a key-priority list. Commander suggestions are
  dicts keyed `text` and sprint lookahead entries are keyed `label`; the previous
  `str(item)` fallback wrote Python dict reprs into `situation.md` and failed
  vault lint on all four non-asset-studio targets.
- Only wikilink next-items derived from doc paths. Issue titles, suggestions,
  and sprint labels name no vault page and render as plain text.
- Recognise the `| **Feature** | … |` README table form in `atlas_seed`;
  commander seeded 0 features and now seeds 38.
- Make the launchd plists machine-independent. They hardcoded
  `/Users/zeal-server/dev/lookout/.commander/runtime/worktree-pool/slot-0` — a
  specific user and a transient Commander worktree slot — so the nightly job
  could not run on any other machine. They are now templates rendered by
  `scripts/install.sh`, which also gained `--with-digest` and `--uninstall`.
- Set PATH explicitly in the launchd jobs. launchd's default
  `/usr/bin:/bin:/usr/sbin:/sbin` has no `gh` and no `claude`, so a sweep
  collected zero GitHub issues and silently skipped every LLM call while still
  reporting success for all five targets.
- Record a `github` source entry in `manifest.json`. `gather()` discarded
  `_collect_gh`'s result, so that failure left no trace anywhere.
- New docs: `docs/pipeline.md` (stage table and run order), `docs/llm-usage.md`.
  `PRODUCT.md`, `DESIGN.md`, `docs/architecture.md`, and `README.md` rewritten
  from scaffold placeholders.

## sprint-7

- #29: Add lookout --all nightly runner with launchd scheduling
- #30: Build Notion weekly digest publisher script
- #31: Build vault inbox capture and promote command
- #32: Define and ship the Hermes reader contract

## sprint-6

- #24: Define idea note conventions and regenerate ledger
- #25: Add assessment pass to SKILL.md idea pipeline
- #26: Track shipped status via linked GitHub issue closure
- #27: Enrich todo-view.md with effort and blocked-by annotations

## sprint-5

- #19: Register three repos and harden collectors for missing files
- #20: Generate cross-project capability map in SKILL.md
- #21: Implement pack.py for lookout pack command
- #22: Add discuss pack command to pack.py
- #23: M5: Full vault lint pass and UAT sign-off

## sprint-4

- #15: Add atlas seeding bootstrap step to SKILL.md
- #17: Add staleness detection, trace cap, and lint path check
- #18: UAT M4: Seed and verify top five perf-coach feature diagrams

## sprint-3

- #10: Implement lookout skill synthesis contract and situation generator
- #11: Add drift detection and todo view generation to SKILL.md
- #12: Add journal cross-links and capability card to SKILL.md
- #13: Add question generation and decision read-back to SKILL.md
- #14: E2E UAT: validate perf-coach across two consecutive runs

## sprint-2

- #5: Implement gather.py snapshot core with commander collectors
- #6: Add gh, git, and docs-manifest local collectors to gather.py
- #8: Add journal delta collector for target mentions
- #9: Wire gather into lookout run wrapper with degradation

## sprint-1

- #1: Scaffold lookout repo structure per DESIGN.md §1
- #3: Add lint.py skeleton with wikilink and index checks
- #4: Add run wrapper script and project README
