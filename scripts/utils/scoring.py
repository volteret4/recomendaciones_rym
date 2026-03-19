import math
from collections import defaultdict



# ── Similitud entre usuarios ──────────────────────────────────

def compute_user_similarity(counts_a: dict[int, int], counts_b: dict[int, int]) -> float:
    """
    Jaccard ponderado con log(1+count). Normaliza la influencia de usuarios
    con muchos scrobbles vs pocos.
    """
    all_artists = set(counts_a) | set(counts_b)
    if not all_artists:
        return 0.0

    def w(c: int) -> float:
        return math.log1p(c)

    intersection = sum(
        min(w(counts_a.get(a, 0)), w(counts_b.get(a, 0)))
        for a in all_artists
    )
    union = sum(
        max(w(counts_a.get(a, 0)), w(counts_b.get(a, 0)))
        for a in all_artists
    )
    return intersection / union if union > 0 else 0.0


def build_similarity_matrix(
    user_artists: dict[str, dict[int, int]]
) -> dict[str, dict[str, float]]:
    """
    Calcula similitud entre todos los pares de usuarios.
    Devuelve {username: {other_username: similarity}}.
    """
    usernames = list(user_artists.keys())
    matrix: dict[str, dict[str, float]] = {u: {} for u in usernames}

    for i, u in enumerate(usernames):
        for j, v in enumerate(usernames):
            if i == j:
                matrix[u][v] = 1.0
            elif j > i:
                sim = compute_user_similarity(user_artists[u], user_artists[v])
                matrix[u][v] = sim
                matrix[v][u] = sim

    return matrix


# ── Normalización de scores ───────────────────────────────────

def normalize(scores: dict[int, float]) -> dict[int, float]:
    """Min-max normalization a [0, 1]."""
    if not scores:
        return {}
    vals = list(scores.values())
    min_v, max_v = min(vals), max(vals)
    if max_v == min_v:
        return {k: 0.5 for k in scores}
    return {k: (v - min_v) / (max_v - min_v) for k, v in scores.items()}


# ── Combinación de motores ────────────────────────────────────

def combine_engine_scores(
    engine_results: dict[str, dict[int, dict]],
    weights: dict[str, float],
    top_n: int = 100,
    per_engine_top_k: int = 300,
) -> list[dict]:
    """
    engine_results:    {engine_id: {artist_id: {'score': float, 'explanation': str, ...}}}
    weights:           {engine_id: float}
    per_engine_top_k:  Limitar cada motor a sus top-K candidatos para evitar que motores
                       muy amplios (country_affinity, etc.) dominen el ranking.

    Devuelve lista de dicts ordenada por final_score desc:
      {'artist_id': int, 'final_score': float, 'engines': {engine_id: data}, ...}
    """
    # Normalizar scores dentro de cada motor y limitar a top-K
    normalized: dict[str, dict[int, dict]] = {}
    for engine_id, results in engine_results.items():
        if not results:
            continue
        raw = {aid: d['score'] for aid, d in results.items()}
        normed = normalize(raw)

        # Limitar al top-K de este motor
        top_k_aids = sorted(normed, key=lambda a: normed[a], reverse=True)[:per_engine_top_k]

        normalized[engine_id] = {
            aid: {**results[aid], 'score': normed[aid]}
            for aid in top_k_aids
        }

    # Agregar por artista
    artist_engines: dict[int, dict[str, dict]] = defaultdict(dict)
    for engine_id, results in normalized.items():
        for artist_id, data in results.items():
            artist_engines[artist_id][engine_id] = data

    # Calcular score bruto (sin cap) para poder normalizar después
    raw_results = []
    for artist_id, engines in artist_engines.items():
        active_weights = {eid: weights.get(eid, 0.1) for eid in engines}
        total_w = sum(active_weights.values())
        if total_w == 0:
            continue

        weighted_sum = sum(
            active_weights[eid] * engines[eid]['score']
            for eid in engines
        )
        base_score = weighted_sum / total_w

        # Multi-señal: artistas validados por varios motores suben sin límite artificial
        multi_factor = 1.0 + math.log1p(len(engines) - 1) * 0.5
        raw_score    = base_score * multi_factor

        raw_results.append({
            'artist_id':   artist_id,
            'raw_score':   raw_score,
            'engines':     engines,
            'engine_count': len(engines),
        })

    if not raw_results:
        return []

    # Normalizar scores finales a [0, 1]
    max_raw = max(r['raw_score'] for r in raw_results)
    for r in raw_results:
        r['final_score'] = round(r['raw_score'] / max_raw, 4) if max_raw > 0 else 0.0

    raw_results.sort(key=lambda x: x['final_score'], reverse=True)
    return raw_results[:top_n]


# ── Categoría de confianza ────────────────────────────────────

def score_to_category(score: float, engine_count: int) -> str:
    if score >= 0.65 and engine_count >= 3:
        return 'high_confidence'
    if score >= 0.4:
        return 'adventurous'
    if engine_count == 1:
        return 'deep_cut'
    return 'exploratory'
