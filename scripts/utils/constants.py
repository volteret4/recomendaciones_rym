# Pesos por motor. Ajustar según resultados reales.
# Los motores no implementados quedan a 0.0 (ignorados en la combinación).

ENGINE_WEIGHTS: dict[str, float] = {
    # Bloque A — Amigos
    'collab_direct':      0.30,
    'musical_twin':       0.25,
    'group_consensus':    0.20,
    'genre_bridge':       0.18,
    'anti_bubble':        0.12,
    'trending_group':     0.12,
    'sync_listen':        0.10,
    'deep_discography':   0.10,
    'discovery_chain':    0.10,
    'taste_inheritance':  0.08,

    # Bloque B — Similitud externa (requiere enrichment)
    'similar_cross_group': 0.0,
    'similar_transitive':  0.0,
    'tag_profile_match':   0.0,
    'tag_top_artists':     0.0,
    'track_similarity':    0.0,

    # Bloque C — Grafos (requiere enrichment)
    'collaboration_graph': 0.0,
    'influence_tree':      0.0,
    'label_curator':       0.15,
    'shared_producers':    0.12,
    'member_network':      0.0,

    # Bloque D — Temporal
    'rabbit_hole':         0.0,
    'seasonal':            0.0,
    'adoption_pace':       0.0,
    'rediscovery_cycle':   0.0,
    'hook_speed':          0.0,
    'musical_lineage':     0.0,

    # Bloque E — Géneros y ratings
    'discogs_styles':      0.0,
    'rating_curator':      0.15,
    'critical_dissonance': 0.0,
    'decade_explorer':     0.12,
    'country_affinity':    0.10,

    # Bloque F — Señales computadas
    'skip_aware':           0.0,
    'loyalty_based':        0.0,
    'diversity_calibrated': 0.0,
    'colistening_cluster':  0.0,
    'artist2vec':           0.0,
    'markov_transition':    0.0,
    'guilty_pleasure':      0.0,
    'duration_energy':      0.0,
    'complete_collection':  0.0,
    'missing_link':         0.0,
    'narrative':            0.0,
}

# Número de recomendaciones finales por usuario
TOP_N_RECOMMENDATIONS = 60

# Penalizar artistas que el usuario ya conoce un poco
# (más de este nº de scrobbles → excluir directamente)
MAX_KNOWN_SCROBBLES = 5

# Ventana temporal para "trending" (en segundos)
TRENDING_WINDOW_SECS = 28 * 24 * 3600  # 4 semanas

# Mínimo de usuarios del grupo para "group_consensus"
GROUP_CONSENSUS_MIN_USERS = 5

# Umbrales de afinidad de género (peso mínimo para considerar)
GENRE_MIN_WEIGHT = 0.3
