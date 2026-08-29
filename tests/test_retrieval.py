from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from shopping_copilot.catalog import CatalogIndex
from shopping_copilot.retrieval.fusion import weighted_reciprocal_rank_fusion
from shopping_copilot.text import retrieval_terms


def test_fts_empty_and_special_character_queries_are_safe(catalog_path) -> None:
    index = CatalogIndex(catalog_path)
    assert index.search("", 10) == []
    results = index.search('red OR " ) * : NEAR(foo) + -', 10)
    assert all(index.contains(item.parent_asin) for item in results)


def test_search_is_deterministic_and_catalog_methods_work(catalog_path) -> None:
    index = CatalogIndex(catalog_path)
    first = [item.parent_asin for item in index.search("blue leather shoes", 5)]
    second = [item.parent_asin for item in index.search("blue leather shoes", 5)]
    assert first == second
    assert first[0] == "A_BLUE_LEATHER_SHOE"
    assert index.size == 6
    assert index.contains(first[0])
    product = index.get_product(first[0])
    assert product is not None
    with pytest.raises(FrozenInstanceError):
        product.title = "mutated"


def test_price_token_can_retrieve_exact_around_budget(catalog_path) -> None:
    index = CatalogIndex(catalog_path)
    results = index.search("budget around $49.99", 3)
    assert results[0].parent_asin == "A_BLUE_LEATHER_SHOE"


def test_all_term_search_is_safe_and_precise(catalog_path) -> None:
    index = CatalogIndex(catalog_path)
    results = index.search("blue leather walking shoes", 5, match_all=True)
    assert [item.parent_asin for item in results] == ["A_BLUE_LEATHER_SHOE"]
    assert index.search("blue leather wool coat", 5, match_all=True) == []


def test_threshold_budget_does_not_become_a_material_percentage_term(agent) -> None:
    terms = retrieval_terms("I need breathable running shoes under $80.")
    assert "under" not in terms
    assert "80" not in terms

    agent.reset("budget", {})
    response = agent.respond("budget", "I need breathable running shoes under $80.", 1, 4)
    assert response["recommendations"][0]["parent_asin"] == "A_RED_COTTON_SHOE"


def test_weighted_rrf_deduplicates_and_has_stable_ties() -> None:
    rankings = {
        "current": ["B", "A", "B"],
        "history": ["A", "C"],
    }
    weights = {"current": 2.0, "history": 1.0}
    first = weighted_reciprocal_rank_fusion(rankings, weights, limit=10)
    second = weighted_reciprocal_rank_fusion(rankings, weights, limit=10)
    assert first == second
    identifiers = [item.parent_asin for item in first]
    assert len(identifiers) == len(set(identifiers))
    assert identifiers[0] in {"A", "B"}
