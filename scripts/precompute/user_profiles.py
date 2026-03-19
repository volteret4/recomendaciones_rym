"""
Calcula el perfil JSON de cada usuario para output/profiles/{username}.json
"""
import math
import time
from collections import defaultdict
from datetime import datetime


def compute_profile(conn, username: str, user_id: int, context: dict) -> dict:
    """Devuelve el dict completo del perfil de usuario."""
    tbl          = f'scrobbles_{username.lower()}'
    artist_counts = context['user_artists'].get(username, {})
    album_counts  = context.get('user_album_counts', {}).get(username, {})

    total_scrobbles = sum(artist_counts.values())
    unique_artists  = len(artist_counts)
    unique_albums   = len(album_counts)

    first_scrobble = _first_scrobble(conn, tbl)
    genre_dist     = _genre_distribution(artist_counts, context['artist_genres'])
    decade_dist    = _decade_distribution(conn, tbl)
    country_dist   = _country_distribution(conn, tbl)
    top_labels     = _top_labels(conn, tbl)
    diversity      = _diversity_index(artist_counts)
    adopter_type   = _adopter_type(conn, username, context)
    core_artists   = _core_artists(conn, tbl, artist_counts)
    recent_disc    = _recent_discoveries(conn, user_id, artist_counts)

    twin, twin_sim = _find_twin(username, context)

    return {
        'username':         username,
        'total_scrobbles':  total_scrobbles,
        'unique_artists':   unique_artists,
        'unique_albums':    unique_albums,
        'first_scrobble':   first_scrobble,
        'diversity_index':  round(diversity, 3),
        'adopter_type':     adopter_type,
        'genre_distribution': genre_dist,
        'decade_distribution': decade_dist,
        'country_distribution': country_dist,
        'top_labels':       top_labels,
        'musical_twin':     twin,
        'twin_similarity':  round(twin_sim, 3),
        'core_artists':     core_artists,
        'recent_discoveries': recent_disc,
        'generated_at':     datetime.utcnow().isoformat() + 'Z',
    }


# ── Helpers ───────────────────────────────────────────────────

def _first_scrobble(conn, tbl: str) -> str | None:
    row = conn.execute(f'SELECT MIN(timestamp) AS ts FROM {tbl}').fetchone()
    if row and row['ts']:
        return datetime.fromtimestamp(row['ts']).strftime('%Y-%m-%d')
    return None


def _genre_distribution(artist_counts: dict, artist_genres: dict) -> list[dict]:
    genre_scores: dict[str, float] = defaultdict(float)
    for artist_id, cnt in artist_counts.items():
        for genre, weight in artist_genres.get(artist_id, []):
            genre_scores[genre] += cnt * weight

    total = sum(genre_scores.values()) or 1
    top   = sorted(genre_scores.items(), key=lambda x: x[1], reverse=True)[:20]
    return [
        {'genre': g, 'weight': round(s / total, 4), 'score': round(s)}
        for g, s in top
    ]


def _decade_distribution(conn, tbl: str) -> list[dict]:
    rows = conn.execute(f'''
        SELECT
            CASE
                WHEN al.year IS NULL OR al.year < 1940 THEN 'Pre-60s'
                WHEN al.year < 1970 THEN '1960s'
                WHEN al.year < 1980 THEN '1970s'
                WHEN al.year < 1990 THEN '1980s'
                WHEN al.year < 2000 THEN '1990s'
                WHEN al.year < 2010 THEN '2000s'
                WHEN al.year < 2020 THEN '2010s'
                ELSE '2020s'
            END AS decade,
            COUNT(*) AS cnt
        FROM {tbl} s
        LEFT JOIN albums al ON al.id = s.album_id
        WHERE s.album_id IS NOT NULL
        GROUP BY decade
        ORDER BY cnt DESC
    ''').fetchall()

    total = sum(r['cnt'] for r in rows) or 1
    return [
        {'decade': r['decade'], 'weight': round(r['cnt'] / total, 4)}
        for r in rows if r['decade'] != 'Pre-60s' or r['cnt'] > 0
    ]


def _country_distribution(conn, tbl: str) -> list[dict]:
    rows = conn.execute(f'''
        SELECT a.country, COUNT(*) AS cnt
        FROM {tbl} s
        JOIN artists a ON a.id = s.artist_id
        WHERE a.country IS NOT NULL AND a.country != ''
        GROUP BY a.country
        ORDER BY cnt DESC
        LIMIT 10
    ''').fetchall()

    total = sum(r['cnt'] for r in rows) or 1
    return [
        {'country': r['country'], 'weight': round(r['cnt'] / total, 4)}
        for r in rows
    ]


