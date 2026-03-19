"""
Motores de sello y productor (Bloque C):
  - label_curator    (Motor 18)
  - shared_producers (Motor 19)
"""
import math
import json
from collections import defaultdict
from .base import RecommendationEngine, EngineResult


class LabelCuratorEngine(RecommendationEngine):
    """
    Motor 18 — Sello Discográfico.
    Calcula afinidad con sellos a partir de scrobbles de álbumes,
    y recomienda artistas desconocidos del mismo sello.
    """
    engine_id   = 'label_curator'
    engine_name = 'Curador de Sello Discográfico'

    def generate(self) -> list[EngineResult]:
        # Scrobbles del target por sello
        label_scores: dict[str, float] = defaultdict(float)
        label_artist_ids: dict[str, set[int]] = defaultdict(set)

        album_counts = self.ctx.get('user_album_counts', {}).get(self.target_username, {})
        for album_id, cnt in album_counts.items():
            row = self.conn.execute(
                'SELECT label, artist_id FROM albums WHERE id = ?', (album_id,)
            ).fetchone()
            if row and row['label']:
                label_scores[row['label']] += math.log1p(cnt)
                label_artist_ids[row['label']].add(row['artist_id'])

        if not label_scores:
            return []

        # Top sellos del target (score normalizado)
        total_score = sum(label_scores.values())
        top_labels  = sorted(label_scores.items(), key=lambda x: x[1], reverse=True)[:10]

        candidates = self.candidates()
        results: dict[int, EngineResult] = {}

        for label, label_score in top_labels:
            label_affinity = label_score / total_score
            if label_affinity < 0.02:
                continue

            known_from_label = label_artist_ids[label]
            n_known          = len(known_from_label)

            # Artistas del sello que el target NO conoce
            other_artists = self.conn.execute(
                'SELECT DISTINCT artist_id FROM albums WHERE label = ?', (label,)
            ).fetchall()

            for row in other_artists:
                artist_id = row['artist_id']
                if artist_id not in candidates or artist_id in known_from_label:
                    continue

                score = label_affinity * math.log1p(n_known)

                if artist_id not in results or score > results[artist_id].score:
                    results[artist_id] = EngineResult(
                        artist_id=artist_id,
                        score=score,
                        explanation=(
                            f"Escuchas {n_known} artista(s) del sello {label}. "
                            f"Este es otro artista del mismo sello."
                        ),
                        metadata={'label': label, 'known_from_label': n_known},
                    )

        return list(results.values())


class SharedProducersEngine(RecommendationEngine):
    """
    Motor 19 — Productores Compartidos.
    Si te gustan álbumes de un productor, recomienda otros álbumes que produjo.
    """
    engine_id   = 'shared_producers'
    engine_name = 'Productores Compartidos'

    def generate(self) -> list[EngineResult]:
        # Scrobbles del target por productor
        producer_scores: dict[str, float] = defaultdict(float)
        producer_artist_ids: dict[str, set[int]] = defaultdict(set)

        album_counts = self.ctx.get('user_album_counts', {}).get(self.target_username, {})
        for album_id, cnt in album_counts.items():
            meta = self.conn.execute(
                'SELECT producers FROM album_metadata WHERE album_id = ?', (album_id,)
            ).fetchone()
            if not meta or not meta['producers']:
                continue

            producers = self._parse_producers(meta['producers'])
            album_row = self.conn.execute(
                'SELECT artist_id FROM albums WHERE id = ?', (album_id,)
            ).fetchone()
            if not album_row:
                continue

            for producer in producers:
                if not producer:
                    continue
                producer_scores[producer] += math.log1p(cnt)
                producer_artist_ids[producer].add(album_row['artist_id'])

        if not producer_scores:
            return []

        total   = sum(producer_scores.values())
        top_prod = sorted(producer_scores.items(), key=lambda x: x[1], reverse=True)[:8]
        candidates = self.candidates()
        results: dict[int, EngineResult] = {}

        for producer, prod_score in top_prod:
            affinity  = prod_score / total
            if affinity < 0.03:
                continue
            known_ids = producer_artist_ids[producer]
            n_known   = len(known_ids)
            if n_known < 2:
                continue  # al menos 2 artistas conocidos del productor

            # Otros álbumes de ese productor
            prod_albums = self.conn.execute('''
                SELECT a.id, a.artist_id FROM albums a
                JOIN album_metadata m ON m.album_id = a.id
                WHERE m.producers LIKE ?
            ''', (f'%{producer}%',)).fetchall()

            for album_row in prod_albums:
                artist_id = album_row['artist_id']
                if artist_id not in candidates or artist_id in known_ids:
                    continue

                score = affinity * math.log1p(n_known)
                if artist_id not in results or score > results[artist_id].score:
                    results[artist_id] = EngineResult(
                        artist_id=artist_id,
                        score=score,
                        explanation=(
                            f"Te gustan {n_known} álbumes producidos por {producer}. "
                            f"Este artista también fue producido por él/ella."
                        ),
                        metadata={'producer': producer, 'known_albums': n_known},
                    )

        return list(results.values())

    @staticmethod
    def _parse_producers(raw: str) -> list[str]:
        """Intenta parsear producers como JSON array o string simple."""
        if not raw:
            return []
        raw = raw.strip()
        if raw.startswith('['):
            try:
                return [p.strip() for p in json.loads(raw) if isinstance(p, str)]
            except json.JSONDecodeError:
                pass
        return [p.strip() for p in raw.split(',') if p.strip()]
