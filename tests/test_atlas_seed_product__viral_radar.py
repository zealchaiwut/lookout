"""Tests for PRODUCT.md feature extraction in atlas_seed (#viral-radar seed)."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import atlas_seed  # noqa: E402

PRODUCT = """# PRODUCT.md — Viral Radar

## The problem (diagnosis, not guess)

Something else.

## What this tool must do — three jobs, in priority order

1. **Find the wave.** Surface which races currently have an audience.
2. **Prove the recipe.** Replace hunches with data.
3. **Protect the voice.** Structure only.

## Core concepts

- **Watchlist** — accounts the user admires.
- **Tiers** — gold / silver / bronze relative to median.
- **Recipe card** — what separates gold from bronze.
- **Self account** — compared against the field.
- **Quarantine** — candidates scored in isolation.

## Milestones and exit tests

| # | Batch | Exit test |
|---|-------|-----------|
| 1 | Core engine (multi-account, paste-fed) | Paste ~20 posts |
| 2 | Apify collector | Backfill one account |
| 3 | AI "why" layer | One digest read changes the week |
| 4 | Discovery | Surfaces ≥1 unknown account |
| 5 | Self-analysis | Produces one suggestion posted |

## Hard constraints

- **Language:** Thai + English.
"""


def test_product_core_concepts_become_features():
    feats = atlas_seed.extract_features(None, None, PRODUCT)
    names = {f["name"] for f in feats}
    assert "Watchlist" in names
    assert "Tiers" in names
    assert "Recipe card" in names
    assert "Self account" in names
    assert "Quarantine" in names


def test_product_jobs_and_milestones_become_features():
    feats = atlas_seed.extract_features(None, None, PRODUCT)
    slugs = {f["slug"] for f in feats}
    assert "find-the-wave" in slugs
    assert "prove-the-recipe" in slugs
    assert "protect-the-voice" in slugs
    assert "apify-collector" in slugs
    assert "ai-why-layer" in slugs
    assert "discovery" in slugs
    assert "self-analysis" in slugs
    assert "core-engine-multi-account-paste-fed" in slugs


def test_hard_constraints_bold_terms_are_not_features():
    feats = atlas_seed.extract_features(None, None, PRODUCT)
    names = {f["name"] for f in feats}
    assert "Language" not in names


def test_readme_features_still_win_and_dedupe_against_product():
    readme = "## Features\n\n- **Watchlist** — from readme\n- **Digest** — gold feed\n"
    feats = atlas_seed.extract_features(readme, None, PRODUCT)
    slugs = [f["slug"] for f in feats]
    assert slugs.count("watchlist") == 1
    assert "digest" in slugs