def _top_labels(conn, tbl: str) -> list[dict]:
    rows = conn.execute(f'''
        SELECT al.label, COUNT(DISTINCT s.artist_id) AS artists, COUNT(*) AS scrobbles
        FROM {tbl} s
        JOIN albums al ON al.id = s.album_id
        WHERE al.label IS NOT NULL AND al.label != '' AND s.album_id IS NOT NULL
        GROUP BY al.label
        ORDER BY artists DESC, scrobbles DESC
        LIMIT 15
    ''').fetchall()

    return [
        {'label': r['label'], 'artists': r['artists'], 'scrobbles': r['scrobbles']}
        for r in rows
    ]


def _diversity_index(artist_counts: dict) -> float:
    """Shannon entropy normalizada como índice de diversidad [0, 1]."""
    total = sum(artist_counts.values())
    if total == 0:
        return 0.0
    entropy = -sum(
        (c / total) * math.log2(c / total)
        for c in artist_counts.values()
        if c > 0
    )
    max_entropy = math.log2(len(artist_counts)) if len(artist_counts) > 1 else 1
    return entropy / max_entropy if max_entropy > 0 else 0.0


def _adopter_type(conn, username: str, context: dict) -> str:
    """
    Clasifica al usuario como early_adopter, mid_adopter o follower
    comparando sus timestamps de first_listen con los del grupo.
    """
    user_id = next((uid for uid, u in context['users'] if u == username), None)
    if not user_id:
        return 'unknown'

    rows = conn.execute('''
        SELECT uf.artist_id,
               uf.first_timestamp AS user_ts,
               g.min_ts           AS group_min_ts
        FROM user_first_artist_listen uf
        JOIN (
            SELECT artist_id, MIN(first_timestamp) AS min_ts
            FROM user_first_artist_listen
            GROUP BY artist_id
        ) g ON g.artist_id = uf.artist_id
        WHERE uf.user_id = ?
          AND uf.first_timestamp IS NOT NULL
          AND g.min_ts IS NOT NULL
        LIMIT 500
    ''', (user_id,)).fetchall()

    if not rows:
        return 'unknown'

    diffs = [r['user_ts'] - r['group_min_ts'] for r in rows]
    avg_diff_days = (sum(diffs) / len(diffs)) / 86400

    if avg_diff_days < 30:
        return 'early_adopter'
    if avg_diff_days < 120:
        return 'mid_adopter'
    return 'follower'


def _core_artists(conn, tbl: str, artist_counts: dict) -> list[dict]:
    """Artistas escuchados en 6+ meses distintos (lealtad)."""
    rows = conn.execute(f'''
        SELECT artist_id,
               COUNT(DISTINCT strftime('%Y-%m', datetime(timestamp, 'unixepoch'))) AS months
        FROM {tbl}
        GROUP BY artist_id
        HAVING months >= 6
        ORDER BY months DESC
        LIMIT 20
    ''').fetchall()

    core = []
    for r in rows:
        artist_row = conn.execute(
            'SELECT name FROM artists WHERE id = ?', (r['artist_id'],)
        ).fetchone()
        if artist_row:
            core.append({
                'artist_id':      r['artist_id'],
                'name':           artist_row['name'],
                'loyalty_months': r['months'],
                'total_scrobbles': artist_counts.get(r['artist_id'], 0),
            })
    return core


def _recent_discoveries(conn, user_id: int, artist_counts: dict) -> list[dict]:
    """Artistas descubiertos en los últimos 90 días."""
    since = int(time.time()) - 90 * 86400
    rows  = conn.execute('''
        SELECT uf.artist_id, uf.first_timestamp, a.name
        FROM user_first_artist_listen uf
        JOIN artists a ON a.id = uf.artist_id
        WHERE uf.user_id = ? AND uf.first_timestamp >= ?
        ORDER BY uf.first_timestamp DESC
        LIMIT 20
    ''', (user_id, since)).fetchall()

    return [
        {
            'artist_id':     r['artist_id'],
            'name':          r['name'],
            'first_listen':  datetime.fromtimestamp(r['first_timestamp']).strftime('%Y-%m-%d'),
            'scrobbles_since': artist_counts.get(r['artist_id'], 0),
        }
        for r in rows
    ]


def _find_twin(username: str, context: dict) -> tuple[str | None, float]:
    sims = context['user_similarity'].get(username, {})
    others = [(u, s) for u, s in sims.items() if u != username]
    if not others:
        return None, 0.0
    twin, sim = max(others, key=lambda x: x[1])
    return twin, sim
