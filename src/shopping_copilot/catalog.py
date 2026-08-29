"""Read-only in-memory catalog and SQLite FTS5 lexical index."""

from __future__ import annotations

import json
import sqlite3
from collections import OrderedDict
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from .models import ProductRecord, SearchHit
from .text import flatten_text, lexical_terms, price_index_text


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value if item not in (None, ""))
    if value in (None, ""):
        return ()
    return (str(value),)


def _details_tuple(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, dict):
        return ()
    return tuple((str(key), flatten_text(item)) for key, item in value.items())


def _float_or_none(value: object) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


class CatalogIndex:
    """Loads a frozen JSONL catalog once and exposes safe deterministic search."""

    FIELD_WEIGHTS = (0.0, 6.0, 4.0, 2.5, 2.5, 1.5, 1.0, 3.0)

    def __init__(self, catalog_path: str | Path) -> None:
        self.catalog_path = Path(catalog_path)
        if not self.catalog_path.is_file():
            raise FileNotFoundError(f"Catalog file not found: {self.catalog_path}")
        # FastAPI runs synchronous endpoints in a worker thread. The demo service
        # serializes Agent access with an RLock, so cross-thread use is safe here.
        self._connection = sqlite3.connect(":memory:", check_same_thread=False)
        self._connection.execute("PRAGMA query_only = OFF")
        self._products: Mapping[str, ProductRecord]
        self._fallback_ids: tuple[str, ...]
        self._search_cache: OrderedDict[tuple[tuple[str, ...], int, bool], tuple[SearchHit, ...]] = OrderedDict()
        self._document_term_cache: OrderedDict[str, frozenset[str]] = OrderedDict()
        self._category_term_cache: OrderedDict[str, frozenset[str]] = OrderedDict()
        self._cache_capacity = 1024
        self._document_cache_capacity = 4096
        self._build()

    def _build(self) -> None:
        cursor = self._connection.cursor()
        cursor.execute(
            "CREATE VIRTUAL TABLE products USING fts5("
            "parent_asin UNINDEXED, title, categories, features, details, store, description, price, "
            "tokenize='porter unicode61 remove_diacritics 2')"
        )
        products: dict[str, ProductRecord] = {}
        batch: list[tuple[str, str, str, str, str, str, str, str]] = []
        with self.catalog_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid catalog JSON at line {line_number}") from exc
                if not isinstance(raw, dict):
                    raise ValueError(f"Catalog record at line {line_number} is not an object")
                parent_asin = str(raw.get("parent_asin") or "").strip()
                if not parent_asin:
                    raise ValueError(f"Catalog record at line {line_number} has no parent_asin")
                if parent_asin in products:
                    raise ValueError(f"Duplicate parent_asin at line {line_number}: {parent_asin}")
                record = ProductRecord(
                    parent_asin=parent_asin,
                    title=str(raw.get("title") or ""),
                    categories=_string_tuple(raw.get("categories")),
                    features=_string_tuple(raw.get("features")),
                    details=_details_tuple(raw.get("details")),
                    store=str(raw.get("store") or ""),
                    description=_string_tuple(raw.get("description")),
                    price=_float_or_none(raw.get("price")),
                    average_rating=_float_or_none(raw.get("average_rating")),
                    rating_number=_int_or_zero(raw.get("rating_number")),
                )
                products[parent_asin] = record
                batch.append(
                    (
                        record.parent_asin,
                        record.title,
                        flatten_text(record.categories),
                        flatten_text(record.features),
                        flatten_text(record.details),
                        record.store,
                        flatten_text(record.description),
                        price_index_text(raw.get("price")),
                    )
                )
                if len(batch) >= 1000:
                    cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?)", batch)
                    batch.clear()
        if batch:
            cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?)", batch)
        self._connection.commit()
        self._connection.execute("PRAGMA query_only = ON")
        self._products = MappingProxyType(products)
        self._fallback_ids = tuple(
            record.parent_asin
            for record in sorted(
                products.values(),
                key=lambda item: (-item.rating_number, -(item.average_rating or 0.0), item.parent_asin),
            )
        )

    @property
    def size(self) -> int:
        return len(self._products)

    def contains(self, parent_asin: object) -> bool:
        return str(parent_asin) in self._products

    def get_product(self, parent_asin: object) -> ProductRecord | None:
        return self._products.get(str(parent_asin))

    def fallback_ids(self, limit: int) -> list[str]:
        return list(self._fallback_ids[: max(0, int(limit))])

    def document_terms(self, parent_asin: object) -> frozenset[str]:
        identifier = str(parent_asin)
        cached = self._document_term_cache.get(identifier)
        if cached is not None:
            self._document_term_cache.move_to_end(identifier)
            return cached
        product = self.get_product(identifier)
        if product is None:
            return frozenset()
        text = " ".join(
            (
                product.title,
                flatten_text(product.categories),
                flatten_text(product.features),
                flatten_text(product.details),
                product.store,
                flatten_text(product.description),
                price_index_text(product.price),
            )
        )
        terms = frozenset(lexical_terms(text, limit=400))
        self._document_term_cache[identifier] = terms
        self._document_term_cache.move_to_end(identifier)
        while len(self._document_term_cache) > self._document_cache_capacity:
            self._document_term_cache.popitem(last=False)
        return terms

    def category_terms(self, parent_asin: object) -> frozenset[str]:
        identifier = str(parent_asin)
        cached = self._category_term_cache.get(identifier)
        if cached is not None:
            self._category_term_cache.move_to_end(identifier)
            return cached
        product = self.get_product(identifier)
        if product is None:
            return frozenset()
        terms = frozenset(
            lexical_terms(
                f"{product.title} {flatten_text(product.categories)}",
                limit=160,
                include_price_tokens=False,
            )
        )
        self._category_term_cache[identifier] = terms
        self._category_term_cache.move_to_end(identifier)
        while len(self._category_term_cache) > self._document_cache_capacity:
            self._category_term_cache.popitem(last=False)
        return terms

    def search(self, query: object, limit: int, *, match_all: bool = False) -> list[SearchHit]:
        safe_limit = max(0, int(limit))
        if safe_limit == 0:
            return []
        terms = lexical_terms(str(query or ""), limit=60)
        if not terms:
            return []
        cache_key = (terms, safe_limit, bool(match_all))
        cached = self._search_cache.get(cache_key)
        if cached is not None:
            self._search_cache.move_to_end(cache_key)
            return list(cached)
        connector = " AND " if match_all else " OR "
        expression = connector.join(f'"{term}"' for term in terms)
        weights = ", ".join(str(value) for value in self.FIELD_WEIGHTS)
        sql = (
            "SELECT parent_asin, bm25(products, " + weights + ") AS lexical_score "
            "FROM products WHERE products MATCH ? "
            "ORDER BY lexical_score ASC, parent_asin ASC LIMIT ?"
        )
        try:
            rows = self._connection.execute(sql, (expression, safe_limit)).fetchall()
        except sqlite3.Error:
            return []
        result = tuple(SearchHit(parent_asin=str(row[0]), lexical_score=float(row[1])) for row in rows)
        self._search_cache[cache_key] = result
        self._search_cache.move_to_end(cache_key)
        while len(self._search_cache) > self._cache_capacity:
            self._search_cache.popitem(last=False)
        return list(result)

    def close(self) -> None:
        self._connection.close()
