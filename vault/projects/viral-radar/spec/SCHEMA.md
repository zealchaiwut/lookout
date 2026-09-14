# Schema

SQLite database (`viral-radar.db`). Schema is applied automatically on startup via `services/db/__init__.py::create_schema()`. Additive migrations run at startup for older databases.

## Tables

### `accounts`

Watched Facebook accounts / pages.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `name` | TEXT UNIQUE | Account handle or page name |
| `last_refreshed_at` | TEXT | ISO 8601 timestamp of last successful refresh |
| `platform` | TEXT | e.g. `facebook` |
| `page_url` | TEXT | Full URL of the page |
| `added_at` | TEXT | ISO 8601 timestamp; defaults to `datetime('now')` |
| `is_self` | INTEGER | `1` if this is the self account (nerdysteps), else `0`; at most one row is `1`. Default 0 |

### `posts`

Individual posts ingested from any source.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `account` | TEXT | Account handle (denormalised for legacy rows) |
| `account_id` | INTEGER | FK → `accounts.id` (paste-batch rows) |
| `content` | TEXT | Raw post content (Apify/collector rows) |
| `post_text` | TEXT | Post body text (paste-batch rows) |
| `images` | TEXT | JSON array of signed image URLs; these expire in ~3-5 days, see `post_images` for cached bytes |
| `features` | TEXT | JSON object of extracted features |
| `published_at` | TEXT | ISO 8601 publication timestamp (Apify) |
| `posted_at` | TEXT | ISO 8601 publication timestamp (paste) |
| `external_id` | TEXT | Apify actor post ID |
| `reactions` | INTEGER | Reaction count (Apify) |
| `likes` | INTEGER | Like count (paste) |
| `comments` | INTEGER | Comment count |
| `shares` | INTEGER | Share count |
| `has_image` | INTEGER | Boolean 0/1 |
| `has_media` | INTEGER | Boolean 0/1 (Apify) |
| `race_or_event_date` | TEXT | YYYY-MM-DD date of associated event (paste) |
| `scraped_at` | TEXT | ISO 8601 timestamp when Apify scraped the post |
| `source` | TEXT | Ingestion mode: `paste`, `backfill`, or `refresh` |
| `source_backend` | TEXT | Collector backend name (e.g. `apify`, `paste`) |
| `content_hash` | TEXT | SHA-256 of `account_id:post_text`; used for dedup |
| `created_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `backfill_state`

Persists resume cursors for resumable backfill runs.

| Column | Type | Notes |
|--------|------|-------|
| `account` | TEXT PK | Account handle |
| `resume_cursor` | TEXT | Opaque cursor passed to the next backfill run |

### `post_analyses`

AI analysis results for individual posts, written by `services/gold_analysis.py`.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `post_id` | INTEGER UNIQUE | FK → `posts.id` |
| `status` | TEXT | `ok` or `analysis-failed` |
| `hook_type` | TEXT | One of: `personal-story`, `data-reveal`, `question`, `contrarian-take`, `timely-event`, `how-to` |
| `emotional_trigger` | TEXT | One of: `pride`, `curiosity`, `fomo`, `belonging`, `surprise`, `aspiration` |
| `wave` | TEXT | Trend/event the post rides, or `none` |
| `format` | TEXT | One of: `race-note`, `analysis`, `tip`, `announcement`, `meme`, `photo-story` |
| `why_it_worked` | TEXT | Single-sentence AI explanation of the post's performance |
| `prompt_tokens` | INTEGER | Anthropic API input token count |
| `completion_tokens` | INTEGER | Anthropic API output token count |
| `analysed_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `post_visuals`

