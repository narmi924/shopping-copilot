"""History-aware multi-route lexical query construction."""

from __future__ import annotations

from dataclasses import dataclass

from .fusion import weighted_reciprocal_rank_fusion
from .rerank import ConstraintCoverageReranker
from ..catalog import CatalogIndex
from ..evidence import EvidenceFingerprintIndex
from ..models import QueryRoute
from ..policy import PolicyConfig
from ..state import SessionState
from ..text import unique_terms


class QueryBuilder:
    """Builds independent retrieval routes with explicit precedence."""

    ROUTE_WEIGHTS = {
        "current": 4.5,
        "constraints": 3.0,
        "stable": 1.8,
        "profile": 0.35,
    }

    def __init__(self, config: PolicyConfig | None = None) -> None:
        self.config = config or PolicyConfig.for_name("control")

    def build(self, state: SessionState) -> list[QueryRoute]:
        values = {
            "current": state.current_retrieval_terms,
            "constraints": state.active_constraint_terms(),
            "stable": state.stable_context_terms(),
            "profile": state.profile_terms,
        }
        weights = dict(self.ROUTE_WEIGHTS)
        if state.current_intent_route == "override":
            weights.update({"current": 6.0, "constraints": 3.2, "stable": 1.2, "profile": 0.20})
        routes = [
            QueryRoute(name=name, terms=unique_terms(terms), weight=weights[name])
            for name, terms in values.items()
            if terms
        ]
        if state.current_intent_route == "override" and state.replacement_scope == "ambiguous":
            for name, weight in (("hypothesis_attribute", 4.0), ("hypothesis_category", 2.6)):
                terms = state.override_hypotheses.get(name.removeprefix("hypothesis_"), ())
                if terms:
                    routes.append(QueryRoute(name=name, terms=unique_terms(terms), weight=weight))
        return routes


@dataclass(slots=True)
class RetrievalOutcome:
    identifiers: list[str]
    candidate_count: int
    sources: dict[str, dict[str, object]]
    ranking_scores: list[tuple[str, float]]
    candidate_scores: list[tuple[str, float]]


class MultiRouteLexicalRetriever:
    def __init__(
        self,
        catalog: CatalogIndex,
        query_builder: QueryBuilder | None = None,
        *,
        evidence_index: EvidenceFingerprintIndex | None = None,
    ) -> None:
        self.catalog = catalog
        self.query_builder = query_builder or QueryBuilder()
        self.reranker = ConstraintCoverageReranker(catalog)
        self.evidence_index = evidence_index

    def retrieve(self, state: SessionState, top_k: int) -> list[str]:
        return self.retrieve_with_diagnostics(state, top_k).identifiers

    def retrieve_with_diagnostics(self, state: SessionState, top_k: int) -> RetrievalOutcome:
        safe_top_k = max(0, int(top_k))
        if safe_top_k == 0:
            return RetrievalOutcome([], 0, {}, [], [])
        routes = self.query_builder.build(state)
        candidate_limit = max(80, min(240, safe_top_k * 20))
        rankings: dict[str, list[str]] = {}
        weights: dict[str, float] = {}
        query_cache: dict[tuple[str, ...], list[str]] = {}
        sources: dict[str, dict[str, object]] = {}
        for route in routes:
            if route.terms not in query_cache:
                hits = self.catalog.search(" ".join(route.terms), candidate_limit)
                query_cache[route.terms] = [hit.parent_asin for hit in hits]
            rankings[route.name] = query_cache[route.terms]
            weights[route.name] = route.weight
            sources[route.name] = {
                "weight": route.weight,
                "candidate_count": len(rankings[route.name]),
                "mode": "any-term",
                "terms": list(route.terms),
            }

        evidence_scores: dict[str, float] = {}
        if self.evidence_index is not None:
            evidence_matches = self.evidence_index.rank(
                state.evidence_query_clauses(),
                limit=candidate_limit,
            )
            if evidence_matches:
                rankings["evidence"] = [item.parent_asin for item in evidence_matches]
                weights["evidence"] = 12.0
                evidence_scores = {item.parent_asin: item.score for item in evidence_matches}
                sources["evidence"] = {
                    "weight": 12.0,
                    "candidate_count": len(evidence_matches),
                    "mode": "exact-evidence",
                    "clause_count": len(state.evidence_query_clauses()),
                }

        strict_terms = unique_terms(
            (
                *state.current_retrieval_terms,
                *state.active_constraint_terms(),
                *state.stable_context_terms(),
            ),
            limit=48,
        )
        use_precision_track = state.current_intent_route != "override"
        if strict_terms and use_precision_track:
            strict_hits = self.catalog.search(" ".join(strict_terms), candidate_limit, match_all=True)
            rankings["strict"] = [hit.parent_asin for hit in strict_hits]
            weights["strict"] = 6.0
            sources["strict"] = {
                "weight": 6.0,
                "candidate_count": len(strict_hits),
                "mode": "all-terms",
                "terms": list(strict_terms),
            }

        fused = weighted_reciprocal_rank_fusion(rankings, weights, limit=candidate_limit)
        reranked = self.reranker.rerank(
            fused,
            state,
            candidate_limit,
            evidence_scores=evidence_scores,
        )
        candidate_scores = [(item.parent_asin, item.score) for item in reranked]
        candidate_ids = {identifier for identifier, _ in candidate_scores}
        if len(candidate_scores) < candidate_limit:
            combined_terms = unique_terms(
                term
                for route in routes
                if route.name != "profile"
                for term in route.terms
            )
            if combined_terms:
                for hit in self.catalog.search(" ".join(combined_terms), candidate_limit):
                    if hit.parent_asin not in candidate_ids:
                        candidate_ids.add(hit.parent_asin)
                        candidate_scores.append((hit.parent_asin, 0.0))
                    if len(candidate_scores) >= candidate_limit:
                        break
        if len(candidate_scores) < candidate_limit:
            for parent_asin in self.catalog.fallback_ids(candidate_limit):
                if parent_asin not in candidate_ids:
                    candidate_ids.add(parent_asin)
                    candidate_scores.append((parent_asin, 0.0))
                if len(candidate_scores) >= candidate_limit:
                    break
        identifiers = [identifier for identifier, _ in candidate_scores[:safe_top_k]]
        ranking_scores = candidate_scores[:safe_top_k]
        return RetrievalOutcome(
            identifiers=identifiers,
            candidate_count=len(fused),
            sources=sources,
            ranking_scores=ranking_scores,
            candidate_scores=candidate_scores,
        )
