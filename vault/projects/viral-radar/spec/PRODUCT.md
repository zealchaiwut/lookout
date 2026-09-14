# PRODUCT.md — Viral Radar

Personal social-media intelligence tool for the **nerdysteps** Facebook page
(running + data + sport science, Thai audience). Built and run by one person;
sprints executed by Claude Code agents via commander.

## The problem (diagnosis, not guess)

nerdysteps' historical numbers: normal posts earn 5–10 likes; race notes on
popular races earn 100+ — a ~10x gap. The page never had an "engagement
problem"; it had a **content-mix problem driven by a supply problem**:

- One format works: personal, data-driven race notes riding an existing wave
  (people already searching/talking about that race).
- That format was rate-limited to ~7–10 self-run races per year.
- Gap-filler posts (free-floating geek info) underperformed, trained the
  audience and algorithm that the page is skippable, and burned the author
  out to near-zero posting.

## What this tool must do — three jobs, in priority order

1. **Find the wave.** Surface which races/events/topics currently have an
   audience pool, by watching accounts that already ride waves well.
2. **Prove the recipe.** Replace hunches with data: what structurally
   separates gold posts from bronze, per account and across the niche.
3. **Protect the voice.** Any generated output is structure only (angles,
   hooks, skeletons). The human writes all prose. If output reads generic,
   the tool has failed. **Exception (issue #109, M12 beta):** the opt-in
   "Generate full draft (beta)" path on the Now tab may produce AI-authored
   prose for evaluation only — it is never the default, never feeds
   templates or diagnosis, and is always labelled as beta. See
   [M12.4 beta review checkpoint](docs/m12-beta-checkpoint.md).

Explicit non-goal: **volume.** The tool must never optimize posts-per-week.
The metric is gold-caliber posts per month divided by hours spent. Fewer,
better, cheaper in time.

## Core concepts

- **Watchlist** — accounts the user admires, ingested via Apify (Facebook
  Posts actor) with paste as the permanent fallback.
- **Tiers** — every post is labeled relative to *its own account's median
  engagement score*: gold ≥ 5x median (configurable to 10–20x),
  silver ≥ 2x, bronze below. Never absolute counts.
- **Recipe card** — per-account and niche-wide aggregation of what separates
  gold from bronze: nine mechanical features (deterministic, no AI) plus an
  AI judgment layer (hook type, emotional trigger, wave, format).
- **Self account** — nerdysteps runs through the identical pipeline but is
  excluded from the niche aggregate; it is compared *against* the field.
- **Quarantine** — discovered candidate accounts are sampled and scored in
  isolation; nothing joins the watchlist or niche stats without human
  approval.

## Milestones and exit tests

| # | Batch | Exit test |
|---|-------|-----------|
| 1 | Core engine (multi-account, paste-fed) | Paste ~20 posts each from 3 admired accounts; correct tiers + a coherent recipe card |
| 2 | Apify collector | Backfill one real account ~1 year for under ~$2, zero hand-pasting |
| 3 | AI "why" layer | One digest read changes what the user would post that week |
| 4 | Discovery | Surfaces ≥1 genuinely unknown running account whose gold posts rate as good |
| 5 | Self-analysis | Produces one suggestion the user actually posts |

## Hard constraints

- **Language:** post content is mixed Thai + English. Thai has no word
  spaces — all text features (word/length counts, first-line hook length,
  race-name matching) must be Thai-aware (e.g. pythainlp segmentation or
  explicit character-length metrics). Keyword lists must accept Thai race
  names. UI chrome is English.
- **Scale honesty:** 5–15 watched accounts, thousands of posts total, one
  user, one machine. No infrastructure beyond FastAPI + SQLite. Apify
  free/Starter tier covers collection; text LLM analysis runs only on gold
  posts. Exception (issue #75): the vision pass over cached post images runs
  on gold + a bronze sample (~100 posts) + all self posts, because
  downstream comparison views need a bronze/self visual baseline or they
  render empty.
- **Cost guards:** no paid collection run starts without an estimated-cost
  confirm; scraper failure degrades loudly to the paste path.
- **Legal posture:** collect only logged-out-accessible public page data via
  the official Apify actors; never log in to scrape.

## Success, one year out

The page posts 2–3 gold-caliber posts per month, mostly wave-timed, each
taking a fraction of the old effort — and the sponsorship conversation can
point at an engagement-per-post record instead of a follower count.