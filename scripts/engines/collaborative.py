"""
Motores colaborativos (Bloque A):
  - collab_direct    (Motor 01)
  - musical_twin     (Motor 05)
  - anti_bubble      (Motor 06)
  - group_consensus  (Motor 10)
"""
import math
from .base import RecommendationEngine, EngineResult
from scripts.utils.constants import GROUP_CONSENSUS_MIN_USERS, GENRE_MIN_WEIGHT


class CollabDirectEngine(RecommendationEngine):
    """
    Motor 01 — Collaborative Filtering Directo.
    Recomienda artistas que escuchan los amigos pero el target no.
    Pondera por similitud con el amigo e intensidad de escucha.
    """
    engine_id   = 'collab_direct'
    engine_name = 'Collaborative Filtering Directo'

    def generate(self) -> list[EngineResult]:
        target_set    = self.target_artists
        candidates    = self.candidates()
        friend_counts: dict[int, list[tuple[str, float, int]]] = {}
        # friend_counts[artist_id] = [(friend_username, similarity, friend_scrobbles), ...]

        for friend, sim in self.other_users():
            if sim < 0.01:
                continue
            friend_artists = self.ctx['user_artists'].get(friend, {})
            for artist_id, cnt in friend_artists.items():
                if artist_id not in candidates:
                    continue
                friend_counts.setdefault(artist_id, []).append((friend, sim, cnt))

        results = []
        for artist_id, friend_data in friend_counts.items():
            n_friends  = len(friend_data)
            # score = sum(sim * log(scrobbles)) normalizado por número de amigos
            raw_score  = sum(sim * math.log1p(cnt) for _, sim, cnt in friend_data)
            raw_score *= math.log1p(n_friends)  # bonus por múltiples amigos

            top_friends = sorted(friend_data, key=lambda x: x[1] * math.log1p(x[2]), reverse=True)
            best_friend, best_sim, best_cnt = top_friends[0]

            explanation = (
                f"Lo escuchan {n_friends} amigo(s). "
                f"{best_friend} tiene {best_cnt} scrobbles y es tu perfil más similar "
                f"({best_sim:.0%} compatibilidad)."
            )
            results.append(EngineResult(
                artist_id=artist_id,
                score=raw_score,
                explanation=explanation,
                metadata={'friends': [{'username': f, 'scrobbles': c} for f, _, c in top_friends[:5]]},
            ))

        return results


class MusicalTwinEngine(RecommendationEngine):
    """
    Motor 05 — Gemelo Musical.
    Encuentra el usuario más similar y recomienda su catálogo.
    """
    engine_id   = 'musical_twin'
    engine_name = 'Gemelo Musical'

    def generate(self) -> list[EngineResult]:
        others    = self.other_users()
        if not others:
            return []

        twin, twin_sim = others[0]
        candidates    = self.candidates()
        twin_artists  = self.ctx['user_artists'].get(twin, {})

        results = []
        for artist_id, cnt in twin_artists.items():
            if artist_id not in candidates:
                continue
            score = twin_sim * math.log1p(cnt)
            results.append(EngineResult(
                artist_id=artist_id,
                score=score,
                explanation=(
                    f"Tu gemelo musical es {twin} ({twin_sim:.0%} compatibilidad). "
                    f"Tiene {cnt} scrobbles de este artista."
                ),
                metadata={'twin': twin, 'twin_similarity': round(twin_sim, 3)},
            ))

        return results


class AntiBubbleEngine(RecommendationEngine):
    """
    Motor 06 — Anti-burbuja.
    Artistas únicos de 1 solo miembro del grupo, compatibles en género con el target.
    """
    engine_id   = 'anti_bubble'
    engine_name = 'Anti-burbuja Grupal'

    def generate(self) -> list[EngineResult]:
        # Contar cuántos usuarios escuchan cada artista candidato
        all_artists: dict[int, list[tuple[str, int]]] = {}
        for username, counts in self.ctx['user_artists'].items():
            if username == self.target_username:
                continue
            for artist_id, cnt in counts.items():
                all_artists.setdefault(artist_id, []).append((username, cnt))

        # Sólo los que escucha exactamente 1 persona
        unique_artists = {
            aid: listeners[0]
            for aid, listeners in all_artists.items()
            if len(listeners) == 1
        }

        candidates  = self.candidates()
        target_gens = self._target_genre_set()

        results = []
        for artist_id, (owner, cnt) in unique_artists.items():
            if artist_id not in candidates:
                continue

            artist_gens = {
                g for g, w in self.ctx['artist_genres'].get(artist_id, [])
                if w >= GENRE_MIN_WEIGHT
            }
            genre_overlap = len(target_gens & artist_gens)
            if genre_overlap == 0 and target_gens:
                continue   # sin compatibilidad de género, saltamos

            score = math.log1p(cnt) * (1 + genre_overlap * 0.3)
            shared = ', '.join(list(target_gens & artist_gens)[:3])
            results.append(EngineResult(
                artist_id=artist_id,
                score=score,
                explanation=(
                    f"Solo {owner} escucha este artista en todo el grupo. "
                    f"Encaja con tu gusto: {shared or 'géneros afines'}."
                ),
                metadata={'unique_listener': owner, 'genre_overlap': genre_overlap},
            ))

        return results

    def _target_genre_set(self) -> set[str]:
        target_gens: dict[str, float] = {}
        for artist_id, cnt in self.target_artist_counts.items():
            for genre, weight in self.ctx['artist_genres'].get(artist_id, []):
                target_gens[genre] = target_gens.get(genre, 0) + weight * math.log1p(cnt)
        # Top géneros del target
        top = sorted(target_gens.items(), key=lambda x: x[1], reverse=True)[:20]
        return {g for g, _ in top}


class GroupConsensusEngine(RecommendationEngine):
    """
    Motor 10 — Consenso del Grupo.
    Artistas que escuchan 5+ de los 11 usuarios pero el target no.
    """
    engine_id   = 'group_consensus'
    engine_name = 'Consenso del Grupo'

    def generate(self) -> list[EngineResult]:
        all_users = [u for _, u in self.ctx['users']]
        n_users   = len(all_users)

        artist_listeners: dict[int, list[tuple[str, int]]] = {}
        for username, counts in self.ctx['user_artists'].items():
            if username == self.target_username:
                continue
            for artist_id, cnt in counts.items():
                artist_listeners.setdefault(artist_id, []).append((username, cnt))

        candidates = self.candidates()
        results    = []

        for artist_id, listeners in artist_listeners.items():
            if artist_id not in candidates:
                continue
            if len(listeners) < GROUP_CONSENSUS_MIN_USERS:
                continue

            avg_scrobbles = sum(c for _, c in listeners) / len(listeners)
            ratio         = len(listeners) / n_users
            score         = ratio * math.log1p(avg_scrobbles)

            names = ', '.join(u for u, _ in listeners[:4])
            results.append(EngineResult(
                artist_id=artist_id,
                score=score,
                explanation=(
                    f"{len(listeners)} de {n_users} del grupo lo escuchan: {names}…"
                ),
                metadata={
                    'listener_count': len(listeners),
                    'total_users':    n_users,
                    'avg_scrobbles':  round(avg_scrobbles),
                    'friends':        [{'username': u, 'scrobbles': c} for u, c in listeners[:5]],
                },
            ))

        return results
