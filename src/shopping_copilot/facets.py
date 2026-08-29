"""Lazy, read-only product facets derived only from visible catalog fields."""

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass

from .catalog import CatalogIndex
from .constraints import COLORS, MATERIALS, STYLES, USE_CASES
from .models import ProductRecord
from .text import flatten_text, lexical_terms, normalize_whitespace, unique_terms


SIZE_TOKEN_RE = re.compile(
    r"\b(?:xxs|xs|small|medium|large|xl|xxl|xxxl|one size|\d{1,2}(?:\.5)?(?:\s*(?:us|uk|eu))?)\b",
    re.IGNORECASE,
)
SIZE_CONTEXT_RE = re.compile(
    r"\bsize\s*[:=-]?\s*(xxs|xs|small|medium|large|xl|xxl|xxxl|one size|\d{1,2}(?:\.5)?(?:\s*(?:us|uk|eu))?)\b",
    re.IGNORECASE,
)
GENERIC_FEATURE_TERMS = frozenset(
    {
        "product", "item", "women", "woman", "mens", "men", "girls", "boys",
        "size", "color", "style", "material", "made", "designed", "includes",
    }
)
FACET_VALUE_TERMS = frozenset(COLORS | MATERIALS | STYLES | USE_CASES)


@dataclass(frozen=True, slots=True)
class ProductFacets:
    category: tuple[str, ...] = ()
    brand: tuple[str, ...] = ()
    color: tuple[str, ...] = ()
    material: tuple[str, ...] = ()
    style: tuple[str, ...] = ()
    size: tuple[str, ...] = ()
    price_bucket: tuple[str, ...] = ()
    feature: tuple[str, ...] = ()
    use_case: tuple[str, ...] = ()

    def values(self, attribute: str) -> tuple[str, ...]:
        if attribute == "budget":
            return self.price_bucket
        value = getattr(self, attribute, ())
        return value if isinstance(value, tuple) else ()


def _normalized_phrase(value: object, *, limit: int = 80) -> str:
    return normalize_whitespace(value).lower().strip(" ,;:./-")[:limit]


def _vocabulary_matches(text: str, vocabulary: set[str]) -> tuple[str, ...]:
    terms = set(lexical_terms(text, limit=300, include_price_tokens=False))
    return tuple(sorted(terms.intersection(vocabulary)))


def _size_values(product: ProductRecord, document_text: str) -> tuple[str, ...]:
    values: list[str] = []
    for key, raw_value in product.details:
        if "size" not in key.lower() and "fit" not in key.lower():
            continue
        for match in SIZE_TOKEN_RE.finditer(raw_value):
            values.append(_normalized_phrase(match.group(0), limit=20))
    if not values:
        for match in SIZE_CONTEXT_RE.finditer(document_text):
            values.append(_normalized_phrase(match.group(1), limit=20))
            if len(values) >= 3:
                break
    return unique_terms(values, limit=4)


def _price_bucket(price: float | None) -> tuple[str, ...]:
    if price is None or price < 0:
        return ()
    if price < 25:
        return ("under_25",)
    if price < 50:
        return ("25_to_49",)
    if price < 100:
        return ("50_to_99",)
    if price < 200:
        return ("100_to_199",)
    return ("200_plus",)


class CandidateFacetIndex:
    """A bounded lazy facet cache over the immutable catalog mapping."""

    def __init__(self, catalog: CatalogIndex, *, cache_capacity: int = 8192) -> None:
        self.catalog = catalog
        self._cache_capacity = max(128, int(cache_capacity))
        self._cache: OrderedDict[str, ProductFacets] = OrderedDict()

    def get(self, parent_asin: object) -> ProductFacets:
        identifier = str(parent_asin)
        cached = self._cache.get(identifier)
        if cached is not None:
            self._cache.move_to_end(identifier)
            return cached
        product = self.catalog.get_product(identifier)
        facets = self._extract(product) if product is not None else ProductFacets()
        self._cache[identifier] = facets
        self._cache.move_to_end(identifier)
        while len(self._cache) > self._cache_capacity:
            self._cache.popitem(last=False)
        return facets

    def _extract(self, product: ProductRecord) -> ProductFacets:
        category_values = [
            _normalized_phrase(value)
            for value in product.categories
            if _normalized_phrase(value)
        ]
        category = (category_values[-1],) if category_values else ()
        details_text = flatten_text(product.details)
        document_text = normalize_whitespace(
            " ".join(
                (
                    product.title,
                    flatten_text(product.categories),
                    flatten_text(product.features),
                    details_text,
                    product.store,
                    flatten_text(product.description),
                )
            )
        ).lower()
        feature_terms = [
            term
            for term in lexical_terms(
                " ".join((flatten_text(product.features), details_text, flatten_text(product.description))),
                limit=48,
                include_price_tokens=False,
            )
            if term not in GENERIC_FEATURE_TERMS and term not in FACET_VALUE_TERMS
        ]
        brand = _normalized_phrase(product.store, limit=64)
        return ProductFacets(
            category=category,
            brand=(brand,) if brand else (),
            color=_vocabulary_matches(document_text, COLORS),
            material=_vocabulary_matches(document_text, MATERIALS),
            style=_vocabulary_matches(document_text, STYLES),
            size=_size_values(product, document_text),
            price_bucket=_price_bucket(product.price),
            feature=unique_terms(feature_terms, limit=24),
            use_case=_vocabulary_matches(document_text, USE_CASES),
        )

    def values(self, parent_asin: object, attribute: str) -> tuple[str, ...]:
        return self.get(parent_asin).values(attribute)

    def signature(self, parent_asin: object) -> tuple[str, ...]:
        facets = self.get(parent_asin)
        values: list[str] = []
        for attribute in ("category", "brand", "color", "material", "style", "price_bucket"):
            attribute_values = getattr(facets, attribute)
            if attribute_values:
                values.append(f"{attribute}:{attribute_values[0]}")
        return tuple(values)
