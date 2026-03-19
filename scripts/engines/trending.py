"""
Motor 04 — Trending en el Grupo.
Detecta artistas con spike de scrobbles recientes en amigos.
"""
import math
import time
from collections import defaultdict
from .base import RecommendationEngine, EngineResult
from scripts.utils.constants import TRENDING_WINDOW_SECS


class TrendingGroupEngine(RecommendationEngine):
    """
    Motor 04 — Trending en el Grupo.
    Un artista es trending si un amigo lo escucha mucho más en las últimas
    4 semanas que en su media histórica, y el target no lo conoce.
    """
    engine_id   = 'trending_group'
    engine_name = 'Trending en el Grupo'

    def generate(self) -> list[EngineResult]:
        now         = int(time.time())
        recent_ts   = now - TRENDING_WINDOW_SECS
        candidates  = self.candidates()

        # Para cada artista candidato, medir spike por usuario
        artist_spikes: dict[int, list[tuple[str, float, int, int]]] = defaultdict(list)
        # [artist_id] = [(friend, spike_ratio, recent_cnt, historical_avg_weekly)]

        for _, friend in self.ctx['users']:
            if friend == self.target_username:
                continue

            tbl          = f'scrobbles_{friend.lower()}'
            total_counts = self.ctx['user_artists'].get(friend, {})

            # Scrobbles recientes de este amigo
            recent_rows = self.conn.execute(
                f'SELECT artist_id, COUNT(*) as cnt FROM {tbl} '
                f'WHERE timestamp >= ? GROUP BY artist_id',
                (recent_ts,)
            ).fetchall()
            recent_counts = {r['artist_id']: r['cnt'] for r in recent_rows}

            # Calcular antigüedad del historial (en semanas)
            oldest = self.conn.execute(
                f'SELECT MIN(timestamp) AS ts FROM {tbl}'
            ).fetchone()
            oldest_ts   = oldest['ts'] if oldest and oldest['ts'] else recent_ts
            total_weeks = max((now - oldest_ts) / (7 * 24 * 3600), 1.0)

            for artist_id, recent_cnt in recent_counts.items():
                if artist_id not in candidates:
                    continue
                historical_total = total_counts.get(artist_id, 0)
                weekly_avg       = historical_total / total_weeks
                recent_weekly    = recent_cnt / (TRENDING_WINDOW_SECS / (7 * 24 * 3600))

                if weekly_avg < 0.5:
                    spike_ratio = recent_cnt  # artista nuevo para el amigo
                else:
                    spike_ratio = recent_weekly / weekly_avg

                if spike_ratio >= 2.0:  # al menos el doble de la media
                    artist_spikes[artist_id].append((
                        friend, spike_ratio, recent_cnt, round(weekly_avg)
                    ))

        results = []
        for artist_id, spikes in artist_spikes.items():
            best = max(spikes, key=lambda x: x[1])
            friend, spike_ratio, recent_cnt, hist_avg = best
            score = math.log1p(spike_ratio) * math.log1p(len(spikes))

            results.append(EngineResult(
                artist_id=artist_id,
                score=score,
                explanation=(
                    f"{friend} está obsesionado últimamente: {recent_cnt} scrobbles "
                    f"en las últimas 4 semanas (×{spike_ratio:.1f} su media habitual)."
                ),
                metadata={
                    'spike_friends': [
                        {'username': f, 'spike': round(s, 1), 'recent': rc}
                        for f, s, rc, _ in spikes[:3]
                    ]
                },
            ))

        return results
