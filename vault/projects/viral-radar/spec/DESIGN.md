# DESIGN.md — Viral Radar

Fresh visual identity. Deliberately **not** commander's design language — do
not import its tokens.css or copy its component styling. Desktop-first
(Mac, large screens); functional down to ~1024px, no mobile optimization
required.

## Direction: race telemetry

The subject's world is road racing: bib numbers, split boards, timing mats,
finisher medals. The product's core data model — gold / silver / bronze —
**is** a podium, so the identity treats tiers as medals and data readouts as
split boards. This is the one place the design is allowed to be loud;
everything else stays quiet and instrumental, like a tool you check at 5am
before a run.

## Signature element

**The podium rail.** Tier indicators are rendered as small medal dots
(solid disc + thin ring) in the three medal colors, used consistently
everywhere a tier appears — tables, chips, account rail, recipe cards.
Gold rows may carry a 2px left medal-gold rule. No other decorative flourish
competes with this; if a screen feels plain, that is correct.

## Palette

| Token | Hex | Use |
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

Rules: medal colors are **semantic and reserved** — never used decoratively.
One accent (`--signal`) total; if something else wants orange, it's wrong.
Light theme only for v1 (dark is a later ticket, not a toggle requirement).

## Typography

Thai + English mixed content is a hard constraint: the body face must ship
real Thai glyphs, not fallback soup.

- **Body & content:** `IBM Plex Sans` with `IBM Plex Sans Thai` loaded and
  first in the fallback chain for post content. One family renders both
  scripts coherently.
- **Data / numerals:** `IBM Plex Mono` for every number that matters —
  engagement counts, multiples-of-median, feature stats, costs. Tabular
  numerals aligned in columns, like a results board.
- **Display (UI chrome only, English):** `Archivo` SemiBold/Bold, slightly
  condensed feel of a bib number, used for screen titles and the podium/
  recipe headers. Never used for Thai content.
- Scale: 13px base UI, 15px post content, 20/28px headers. Generous
  line-height (1.6) on Thai text — Thai ascenders/descenders need air.

## Layout

Three-zone desktop shell:

```
┌──────────┬──────────────────────────────┬───────────┐
│ Accounts │  Main workspace              │ Inspector │
│ rail     │  (paste / tiers / recipes /  │ (post     │
│ (podium  │   digest / discovery)        │  detail,  │
│  chips)  │                              │  features)│
└──────────┴──────────────────────────────┴───────────┘
```

- Left rail: watchlist accounts, each with medal-dot tier breakdown.
- Main pane: dense, table-first. Tables are the primary surface — this is
  an analyst's tool, not a marketing site.
- Right inspector: opens on row click; full post text (Thai-safe wrapping),
  feature readout as a split-board (mono, two columns), AI why-card.
- Recipe cards styled as **result cards**: a header strip, then labeled
  stat rows in mono — reads like a race split printout.

## Motion & interaction

Minimal. One earned moment: when analysis completes, tier medals settle in
with a 150ms stagger down the table — a results board populating. No other
entrance animations, no shimmer, no pulse except a small live dot during a
running Apify/LLM job. Respect `prefers-reduced-motion`.

## Voice (interface copy)

Plain, active, runner-literate but not jokey. Buttons say what they do:
"Backfill 1 year", "Analyze gold posts", "Export skeleton". Errors state
cause + fix: "Apify actor failed — Facebook layout may have changed. Use
paste instead." Empty states are invitations: "No accounts yet. Add the
first page you wish you'd written."

## Quality floor

Keyboard focus visible (`--signal` outline), tables navigable by keyboard,
reduced motion honored, Thai text tested for wrapping/ellipsis at every
truncation point (Thai breaks differently — use `line-break: strict` and
test with real post text, not lorem).