"""
Motor 27 — Rating Curator.
Detecta correlación entre ratings de crítica y scrobbles del target,
y recomienda artistas bien valorados en géneros compatibles.
"""
import math
from collections import defaultdict
from .base import RecommendationEngine, EngineResult
from scripts.utils.constants import GENRE_MIN_WEIGHT


class RatingCuratorEngine(RecommendationEngine):
    """
    Motor 27 — Ratings como Curador.
    Analiza si el target tiende a escuchar artistas bien valorados
    (Scaruffi, AOTY, Metacritic) y recomienda en esa dirección.
    """
    engine_id   = 'rating_curator'
    engine_name = 'Ratings como Curador'

    def generate(self) -> list[EngineResult]:
        # Calcular correlación entre ratings y scrobbles del target
        rating_correlation = self._compute_rating_correlation()
        if abs(rating_correlation) < 0.1:
            return []   # no hay correlación significativa

        # Géneros del target
        target_genres = self._target_genre_scores()
        if not target_genres:
            return []

        top_genres = {g for g, _ in sorted(target_genres.items(), key=lambda x: x[1], reverse=True)[:15]}
        candidates = self.candidates()
        results    = []

        # Artistas candidatos con buenos ratings y géneros compatibles
        rated_artists = self.conn.execute('''
            SELECT DISTINCT a.artist_id,
                   MAX(COALESCE(al.aoty_critic_score, al.aoty_user_score, al.metacritic_score)) AS best_rating
            FROM albums al
            JOIN artists a ON a.id = al.artist_id
            WHERE COALESCE(al.aoty_critic_score, al.aoty_user_score, al.metacritic_score, 0) >= 70
            GROUP BY a.artist_id
        ''').fetchall()

        for row in rated_artists:
            artist_id  = row['artist_id']
            best_rating = row['best_rating'] or 0

            if artist_id not in candidates:
                continue

            artist_genres = {
                g for g, w in self.ctx['artist_genres'].get(artist_id, [])
                if w >= GENRE_MIN_WEIGHT
            }
            genre_match = len(artist_genres & top_genres)
            if genre_match == 0 and top_genres:
                continue

            rating_factor = (best_rating - 70) / 30  # 0.0 a 1.0 para ratings 70-100
            score = rating_factor * (1 + genre_match * 0.2) * abs(rating_correlation)

            # Determinar qué fuente de rating es más relevante para este target
            rating_source = self._rating_source(best_rating)

            results.append(EngineResult(
                artist_id=artist_id,
                score=score,
                explanation=(
                    f"Tus artistas favoritos coinciden con valoraciones de crítica alta. "
                    f"{rating_source} le da un {best_rating}/100 a este artista."
                ),
                metadata={
                    'best_rating':       best_rating,
                    'genre_match':       genre_match,
                    'correlation':       round(rating_correlation, 2),
                },
            ))

        return results

    def _compute_rating_correlation(self) -> float:
        """
        Correlación de Pearson simplificada entre scrobbles del target
        y rating de sus álbumes más escuchados.
        """
        album_counts = self.ctx.get('user_album_counts', {}).get(self.target_username, {})
        if len(album_counts) < 5:
            return 0.0

        pairs = []
        for album_id, cnt in list(album_counts.items())[:200]:
            row = self.conn.execute(
                'SELECT COALESCE(aoty_critic_score, aoty_user_score, metacritic_score) AS rating '
                'FROM albums WHERE id = ?', (album_id,)
            ).fetchone()
            if row and row['rating']:
                pairs.append((math.log1p(cnt), row['rating']))

        if len(pairs) < 5:
            return 0.0

        n      = len(pairs)
        xs     = [p[0] for p in pairs]
        ys     = [p[1] for p in pairs]
        x_mean = sum(xs) / n
        y_mean = sum(ys) / n
        cov    = sum((x - x_mean) * (y - y_mean) for x, y in pairs)
        std_x  = math.sqrt(sum((x - x_mean) ** 2 for x in xs) + 1e-9)
        std_y  = math.sqrt(sum((y - y_mean) ** 2 for y in ys) + 1e-9)
        return cov / (std_x * std_y)

    def _target_genre_scores(self) -> dict[str, float]:
        scores: dict[str, float] = defaultdict(float)
        for artist_id, cnt in self.target_artist_counts.items():
            for genre, weight in self.ctx['artist_genres'].get(artist_id, []):
                scores[genre] += cnt * weight
        return scores

    @staticmethod
    def _rating_source(score: int) -> str:
        if score >= 85:
            return "La crítica"
        if score >= 75:
            return "AOTY"
        return "Metacritic"
