# crux — Capability Card

## What it is

Crux is a research and diagnosis tool that transforms a messy problem into falsifiable hypotheses, generates and researches three competing root-cause explanations (A/B/C) with cited sources, re-ranks them against your data, and designs short/medium/long-horizon experiments to settle the question. It's designed for individuals (particularly engineers) diagnosing performance bottlenecks or other technical mysteries to move from uncertainty to an action plan backed by structured hypothesis testing.

## Data it owns

- Snapshot artifacts under `vault/projects/crux/raw/`
- Situation summary at `vault/projects/crux/situation.md`
- Drift flags at `vault/projects/crux/drift.md`
- Todo view at `vault/projects/crux/todo-view.md`

## Read surfaces

- `GET /healthz` — {status, env}` — no auth required
  - Example: `curl http://localhost:8000/healthz`
- `GET /api/cases` — List all cases, newest first
  - Example: `curl http://localhost:8000/api/cases`
- `GET /api/cases/{id}` — Full case with nested plans, sources, probe, verdict
  - Example: `curl http://localhost:8000/api/cases/{id}`
- `GET /api/cases/{id}/related` — Cosine similarity against closed cases
  - Example: `curl http://localhost:8000/api/cases/{id}/related`
- `GET /api/sources?plan_id={id}` — List sources for a plan
  - Example: `curl http://localhost:8000/api/sources?plan_id={id}`
- `GET /api/plans/{id}/gather-status` — Poll: `{gather_status, error, sources}
  - Example: `curl http://localhost:8000/api/plans/{id}/gather-status`

## How to make it do things

- **Commander slug:** `crux`
- **Bulk-create path:** `POST /api/briefs` with `{"slug": "crux"}`
- **CLI:** `python gather.py crux` (snapshot), `python synthesize.py crux` (situation.md)
- **Lookout runner:** `bin/lookout crux`

## Constraints

- Snapshot data is read-only; Lookout never writes to the target repository.
- Commander API must be reachable at `sources.commander_api` for live data.
- Journal cross-links are populated only when `journal_entries` source is configured.
- GitHub repository: `zealchaiwut/crux`

## Notes for AI

_Add notes here to preserve across regenerations._
