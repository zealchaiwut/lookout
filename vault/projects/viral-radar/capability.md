# viral-radar — Capability Card

## What it is

Viral-Radar is a Facebook content analytics service for creators and marketers that ingests posts, classifies engagement tiers per account, and identifies the features distinguishing high-performing content. It discovers candidate creator accounts, generates AI-powered post suggestions tailored to niche-specific engagement patterns, and surfaces content strategy gaps.

## Data it owns

- Snapshot artifacts under `vault/projects/viral-radar/raw/`
- Situation summary at `vault/projects/viral-radar/situation.md`
- Drift flags at `vault/projects/viral-radar/drift.md`
- Todo view at `vault/projects/viral-radar/todo-view.md`

## Read surfaces

- `GET /api/digest?days=30` — Gold post feed filtered to the last N days (7, 30, or 90)
  - Example: `curl http://localhost:8000/api/digest?days=30`
- `GET /api/posts/{post_id}` — Post detail including AI analysis fields
  - Example: `curl http://localhost:8000/api/posts/{post_id}`
- `GET /niches/{niche_id}/recipe` — Niche recipe: equal-weighted signal aggregation with AI blend and example posts
  - Example: `curl http://localhost:8000/niches/{niche_id}/recipe`
- `GET /candidates/{id}/sample` — Return the cached quarantine scorecard for a candidate without re-scraping
  - Example: `curl http://localhost:8000/candidates/{id}/sample`
- `GET /suggestions` — Discovery UI — `static/suggestions.html
  - Example: `curl http://localhost:8000/suggestions`
- `GET /api/suggestions` — List all content suggestions
  - Example: `curl http://localhost:8000/api/suggestions`
- `GET /api/suggestions/{id}/export` — Export a kept suggestion as a prose-free skeleton Markdown draft
  - Example: `curl http://localhost:8000/api/suggestions/{id}/export`
- `GET /api/waves` — List engagement waves available as sources for AI post suggestions
  - Example: `curl http://localhost:8000/api/waves`
- `GET /api/waves/{wave}/suggestions` — List previously generated suggestions for a wave
  - Example: `curl http://localhost:8000/api/waves/{wave}/suggestions`
- `GET /api/settings/voice-notes` — Get the stored voice-notes guidance used to steer suggestion generation
  - Example: `curl http://localhost:8000/api/settings/voice-notes`
- `GET /niches/{niche_id}/gap-report?account=<name>` — Gap report: gold-post signals present in the niche recipe but missing from an account
  - Example: `curl http://localhost:8000/niches/{niche_id}/gap-report?account=<name>`
- `GET /self-account` — Return the current self account, or null if none is registered
  - Example: `curl http://localhost:8000/self-account`
- `GET /self-account/posts` — Return posts for the self account (powers the Self tab)
  - Example: `curl http://localhost:8000/self-account/posts`
- `GET /accounts` — List watchlist accounts, excluding the self account
  - Example: `curl http://localhost:8000/accounts`

## How to make it do things

- **Commander slug:** `viral-radar`
- **Bulk-create path:** `POST /api/briefs` with `{"slug": "viral-radar"}`
- **CLI:** `python gather.py viral-radar` (snapshot), `python synthesize.py viral-radar` (situation.md)
- **Lookout runner:** `bin/lookout viral-radar`

## Constraints

- Snapshot data is read-only; Lookout never writes to the target repository.
- Commander API must be reachable at `sources.commander_api` for live data.
- Journal cross-links are populated only when `journal_entries` source is configured.
- GitHub repository: `zealchaiwut/viral-radar`

## Notes for AI

_Add notes here to preserve across regenerations._
