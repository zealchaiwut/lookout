# viral-radar — Flow

Machine-generated from the target's own docs and atlas. Lookout does not invent features or stages. Product lifecycle comes from PRODUCT.md when present; the shared Commander sprint template in `docs/workflow.md` is listed separately as how work ships.

## Product lifecycle

Extracted from `viral-radar` `PRODUCT.md` (3 numbered step(s)).

```mermaid
flowchart LR
  Findthewave[Find the wave]
  Provetherecipe[Prove the recipe]
  Protectthevoice[Protect the voice]
  Findthewave --> Provetherecipe
  Provetherecipe --> Protectthevoice
```

### Find the wave

Surface which races/events/topics currently have an

### Prove the recipe

Replace hunches with data: what structurally

### Protect the voice

Any generated output is structure only (angles,

## How work ships

From `viral-radar` `docs/workflow.md` — the Commander sprint pipeline used to build this project (3 stage(s)). This is how tickets ship, not the end-user product flow.

```mermaid
flowchart LR
  BulkCreate[Bulk Create]
  RunSprint[Run Sprint]
  FinishRerunSprint[Finish / Rerun Sprint]
  BulkCreate --> RunSprint
  RunSprint --> FinishRerunSprint
```

### Stage 1 — Bulk Create

- Paste prompts (separated by `---`) into the Bulk Create tab. - **BA agent** drafts each ticket (title, body, AC, UAT steps), one per prompt. - **Estimator** sizes each draft (S/M/L/XL). - Review and edit the drafts, then post the selected ones as GitHub issues.

### Stage 2 — Run Sprint

For each ticket in a `sprint-N` label:

### Stage 3 — Finish / Rerun Sprint

- **Finish:** the human reviews UAT tickets, closes the good ones; a sprint summary is posted as a GitHub issue, which marks the sprint finished. - **Rerun:** tickets tagged `needs-rework` run as an independent sub-sprint (`sprint-N.1`, `sprint-N.2`, …) with their own label, branch, PR, and summary.

## Architecture (from the project)

_`docs/architecture.md` has no `flowchart LR` mermaid block to copy._

## Sitemap

Feature inventory lives in the atlas: [[projects/viral-radar/atlas/index]].

Docs recorded in the latest snapshot:

- `README.md`
- `PRODUCT.md`
- `DESIGN.md`
- `SCHEMA.md`
- `docs/architecture.md`
- `docs/bulk-create/2026-07-02-1-viral-radar-core-engine.md`
- `docs/bulk-create/2026-07-02-2-viral-radar-apify-collector.md`
- `docs/bulk-create/2026-07-02-3-viral-radar-why-layer.md`
- `docs/bulk-create/2026-07-02-4-viral-radar-discovery.md`
- `docs/bulk-create/2026-07-02-5-viral-radar-self-analysis.md`
- `docs/bulk-create/README.md`
- `docs/changelog/sprint-1.1.md`
- `docs/features/README.md`
- `docs/milestones/next-stage-bcd.md`
- `docs/milestones.md`
- `docs/quickstart.md`
- `docs/tutorial.md`
- `docs/workflow.md`

