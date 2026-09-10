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
| App home (Now tab HTML) | `GET /` | `curl -sS http://localhost:8000/` → `200 JSON — App home (Now tab HTML)` |
| Health check — '{"status": "ok", "db": "ok"} | `GET /api/health` | `curl -sS http://localhost:8000/api/health` → `200 JSON — Health check — '{"status": "ok", "db": "ok"}` |
| Post detail including AI analysis fields | `GET /api/posts/{post_id}` | `curl -sS http://localhost:8000/api/posts/example` → `200 JSON — Post detail including AI analysis fields` |
| List watchlist accounts, excluding the self account | `GET /accounts` | `curl -sS http://localhost:8000/accounts` → `200 JSON — List watchlist accounts, excluding the self account` |
| List accounts pending scorecard review | `GET /accounts/scorecard-review` | `curl -sS http://localhost:8000/accounts/scorecard-review` → `200 JSON — List accounts pending scorecard review` |
| List posts for an account | `GET /accounts/{account_id}/posts` | `curl -sS http://localhost:8000/accounts/example/posts` → `200 JSON — List posts for an account` |
| List scrape runs for an account | `GET /accounts/{account_id}/scrapes` | `curl -sS http://localhost:8000/accounts/example/scrapes` → `200 JSON — List scrape runs for an account` |
| Return the current self account, or null | `GET /self-account` | `curl -sS http://localhost:8000/self-account` → `200 JSON — Return the current self account, or null` |
| Return posts for the self account (powers the Self tab) | `GET /self-account/posts` | `curl -sS http://localhost:8000/self-account/posts` → `200 JSON — Return posts for the self account (powers the Self tab)` |
| Return analysis for the self account | `GET /self-account/analysis` | `curl -sS http://localhost:8000/self-account/analysis` → `200 JSON — Return analysis for the self account` |
| List scrape runs for the self account | `GET /self-account/scrapes` | `curl -sS http://localhost:8000/self-account/scrapes` → `200 JSON — List scrape runs for the self account` |
| Return the default niche | `GET /niches/default` | `curl -sS http://localhost:8000/niches/default` → `200 JSON — Return the default niche` |
| Niche recipe: equal-weighted signal aggregation with AI blend and example posts | `GET /niches/{niche_id}/recipe` | `curl -sS http://localhost:8000/niches/example/recipe` → `200 JSON — Niche recipe: equal-weighted signal aggregation with AI blend and example posts` |
| Gap report: gold-post signals present in the niche recipe but missing from an account ('?account=<name>') | `GET /niches/{niche_id}/gap-report` | `curl -sS http://localhost:8000/niches/example/gap-report` → `200 JSON — Gap report: gold-post signals present in the niche recipe but missing from an account ('?account=<name>')` |
| List anti-pattern findings scoped to a niche | `GET /niches/{niche_id}/anti-patterns` | `curl -sS http://localhost:8000/niches/example/anti-patterns` → `200 JSON — List anti-pattern findings scoped to a niche` |
| Gap report for the default niche and self account | `GET /api/gap-report/default` | `curl -sS http://localhost:8000/api/gap-report/default` → `200 JSON — Gap report for the default niche and self account` |
| Poll the status of the current discovery run | `GET /candidates/discover/status` | `curl -sS http://localhost:8000/candidates/discover/status` → `200 JSON — Poll the status of the current discovery run` |
| Get stored web-search queries | `GET /candidates/settings/queries` | `curl -sS http://localhost:8000/candidates/settings/queries` → `200 JSON — Get stored web-search queries` |
| Return the cached quarantine scorecard without re-scraping | `GET /candidates/{candidate_id}/sample` | `curl -sS http://localhost:8000/candidates/example/sample` → `200 JSON — Return the cached quarantine scorecard without re-scraping` |
| List all post suggestions | `GET /api/suggestions` | `curl -sS http://localhost:8000/api/suggestions` → `200 JSON — List all post suggestions` |
| Export a kept suggestion as a prose-free skeleton Markdown draft | `GET /api/suggestions/{suggestion_id}/export` | `curl -sS http://localhost:8000/api/suggestions/example/export` → `200 JSON — Export a kept suggestion as a prose-free skeleton Markdown draft` |
| List engagement waves available as sources for AI post suggestions | `GET /api/waves` | `curl -sS http://localhost:8000/api/waves` → `200 JSON — List engagement waves available as sources for AI post suggestions` |
| List previously generated suggestions for a wave | `GET /api/waves/{wave}/suggestions` | `curl -sS http://localhost:8000/api/waves/example/suggestions` → `200 JSON — List previously generated suggestions for a wave` |
| Export all kept suggestions for a wave | `GET /api/waves/{wave}/suggestions/export-kept` | `curl -sS http://localhost:8000/api/waves/example/suggestions/export-kept` → `200 JSON — Export all kept suggestions for a wave` |
| List currently live waves with lift scores | `GET /api/waves/live` | `curl -sS http://localhost:8000/api/waves/live` → `200 JSON — List currently live waves with lift scores` |
| Get wave search terms configuration | `GET /api/waves/terms` | `curl -sS http://localhost:8000/api/waves/terms` → `200 JSON — Get wave search terms configuration` |
| Get the voice-notes guidance used to steer suggestion generation | `GET /api/settings/voice-notes` | `curl -sS http://localhost:8000/api/settings/voice-notes` → `200 JSON — Get the voice-notes guidance used to steer suggestion generation` |
| Get the configured gold-tier engagement multiplier | `GET /api/settings/gold-multiplier` | `curl -sS http://localhost:8000/api/settings/gold-multiplier` → `200 JSON — Get the configured gold-tier engagement multiplier` |
| Return the self account's voice fingerprint | `GET /api/fingerprint` | `curl -sS http://localhost:8000/api/fingerprint` → `200 JSON — Return the self account's voice fingerprint` |
| Compare the self account's voice fingerprint with niche patterns | `GET /api/fingerprint/compare` | `curl -sS http://localhost:8000/api/fingerprint/compare` → `200 JSON — Compare the self account's voice fingerprint with niche patterns` |
| Return the niche-level voice fingerprint | `GET /api/fingerprint/niche` | `curl -sS http://localhost:8000/api/fingerprint/niche` → `200 JSON — Return the niche-level voice fingerprint` |
| Return the raw voice fingerprint record | `GET /api/voice-fingerprint` | `curl -sS http://localhost:8000/api/voice-fingerprint` → `200 JSON — Return the raw voice fingerprint record` |
| List audience questions | `GET /api/questions` | `curl -sS http://localhost:8000/api/questions` → `200 JSON — List audience questions` |
| Export a question as a prose-free skeleton | `GET /api/questions/{question_id}/export` | `curl -sS http://localhost:8000/api/questions/example/export` → `200 JSON — Export a question as a prose-free skeleton` |
| List scraped comments for a post | `GET /api/posts/{post_id}/comments` | `curl -sS http://localhost:8000/api/posts/example/comments` → `200 JSON — List scraped comments for a post` |
| List gold posts that have unanswered audience questions | `GET /api/comments/gold-targets` | `curl -sS http://localhost:8000/api/comments/gold-targets` → `200 JSON — List gold posts that have unanswered audience questions` |
| List calendar events | `GET /api/calendar/events` | `curl -sS http://localhost:8000/api/calendar/events` → `200 JSON — List calendar events` |
| Get a calendar event | `GET /api/calendar/events/{event_id}` | `curl -sS http://localhost:8000/api/calendar/events/example` → `200 JSON — Get a calendar event` |
| List upcoming posting windows derived from calendar events | `GET /api/calendar/windows` | `curl -sS http://localhost:8000/api/calendar/windows` → `200 JSON — List upcoming posting windows derived from calendar events` |
| Weekly Now-tab recommendation payload | `GET /api/now` | `curl -sS http://localhost:8000/api/now` → `200 JSON — Weekly Now-tab recommendation payload` |
| List drafts | `GET /api/drafts` | `curl -sS http://localhost:8000/api/drafts` → `200 JSON — List drafts` |
| Return tier-prediction calibration stats | `GET /api/predictions/calibration` | `curl -sS http://localhost:8000/api/predictions/calibration` → `200 JSON — Return tier-prediction calibration stats` |
| Return the most recent AI-authored beta draft | `GET /api/beta-drafts/latest` | `curl -sS http://localhost:8000/api/beta-drafts/latest` → `200 JSON — Return the most recent AI-authored beta draft` |
| List active template variants | `GET /api/templates` | `curl -sS http://localhost:8000/api/templates` → `200 JSON — List active template variants` |
| List verdict rules used in template scoring | `GET /api/templates/verdict-rules` | `curl -sS http://localhost:8000/api/templates/verdict-rules` → `200 JSON — List verdict rules used in template scoring` |
| Analysis feed — flagged suggestions and pattern findings | `GET /api/analysis` | `curl -sS http://localhost:8000/api/analysis` → `200 JSON — Analysis feed — flagged suggestions and pattern findings` |
| List analysis flag entries | `GET /api/analysis/flags` | `curl -sS http://localhost:8000/api/analysis/flags` → `200 JSON — List analysis flag entries` |
| Poll the status of the current gold-analysis job | `GET /api/gold-analysis/status` | `curl -sS http://localhost:8000/api/gold-analysis/status` → `200 JSON — Poll the status of the current gold-analysis job` |
| List content-plan slots pending post attribution | `GET /api/content-plan/pending-attribution` | `curl -sS http://localhost:8000/api/content-plan/pending-attribution` → `200 JSON — List content-plan slots pending post attribution` |
| Return the beat inventory for a content-plan slot | `GET /api/content-plan/{plan_id}/beats` | `curl -sS http://localhost:8000/api/content-plan/example/beats` → `200 JSON — Return the beat inventory for a content-plan slot` |
| List criteria self-audit findings | `GET /api/criteria-audit` | `curl -sS http://localhost:8000/api/criteria-audit` → `200 JSON — List criteria self-audit findings` |
| Return the settled crux verdict for a content-plan slot | `GET /api/crux/verdicts/{plan_id}` | `curl -sS http://localhost:8000/api/crux/verdicts/example` → `200 JSON — Return the settled crux verdict for a content-plan slot` |
| Gold-caliber posts per month vs hours spent | `GET /api/crux/summary` | `curl -sS http://localhost:8000/api/crux/summary` → `200 JSON — Gold-caliber posts per month vs hours spent` |

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
