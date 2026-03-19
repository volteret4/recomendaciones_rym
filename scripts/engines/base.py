import sqlite3
from dataclasses import dataclass, field


@dataclass
class EngineResult:
    artist_id: int
    score: float           # score bruto; se normaliza después
    explanation: str
    metadata: dict = field(default_factory=dict)


class RecommendationEngine:
    """
    Clase base para todos los motores de recomendación.

    `context` es un dict compartido con datos pre-calculados:
      - user_artists:    {username: {artist_id: scrobble_count}}
      - user_similarity: {username: {other_username: similarity_score}}
      - artist_genres:   {artist_id: [(genre_name, weight), ...]}
      - users:           [(user_id, username), ...]
    """

    engine_id:   str = ''
    engine_name: str = ''

    def __init__(
        self,
        conn: sqlite3.Connection,
        target_username: str,
        target_user_id: int,
        context: dict,
    ):
        self.conn             = conn
        self.target_username  = target_username
        self.target_user_id   = target_user_id
        self.ctx              = context

    # ── Helpers de uso frecuente ──────────────────────────────

    @property
    def target_artist_counts(self) -> dict[int, int]:
        return self.ctx['user_artists'].get(self.target_username, {})

    @property
    def target_artists(self) -> set[int]:
        return set(self.target_artist_counts.keys())

    def other_users(self) -> list[tuple[str, float]]:
        """Devuelve [(username, similarity), ...] con el resto de usuarios, ordenados por sim."""
        sims = self.ctx['user_similarity'].get(self.target_username, {})
        return sorted(
            [(u, s) for u, s in sims.items() if u != self.target_username],
            key=lambda x: x[1],
            reverse=True,
        )

    def candidates(self, exclude_known: bool = True) -> set[int]:
        """
        Todos los artistas del grupo que el target no conoce
        (o apenas conoce si exclude_known=True).
        """
        from scripts.utils.constants import MAX_KNOWN_SCROBBLES
        all_group = set()
        for counts in self.ctx['user_artists'].values():
            all_group |= set(counts.keys())

        if exclude_known:
            known = {
                aid for aid, cnt in self.target_artist_counts.items()
                if cnt > MAX_KNOWN_SCROBBLES
            }
            return all_group - known
        return all_group

    # ── Método principal ──────────────────────────────────────

    def generate(self) -> list[EngineResult]:
        raise NotImplementedError

    def run(self) -> dict[int, dict]:
        """
        Ejecuta el motor y devuelve {artist_id: {'score': float, 'explanation': str}}.
        Captura excepciones para no romper el pipeline.
        """
        try:
            results = self.generate()
            return {
                r.artist_id: {
                    'score':       r.score,
                    'explanation': r.explanation,
                    'metadata':    r.metadata,
                }
                for r in results
                if r.score > 0
            }
        except Exception as e:
            print(f'  [ERROR] Motor {self.engine_id} falló: {e}')
            return {}
