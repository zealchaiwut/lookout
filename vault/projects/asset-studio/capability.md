# asset-studio — Capability Card

## What it is

Asset-studio is a local web app for social media creators to build and export multi-slide carousels using AI image upscaling (Magnific) and generation (Mystic) paired with text compositing and brand templates. Batch flows process multiple images with visual consistency locks, and job state persists across server restarts to survive interrupted workflows.

## Data it owns

- Snapshot artifacts under `vault/projects/asset-studio/raw/`
- Situation summary at `vault/projects/asset-studio/situation.md`
- Drift flags at `vault/projects/asset-studio/drift.md`
- Todo view at `vault/projects/asset-studio/todo-view.md`

## Read surfaces

- `GET /` — Main asset studio UI
  - Example: `curl http://localhost:8000/`
- `GET /api/job/{id}` — Poll a job's status
  - Example: `curl http://localhost:8000/api/job/{id}`
- `GET /api/jobs` — List all jobs (session-scoped)
  - Example: `curl http://localhost:8000/api/jobs`
- `GET /api/profile` — Load brand profile
  - Example: `curl http://localhost:8000/api/profile`
- `GET /api/profile/instruction-context` — Profile fields for generation prompts
  - Example: `curl http://localhost:8000/api/profile/instruction-context`
- `GET /api/templates` — List available slide templates
  - Example: `curl http://localhost:8000/api/templates`
- `GET /api/batch/{id}` — Aggregated batch status: per-job state, counts, and `total_cost_usd` rollup
  - Example: `curl http://localhost:8000/api/batch/{id}`
- `GET /api/accounts` — List registered accounts
  - Example: `curl http://localhost:8000/api/accounts`
- `GET /api/accounts/{handle}/templates` — List an account's layouts with their slot manifests
  - Example: `curl http://localhost:8000/api/accounts/{handle}/templates`
- `GET /api/accounts/{handle}/characters/jobs/{id}` — Poll a character-generation job
  - Example: `curl http://localhost:8000/api/accounts/{handle}/characters/jobs/{id}`
- `GET /api/accounts/{handle}/characters/cutouts` — List cutouts (optional `action` filter)
  - Example: `curl http://localhost:8000/api/accounts/{handle}/characters/cutouts`
- `GET /api/slide-editor/flows/{id}` — Get slide-editor flow state
  - Example: `curl http://localhost:8000/api/slide-editor/flows/{id}`
- `GET /api/slide-editor/flows/{id}/slides/{i}/slots` — Slot manifest + current text for a slide
  - Example: `curl http://localhost:8000/api/slide-editor/flows/{id}/slides/{i}/slots`
- `GET /api/slide-editor/flows/{id}/slides/{i}/preview` — Render a slide preview PNG
  - Example: `curl http://localhost:8000/api/slide-editor/flows/{id}/slides/{i}/preview`
- `GET /api/v2/flows` — List all flows (queue view: status, title, timestamps)
  - Example: `curl http://localhost:8000/api/v2/flows`
- `GET /api/v2/flows/{id}` — Get v2 flow state
  - Example: `curl http://localhost:8000/api/v2/flows/{id}`
- `GET /api/v2/flows/{id}/slides/{i}/preview` — Preview a v2 slide PNG
  - Example: `curl http://localhost:8000/api/v2/flows/{id}/slides/{i}/preview`

## How to make it do things

- **Commander slug:** `asset-studio`
- **Bulk-create path:** `POST /api/briefs` with `{"slug": "asset-studio"}`
- **CLI:** `python gather.py asset-studio` (snapshot), `python synthesize.py asset-studio` (situation.md)
- **Lookout runner:** `bin/lookout asset-studio`

## Constraints

- Snapshot data is read-only; Lookout never writes to the target repository.
- Commander API must be reachable at `sources.commander_api` for live data.
- Journal cross-links are populated only when `journal_entries` source is configured.
- GitHub repository: `zealchaiwut/asset-studio`

## Notes for AI

_Add notes here to preserve across regenerations._
