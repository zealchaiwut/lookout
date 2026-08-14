# asset-studio — Capability Card

## What it is

Asset-studio is a local web app for social media creators to build and export multi-slide carousels using AI image upscaling (Magnific) and generation (Mystic) paired with text compositing and brand templates. Batch flows process multiple images with visual consistency locks, and job state persists across server restarts to survive interrupted workflows.

## Data it owns

- Snapshot artifacts under `vault/projects/asset-studio/raw/`
- Situation summary at `vault/projects/asset-studio/situation.md`
- Drift flags at `vault/projects/asset-studio/drift.md`
- Todo view at `vault/projects/asset-studio/todo-view.md`

## Read surfaces

| API name | API | Example |
|---|---|---|
| Main asset studio UI | `GET /` | `curl -sS http://localhost:8000/` → `200 JSON — Main asset studio UI` |
| Poll a job's status | `GET /api/job/{id}` | `curl -sS http://localhost:8000/api/job/example` → `200 JSON — Poll a job's status` |
| List all jobs (session-scoped) | `GET /api/jobs` | `curl -sS http://localhost:8000/api/jobs` → `200 JSON — List all jobs (session-scoped)` |
| Load brand profile | `GET /api/profile` | `curl -sS http://localhost:8000/api/profile` → `200 JSON — Load brand profile` |
| Profile fields for generation prompts | `GET /api/profile/instruction-context` | `curl -sS http://localhost:8000/api/profile/instruction-context` → `200 JSON — Profile fields for generation prompts` |
| List available slide templates | `GET /api/templates` | `curl -sS http://localhost:8000/api/templates` → `200 JSON — List available slide templates` |
| Aggregated batch status: per-job state, counts, and 'total_cost_usd' rollup | `GET /api/batch/{id}` | `curl -sS http://localhost:8000/api/batch/example` → `200 JSON — Aggregated batch status: per-job state, counts, and 'total_cost_usd' rollup` |
| List registered accounts | `GET /api/accounts` | `curl -sS http://localhost:8000/api/accounts` → `200 JSON — List registered accounts` |
| List an account's layouts with their slot manifests | `GET /api/accounts/{handle}/templates` | `curl -sS http://localhost:8000/api/accounts/example/templates` → `200 JSON — List an account's layouts with their slot manifests` |
| Poll a character-generation job | `GET /api/accounts/{handle}/characters/jobs/{id}` | `curl -sS http://localhost:8000/api/accounts/example/characters/jobs/example` → `200 JSON — Poll a character-generation job` |
| List cutouts (optional 'action' filter) | `GET /api/accounts/{handle}/characters/cutouts` | `curl -sS http://localhost:8000/api/accounts/example/characters/cutouts` → `200 JSON — List cutouts (optional 'action' filter)` |
| Get slide-editor flow state | `GET /api/slide-editor/flows/{id}` | `curl -sS http://localhost:8000/api/slide-editor/flows/example` → `200 JSON — Get slide-editor flow state` |
| Slot manifest + current text for a slide | `GET /api/slide-editor/flows/{id}/slides/{i}/slots` | `curl -sS http://localhost:8000/api/slide-editor/flows/example/slides/example/slots` → `200 JSON — Slot manifest + current text for a slide` |
| Render a slide preview PNG | `GET /api/slide-editor/flows/{id}/slides/{i}/preview` | `curl -sS http://localhost:8000/api/slide-editor/flows/example/slides/example/preview` → `200 JSON — Render a slide preview PNG` |
| List all flows (queue view: status, title, timestamps) | `GET /api/v2/flows` | `curl -sS http://localhost:8000/api/v2/flows` → `200 JSON — List all flows (queue view: status, title, timestamps)` |
| Get v2 flow state | `GET /api/v2/flows/{id}` | `curl -sS http://localhost:8000/api/v2/flows/example` → `200 JSON — Get v2 flow state` |
| Preview a v2 slide PNG | `GET /api/v2/flows/{id}/slides/{i}/preview` | `curl -sS http://localhost:8000/api/v2/flows/example/slides/example/preview` → `200 JSON — Preview a v2 slide PNG` |

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
