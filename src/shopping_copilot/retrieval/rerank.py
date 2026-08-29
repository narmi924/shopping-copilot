"""Constraint-coverage reranking over a bounded lexical candidate pool."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..catalog import CatalogIndex
from ..models import Constraint
from ..state import SessionState
from .fusion import FusedResult


ATTRIBUTE_WEIGHTS = {
    "category": 3.4,
    "material": 3.0,
    "color": 3.0,
    "size": 2.8,
    "style": 2.2,
    "brand": 2.8,
    "budget": 3.0,
    "feature": 2.6,
    "use_case": 2.2,
}


@dataclass(frozen=True, slots=True)
class RerankedResult:
    parent_asin: str
    score: float
    base_rank: int


def _coverage(terms: tuple[str, ...], document_terms: frozenset[str]) -> float:
    if not terms:
        return 0.0
    return sum(term in document_terms for term in terms) / len(terms)


def _budget_score(value: str, price: float | None) -> float | None:
    if price is None:
        return None
    match = re.search(r"(\d+(?:\.\d{1,2})?)", value)
    if not match:
        return None
    target = float(match.group(1))
    lowered = value.lower()
    if any(marker in lowered for marker in ("under", "below", "less than", "up to", "maximum", "max")):
        return 1.0 if price <= target else 0.0
    tolerance = max(5.0, target * 0.15)
    return max(0.0, 1.0 - abs(price - target) / tolerance)


class ConstraintCoverageReranker:
    """Rewards products covering the newest message and every active slot."""

    def __init__(self, catalog: CatalogIndex) -> None:
        self.catalog = catalog

    def rerank(
        self,
        candidates: list[FusedResult],
        state: SessionState,
        limit: int,
        *,
        evidence_scores: dict[str, float] | None = None,
    ) -> list[RerankedResult]:
        scored: list[RerankedResult] = []
        active_constraints: list[Constraint] = [
            constraint
            for values in state.active_constraints.values()
            for constraint in values
            if constraint.attribute not in state.declined_attributes
        ]
        override_turn = state.current_intent_route == "override"
        current_constraints = [
            constraint
            for constraint in state.current_turn_constraints
            if constraint.attribute not in state.declined_attributes
        ]
        latest_superseded = (
            list(state.override_events[-1].superseded)
            if override_turn and state.override_events
            else []
        )
        exact_evidence_scores = evidence_scores or {}
        for base_rank, candidate in enumerate(candidates, 1):
            terms = self.catalog.document_terms(candidate.parent_asin)
            product = self.catalog.get_product(candidate.parent_asin)
            score = candidate.score * 5.0 + 1.0 / (20.0 + base_rank)
            if candidate.parent_asin in exact_evidence_scores:
                score += min(18.0, 2.0 * exact_evidence_scores[candidate.parent_asin])

            current_coverage = _coverage(state.current_retrieval_terms, terms)
            score += 4.5 * current_coverage
            if state.current_retrieval_terms and current_coverage == 1.0:
                score += 2.0

            stable_coverage = _coverage(state.stable_context_terms(), terms)
            score += 1.25 * stable_coverage

            for constraint in active_constraints:
                weight = ATTRIBUTE_WEIGHTS.get(constraint.attribute, 1.5)
                if constraint.attribute == "budget":
                    budget_score = _budget_score(constraint.value, product.price if product else None)
                    if budget_score is not None:
                        score += weight * (budget_score - 0.35)
                    continue
                comparison_terms = (
                    self.catalog.category_terms(candidate.parent_asin)
                    if constraint.attribute == "category"
                    else terms
                )
                coverage = _coverage(constraint.terms, comparison_terms)
                score += weight * coverage
                if coverage == 1.0:
                    score += weight * 0.55
                elif coverage == 0.0 and constraint.attribute in {
                    "material", "color", "size", "brand", "budget"
                }:
                    score -= weight * 0.15

            if override_turn:
                for constraint in current_constraints:
                    weight = ATTRIBUTE_WEIGHTS.get(constraint.attribute, 1.5)
                    if constraint.attribute == "budget":
                        budget_score = _budget_score(constraint.value, product.price if product else None)
                        if budget_score is not None:
                            score += 1.4 * weight * budget_score * constraint.confidence
                        continue
                    comparison_terms = (
                        self.catalog.category_terms(candidate.parent_asin)
                        if constraint.attribute == "category"
                        else terms
                    )
                    coverage = _coverage(constraint.terms, comparison_terms)
                    score += 1.35 * weight * coverage * constraint.confidence
                    if coverage == 1.0:
                        score += 0.45 * weight * constraint.confidence

                negative_penalty = 0.0
                for constraint in state.negative_constraints:
                    if constraint.attribute in state.declined_attributes:
                        continue
                    weight = ATTRIBUTE_WEIGHTS.get(constraint.attribute, 1.5)
                    if constraint.attribute == "budget":
                        violation = _budget_score(constraint.value, product.price if product else None)
                        coverage = violation or 0.0
                    else:
                        comparison_terms = (
                            self.catalog.category_terms(candidate.parent_asin)
                            if constraint.attribute == "category"
                            else terms
                        )
                        coverage = _coverage(constraint.terms, comparison_terms)
                    negative_penalty += weight * 1.15 * coverage * constraint.confidence
                score -= min(5.5, negative_penalty)

                active_terms_by_slot = {
                    attribute: {
                        term
                        for item in values
                        for term in item.terms
                    }
                    for attribute, values in state.active_constraints.items()
                }
                superseded_penalty = 0.0
                for constraint in latest_superseded:
                    if set(constraint.terms).intersection(active_terms_by_slot.get(constraint.attribute, set())):
                        continue
                    comparison_terms = (
                        self.catalog.category_terms(candidate.parent_asin)
                        if constraint.attribute == "category"
                        else terms
                    )
                    coverage = _coverage(constraint.terms, comparison_terms)
                    superseded_penalty += (
                        ATTRIBUTE_WEIGHTS.get(constraint.attribute, 1.5)
                        * 0.45
                        * coverage
                        * constraint.confidence
                    )
                score -= min(2.5, superseded_penalty)

            scored.append(
                RerankedResult(
                    parent_asin=candidate.parent_asin,
                    score=score,
                    base_rank=base_rank,
                )
            )
        scored.sort(key=lambda item: (-item.score, item.base_rank, item.parent_asin))
        return scored[: max(0, int(limit))]
