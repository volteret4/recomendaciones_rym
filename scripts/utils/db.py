import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / 'lastfm_cache_rym_new_normalized.db'


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA cache_size=-65536')   # 64 MB cache
    conn.execute('PRAGMA temp_store=MEMORY')
    return conn


def get_all_users(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    """Devuelve [(user_id, username), ...]."""
    return [
        (r['id'], r['username'])
        for r in conn.execute('SELECT id, username FROM users ORDER BY id')
    ]


def scrobble_table(username: str) -> str:
    # Las tablas son siempre lowercase aunque el username tenga capitalización mixta
    return f'scrobbles_{username.lower()}'


def get_user_artist_counts(conn: sqlite3.Connection, username: str) -> dict[int, int]:
    """Devuelve {artist_id: nº_scrobbles} para un usuario."""
    tbl = scrobble_table(username)
    rows = conn.execute(
        f'SELECT artist_id, COUNT(*) AS cnt FROM {tbl} GROUP BY artist_id'
    ).fetchall()
    return {r['artist_id']: r['cnt'] for r in rows}


def get_user_album_counts(conn: sqlite3.Connection, username: str) -> dict[int, int]:
    """Devuelve {album_id: nº_scrobbles} (excluye NULL album_id)."""
    tbl = scrobble_table(username)
    rows = conn.execute(
        f'SELECT album_id, COUNT(*) AS cnt FROM {tbl} WHERE album_id IS NOT NULL GROUP BY album_id'
    ).fetchall()
    return {r['album_id']: r['cnt'] for r in rows}


def get_user_id(conn: sqlite3.Connection, username: str) -> int | None:
    row = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
    return row['id'] if row else None


def get_artist_info(conn: sqlite3.Connection, artist_id: int) -> dict | None:
    row = conn.execute('SELECT * FROM artists WHERE id = ?', (artist_id,)).fetchone()
    return dict(row) if row else None


def get_artist_genres_bulk(conn: sqlite3.Connection) -> dict[int, list[tuple[str, float]]]:
    """
    Carga géneros de todos los artistas de una vez.
    Devuelve {artist_id: [(genre_name, weight), ...]} ordenado por weight desc.
    """
    rows = conn.execute('''
        SELECT ag.artist_id, g.name, ag.weight
        FROM artist_genres ag
        JOIN genres g ON g.id = ag.genre_id
        ORDER BY ag.artist_id, ag.weight DESC
    ''').fetchall()

    result: dict[int, list[tuple[str, float]]] = {}
    for r in rows:
        result.setdefault(r['artist_id'], []).append((r['name'], r['weight']))
    return result


def get_recent_scrobbles(conn: sqlite3.Connection, username: str, since_ts: int) -> list[dict]:
    """Scrobbles más recientes que since_ts."""
    tbl = scrobble_table(username)
    rows = conn.execute(
        f'SELECT artist_id, timestamp FROM {tbl} WHERE timestamp >= ? ORDER BY timestamp',
        (since_ts,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_best_album_for_artist(conn: sqlite3.Connection, artist_id: int) -> dict | None:
    """Álbum del artista con mejor rating combinado (o más conocido)."""
    row = conn.execute('''
        SELECT id, name, year, cover_url,
               COALESCE(aoty_critic_score, aoty_user_score, metacritic_score, 0) AS rating
        FROM albums
        WHERE artist_id = ? AND album_type IN ('Album', 'album', NULL)
        ORDER BY rating DESC, year ASC
        LIMIT 1
    ''', (artist_id,)).fetchone()
    return dict(row) if row else None
