"""
Motor 08 — Profundización de Discografía.
Recomienda álbumes de artistas que el target YA escucha,
pero cuyos álbumes no ha tocado y los amigos escuchan mucho.
"""
import math
from collections import defaultdict
from .base import RecommendationEngine, EngineResult


class DeepDiscographyEngine(RecommendationEngine):
    """
    Motor 08 — Profundización de Discografía.
    No recomienda artistas nuevos: recomienda álbumes inexplorados
    de artistas que el target ya conoce. El resultado se incluye en
    recommendations como artistas conocidos con recomendación de álbum específico.

    Para integrar esto en el sistema de scoring, cada artista conocido
    genera un candidato con el álbum recomendado en metadata.
    Se usa un artist_id "virtual" real pero con explanation específico.
    """
    engine_id   = 'deep_discography'
    engine_name = 'Profundización de Discografía'

    def generate(self) -> list[EngineResult]:
        # Álbumes que el target ya ha escuchado
        target_albums = set(self.ctx.get('target_album_counts', {}).get(self.target_username, {}).keys())

        # Artistas que el target escucha bastante (top 50)
        top_target_artists = sorted(
            self.target_artist_counts.items(),
            key=lambda x: x[1], reverse=True
        )[:50]

        results = []

        for artist_id, target_cnt in top_target_artists:
            # Álbumes del artista que el target NO ha tocado
            untouched = self.conn.execute('''
                SELECT id, name, year, cover_url,
                       COALESCE(aoty_critic_score, aoty_user_score, metacritic_score, 50) AS rating
                FROM albums
                WHERE artist_id = ? AND album_type IN ('Album', 'album')
            ''', (artist_id,)).fetchall()

            untouched_ids = [r['id'] for r in untouched if r['id'] not in target_albums]
            if not untouched_ids:
                continue

            # Scrobbles de los amigos en esos álbumes
            best_album_id    = None
            best_album_score = 0.0
            best_album_info  = None

            for album_row in untouched:
                album_id = album_row['id']
                if album_id in target_albums:
                    continue

                friend_scrobbles = 0
                for friend, _ in self.other_users():
                    friend_album_counts = self.ctx.get('user_album_counts', {}).get(friend, {})
                    friend_scrobbles   += friend_album_counts.get(album_id, 0)

                album_score = math.log1p(friend_scrobbles) * (album_row['rating'] / 100 + 0.5)

                if album_score > best_album_score:
                    best_album_score = album_score
                    best_album_id    = album_id
                    best_album_info  = dict(album_row)

            if best_album_id and best_album_score > 0:
                # Score inverso al target_cnt: más importante si el target lo escucha bastante
                score = best_album_score * math.log1p(target_cnt) * 0.5

                results.append(EngineResult(
                    artist_id=artist_id,
                    score=score,
                    explanation=(
                        f"Ya escuchas a este artista pero no has tocado "
                        f"«{best_album_info['name']}» ({best_album_info.get('year', '?')}), "
                        f"muy escuchado por tus amigos."
                    ),
                    metadata={
                        'recommended_album': {
                            'id':     best_album_info['id'],
                            'name':   best_album_info['name'],
                            'year':   best_album_info.get('year'),
                            'cover':  best_album_info.get('cover_url'),
                            'reason': 'Álbum favorito de tus amigos que no has explorado',
                        }
                    },
                ))

        return results
