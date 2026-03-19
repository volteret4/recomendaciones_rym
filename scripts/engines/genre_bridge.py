"""
Motores de género (Bloque A/E):
  - genre_bridge     (Motor 02)
  - decade_explorer  (Motor 29)
  - country_affinity (Motor 30)
"""
import math
from collections import defaultdict
from .base import RecommendationEngine, EngineResult
from scripts.utils.constants import GENRE_MIN_WEIGHT


class GenreBridgeEngine(RecommendationEngine):
    """
    Motor 02 — Puente de Géneros Adyacentes.
    Busca géneros que un amigo escucha mucho pero target apenas toca,
    y recomienda los artistas top de ese amigo en esos géneros.
    """
    engine_id   = 'genre_bridge'
    engine_name = 'Puente de Géneros Adyacentes'

    def generate(self) -> list[EngineResult]:
        target_genre_scores = self._user_genre_scores(self.target_username)
        candidates          = self.candidates()
        scores: dict[int, list[tuple[float, str]]] = defaultdict(list)

        for friend, sim in self.other_users():
            if sim < 0.05:
                continue

            friend_genre_scores = self._user_genre_scores(friend)

            # Géneros "adyacentes": el amigo escucha mucho, target muy poco
            adjacent: list[tuple[str, float]] = []
            for genre, friend_score in friend_genre_scores.items():
                target_score = target_genre_scores.get(genre, 0.0)
                if friend_score > 0 and target_score / max(friend_score, 1e-9) < 0.15:
                    adjacent.append((genre, friend_score))

            if not adjacent:
                continue

            adj_genres = {g for g, _ in adjacent}

            # Artistas del amigo que pertenecen a géneros adyacentes
            friend_counts = self.ctx['user_artists'].get(friend, {})
            for artist_id, cnt in friend_counts.items():
                if artist_id not in candidates:
                    continue
                artist_gens = {
                    g for g, w in self.ctx['artist_genres'].get(artist_id, [])
                    if w >= GENRE_MIN_WEIGHT
                }
                overlap = artist_gens & adj_genres
                if not overlap:
                    continue

                score = sim * math.log1p(cnt) * len(overlap)
                genre_str = ', '.join(list(overlap)[:2])
                scores[artist_id].append((
                    score,
                    f"Tú y {friend} compartís gustos similares. "
                    f"Él también escucha mucho {genre_str} y este artista es uno de sus favoritos.",
                ))

        results = []
        for artist_id, entries in scores.items():
            best_score, best_expl = max(entries, key=lambda x: x[0])
            total_score = sum(s for s, _ in entries)
            results.append(EngineResult(
                artist_id=artist_id,
                score=total_score,
                explanation=best_expl,
            ))
        return results

    def _user_genre_scores(self, username: str) -> dict[str, float]:
        """Puntuación por género = sum(scrobbles * genre_weight)."""
        genre_scores: dict[str, float] = defaultdict(float)
        for artist_id, cnt in self.ctx['user_artists'].get(username, {}).items():
            for genre, weight in self.ctx['artist_genres'].get(artist_id, []):
                genre_scores[genre] += cnt * weight
        return genre_scores


class DecadeExplorerEngine(RecommendationEngine):
    """
    Motor 29 — Exploración por Década.
    Calcula la distribución de escuchas por década y recomienda artistas
    de las décadas preferidas que el target no conoce.
    """
    engine_id   = 'decade_explorer'
    engine_name = 'Exploración por Década'

    def generate(self) -> list[EngineResult]:
        # Calcular preferencia de décadas del target
        decade_scores: dict[str, float] = defaultdict(float)
        for artist_id, cnt in self.target_artist_counts.items():
            decade = self._artist_decade(artist_id)
            if decade:
                decade_scores[decade] += cnt

        if not decade_scores:
            return []

        top_decades = sorted(decade_scores.items(), key=lambda x: x[1], reverse=True)
        top_3 = {d for d, _ in top_decades[:3]}
        total = sum(decade_scores.values())

        candidates = self.candidates()
        results    = []

        group_artist_totals: dict[int, int] = {}
        for counts in self.ctx['user_artists'].values():
            for aid, cnt in counts.items():
                group_artist_totals[aid] = group_artist_totals.get(aid, 0) + cnt

        for artist_id in candidates:
            decade = self._artist_decade(artist_id)
            if decade not in top_3:
                continue
            pref_score = decade_scores.get(decade, 0) / total
            group_cnt  = group_artist_totals.get(artist_id, 0)
            results.append(EngineResult(
                artist_id=artist_id,
                score=pref_score * math.log1p(group_cnt),
                explanation=(
                    f"El {pref_score:.0%} de tus escuchas son de artistas de los {decade}. "
                    f"Este es de esa época."
                ),
                metadata={'decade': decade, 'preference': round(pref_score, 3)},
            ))

        return results

    def _artist_decade(self, artist_id: int) -> str | None:
        """Obtiene la década del artista a partir de formed_year."""
        # Se cachea en contexto para eficiencia
        if 'artist_decade_cache' not in self.ctx:
            self.ctx['artist_decade_cache'] = {}
        cache = self.ctx['artist_decade_cache']

        if artist_id not in cache:
            row = self.conn.execute(
                'SELECT formed_year FROM artists WHERE id = ?', (artist_id,)
            ).fetchone()
            year = row['formed_year'] if row and row['formed_year'] else None
            cache[artist_id] = f"{(year // 10) * 10}s" if year else None

        return cache[artist_id]


class CountryAffinityEngine(RecommendationEngine):
    """
    Motor 30 — País de Origen.
    Detecta afinidades geográficas implícitas y recomienda más artistas del mismo país.
    """
    engine_id   = 'country_affinity'
    engine_name = 'Afinidad por País'

    def generate(self) -> list[EngineResult]:
        # Distribución de escuchas por país para el target
        country_scores: dict[str, float] = defaultdict(float)
        for artist_id, cnt in self.target_artist_counts.items():
            country = self._artist_country(artist_id)
            if country:
                country_scores[country] += cnt

        if not country_scores:
            return []

        total     = sum(country_scores.values())
        top_countries = {
            c for c, s in country_scores.items()
            if s / total >= 0.05   # al menos 5% de escuchas
        }

        candidates = self.candidates()
        results    = []

        # Scrobbles totales del grupo por artista (para diferenciar candidatos del mismo país)
        group_artist_totals: dict[int, int] = {}
        for counts in self.ctx['user_artists'].values():
            for aid, cnt in counts.items():
                group_artist_totals[aid] = group_artist_totals.get(aid, 0) + cnt

        for artist_id in candidates:
            country = self._artist_country(artist_id)
            if country not in top_countries:
                continue
            ratio       = country_scores[country] / total
            group_cnt   = group_artist_totals.get(artist_id, 0)
            score       = ratio * math.log1p(group_cnt)
            results.append(EngineResult(
                artist_id=artist_id,
                score=score,
                explanation=(
                    f"El {ratio:.0%} de tus escuchas son de artistas de {country}. "
                    f"Este también es de allí."
                ),
                metadata={'country': country, 'preference': round(ratio, 3)},
            ))

        return results

    def _artist_country(self, artist_id: int) -> str | None:
        if 'artist_country_cache' not in self.ctx:
            self.ctx['artist_country_cache'] = {}
        cache = self.ctx['artist_country_cache']
        if artist_id not in cache:
            row = self.conn.execute(
                'SELECT country FROM artists WHERE id = ?', (artist_id,)
            ).fetchone()
            cache[artist_id] = row['country'] if row and row['country'] else None
        return cache[artist_id]