Vision-analysis results for individual posts, written by `services/post_visuals.py`
(issue #75). Mirrors `post_analyses`'s shape (one row per post, `status` +
token/cost fields), but the source is `claude -p` (CLI) classifying a
`post_images`-cached image against a closed vocabulary via `--json-schema` —
never a live URL, never the Anthropic API.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `post_id` | INTEGER UNIQUE | FK → `posts.id` |
| `status` | TEXT | `ok` or `analysis-failed` |
| `shot_type` | TEXT | One of: `bib-selfie`, `finish-line`, `watch-screenshot`, `chart`, `crowd`, `gear-flatlay`, `course`, `other` |
| `data_visual` | INTEGER | 0/1 boolean |
| `has_text_overlay` | INTEGER | 0/1 boolean |
| `face_present` | INTEGER | 0/1 boolean |
| `subject_count` | INTEGER | Non-negative integer |
| `setting` | TEXT | One of: `race`, `training`, `indoor`, `other` |
| `prompt_tokens` | INTEGER | From the `claude -p` result's `usage.input_tokens` |
| `completion_tokens` | INTEGER | From the `claude -p` result's `usage.output_tokens` |
| `cost_usd` | REAL | From the `claude -p` result's `total_cost_usd` |
| `failure_reason` | TEXT | Set when `status = 'analysis-failed'` (non-zero exit, `is_error`, missing `structured_output`, over-budget, or vocab-validation failure) |
| `analysed_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `niches`

Named groups of accounts for niche recipe aggregation.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `name` | TEXT UNIQUE | Human-readable niche label |
| `created_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `niche_accounts`

Many-to-many join between niches and accounts.

| Column | Type | Notes |
|--------|------|-------|
| `niche_id` | INTEGER | FK → `niches.id` |
| `account_name` | TEXT | Account handle matching `posts.account` |
| `added_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `candidates`

Candidate Facebook accounts discovered via post mining or web search, pending review before watchlist promotion.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `name` | TEXT UNIQUE | Account handle or page name |
| `page_url` | TEXT | Full URL of the page |
| `mention_count` | INTEGER | Times mentioned across stored posts; default 0 |
| `gold_mention_count` | INTEGER | Mentions in gold-tier posts; default 0 |
| `first_seen` | TEXT | ISO 8601 timestamp of first discovery |
| `status` | TEXT | `new`, `sampled`, `approved`, or `rejected`; default `new` |
| `source` | TEXT | Discovery source: `post_mining` or `web_search` |
| `source_query` | TEXT | Web-search query string that surfaced this candidate (nullable) |
| `approved_at` | TEXT | ISO 8601 timestamp when approved (nullable) |
| `rejected_at` | TEXT | ISO 8601 timestamp when rejected (nullable) |

### `candidate_posts`

Join table linking candidates to the stored posts in which they were mentioned.

| Column | Type | Notes |
|--------|------|-------|
| `candidate_id` | INTEGER | FK → `candidates.id`; part of composite PK |
| `post_id` | INTEGER | FK → `posts.id`; part of composite PK |

### `candidate_quarantine`

Tracks Apify sample runs for candidates. Quarantine data is intentionally isolated from watchlist analytics.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `candidate_id` | INTEGER UNIQUE | FK → `candidates.id` |
| `sampled_at` | TEXT | ISO 8601 timestamp of scrape |
| `post_cap` | INTEGER | Max posts requested; default 30 |
| `status` | TEXT | `pending`, `ok`, or `error`; default `pending` |
| `error_reason` | TEXT | Error detail if status is `error` (nullable) |
| `post_count` | INTEGER | Number of posts successfully stored; default 0 |

### `candidate_quarantine_posts`

Individual posts scraped during a candidate quarantine sample.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `quarantine_id` | INTEGER | FK → `candidate_quarantine.id` |
| `content` | TEXT | Post text |
| `reactions` | INTEGER | Reaction count |
| `comments` | INTEGER | Comment count |
| `shares` | INTEGER | Share count |
| `created_at` | TEXT | ISO 8601 publication date |
| `tier` | TEXT | Engagement tier (`gold`, `silver`, `bronze`) |
| `score` | REAL | Raw engagement score |
| `multiple` | REAL | Score multiple vs. account median |
| `features` | TEXT | JSON object of extracted features; default `'{}'` |

### `content_suggestions`

Content ideas created from niche recipe signals, with keep/export workflow.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `niche_id` | INTEGER | FK → `niches.id` (nullable) |
| `title` | TEXT | Suggestion headline |
| `status` | TEXT | `draft` or `kept`; default `draft` |
| `created_at` | TEXT | ISO 8601; defaults to `datetime('now')` |
| `kept_at` | TEXT | ISO 8601 timestamp when marked kept (nullable) |

### `post_suggestions`

AI-generated post suggestions derived from watchlist engagement waves.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `wave` | TEXT | Source engagement wave the suggestion was generated from |
| `angle` | TEXT | Suggested content angle |
| `hook_draft` | TEXT | Draft opening hook |
| `recommended_format` | TEXT | Recommended post format |
| `hook_type` | TEXT | Classified hook type |
| `status` | TEXT | Workflow status; default `new` |
| `source_post_ids` | TEXT | JSON array of post IDs that informed the suggestion; default `'[]'` |
| `created_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `post_images`

