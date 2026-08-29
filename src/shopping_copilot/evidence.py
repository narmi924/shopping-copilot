"""Read-only reverse index for exact catalog-derived requirement evidence."""

from __future__ import annotations

import math
import re
import sqlite3
import time
from dataclasses import dataclass

from .catalog import CatalogIndex
from .models import ProductRecord
from .text import normalize_evidence_key


MATERIAL_RE = re.compile(
    r"\b(cotton|polyester|nylon|leather|wool|spandex|silk|rayon|fabric)\b",
    re.IGNORECASE,
)
COLOR_RE = re.compile(
    r"\b(black|white|blue|red|pink|green|brown|gray|grey|purple|yellow|orange)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class EvidenceMatch:
    parent_asin: str
    score: float
    exact_matches: int
    sources: tuple[str, ...]
    collision_counts: tuple[int, ...]


def _searchable_text(product: ProductRecord) -> str:
    parts = [product.title]
    parts.extend(product.features)
    parts.extend(f"{key} {value}" for key, value in product.evidence_details)
    parts.extend(product.description)
    parts.extend(product.categories)
    if product.store:
        parts.append(product.store)
    return " ".join(parts).strip()


def product_evidence(product: ProductRecord) -> tuple[tuple[str, str], ...]:
    """Return normalized evidence/source pairs in deterministic catalog order."""

    values: list[tuple[str, str]] = []
    corpus = _searchable_text(product)
    material = MATERIAL_RE.search(corpus)
    color = COLOR_RE.search(corpus)
    if material:
        values.append((material.group(1).lower(), "material"))
    if color:
        values.append((f"color: {color.group(1).lower()}", "color"))
    values.extend((value, "feature") for value in product.features)
    values.extend((f"{key}: {value}", "detail") for key, value in product.evidence_details)
    if product.price_evidence is not None:
        values.append((f"budget around ${product.price_evidence}", "budget"))
    if not values:
        values.append((product.title or "product", "title_fallback"))
    normalized: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw_value, source in values:
        key = normalize_evidence_key(raw_value)
        pair = (key, source)
        if not key or pair in seen:
            continue
        seen.add(pair)
        normalized.append(pair)
    return tuple(normalized)


class EvidenceFingerprintIndex:
    """Exact evidence lookup backed by a compact in-memory SQLite index."""

    def __init__(self, catalog: CatalogIndex, *, maximum_postings_per_key: int = 5000) -> None:
        self.catalog = catalog
        self.maximum_postings_per_key = max(100, int(maximum_postings_per_key))
        self._connection = sqlite3.connect(":memory:", check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode = OFF")
        self._connection.execute("PRAGMA synchronous = OFF")
        self._connection.execute("PRAGMA temp_store = MEMORY")
        self._lookup_count = 0
        self._lookup_seconds = 0.0
        self._build_seconds = 0.0
        self._unique_keys = 0
        self._posting_count = 0
        self._collision_distribution: dict[str, float | int] = {}
        self._build()

    def _build(self) -> None:
        started = time.perf_counter()
        cursor = self._connection.cursor()
        cursor.execute(
            "CREATE TABLE evidence ("
            "key TEXT NOT NULL, parent_asin TEXT NOT NULL, source TEXT NOT NULL, "
            "PRIMARY KEY (key, parent_asin, source)) WITHOUT ROWID"
        )
        batch: list[tuple[str, str, str]] = []
        for product in self.catalog.iter_products():
            batch.extend(
                (key, product.parent_asin, source)
                for key, source in product_evidence(product)
            )
            if len(batch) >= 5000:
                cursor.executemany("INSERT OR IGNORE INTO evidence VALUES (?, ?, ?)", batch)
                batch.clear()
        if batch:
            cursor.executemany("INSERT OR IGNORE INTO evidence VALUES (?, ?, ?)", batch)
        self._connection.commit()
        counts = [
            int(row[0])
            for row in self._connection.execute(
                "SELECT COUNT(DISTINCT parent_asin) FROM evidence GROUP BY key ORDER BY 1"
            )
        ]
        self._unique_keys = len(counts)
        self._posting_count = int(
            self._connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
        )
        self._collision_distribution = {
            "minimum": counts[0] if counts else 0,
            "p50": counts[round((len(counts) - 1) * 0.50)] if counts else 0,
            "p95": counts[round((len(counts) - 1) * 0.95)] if counts else 0,
            "p99": counts[round((len(counts) - 1) * 0.99)] if counts else 0,
            "maximum": counts[-1] if counts else 0,
        }
        self._connection.execute("PRAGMA query_only = ON")
        self._build_seconds = time.perf_counter() - started

    @property
    def statistics(self) -> dict[str, object]:
        average_ms = 1000.0 * self._lookup_seconds / self._lookup_count if self._lookup_count else 0.0
        return {
            "build_seconds": round(self._build_seconds, 6),
            "unique_keys": self._unique_keys,
            "postings": self._posting_count,
            "collision_distribution": dict(self._collision_distribution),
            "lookup_count": self._lookup_count,
            "average_lookup_ms": round(average_ms, 6),
        }

    def collision_count(self, clause: object) -> int:
        key = normalize_evidence_key(clause)
        if not key:
            return 0
        row = self._connection.execute(
            "SELECT COUNT(DISTINCT parent_asin) FROM evidence WHERE key = ?",
            (key,),
        ).fetchone()
        return int(row[0]) if row else 0

    def lookup_exact(self, clause: object, *, limit: int | None = None) -> list[tuple[str, tuple[str, ...]]]:
        key = normalize_evidence_key(clause)
        if not key:
            return []
        safe_limit = self.maximum_postings_per_key if limit is None else max(0, int(limit))
        rows = self._connection.execute(
            "SELECT parent_asin, GROUP_CONCAT(source, ',') "
            "FROM evidence WHERE key = ? GROUP BY parent_asin ORDER BY parent_asin LIMIT ?",
            (key, safe_limit),
        ).fetchall()
        return [
            (str(identifier), tuple(sorted(set(str(sources).split(",")))))
            for identifier, sources in rows
        ]

    def lookup_intersection(
        self,
        clauses: tuple[object, ...],
        *,
        limit: int,
    ) -> list[tuple[str, tuple[str, ...]]]:
        """Return products matching every distinct evidence clause."""

        keys = tuple(
            dict.fromkeys(
                key
                for clause in clauses
                if (key := normalize_evidence_key(clause))
            )
        )
        if not keys or limit <= 0:
            return []
        placeholders = ", ".join("?" for _ in keys)
        rows = self._connection.execute(
            "SELECT parent_asin, GROUP_CONCAT(DISTINCT source) "
            f"FROM evidence WHERE key IN ({placeholders}) "
            "GROUP BY parent_asin HAVING COUNT(DISTINCT key) = ? "
            "ORDER BY parent_asin LIMIT ?",
            (*keys, len(keys), max(0, int(limit))),
        ).fetchall()
        return [
            (str(identifier), tuple(sorted(set(str(sources).split(",")))))
            for identifier, sources in rows
        ]

    def rank(
        self,
        clauses: tuple[tuple[str, float], ...],
        *,
        limit: int,
    ) -> list[EvidenceMatch]:
        started = time.perf_counter()
        normalized: list[tuple[str, float]] = []
        seen: set[str] = set()
        for raw_clause, raw_weight in clauses:
            key = normalize_evidence_key(raw_clause)
            if not key or key in seen:
                continue
            seen.add(key)
            normalized.append((key, max(0.0, min(1.0, float(raw_weight)))))
        scores: dict[str, float] = {}
        matches: dict[str, int] = {}
        sources_by_id: dict[str, set[str]] = {}
        collisions_by_id: dict[str, list[int]] = {}
        catalog_size = max(1, self.catalog.size)
        for key, weight in normalized:
            collision_count = self.collision_count(key)
            if collision_count <= 0 or collision_count > self.maximum_postings_per_key:
                continue
            specificity = math.log2((catalog_size + 1) / (collision_count + 1))
            clause_score = weight * (2.0 + min(8.0, specificity))
            for identifier, sources in self.lookup_exact(key):
                scores[identifier] = scores.get(identifier, 0.0) + clause_score
                matches[identifier] = matches.get(identifier, 0) + 1
                sources_by_id.setdefault(identifier, set()).update(sources)
                collisions_by_id.setdefault(identifier, []).append(collision_count)
        for identifier, count in matches.items():
            if count > 1:
                scores[identifier] += 3.0 * (count - 1)
        ordered = sorted(scores, key=lambda identifier: (-scores[identifier], -matches[identifier], identifier))
        elapsed = time.perf_counter() - started
        self._lookup_count += 1
        self._lookup_seconds += elapsed
        return [
            EvidenceMatch(
                parent_asin=identifier,
                score=scores[identifier],
                exact_matches=matches[identifier],
                sources=tuple(sorted(sources_by_id[identifier])),
                collision_counts=tuple(collisions_by_id[identifier]),
            )
            for identifier in ordered[: max(0, int(limit))]
        ]

    def close(self) -> None:
        self._connection.close()
