# viral-radar — Spec

Planning-stage source of truth (readable). Portable files live under `vault/projects/viral-radar/spec/`; promote copies them into the clone. Use the TOC below when you are confused mid-sprint.

**Pack:** _No `spec.json` yet — run `bin/lookout <target>`._

**Status:** `draft` · updated 2026-09-14T03:47:54Z

**CLI:** `lookout spec validate|submit|approve` · `lookout promote-spec` (when approved)

## Contents

- [Product](#product) — problem, jobs, concepts, non-goals
- [Requirements](#requirements) — hard constraints, milestones
- [Design](#design) — direction, signature, palette, type, layout
- [API](#api) — OpenAPI pack
- [Plan](#plan) — checklist + status history

## Product

### The problem

nerdysteps' historical numbers: normal posts earn 5–10 likes; race notes on
popular races earn 100+ — a ~10x gap. The page never had an "engagement
problem"; it had a **content-mix problem driven by a supply problem**:

### Jobs

1. **Find the wave.** Surface which races/events/topics currently have an audience pool, by watching accounts that already ride waves well.
2. **Prove the recipe.** Replace hunches with data: what structurally separates gold posts from bronze, per account and across the niche.
3. **Protect the voice.** Any generated output is structure only (angles, hooks, skeletons). The human writes all prose. If output reads generic, the tool has failed. **Exception (issue #109, M12 beta):** the opt-in "Generate full draft (beta)" path on the Now tab may produce AI-authored prose for evaluation only — it is never the default, never feeds templates or diagnosis, and is always labelled as beta. See [M12.4 beta review checkpoint](docs/m12-beta-checkpoint.md).

### Core concepts

- **Watchlist** — accounts the user admires, ingested via Apify (Facebook Posts actor) with paste as the permanent fallback.
- **Tiers** — every post is labeled relative to *its own account's median engagement score*: gold ≥ 5x median (configurable to 10–20x), silver ≥ 2x, bronze below. Never absolute counts.
- **Recipe card** — per-account and niche-wide aggregation of what separates gold from bronze: nine mechanical features (deterministic, no AI) plus an AI judgment layer (hook type, emotional trigger, wave, format).
- **Self account** — nerdysteps runs through the identical pipeline but is excluded from the niche aggregate; it is compared *against* the field.
- **Quarantine** — discovered candidate accounts are sampled and scored in isolation; nothing joins the watchlist or niche stats without human approval.

### Non-goals

- Explicit non-goal: **volume.** The tool must never optimize posts-per-week.

_(source: PRODUCT.md)_

## Requirements

### Hard constraints

- **Language:** post content is mixed Thai + English. Thai has no word spaces — all text features (word/length counts, first-line hook length, race-name matching) must be Thai-aware (e.g. pythainlp segmentation or explicit character-length metrics). Keyword lists must accept Thai race names. UI chrome is English.
- **Scale honesty:** 5–15 watched accounts, thousands of posts total, one user, one machine. No infrastructure beyond FastAPI + SQLite. Apify free/Starter tier covers collection; text LLM analysis runs only on gold posts. Exception (issue #75): the vision pass over cached post images runs on gold + a bronze sample (~100 posts) + all self posts, because downstream comparison views need a bronze/self visual baseline or they render empty.
- **Cost guards:** no paid collection run starts without an estimated-cost confirm; scraper failure degrades loudly to the paste path.
- **Legal posture:** collect only logged-out-accessible public page data via the official Apify actors; never log in to scrape.

### Milestones and exit tests

| # | Batch | Exit test |
|---|-------|-----------|
| 1 | Core engine (multi-account, paste-fed) | Paste ~20 posts each from 3 admired accounts; correct tiers + a coherent recipe card |
| 2 | Apify collector | Backfill one real account ~1 year for under ~$2, zero hand-pasting |
| 3 | AI "why" layer | One digest read changes what the user would post that week |
| 4 | Discovery | Surfaces ≥1 genuinely unknown running account whose gold posts rate as good |
| 5 | Self-analysis | Produces one suggestion the user actually posts |

_(source: PRODUCT.md)_

## Design

### Direction

**race telemetry**

The subject's world is road racing: bib numbers, split boards, timing mats,
finisher medals. The product's core data model — gold / silver / bronze —
**is** a podium, so the identity treats tiers as medals and data readouts as
split boards. This is the one place the design is allowed to be loud;
everything else stays quiet and instrumental, like a tool you check at 5am

### Signature element

**The podium rail.** Tier indicators are rendered as small medal dots
(solid disc + thin ring) in the three medal colors, used consistently
everywhere a tier appears — tables, chips, account rail, recipe cards.
Gold rows may carry a 2px left medal-gold rule. No other decorative flourish
competes with this; if a screen feels plain, that is correct.

### Palette

```palette
`--track`|#F2F3F1|App background — cool concrete, not cream
`--lane`|#FFFFFF|Cards, panels
`--ink`|#1B2430|Primary text — pre-dawn navy, not pure black
`--ink-soft`|#5C6672|Secondary text
`--line`|#DDE1E4|Borders, dividers
`--signal`|#E8590C|Single accent: actions, live states, focus — race-cone orange
`--medal-gold`|#C9A227|Gold tier
`--medal-silver`|#8E99A6|Silver tier
`--medal-bronze`|#A46A3C|Bronze tier
`--ok`|#2F9E44|Status only, never tiers
`--warn`|#E8590C|Status only, never tiers
`--fail`|#D6336C|Status only, never tiers
```

| Token | Value | Use |
|---|---|---|
| `--track` | `#F2F3F1` | App background — cool concrete, not cream |
| `--lane` | `#FFFFFF` | Cards, panels |
| `--ink` | `#1B2430` | Primary text — pre-dawn navy, not pure black |
| `--ink-soft` | `#5C6672` | Secondary text |
| `--line` | `#DDE1E4` | Borders, dividers |
| `--signal` | `#E8590C` | Single accent: actions, live states, focus — race-cone orange |
| `--medal-gold` | `#C9A227` | Gold tier |
| `--medal-silver` | `#8E99A6` | Silver tier |
| `--medal-bronze` | `#A46A3C` | Bronze tier |
| `--ok` / `--warn` / `--fail` | `#2F9E44` / `#E8590C` / `#D6336C` | Status only, never tiers |

### Typography

- **Body & content:** `IBM Plex Sans` with `IBM Plex Sans Thai` loaded and first in the fallback chain for post content. One family renders both scripts coherently.
- **Data / numerals:** `IBM Plex Mono` for every number that matters — engagement counts, multiples-of-median, feature stats, costs. Tabular numerals aligned in columns, like a results board.
- **Display (UI chrome only, English):** `Archivo` SemiBold/Bold, slightly condensed feel of a bib number, used for screen titles and the podium/ recipe headers. Never used for Thai content.
- Scale: 13px base UI, 15px post content, 20/28px headers. Generous line-height (1.6) on Thai text — Thai ascenders/descenders need air.

### Layout

```
┌──────────┬──────────────────────────────┬───────────┐
│ Accounts │  Main workspace              │ Inspector │
│ rail     │  (paste / tiers / recipes /  │ (post     │
│ (podium  │   digest / discovery)        │  detail,  │
│  chips)  │                              │  features)│
└──────────┴──────────────────────────────┴───────────┘
```

- Left rail: watchlist accounts, each with medal-dot tier breakdown.
- Main pane: dense, table-first. Tables are the primary surface — this is an analyst's tool, not a marketing site.
- Right inspector: opens on row click; full post text (Thai-safe wrapping), feature readout as a split-board (mono, two columns), AI why-card.
- Recipe cards styled as **result cards**: a header strip, then labeled stat rows in mono — reads like a race split printout.

### Motion and interaction

Minimal. One earned moment: when analysis completes, tier medals settle in
with a 150ms stagger down the table — a results board populating. No other
entrance animations, no shimmer, no pulse except a small live dot during a
running Apify/LLM job. Respect `prefers-reduced-motion`.

_(source: DESIGN.md)_

## API

**53** documented path(s).

- Vault: [[projects/viral-radar/spec/api|spec/api.yaml]]

- Clone: absent — promote to flip Spec pack API ✓

- Path table on [[projects/viral-radar/discovery#api-map|Discovery → API map]]


## Plan

## Intent

_What changes and why._

## Acceptance

- [ ] Spec pack files reviewed
- [ ] Mock validate passes
- [ ] Approved in status.yaml

## Notes

### Status history

- `draft` · 2026-09-14T03:47:54Z — workspace created

_(source: plan.md + status.yaml)_

