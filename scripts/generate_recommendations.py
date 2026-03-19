#!/usr/bin/env python3
"""
Generador principal de recomendaciones.

Uso:
    python scripts/generate_recommendations.py
    python scripts/generate_recommendations.py --user frikomid
    python scripts/generate_recommendations.py --top-n 50
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Asegurar que el raíz del proyecto está en el path.
# Eliminamos el directorio del script si Python lo añadió automáticamente
# (evita doble importación de módulos cuando se ejecuta como `python scripts/...`)
ROOT        = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = str(Path(__file__).resolve().parent)
sys.path     = [p for p in sys.path if p != SCRIPTS_DIR]
sys.path.insert(0, str(ROOT))

from scripts.utils.db       import get_connection, get_all_users, get_user_artist_counts, get_user_album_counts, get_artist_info, get_artist_genres_bulk, get_best_album_for_artist
from scripts.utils.scoring  import build_similarity_matrix, combine_engine_scores, score_to_category
from scripts.utils.constants import ENGINE_WEIGHTS, TOP_N_RECOMMENDATIONS

from scripts.engines.collaborative  import CollabDirectEngine, MusicalTwinEngine, AntiBubbleEngine, GroupConsensusEngine
from scripts.engines.genre_bridge   import GenreBridgeEngine, DecadeExplorerEngine, CountryAffinityEngine
from scripts.engines.trending       import TrendingGroupEngine
from scripts.engines.discography    import DeepDiscographyEngine
from scripts.engines.label_producer import LabelCuratorEngine, SharedProducersEngine
from scripts.engines.ratings        import RatingCuratorEngine

from scripts.precompute.user_profiles import compute_profile

OUTPUT_DIR = ROOT / 'output'

# Todos los motores de Fase 1 (sin APIs externas)
PHASE1_ENGINES = [
    CollabDirectEngine,
    MusicalTwinEngine,
    AntiBubbleEngine,
    GroupConsensusEngine,
    GenreBridgeEngine,
    DecadeExplorerEngine,
    CountryAffinityEngine,
    TrendingGroupEngine,
    DeepDiscographyEngine,
    LabelCuratorEngine,
    SharedProducersEngine,
    RatingCuratorEngine,
]


def build_context(conn, users: list[tuple[int, str]]) -> dict:
    """Pre-calcula todos los datos que los motores necesitan."""
    print('Precalculando datos de usuarios…')
    t0 = time.time()

    user_artists: dict[str, dict[int, int]] = {}
    user_album_counts: dict[str, dict[int, int]] = {}

    for _, username in users:
        user_artists[username]      = get_user_artist_counts(conn, username)
        user_album_counts[username] = get_user_album_counts(conn, username)

    print(f'  → Artistas cargados en {time.time()-t0:.1f}s')

    print('Calculando matriz de similitud entre usuarios…')
    t1 = time.time()
    user_similarity = build_similarity_matrix(user_artists)
    print(f'  → Similitud calculada en {time.time()-t1:.1f}s')

    print('Cargando géneros de artistas…')
    t2 = time.time()
    artist_genres = get_artist_genres_bulk(conn)
    print(f'  → Géneros cargados en {time.time()-t2:.1f}s')

    return {
        'users':             users,
        'user_artists':      user_artists,
        'user_album_counts': user_album_counts,
        'user_similarity':   user_similarity,
        'artist_genres':     artist_genres,
    }


def run_engines(conn, username: str, user_id: int, context: dict) -> dict[str, dict[int, dict]]:
    """Ejecuta todos los motores para un usuario y devuelve sus resultados."""
    results = {}
    for EngineClass in PHASE1_ENGINES:
        engine = EngineClass(conn, username, user_id, context)
        t0 = time.time()
        engine_results = engine.run()
        elapsed = time.time() - t0
        n = len(engine_results)
        print(f'    {engine.engine_id:<25} {n:>4} candidatos  ({elapsed:.2f}s)')
        if engine_results:
            results[engine.engine_id] = engine_results
    return results


def build_recommendation_entry(rank: int, item: dict, conn, context: dict, target_username: str) -> dict:
    """Convierte un item del pipeline de scoring en un dict listo para el JSON."""
    artist_id = item['artist_id']
    artist    = get_artist_info(conn, artist_id)
    if not artist:
        return None

    genres = [g for g, _ in context['artist_genres'].get(artist_id, [])[:5]]

    # Álbum recomendado: primero desde metadata de deep_discography, luego el mejor disponible
    rec_album = None
    if 'deep_discography' in item['engines']:
        rec_album = item['engines']['deep_discography'].get('metadata', {}).get('recommended_album')
    if not rec_album:
        album_row = get_best_album_for_artist(conn, artist_id)
        if album_row:
            rec_album = {
                'id':     album_row['id'],
                'name':   album_row['name'],
                'year':   album_row['year'],
                'reason': 'El álbum mejor valorado',
            }

    # Amigos que lo escuchan (desde metadata del motor collab_direct o group_consensus)
    friends_who_listen = []
    for engine_id in ('collab_direct', 'group_consensus', 'musical_twin'):
        if engine_id in item['engines']:
            meta = item['engines'][engine_id].get('metadata', {})
            friends = meta.get('friends', [])
            if friends:
                friends_who_listen = friends
                break

    # Engines para el JSON (sin metadata interna)
    engines_json = {
        eid: {'score': round(edata['score'], 4), 'explanation': edata.get('explanation', '')}
        for eid, edata in item['engines'].items()
    }

    # Explicación corta: concatenar las 2 mejores explicaciones
    top_explanations = sorted(
        [(eid, edata['score'], edata.get('explanation', '')) for eid, edata in item['engines'].items()],
        key=lambda x: x[1], reverse=True
    )
    explanation_short = ' '.join(
        expl for _, _, expl in top_explanations[:2] if expl
    )[:300]

    final_score = item['final_score']
    category    = score_to_category(final_score, item['engine_count'])

    return {
        'rank':               rank,
        'artist': {
            'id':             artist['id'],
            'name':           artist['name'],
            'country':        artist['country'],
            'formed_year':    artist['formed_year'],
            'genres':         genres,
            'cover_url':      artist['img_url'],
            'spotify_url':    artist['spotify_url'],
            'youtube_url':    artist['youtube_url'],
            'lastfm_url':     artist['lastfm_url'],
            'bandcamp_url':   artist['bandcamp_url'],
            'rym_url':        artist['rateyourmusic_url'],
        },
        'final_score':        round(final_score, 4),
        'confidence':         'high' if final_score >= 0.65 else 'medium' if final_score >= 0.4 else 'low',
        'category':           category,
        'engines':            engines_json,
        'explanation_short':  explanation_short,
        'explanation_full':   None,   # Motor 42 (narrativo) lo rellenará en fases posteriores
        'recommended_album':  rec_album,
        'friends_who_listen': friends_who_listen,
    }


def generate_for_user(conn, username: str, user_id: int, context: dict, top_n: int) -> tuple[dict, dict]:
    """
    Genera recommendations JSON y profile JSON para un usuario.
    Devuelve (recommendations_dict, profile_dict).
    """
    print(f'\n── {username} ─────────────────────────────────────')

    # 1. Motores
    engine_results = run_engines(conn, username, user_id, context)

    # 2. Combinar scores
    combined = combine_engine_scores(engine_results, ENGINE_WEIGHTS, top_n=top_n)

    # 3. Construir entradas de recomendación
    recommendations = []
    rank = 1
    for item in combined:
        entry = build_recommendation_entry(rank, item, conn, context, username)
        if entry:
            recommendations.append(entry)
            rank += 1

    # 4. Stats de motores
    engine_stats = {
        eid: {'candidates': len(res), 'active': True}
        for eid, res in engine_results.items()
    }
    # Motores no ejecutados
    for EngineClass in PHASE1_ENGINES:
        if EngineClass.engine_id not in engine_stats:
            engine_stats[EngineClass.engine_id] = {
                'candidates': 0,
                'active':     False,
                'reason':     'Sin datos o no implementado',
            }

    recs_json = {
        'user': {
            'id':           user_id,
            'username':     username,
            'generated_at': datetime.utcnow().isoformat() + 'Z',
        },
        'recommendations': recommendations,
        'engine_stats':    engine_stats,
    }

    # 5. Perfil
    profile_json = compute_profile(conn, username, user_id, context)

    return recs_json, profile_json


def main():
    parser = argparse.ArgumentParser(description='Genera recomendaciones musicales')
    parser.add_argument('--user',   help='Generar solo para este usuario')
    parser.add_argument('--top-n',  type=int, default=TOP_N_RECOMMENDATIONS,
                        help=f'Máximo de recomendaciones por usuario (default: {TOP_N_RECOMMENDATIONS})')
    args = parser.parse_args()

    t_start = time.time()
    print('MusicCircle — Generador de Recomendaciones')
    print('=' * 50)

    conn  = get_connection()
    users = get_all_users(conn)   # [(user_id, username), ...]

    # Filtrar qué usuarios generar (pero el contexto siempre usa TODOS los usuarios)
    target_users = users
    if args.user:
        target_users = [(uid, u) for uid, u in users if u == args.user]
        if not target_users:
            print(f'Usuario "{args.user}" no encontrado en la base de datos.')
            print(f'Usuarios disponibles: {[u for _, u in users]}')
            sys.exit(1)

    # El contexto necesita TODOS los usuarios para la similitud y los motores colaborativos
    context = build_context(conn, users)
    users   = target_users   # a partir de aquí solo iteramos los seleccionados

    # Preparar directorios de salida
    (OUTPUT_DIR / 'recommendations').mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / 'profiles').mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / 'stats').mkdir(parents=True, exist_ok=True)

    # Generar por usuario
    all_engine_stats = {}
    for user_id, username in users:
        recs_json, profile_json = generate_for_user(
            conn, username, user_id, context, top_n=args.top_n
        )

        recs_path    = OUTPUT_DIR / 'recommendations' / f'{username}.json'
        profile_path = OUTPUT_DIR / 'profiles' / f'{username}.json'

        recs_path.write_text(json.dumps(recs_json, ensure_ascii=False, indent=2))
        profile_path.write_text(json.dumps(profile_json, ensure_ascii=False, indent=2))
        print(f'  ✓ {len(recs_json["recommendations"])} recomendaciones → {recs_path.name}')

        all_engine_stats[username] = recs_json['engine_stats']

    # Meta JSON
    meta = {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'users':        [u for _, u in users],
        'top_n':        args.top_n,
        'phase':        1,
        'active_engines': [E.engine_id for E in PHASE1_ENGINES],
    }
    (OUTPUT_DIR / 'recommendations' / 'meta.json').write_text(
        json.dumps(meta, ensure_ascii=False, indent=2)
    )

    # Stats globales
    stats = {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'engine_stats': all_engine_stats,
        'user_similarity': {
            u: dict(sorted(sims.items(), key=lambda x: x[1], reverse=True))
            for u, sims in context['user_similarity'].items()
        },
    }
    (OUTPUT_DIR / 'stats' / 'engine_diagnostics.json').write_text(
        json.dumps(stats, ensure_ascii=False, indent=2)
    )

    elapsed = time.time() - t_start
    print(f'\n✓ Completado en {elapsed:.1f}s')
    conn.close()


if __name__ == '__main__':
    main()
