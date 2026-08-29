"""History-aware multi-route lexical query construction."""

from __future__ import annotations

from dataclasses import dataclass

from .fusion import weighted_reciprocal_rank_fusion
from .rerank import ConstraintCoverageReranker
from ..catalog import CatalogIndex
from ..models import QueryRoute
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

    def build(self, state: SessionState) -> list[QueryRoute]:
        values = {
            "current": state.current_retrieval_terms,
            "constraints": state.active_constraint_terms(),
            "stable": state.stable_context_terms(),
            "profile": state.profile_terms,
        }
        return [
            QueryRoute(name=name, terms=unique_terms(terms), weight=self.ROUTE_WEIGHTS[name])
            for name, terms in values.items()
            if terms
        ]


@dataclass(slots=True)
class RetrievalOutcome:
    identifiers: list[str]
    candidate_count: int
    sources: dict[str, dict[str, object]]
    ranking_scores: list[tuple[str, float]]


class MultiRouteLexicalRetriever:
    def __init__(self, catalog: CatalogIndex, query_builder: QueryBuilder | None = None) -> None:
        self.catalog = catalog
        self.query_builder = query_builder or QueryBuilder()
        self.reranker = ConstraintCoverageReranker(catalog)

    def retrieve(self, state: SessionState, top_k: int) -> list[str]:
        return self.retrieve_with_diagnostics(state, top_k).identifiers

    def retrieve_with_diagnostics(self, state: SessionState, top_k: int) -> RetrievalOutcome:
        safe_top_k = max(0, int(top_k))
        if safe_top_k == 0:
            return RetrievalOutcome([], 0, {}, [])
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
        if use_precision_track:
            reranked = self.reranker.rerank(fused, state, safe_top_k)
            identifiers = [item.parent_asin for item in reranked]
            ranking_scores = [(item.parent_asin, item.score) for item in reranked]
        else:
            identifiers = [item.parent_asin for item in fused[:safe_top_k]]
            ranking_scores = [(item.parent_asin, item.score) for item in fused[:safe_top_k]]
        if len(identifiers) < safe_top_k:
            combined_terms = unique_terms(
                term
                for route in routes
                if route.name != "profile"
                for term in route.terms
            )
            if combined_terms:
                for hit in self.catalog.search(" ".join(combined_terms), candidate_limit):
                    if hit.parent_asin not in identifiers:
                        identifiers.append(hit.parent_asin)
                        ranking_scores.append((hit.parent_asin, 0.0))
                    if len(identifiers) >= safe_top_k:
                        break
        if len(identifiers) < safe_top_k:
            for parent_asin in self.catalog.fallback_ids(safe_top_k):
                if parent_asin not in identifiers:
                    identifiers.append(parent_asin)
                    ranking_scores.append((parent_asin, 0.0))
                if len(identifiers) >= safe_top_k:
                    break
        return RetrievalOutcome(
            identifiers=identifiers[:safe_top_k],
            candidate_count=len(fused),
            sources=sources,
            ranking_scores=ranking_scores[:safe_top_k],
        )
