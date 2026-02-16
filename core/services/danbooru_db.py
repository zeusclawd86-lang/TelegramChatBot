"""Mapper de tags Danbooru con búsqueda fuzzy contra una base SQLite local.

Carga ~80k tags reales de Danbooru en memoria al inicio y ofrece:
  - Búsqueda exacta (O(1) por set lookup)
  - Búsqueda fuzzy (rapidfuzz WRatio) con fallback a post_count como desempate
  - Mapeo batch de conceptos a tags reales
"""

import logging
import sqlite3
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz, process

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "danbooru_tags.db"

# Categorías de Danbooru
CAT_GENERAL = 0
CAT_ARTIST = 1
CAT_COPYRIGHT = 3
CAT_CHARACTER = 4
CAT_META = 5


class DanbooruTagMapper:
    """Mapea conceptos de texto libre a tags reales de Danbooru usando fuzzy matching."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self._names: list[str] = []
        self._name_set: set[str] = set()
        self._meta: dict[str, dict] = {}
        self._loaded = False

    @property
    def available(self) -> bool:
        """True si la base de datos existe y se puede cargar."""
        return self.db_path.exists()

    def _ensure_loaded(self) -> bool:
        """Carga los tags en memoria la primera vez. Retorna True si hay datos."""
        if self._loaded:
            return bool(self._names)

        self._loaded = True

        if not self.db_path.exists():
            logging.warning(f"Danbooru DB not found at {self.db_path}. Run: python scripts/build_danbooru_db.py")
            return False

        try:
            conn = sqlite3.connect(str(self.db_path))
            cur = conn.cursor()
            cur.execute("SELECT name, category, post_count FROM tags ORDER BY post_count DESC")
            rows = cur.fetchall()
            conn.close()

            self._names = [r[0] for r in rows]
            self._name_set = set(self._names)
            self._meta = {r[0]: {"category": r[1], "post_count": r[2]} for r in rows}

            logging.info(f"DanbooruTagMapper: {len(self._names):,} tags loaded from {self.db_path.name}")
            return True
        except Exception as e:
            logging.error(f"Error loading Danbooru DB: {e}")
            return False

    def normalize(self, text: str) -> str:
        """Normaliza un concepto para compararlo con tags Danbooru."""
        return text.lower().strip().replace(" ", "_")

    def exact_match(self, concept: str) -> Optional[str]:
        """Busca coincidencia exacta. Retorna el tag o None."""
        if not self._ensure_loaded():
            return None
        norm = self.normalize(concept)
        return norm if norm in self._name_set else None

    def fuzzy_match(
        self,
        concept: str,
        category: Optional[int] = None,
        limit: int = 3,
        threshold: int = 80,
    ) -> list[tuple[str, int]]:
        """Busca los tags más parecidos usando fuzzy matching.

        Args:
            concept: Texto a buscar (ej: "blonde hair", "sitting on bed").
            category: Filtrar por categoría Danbooru (0=general, 1=artist, etc.). None = todas.
            limit: Cantidad máxima de resultados.
            threshold: Puntaje mínimo (0-100) para considerar un match.

        Returns:
            Lista de (tag_name, score) ordenada por relevancia.
        """
        if not self._ensure_loaded():
            return []

        norm = self.normalize(concept)

        # Palabras prohibidas que suelen causar falsos positivos en Danbooru
        forbidden_words = {"ax", "axe", "king", "hilt", "sword", "weapon", "blade"}
        if norm in forbidden_words:
            return []

        # Exacta primero
        if norm in self._name_set:
            if category is None or self._meta[norm]["category"] == category:
                return [(norm, 100)]

        # Filtrar por categoría si se especifica
        if category is not None:
            candidates = [n for n in self._names if self._meta[n]["category"] == category]
        else:
            candidates = self._names

        if not candidates:
            return []

        results = process.extract(norm, candidates, scorer=fuzz.WRatio, limit=limit * 2)

        # Filtrar por threshold y desempatar por post_count
        filtered = []
        for tag_name, score, _idx in results:
            if score >= threshold:
                # Evitar que palabras cortas mapeen a armas
                if tag_name in forbidden_words:
                    continue
                filtered.append((tag_name, int(score)))

        # Si hay empates cercanos (dentro de 5 puntos), preferir el de mayor post_count
        filtered.sort(key=lambda x: (-x[1], -self._meta.get(x[0], {}).get("post_count", 0)))

        return filtered[:limit]

    def map_concept(self, concept: str, category: Optional[int] = None, threshold: int = 80) -> Optional[str]:
        """Mapea un concepto a su mejor tag Danbooru. Retorna None si no hay match."""
        matches = self.fuzzy_match(concept, category=category, limit=1, threshold=threshold)
        return matches[0][0] if matches else None

    def map_concepts(
        self,
        concepts: list[str],
        category: Optional[int] = None,
        threshold: int = 80,
    ) -> list[str]:
        """Mapea una lista de conceptos a tags Danbooru. Solo incluye los que tengan match."""
        mapped = []
        for concept in concepts:
            if not concept or not concept.strip():
                continue
            tag = self.map_concept(concept.strip(), category=category, threshold=threshold)
            if tag and tag not in mapped:
                mapped.append(tag)
        return mapped

    def get_tag_info(self, tag_name: str) -> Optional[dict]:
        """Retorna metadata de un tag (category, post_count)."""
        if not self._ensure_loaded():
            return None
        norm = self.normalize(tag_name)
        return self._meta.get(norm)
