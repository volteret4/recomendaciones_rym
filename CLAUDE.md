# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MusicCircle** (consejero_rym) is a music recommendation system for a group of 11 friends based on their Last.fm scrobbling data. It implements 42 different recommendation engines whose outputs are combined into a final score. The project is in early implementation phase — the specification is complete but most code is yet to be written.

## Commands

### Running Scripts
```bash
# Main entry point (generate all recommendations)
python scripts/generate_recommendations.py

# Pre-computation (run before generating recommendations)
python scripts/precompute/user_profiles.py
python scripts/precompute/similarity_matrix.py
python scripts/precompute/session_clusters.py
python scripts/precompute/artist_embeddings.py
python scripts/precompute/transition_matrix.py
python scripts/precompute/loyalty_scores.py

# External data enrichment (Phase 3)
python scripts/enrichment/fetch_lastfm_similar.py
python scripts/enrichment/fetch_lastfm_tags.py
python scripts/enrichment/fetch_musicbrainz_relations.py

# Frontend (no build step required — static HTML/JS/CSS)
# Serve with any static HTTP server, e.g.:
python -m http.server 8000 --directory docs/
```

### Dependencies
```bash
pip install numpy scipy networkx python-louvain gensim requests
```

## Architecture

```
consejero_rym/
├── scripts/
│   ├── generate_recommendations.py   # Main orchestrator
│   ├── engines/                       # 42 recommendation engines
│   │   ├── base.py                   # RecommendationEngine base class
│   │   ├── collaborative.py          # Engines 1, 5-7, 10 (friend group)
│   │   ├── genre_bridge.py           # Engines 2, 14, 26, 29-30
│   │   ├── discovery_chains.py       # Engines 3, 9, 21, 23-25, 40
│   │   ├── trending.py               # Engine 4
│   │   ├── discography.py            # Engines 8, 39
│   │   ├── external_similarity.py    # Engines 11-13, 15
│   │   ├── graph_relations.py        # Engines 16-17, 19-20
│   │   ├── label_producer.py         # Engines 18-19
│   │   ├── temporal.py               # Engines 22, 31, 37
│   │   ├── ratings.py                # Engines 27-28
│   │   ├── computed.py               # Engines 32-36, 38
│   │   └── narrative.py              # Engines 41-42
│   ├── enrichment/                   # External API data fetchers
│   ├── precompute/                   # Heavy precomputation scripts
│   └── utils/
│       ├── db.py                     # SQLite helpers
│       ├── scoring.py                # Score normalization/combination
│       └── constants.py              # Weights, thresholds, config
├── output/                           # Generated static JSON files
│   ├── recommendations/{username}.json
│   ├── profiles/{username}.json
│   ├── precomputed/
│   └── stats/
└── docs/                             # Vanilla JS SPA (no build step) — también es la fuente de GitHub Pages
    ├── index.html
    ├── js/
    │   ├── app.js                    # Router, state management
    │   ├── views/                    # Page components
    │   └── components/               # Reusable UI components
    ├── css/styles.css                # Dark theme
    ├── .nojekyll                     # Evita que GitHub Pages use Jekyll
    └── data/ → ../output/            # Symlink local (gitignored); en GitHub Pages no hay datos
```

## Database

The SQLite database is at `lastfm_cache_rym_new_normalized.db` (symlink to sibling project). See `schema_lastfm_cache_rym_new_normalized.sql` for the full schema.

**Key existing tables**: `users`, `artists`, `albums`, `tracks`, `genres`, `album_genres`, `artist_genres`, `scrobbles_{username}` (one per user)

**11 users**: eliasj72, frikomid, gabredmared, lonsonxd, nubis84, rocky_stereo, alberto_gu, paqueradejere, sdecandelario, bipolarmuzik, verygooood

**Tables to create** (via migration scripts): `artist_similarities`, `artist_relations`, `artist_tags_lastfm`, `artist_styles_discogs`, `user_computed_profiles`, `user_sessions`, `recommendation_cache`, `recommendations_final`

## Implementation Phases

1. **Phase 1 (Foundation)**: Implement utils + precompute scripts + engines that only use existing DB tables (no external APIs). Engines 1–10 approximately.
2. **Phase 2 (Computed engines)**: Word2Vec embeddings, Markov chains, community detection, session clusters.
3. **Phase 3 (External enrichment)**: LastFM API, MusicBrainz, Discogs.
4. **Phase 4 (Polish)**: Frontend SPA, scoring tuning, engine reweighting based on feedback.

## Scoring System

Each engine produces candidates with normalized scores (min-max per engine). Final score = weighted sum across engines + multi-signal bonus (artist recommended by N engines). Diversity penalties applied for over-represented artists/genres. See README.md §Scoring for exact weights.

## Frontend

Pure Vanilla JS/HTML5/CSS3 SPA. No framework, no build step. Chart.js loaded via CDN. The `web/data/` directory is a symlink to `output/`, so the frontend consumes pre-generated JSON files directly.

## Secret Detection

Pre-commit hook runs Gitleaks on staged files. Never commit `.env` files or API keys. API keys for LastFM, MusicBrainz, Discogs must be stored in `.env` (gitignored).
