"""Candidate-aware, deterministic clarification question selection."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from .facets import CandidateFacetIndex
from .models import ALLOWED_ATTRIBUTES
from .state import SessionState


FACET_ATTRIBUTES = (
    "category",
    "material",
    "color",
    "size",
    "style",
    "brand",
    "budget",
    "feature",
    "use_case",
)

ROUTE_RELEVANCE = {
    "buying": {
        "category": 0.72,
        "material": 0.92,
        "color": 0.88,
        "size": 1.00,
        "style": 0.76,
        "brand": 0.76,
        "budget": 1.00,
        "feature": 1.00,
        "use_case": 0.70,
    },
    "browsing": {
        "category": 0.88,
        "material": 0.68,
        "color": 0.62,
        "size": 0.46,
        "style": 0.94,
        "brand": 0.55,
        "budget": 0.58,
        "feature": 1.00,
        "use_case": 0.98,
    },
    "override": {
        "category": 1.00,
        "material": 0.90,
        "color": 0.90,
        "size": 0.88,
        "style": 0.92,
        "brand": 0.88,
        "budget": 0.92,
        "feature": 0.94,
        "use_case": 0.84,
    },
}


@dataclass(frozen=True, slots=True)
class QuestionDecision:
    attribute: str | None
    score: float
    factors: dict[str, float]
    alternatives: tuple[tuple[str, float], ...]

    def as_debug(self) -> dict[str, object]:
        return {
            "attribute": self.attribute,
            "score": round(self.score, 6),
            "factors": {key: round(value, 6) for key, value in sorted(self.factors.items())},
            "alternatives": [
                {"attribute": attribute, "score": round(score, 6)}
                for attribute, score in self.alternatives
            ],
        }


def _binary_entropy(probability: float) -> float:
    if probability <= 0.0 or probability >= 1.0:
        return 0.0
    return -(probability * math.log2(probability) + (1.0 - probability) * math.log2(1.0 - probability))


def _normalized_entropy(counts: Counter[str]) -> float:
    if len(counts) <= 1:
        return 0.0
    total = sum(counts.values())
    entropy = -sum((count / total) * math.log(count / total) for count in counts.values())
    return min(1.0, entropy / math.log(min(len(counts), 12)))


class QuestionValueEstimator:
    """Choose the missing slot with the greatest bounded partition utility."""

    def __init__(self, facets: CandidateFacetIndex, *, candidate_limit: int = 60) -> None:
        self.facets = facets
        self.candidate_limit = max(10, int(candidate_limit))

    def _partition_factors(self, identifiers: list[str], attribute: str) -> tuple[float, float]:
        if not identifiers:
            return 0.0, 0.0
        values_by_product = [self.facets.values(identifier, attribute) for identifier in identifiers]
        covered = [values for values in values_by_product if values]
        coverage = len(covered) / len(identifiers)
        if not covered:
            return 0.0, 0.0
        if attribute in {"feature", "use_case"}:
            token_counts: Counter[str] = Counter()
            for values in covered:
                token_counts.update(set(values))
            if not token_counts:
                return coverage, 0.0
            best_count = min(
                token_counts.values(),
                key=lambda count: (abs(count / len(identifiers) - 0.5), -count),
            )
            partition_gain = _binary_entropy(best_count / len(identifiers))
        else:
            primary_counts = Counter(values[0] for values in covered)
            partition_gain = _normalized_entropy(primary_counts)
        return coverage, partition_gain

    @staticmethod
    def _uncertainty(candidate_scores: list[tuple[str, float]]) -> float:
        scores = [float(score) for _, score in candidate_scores[:10]]
        if len(scores) < 2:
            return 1.0
        scale = max(1.0, abs(scores[0]))
        spread = max(0.0, scores[0] - scores[-1]) / scale
        return max(0.35, min(1.0, 1.0 - 0.65 * spread))

    def choose(
        self,
        state: SessionState,
        candidate_scores: list[tuple[str, float]],
    ) -> QuestionDecision:
        identifiers = list(dict.fromkeys(identifier for identifier, _ in candidate_scores))[: self.candidate_limit]
        route = state.current_intent_route
        relevance = ROUTE_RELEVANCE.get(route, ROUTE_RELEVANCE["browsing"])
        active = {attribute for attribute, values in state.active_constraints.items() if values}
        current_turn = state.turn_history[-1].turn if state.turn_history else 1
        remaining_turns = max(0, 10 - current_turn)
        turn_factor = max(0.35, min(1.0, remaining_turns / 7.0))
        uncertainty = self._uncertainty(candidate_scores)
        scores: list[tuple[str, float, dict[str, float]]] = []
        affected_slots = {
            constraint.attribute
            for constraint in state.current_turn_constraints
            if constraint.attribute in FACET_ATTRIBUTES
        }

        for attribute in FACET_ATTRIBUTES:
            if attribute in state.asked_attributes or attribute in state.declined_attributes:
                continue
            allow_active_category = (
                route == "override"
                and state.replacement_scope == "ambiguous"
                and attribute == "category"
            )
            if attribute in active and not allow_active_category:
                continue
            coverage, partition_gain = self._partition_factors(identifiers, attribute)
            route_relevance = relevance[attribute]
            ambiguity_boost = 1.0
            if route == "override" and state.replacement_scope == "ambiguous":
                if attribute == "category":
                    ambiguity_boost = 1.35
                elif attribute in affected_slots:
                    ambiguity_boost = 1.18
            usefulness = coverage * partition_gain * route_relevance * uncertainty * turn_factor * ambiguity_boost
            factors = {
                "coverage": coverage,
                "partition_gain": partition_gain,
                "route_relevance": route_relevance,
                "uncertainty": uncertainty,
                "turn_factor": turn_factor,
                "ambiguity_boost": ambiguity_boost,
            }
            scores.append((attribute, min(1.0, usefulness), factors))

        scores.sort(key=lambda item: (-item[1], FACET_ATTRIBUTES.index(item[0]), item[0]))
        if scores and scores[0][1] >= 0.075:
            attribute, score, factors = scores[0]
            return QuestionDecision(
                attribute=attribute,
                score=score,
                factors=factors,
                alternatives=tuple((name, value) for name, value, _ in scores[:4]),
            )

        if (
            "other" in ALLOWED_ATTRIBUTES
            and "other" not in state.asked_attributes
            and "other" not in state.declined_attributes
            and remaining_turns >= 3
        ):
            return QuestionDecision(
                attribute="other",
                score=0.05,
                factors={"fallback": 1.0, "turn_factor": turn_factor},
                alternatives=tuple((name, value) for name, value, _ in scores[:4]),
            )
        return QuestionDecision(
            attribute=None,
            score=0.0,
            factors={"remaining_turns": float(remaining_turns)},
            alternatives=tuple((name, value) for name, value, _ in scores[:4]),
        )
