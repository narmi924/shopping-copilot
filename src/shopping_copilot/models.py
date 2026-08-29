"""Shared immutable data models for the shopping agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ALLOWED_ATTRIBUTES = frozenset(
    {
        "category",
        "material",
        "color",
        "size",
        "style",
        "brand",
        "budget",
        "feature",
        "use_case",
        "other",
    }
)


@dataclass(frozen=True, slots=True)
class ProductRecord:
    """Read-only catalog representation retained by :class:`CatalogIndex`."""

    parent_asin: str
    title: str
    categories: tuple[str, ...]
    features: tuple[str, ...]
    details: tuple[tuple[str, str], ...]
    store: str
    description: tuple[str, ...]
    price: float | None
    average_rating: float | None
    rating_number: int


@dataclass(frozen=True, slots=True)
class SearchHit:
    parent_asin: str
    lexical_score: float


@dataclass(frozen=True, slots=True)
class Constraint:
    attribute: str
    value: str
    terms: tuple[str, ...]
    source_turn: int


@dataclass(frozen=True, slots=True)
class TurnRecord:
    turn: int
    user_message: str
    intent_route: str
    retrieval_terms: tuple[str, ...]
    declined_attributes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OverrideEvent:
    turn: int
    user_message: str
    superseded: tuple[Constraint, ...]
    replacement_terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class QueryRoute:
    name: str
    terms: tuple[str, ...]
    weight: float


@dataclass(slots=True)
class ConstraintExtraction:
    constraints: list[Constraint] = field(default_factory=list)
    category_terms: tuple[str, ...] = ()
    retrieval_terms: tuple[str, ...] = ()
    declined_attributes: set[str] = field(default_factory=set)
    decline_only: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