Cached image bytes for a post, fetched from the signed URLs in `posts.images`
before they expire (issue #74).

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `post_id` | INTEGER | FK → `posts.id` |
| `idx` | INTEGER | Position within the post's images array |
| `sha256` | TEXT | SHA-256 of `bytes` |
| `content_type` | TEXT | e.g. `image/jpeg` |
| `bytes` | BLOB | Raw image bytes |
| `width` | INTEGER | Best-effort, sniffed from the image header (nullable) |
| `height` | INTEGER | Best-effort, sniffed from the image header (nullable) |
| `fetched_at` | TEXT | ISO 8601; defaults to `datetime('now')` |
| `source_url` | TEXT | The signed URL the bytes were fetched from |

Unique on (`post_id`, `idx`).

### `post_image_fetch_failures`

Records image fetches that failed, so permanent losses (HTTP 403/404 — the
signed URL is gone for good) are never retried, per PRODUCT.md's "degrades
loudly" collector posture (issue #74).

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `post_id` | INTEGER | FK → `posts.id` |
| `idx` | INTEGER | Position within the post's images array |
| `source_url` | TEXT | The URL that failed to fetch |
| `status_code` | INTEGER | HTTP status code, if any |
| `reason` | TEXT | Failure description |
| `permanent` | INTEGER | `1` if this URL should never be retried (403/404), else `0` |
| `failed_at` | TEXT | ISO 8601; defaults to `datetime('now')`, updated on re-failure |

Unique on (`post_id`, `idx`).

### `app_settings`

Simple key/value store for app-level settings (e.g. voice-notes guidance for suggestion generation).

| Column | Type | Notes |
|--------|------|-------|
| `key` | TEXT PK | Setting name |
| `value` | TEXT | Setting value; default `''` |

### `scrape_runs`

Tracks every Apify scrape run (backfill or refresh) for auditing and cost accounting.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `account` | TEXT | Account handle being scraped |
| `page_url` | TEXT | Full Facebook page URL |
| `mode` | TEXT | `backfill` or `refresh` |
| `status` | TEXT | `pending`, `running`, `ok`, or `error` |
| `started_at` | TEXT | ISO 8601 start timestamp |
| `finished_at` | TEXT | ISO 8601 finish timestamp (nullable) |
| `apify_run_id` | TEXT | Apify actor run ID (nullable) |
| `results_limit` | INTEGER | Post cap requested |
| `only_posts_newer_than` | TEXT | ISO 8601 lower-bound filter for refresh mode (nullable) |
| `fetched` | INTEGER | Posts fetched from Apify |
| `stored` | INTEGER | New posts inserted |
| `updated` | INTEGER | Existing posts updated |
| `skipped` | INTEGER | Duplicate posts skipped |
| `error` | TEXT | Error detail when status is `error` (nullable) |

### `anti_pattern_findings`

AI-detected anti-patterns aggregated across a gold analysis run; never auto-applied.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `source_run` | TEXT | Analysis run identifier (e.g. ISO timestamp) |
| `scope` | TEXT | Scope label: `niche`, `account`, or `self` |
| `items_json` | TEXT | JSON array of anti-pattern finding objects |
| `created_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `audience_questions`

Questions sourced from Reddit or other platforms that map to engagement waves, used as content-angle seeds.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `source` | TEXT | Origin platform (e.g. `reddit`) |
| `title` | TEXT | Question headline |
| `body_excerpt` | TEXT | First few hundred characters of the question body (nullable) |
| `url` | TEXT | Source URL (nullable) |
| `engagement` | INTEGER | Engagement score from the source platform (nullable) |
| `topic_tags` | TEXT | JSON array of topic tags |
| `wave` | TEXT | Matching engagement wave label (nullable) |
| `status` | TEXT | `new`, `kept`, or `dismissed`; default `new` |
| `skeleton_md` | TEXT | Structure-only skeleton Markdown for the question (nullable) |
| `created_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `beta_prose_drafts`

Opt-in AI-authored prose drafts (beta feature) generated via `claude -p` from the structured beat skeleton; always labelled AI-authored and never generated automatically.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `template_id` | INTEGER | FK → `template_variants.id` |
| `template_label` | TEXT | Template label at generation time |
| `draft_text` | TEXT | Full prose draft as generated |
| `voice_fingerprint_id` | INTEGER | FK → `voice_fingerprint.id` used at generation time (nullable) |
| `unverified_facts` | TEXT | JSON array of facts flagged `[confirm with user]` |
| `outcome` | TEXT | `used_as_is`, `heavily_edited`, or `discarded` (nullable until tagged) |
| `generated_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `crux_claim_cache`

Local cache of claim-verification results from the crux sibling service (issue #164). Prevents re-calling crux for the same claim.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `claim_text` | TEXT | The claim submitted for verification (unique) |
| `support_status` | TEXT | `supported`, `contradicted`, or `unverified` |
| `citations` | TEXT | JSON array of citation objects (`source`, `url`, `excerpt`) |
| `fetch_error` | TEXT | Error message when crux was unreachable (nullable) |
| `verified_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `content_plan`

Weekly content-plan slots — one row per week × template, tracking from recommendation through post publication.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `week_start` | TEXT | ISO 8601 Monday date (YYYY-MM-DD) |
| `template_label` | TEXT | Template label assigned to this slot |
| `mode` | TEXT | `wave` or `waveless` |
| `topic_seed` | TEXT | Seed topic string used to populate the slot (nullable) |
| `reason` | TEXT | One-line rationale for the recommendation (nullable) |
| `input_needed` | TEXT | What the operator still needs to provide (nullable) |
| `confidence` | TEXT | `high`, `medium`, or `low` |
| `status` | TEXT | `recommended`, `chosen`, `skipped`, `in_progress`, `done` |
| `outcome_note` | TEXT | Human note on why the slot was skipped or changed (nullable) |
| `source_run` | TEXT | Wave analysis run that produced this slot (nullable) |
| `created_at` | TEXT | ISO 8601; defaults to `datetime('now')` |
| `chosen_variant` | TEXT | Template variant label chosen by the operator (nullable) |
| `suggestion_id` | INTEGER | FK → `post_suggestions.id` that seeded this slot (nullable) |
| `wave` | TEXT | Wave label this slot rides (nullable) |
| `export_date` | TEXT | ISO 8601 date the slot was exported (nullable) |
| `post_id` | INTEGER | FK → `posts.id` — the published post attributed to this slot (nullable) |

### `criteria_audit_log`

Read-only findings from the criteria self-audit loop — tracks mechanical criterion/status combinations that mis-predict across ≥5 rated posts.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `criterion` | TEXT | Criterion name (e.g. `hook_type:personal-story`) |
| `status` | TEXT | Verdict status tested (e.g. `gold`) |
| `post_count` | INTEGER | Number of rated posts sharing this (criterion, status) pair |
| `post_ids` | TEXT | JSON array of post IDs |
| `finding_text` | TEXT | Human-readable description of the discrepancy |
| `checked_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `draft_checks`

Results of the mechanical Stage 0 draft-check pass (deterministic, zero-LLM) for each draft submitted for checking.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `draft_id` | INTEGER | FK → `drafts.id` |
| `raw_snapshot` | TEXT | Draft text at check time (for diff rendering) |
| `hard_flags` | TEXT | JSON array of hard-fail findings |
| `soft_notes` | TEXT | JSON array of soft advisory notes |
| `voice_flags` | TEXT | JSON array of voice-consistency flags (quote+issue pairs) |
| `batch_id` | TEXT | Batch identifier shared across drafts in the same check run |
| `checked_at` | TEXT | ISO 8601; defaults to `datetime('now')` |
| `source_run` | TEXT | Run identifier for the LLM batch diagnosis pass (nullable) |

### `draft_predictions`

Tier predictions for candidate drafts, produced by the Stage 1 LLM batch diagnosis pass alongside voice flags.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `draft_id` | INTEGER | FK → `drafts.id` |
| `plan_id` | INTEGER | FK → `content_plan.id` (nullable) |
| `predicted_tier` | TEXT | `gold`, `silver`, or `bronze` |
| `predicted_multiple_low` | REAL | Lower bound of the predicted engagement multiple |
| `predicted_multiple_high` | REAL | Upper bound |
| `confidence` | TEXT | Mechanically computed from gold-sample size; never model-asserted |
| `evidence_json` | TEXT | JSON object of evidence used for the prediction |
| `predicted_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `drafts`

Operator drafts in the writing desk — text or carousel format, linked to a content-plan slot once assigned.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `name` | TEXT | Human-readable draft label |
| `format_type` | TEXT | `text`, `carousel`, or `carousel+caption` |
| `current_raw` | TEXT | Current draft content (text or JSON) |
| `is_candidate` | INTEGER | `1` if marked as a tier-prediction candidate |
| `plan_id` | INTEGER | FK → `content_plan.id` (nullable until assigned) |
| `archived_at` | TEXT | ISO 8601 when archived (nullable) |
| `created_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `gold_analysis_jobs`

Background job records for Claude gold-post analysis runs — one row per trigger, updated throughout the job lifecycle.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `status` | TEXT | `pending`, `running`, `ok`, or `error` |
| `started_at` | TEXT | ISO 8601 start timestamp |
| `finished_at` | TEXT | ISO 8601 finish timestamp (nullable) |
| `exit_code` | INTEGER | Process exit code (nullable until finished) |
| `message` | TEXT | Human-readable status message |
| `mode` | TEXT | Analysis mode: `full`, `no-templates`, or `templates-only` |
| `force` | INTEGER | `1` if `--force` was passed (re-analyses already-analysed posts) |
| `account` | TEXT | Account handle filter (nullable = all accounts) |
| `account_id` | INTEGER | FK → `accounts.id` (nullable) |
| `limit_n` | INTEGER | `--limit` cap (nullable) |
| `report_hint` | TEXT | Path to the analysis run report (nullable) |
| `steps_json` | TEXT | JSON array of step-level progress objects |
| `logs_json` | TEXT | JSON array of log lines |
| `updated_at` | TEXT | ISO 8601; updated on each status change |

### `now_inbox`

Inbox items for the Now tab — notifications, wave alerts, and action prompts surfaced to the operator.

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT PK | Stable content-addressed ID |
| `kind` | TEXT | Item kind: `wave_alert`, `action_prompt`, etc. |
| `source_label` | TEXT | Human-readable source description |
| `title` | TEXT | Headline shown in the inbox |
| `description` | TEXT | Body text (nullable) |
| `created_at` | TEXT | ISO 8601 when first created |
| `action` | TEXT | Action taken: `assigned`, `dismissed`, `own_idea`, or null |
| `acted_at` | TEXT | ISO 8601 when the action was taken (nullable) |
| `ref_id` | TEXT | FK reference to the related entity (e.g. content_plan.id as text) |

### `post_comments`

Scraped comments for individual posts, used to generate audience-question seeds.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `post_id` | INTEGER | FK → `posts.id` |
| `author` | TEXT | Comment author handle (nullable) |
| `body` | TEXT | Comment text |
| `likes` | INTEGER | Comment like count; default 0 |
| `source` | TEXT | Origin: `apify` or `paste` |
| `created_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `post_engagement_snapshots`

Point-in-time engagement readings for posts, used to score tier predictions at T+14.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `post_id` | INTEGER | FK → `posts.id` |
| `captured_at` | TEXT | ISO 8601 timestamp of the snapshot |
| `post_age_hours` | REAL | Post age in hours at snapshot time |
| `likes` | INTEGER | Like count at snapshot time |
| `comments` | INTEGER | Comment count |
| `shares` | INTEGER | Share count |
| `engagement_score` | REAL | Computed score (likes×1 + comments×3 + shares×5) |
| `source_run` | INTEGER | Scrape run ID that produced this snapshot (nullable) |

### `post_verdicts`

Final engagement-tier verdicts for posts, written by the engagement-tier classifier after a snapshot is taken.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `post_id` | INTEGER | FK → `posts.id` |
| `verdict` | TEXT | `gold`, `silver`, or `bronze` |
| `miss_reason` | TEXT | Why a predicted-gold post missed tier (nullable) |
| `tier` | TEXT | Tier label (mirrors `verdict` for query convenience) |
| `engagement_score` | REAL | Engagement score used for this verdict |
| `median_used` | REAL | Per-account median score used to compute the multiple |
| `multiplier` | REAL | `engagement_score / median_used` |
| `gold_multiplier` | INTEGER | Configured gold-tier threshold used at rating time |
| `rating_age_days` | INTEGER | Post age in days when rated |
| `snapshot_id` | INTEGER | FK → `post_engagement_snapshots.id` (nullable) |
| `wave_materialised` | INTEGER | `1` if a wave had materialised by rating time |
| `rated_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `prediction_scores`

Outcome scores for draft tier predictions, written at T+14 when the real post verdict is available.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `prediction_id` | INTEGER | FK → `draft_predictions.id` |
| `predicted_tier` | TEXT | What the model predicted |
| `actual_tier` | TEXT | The post's actual engagement tier |
| `tier_hit` | INTEGER | `1` if `predicted_tier == actual_tier` |
| `band_hit` | INTEGER | `1` if the actual engagement multiple fell within the predicted band |
| `scored_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `perf_coach_cache`

Local cache of facts fetched from the perf-coach sibling service (issue #163). Keyed by `(race_id, fact_key)` so the writing desk does not re-call the sibling on every render. Each row is attributed to the race it was fetched for via `race_id`.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `race_id` | TEXT | Race identifier (plan `topic_seed`) the fact belongs to |
| `fact_key` | TEXT | Which fact type was fetched (e.g. `perf-coach`) |
| `value` | TEXT | JSON-encoded fetched payload; NULL if `fetch_error` is set |
| `fetch_error` | TEXT | Error message from a failed fetch; NULL on success |
| `fetched_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `race_events`

Named race / event calendar entries, used as wave anchors for Thai-language race-name matching.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `name` | TEXT | Canonical event name |
| `event_date` | TEXT | ISO 8601 event date (YYYY-MM-DD) |
| `aliases` | TEXT | JSON array of alternative spellings / Thai names |
| `notes` | TEXT | Operator notes (nullable) |
| `created_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `schema_migrations`

Migration-runner tracking table — records which named migrations have been applied so re-runs are idempotent.

| Column | Type | Notes |
|--------|------|-------|
| `name` | TEXT PK | Migration module name (e.g. `001_add_issue3_schema`) |
| `applied_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `template_rule_overrides`

Per-template overrides for individual verdict rules — allows a template to suppress or relax a rule that fires incorrectly for its specific structure.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `template_id` | INTEGER | FK → `template_variants.id` |
| `rule_id` | TEXT | Verdict-rule identifier being overridden |
| `reason` | TEXT | Human justification for the override |
| `overridden_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `template_variants`

Structure-only post-template skeletons produced by Claude gold analysis (Stage 3). Each variant is an A/B template with beat outlines and hypotheses — never prose.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `label` | TEXT | Short label: `A`, `B`, or `C` |
| `name` | TEXT | Human-readable template name |
| `beats` | TEXT | JSON array of beat objects (structure only) |
| `hypothesis` | TEXT | One-sentence hypothesis on why this template wins |
| `scope` | TEXT | `niche` or `account`; default `niche` |
| `source_run` | TEXT | Analysis run that produced this variant (nullable) |
| `status` | TEXT | `active` or `retired`; default `active` |
| `created_at` | TEXT | ISO 8601; defaults to `datetime('now')` |
| `wave_dependency` | TEXT | `wave_required`, `waveless`, or `low_effort` (nullable) |
| `headlines` | TEXT | JSON array of structure-only headline skeletons; default `[]` |
| `beat_examples` | TEXT | JSON array of verbatim gold-post fragments per beat; default `[]` |
| `beat_inputs` | TEXT | JSON array of operator-fill-in prompts per beat; default `[]` |
| `retrofit_post_id` | INTEGER | FK → `posts.id` — self-account post retrofitted to this template (nullable) |
| `use_count` | INTEGER | Times this template has been assigned to a content-plan slot; default 0 |
| `segments` | TEXT | JSON array of segment objects for carousel templates; default `[]` |
| `beats_meta` | TEXT | JSON array of beat metadata; default `[]` |
| `retrofit_post_text` | TEXT | Cached text of the retrofit post (nullable) |
| `niche_beat_examples` | TEXT | Niche-scoped beat examples; default `[]` |
| `niche_segments` | TEXT | Niche-scoped carousel segments; default `[]` |
| `niche_retrofit_post_id` | INTEGER | FK → `posts.id` — niche retrofit post (nullable) |
| `niche_retrofit_account` | TEXT | Account handle of the niche retrofit post (nullable) |
| `niche_retrofit_post_text` | TEXT | Cached text of the niche retrofit post (nullable) |
| `niche_retrofit_headlines` | TEXT | Niche-scoped retrofit headlines; default `[]` |

### `voice_fingerprint`

Computed voice fingerprint for the self account — rhythm stats, opening/ending patterns, phrase frequency, and belief candidates, all derived from gold posts. `manual_refinements` always outranks computed fields and survives recomputation.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `account_id` | INTEGER | FK → `accounts.id` |
| `rhythm_stats` | TEXT | JSON object of word-count distribution stats |
| `opening_patterns` | TEXT | JSON array of classified opening-pattern objects |
| `ending_patterns` | TEXT | JSON array of classified ending-pattern objects |
| `phrase_frequency` | TEXT | JSON object of recurring phrase counts |
| `belief_candidates` | TEXT | JSON array of candidate belief-statement strings |
| `manual_refinements` | TEXT | JSON object of operator-supplied overrides (outranks computed fields) |
| `computed_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `wave_topics`

Detected engagement-wave topics aggregated from watchlist posts, used to power Now tab recommendations and post suggestions.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `source_run` | TEXT | Wave-detection run identifier |
| `label` | TEXT | Human-readable wave label (e.g. `Boston Marathon 2026`) |
| `accounts_json` | TEXT | JSON array of account handles actively posting on this wave |
| `first_seen` | TEXT | ISO 8601 date of earliest wave signal |
| `last_seen` | TEXT | ISO 8601 date of most recent signal |
| `kind` | TEXT | `race_event`, `training_topic`, or `general` |
| `created_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `crux_probes`

Links a content-plan slot to a crux probe (issue #166). One row per plan; updated in place if the probe ID changes before the verdict is settled.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `plan_id` | INTEGER UNIQUE | FK → `content_plan.id` |
| `probe_id` | TEXT | Crux probe identifier |
| `linked_at` | TEXT | ISO 8601; defaults to `datetime('now')` |

### `crux_verdicts`

Settled verdict received from crux after submitting the post's engagement metric (issue #166). One row per probe; unique on `probe_id` so re-submission is idempotent.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `probe_id` | TEXT UNIQUE | Crux probe identifier |
| `verdict` | TEXT | Verdict string returned by crux (e.g. `gold`, `pass`, `fail`) |
| `metric` | REAL | Engagement score submitted to crux |
| `settled_at` | TEXT | ISO 8601; defaults to `datetime('now')` |
