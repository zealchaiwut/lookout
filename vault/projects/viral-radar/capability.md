# viral-radar — Capability Card

## What it is

Viral-Radar is a Facebook content analytics service for creators and marketers that ingests posts, classifies engagement tiers per account, and identifies the features distinguishing high-performing content. It discovers candidate creator accounts, generates AI-powered post suggestions tailored to niche-specific engagement patterns, and surfaces content strategy gaps.

## Data it owns

- Snapshot artifacts under `vault/projects/viral-radar/raw/`
- Situation summary at `vault/projects/viral-radar/situation.md`
- Drift flags at `vault/projects/viral-radar/drift.md`
- Todo view at `vault/projects/viral-radar/todo-view.md`

## Read surfaces

| API name | API | Example |
|---|---|---|
| Gold post feed filtered to the last N days (7, 30, or 90) | `GET /api/digest?days=30` | `curl -sS http://localhost:8000/api/digest?days=30` → `200 JSON — Gold post feed filtered to the last N days (7, 30, or 90)` |
| Post detail including AI analysis fields | `GET /api/posts/{post_id}` | `curl -sS http://localhost:8000/api/posts/example` → `200 JSON — Post detail including AI analysis fields` |
| Niche recipe: equal-weighted signal aggregation with AI blend and example posts | `GET /niches/{niche_id}/recipe` | `curl -sS http://localhost:8000/niches/example/recipe` → `200 JSON — Niche recipe: equal-weighted signal aggregation with AI blend and example posts` |
| Return the cached quarantine scorecard for a candidate without re-scraping | `GET /candidates/{id}/sample` | `curl -sS http://localhost:8000/candidates/example/sample` → `200 JSON — Return the cached quarantine scorecard for a candidate without re-scraping` |
| Discovery UI — 'static/suggestions.html | `GET /suggestions` | `curl -sS http://localhost:8000/suggestions` → `200 JSON — Discovery UI — 'static/suggestions.html` |
| List all content suggestions | `GET /api/suggestions` | `curl -sS http://localhost:8000/api/suggestions` → `200 JSON — List all content suggestions` |
| Export a kept suggestion as a prose-free skeleton Markdown draft | `GET /api/suggestions/{id}/export` | `curl -sS http://localhost:8000/api/suggestions/example/export` → `200 JSON — Export a kept suggestion as a prose-free skeleton Markdown draft` |
| List engagement waves available as sources for AI post suggestions | `GET /api/waves` | `curl -sS http://localhost:8000/api/waves` → `200 JSON — List engagement waves available as sources for AI post suggestions` |
| List previously generated suggestions for a wave | `GET /api/waves/{wave}/suggestions` | `curl -sS http://localhost:8000/api/waves/example/suggestions` → `200 JSON — List previously generated suggestions for a wave` |
| Get the stored voice-notes guidance used to steer suggestion generation | `GET /api/settings/voice-notes` | `curl -sS http://localhost:8000/api/settings/voice-notes` → `200 JSON — Get the stored voice-notes guidance used to steer suggestion generation` |
| Gap report: gold-post signals present in the niche recipe but missing from an account | `GET /niches/{niche_id}/gap-report?account=<name>` | `curl -sS http://localhost:8000/niches/example/gap-report?account=<name>` → `200 JSON — Gap report: gold-post signals present in the niche recipe but missing from an account` |
| Return the current self account, or null if none is registered | `GET /self-account` | `curl -sS http://localhost:8000/self-account` → `200 JSON — Return the current self account, or null if none is registered` |
| Return posts for the self account (powers the Self tab) | `GET /self-account/posts` | `curl -sS http://localhost:8000/self-account/posts` → `200 JSON — Return posts for the self account (powers the Self tab)` |
| List watchlist accounts, excluding the self account | `GET /accounts` | `curl -sS http://localhost:8000/accounts` → `200 JSON — List watchlist accounts, excluding the self account` |

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
