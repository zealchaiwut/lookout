# viral-radar — Spec

Human-readable extract of the Spec pack. Portable sources live in the target clone (and optionally under `spec/` in this vault). Raw `api.yaml` is linked when present — this page is for scanning.

## Product

### Jobs / flows

1. **Find the wave.** Surface which races/events/topics currently have an
2. **Prove the recipe.** Replace hunches with data: what structurally
3. **Protect the voice.** Any generated output is structure only (angles,

### Core concepts

- **Watchlist** — accounts the user admires, ingested via Apify (Facebook
- **Tiers** — every post is labeled relative to *its own account's median
- **Recipe card** — per-account and niche-wide aggregation of what separates
- **Self account** — nerdysteps runs through the identical pipeline but is
- **Quarantine** — discovered candidate accounts are sampled and scored in

_(source: PRODUCT.md)_

## Design

**Direction:** The subject's world is road racing: bib numbers, split boards, timing mats,

### Tokens

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

### Layout

```
┌──────────┬──────────────────────────────┬───────────┐
│ Accounts │  Main workspace              │ Inspector │
│ rail     │  (paste / tiers / recipes /  │ (post     │
│ (podium  │   digest / discovery)        │  detail,  │
│  chips)  │                              │  features)│
└──────────┴──────────────────────────────┴───────────┘
```

_(source: DESIGN.md)_

## API

- Vault draft: [[projects/viral-radar/spec/api|spec/api.yaml]] (promote into the clone to flip Spec pack API ✓)

