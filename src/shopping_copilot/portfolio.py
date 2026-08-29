"""Rank-aware deterministic selection of a precision core and exploration tail."""

from __future__ import annotations

from dataclasses import dataclass

from .catalog import CatalogIndex
from .facets import CandidateFacetIndex
from .policy import PolicyConfig
from .state import SessionState


@dataclass(frozen=True, slots=True)
class PortfolioDecision:
    identifiers: tuple[str, ...]
    precision_count: int
    exploration_count: int
    considered_count: int
    selection_gains: tuple[tuple[str, float], ...]

    def as_debug(self) -> dict[str, object]:
        return {
            "precision_count": self.precision_count,
            "exploration_count": self.exploration_count,
            "considered_count": self.considered_count,
            "selection_gains": [
                {"parent_asin": identifier, "gain": round(gain, 6)}
                for identifier, gain in self.selection_gains
            ],
        }


def _coverage(terms: tuple[str, ...], document_terms: frozenset[str]) -> float:
    if not terms:
        return 0.0
    return sum(term in document_terms for term in terms) / len(terms)


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


class AdaptiveCandidatePortfolio:
    """Protect high ranks, then select a bounded, relevant exploration tail."""

    def __init__(
        self,
        catalog: CatalogIndex,
        facets: CandidateFacetIndex,
        config: PolicyConfig,
    ) -> None:
        self.catalog = catalog
        self.facets = facets
        self.config = config

    def _precision_count(self, state: SessionState, top_k: int) -> int:
        if top_k <= 3:
            return top_k
        active_count = sum(bool(values) for values in state.active_constraints.values())
        if state.current_intent_route == "buying":
            fraction = self.config.buying_precision_fraction
        elif state.current_intent_route == "override":
            fraction = self.config.override_precision_fraction
            if state.replacement_scope != "ambiguous" and state.override_confidence >= 0.85:
                fraction = max(fraction, 0.85)
        else:
            refined = active_count >= 2 or len(state.asked_attributes) >= 2
            fraction = (
                self.config.browsing_refined_fraction
                if refined
                else self.config.browsing_precision_fraction
            )
            if state.declined_attributes:
                fraction = max(fraction, 0.80)
        return max(3, min(top_k, int(round(top_k * fraction))))

    def select(
        self,
        state: SessionState,
        candidate_scores: list[tuple[str, float]],
        top_k: int,
    ) -> PortfolioDecision:
        safe_top_k = max(0, int(top_k))
        ranked: list[tuple[str, float]] = []
        seen: set[str] = set()
        for identifier, raw_score in candidate_scores:
            identifier = str(identifier)
            if identifier in seen or not self.catalog.contains(identifier):
                continue
            seen.add(identifier)
            ranked.append((identifier, float(raw_score)))
            if len(ranked) >= self.config.portfolio_candidate_limit:
                break
        if safe_top_k == 0 or not ranked:
            return PortfolioDecision((), 0, 0, len(ranked), ())

        precision_count = min(self._precision_count(state, safe_top_k), len(ranked))
        selected = list(ranked[:precision_count])
        if len(selected) >= safe_top_k:
            return PortfolioDecision(
                identifiers=tuple(identifier for identifier, _ in selected[:safe_top_k]),
                precision_count=min(precision_count, safe_top_k),
                exploration_count=0,
                considered_count=len(ranked),
                selection_gains=(),
            )

        maximum = ranked[0][1]
        minimum = ranked[-1][1]
        span = maximum - minimum
        selected_ids = {identifier for identifier, _ in selected}
        selected_signatures = [set(self.facets.signature(identifier)) for identifier, _ in selected]
        current_terms = state.current_retrieval_terms
        active_terms = state.active_constraint_terms()
        negative_terms = state.negative_constraint_terms()
        superseded_terms = tuple(
            term
            for constraint in state.superseded_constraints[-12:]
            for term in constraint.terms
            if constraint.attribute not in state.declined_attributes
        )
        gains: list[tuple[str, float]] = []

        while len(selected) < min(safe_top_k, len(ranked)):
            best: tuple[float, int, str, float] | None = None
            for rank, (identifier, score) in enumerate(ranked[precision_count:], precision_count + 1):
                if identifier in selected_ids:
                    continue
                document_terms = self.catalog.document_terms(identifier)
                signature = set(self.facets.signature(identifier))
                relevance = (score - minimum) / span if span > 1e-12 else 1.0
                current_coverage = _coverage(current_terms, document_terms)
                active_coverage = _coverage(active_terms, document_terms)
                negative_violation = _coverage(negative_terms, document_terms)
                superseded_violation = _coverage(superseded_terms, document_terms)
                duplicate_similarity = max(
                    (_jaccard(signature, existing) for existing in selected_signatures),
                    default=0.0,
                )
                covered_signature = set().union(*selected_signatures) if selected_signatures else set()
                novelty = len(signature - covered_signature) / max(1, len(signature))
                gain = (
                    self.config.exploration_relevance_weight * relevance
                    + 0.12 * current_coverage
                    + 0.08 * active_coverage
                    + self.config.exploration_novelty_weight * novelty
                    - 0.18 * duplicate_similarity
                    - 0.85 * negative_violation
                    - 0.20 * superseded_violation
                )
                key = (gain, -rank, identifier, score)
                if best is None or key > best:
                    best = key
            if best is None:
                break
            gain, _, identifier, raw_score = best
            selected.append((identifier, raw_score))
            selected_ids.add(identifier)
            selected_signatures.append(set(self.facets.signature(identifier)))
            gains.append((identifier, gain))

        return PortfolioDecision(
            identifiers=tuple(identifier for identifier, _ in selected[:safe_top_k]),
            precision_count=min(precision_count, safe_top_k),
            exploration_count=max(0, min(safe_top_k, len(selected)) - precision_count),
            considered_count=len(ranked),
            selection_gains=tuple(gains),
        )
