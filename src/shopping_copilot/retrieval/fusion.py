"""Deterministic weighted Reciprocal Rank Fusion."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FusedResult:
    parent_asin: str
    score: float
    best_rank: int


def weighted_reciprocal_rank_fusion(
    rankings: Mapping[str, Sequence[str]],
    weights: Mapping[str, float],
    *,
    limit: int,
    rank_constant: int = 50,
) -> list[FusedResult]:
    """Fuse deduplicated routes with stable score/rank/identifier ordering."""

    if limit <= 0:
        return []
    scores: dict[str, float] = {}
    best_ranks: dict[str, int] = {}
    for route_name, identifiers in rankings.items():
        weight = max(0.0, float(weights.get(route_name, 0.0)))
        if weight == 0.0:
            continue
        seen: set[str] = set()
        for rank, raw_identifier in enumerate(identifiers, 1):
            identifier = str(raw_identifier).strip()
            if not identifier or identifier in seen:
                continue
            seen.add(identifier)
            scores[identifier] = scores.get(identifier, 0.0) + weight / (rank_constant + rank)
            best_ranks[identifier] = min(rank, best_ranks.get(identifier, rank))
    ordered = sorted(scores, key=lambda identifier: (-scores[identifier], best_ranks[identifier], identifier))
    return [
        FusedResult(parent_asin=identifier, score=scores[identifier], best_rank=best_ranks[identifier])
        for identifier in ordered[:limit]
    ]
