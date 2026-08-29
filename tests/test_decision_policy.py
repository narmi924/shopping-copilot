from __future__ import annotations

import json
from pathlib import Path

import pytest

from shopping_copilot.agent import Agent
from shopping_copilot.models import Constraint
from shopping_copilot.policy import PolicyConfig
from shopping_copilot.portfolio import AdaptiveCandidatePortfolio
from shopping_copilot.question_value import QuestionValueEstimator
from shopping_copilot.state import SessionState


def _write_catalog(path: Path, products: list[dict]) -> Path:
    path.write_text(
        "".join(json.dumps(product) + "\n" for product in products),
        encoding="utf-8",
    )
    return path


def test_accepted_policy_is_default_and_control_remains_available(catalog_path: Path) -> None:
    accepted = Agent(catalog_path)
    control = Agent(catalog_path, policy_mode="control")

    assert accepted.policy_config.name == "question_portfolio"
    assert accepted.policy_config.question_value is True
    assert accepted.policy_config.candidate_portfolio is True
    assert control.policy_config.name == "control"
    assert control.policy_config.question_value is False
    assert control.policy_config.candidate_portfolio is False


def test_unknown_policy_mode_is_rejected(catalog_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown policy mode"):
        Agent(catalog_path, policy_mode="not-a-policy")


def _uncertainty_products(varying_slot: str) -> list[dict]:
    products: list[dict] = []
    for index in range(8):
        color = "Black" if varying_slot != "color" or index < 4 else "White"
        material = "Cotton" if varying_slot != "material" or index < 4 else "Wool"
        products.append(
            {
                "parent_asin": f"UNCERTAINTY_{varying_slot}_{index}",
                "title": f"{color} {material} Shirt {index}",
                "categories": ["Clothing", "Shirts"],
                "features": ["breathable soft garment"],
                "details": {"Color": color, "Material": material},
                "store": "One Store",
                "description": ["comfortable garment"],
                "price": 30,
                "average_rating": 4.5,
                "rating_number": 10,
            }
        )
    return products


def _question_for(tmp_path: Path, varying_slot: str) -> str | None:
    path = _write_catalog(tmp_path / f"{varying_slot}.jsonl", _uncertainty_products(varying_slot))
    agent = Agent(path, policy_mode="question")
    state = SessionState.create("question", {})
    state.record_turn(1, "I need a shirt.", "buying", ("shirt",))
    scores = [(product.parent_asin, 10.0 - index * 0.05) for index, product in enumerate(agent.catalog.iter_products())]
    estimator = QuestionValueEstimator(agent.facets)
    return estimator.choose(state, scores).attribute


def test_question_value_changes_with_candidate_uncertainty(tmp_path: Path) -> None:
    assert _question_for(tmp_path, "color") == "color"
    assert _question_for(tmp_path, "material") == "material"


def test_question_value_skips_active_asked_and_declined_slots(tmp_path: Path) -> None:
    path = _write_catalog(tmp_path / "questions.jsonl", _uncertainty_products("color"))
    agent = Agent(path, policy_mode="question")
    state = SessionState.create("question", {})
    state.record_turn(1, "I need a shirt.", "buying", ("shirt",))
    state.asked_attributes.add("color")
    state.declined_attributes.add("material")
    scores = [(product.parent_asin, 10.0 - index * 0.05) for index, product in enumerate(agent.catalog.iter_products())]

    decision = agent.question_estimator.choose(state, scores)

    assert decision.attribute not in {"color", "material"}


def _portfolio_products() -> list[dict]:
    products: list[dict] = []
    variants = [
        ("Shirts", "Black", "Cotton"),
        ("Dresses", "Red", "Silk"),
        ("Walking Shoes", "Blue", "Leather"),
        ("Backpacks", "Green", "Nylon"),
    ]
    for index in range(16):
        category, color, material = variants[0] if index < 10 else variants[1 + (index - 10) % 3]
        products.append(
            {
                "parent_asin": f"PORTFOLIO_{index:02d}",
                "title": f"{color} {material} {category} {index}",
                "categories": ["Clothing", category],
                "features": ["useful comfortable design"],
                "details": {"Color": color, "Material": material},
                "store": "Core Store" if index < 10 else f"Store {index}",
                "description": ["practical option"],
                "price": 40 + index,
                "average_rating": 4.5,
                "rating_number": 20,
            }
        )
    return products


def _portfolio_context(tmp_path: Path) -> tuple[Agent, list[tuple[str, float]]]:
    path = _write_catalog(tmp_path / "portfolio.jsonl", _portfolio_products())
    agent = Agent(path, policy_mode="portfolio")
    candidates = [
        (product.parent_asin, 20.0 - index * 0.2)
        for index, product in enumerate(agent.catalog.iter_products())
    ]
    return agent, candidates


def test_portfolio_is_deterministic_unique_and_catalog_valid(tmp_path: Path) -> None:
    agent, candidates = _portfolio_context(tmp_path)
    state = SessionState.create("browse", {})
    state.record_turn(1, "Show me some ideas.", "browsing", ("ideas",))
    selector = AdaptiveCandidatePortfolio(agent.catalog, agent.facets, PolicyConfig.for_name("portfolio"))

    first = selector.select(state, candidates, 10)
    second = selector.select(state, candidates, 10)

    assert first == second
    assert len(first.identifiers) == len(set(first.identifiers)) == 10
    assert all(agent.catalog.contains(identifier) for identifier in first.identifiers)


def test_portfolio_preserves_buying_precision_and_adds_browsing_diversity(tmp_path: Path) -> None:
    agent, candidates = _portfolio_context(tmp_path)
    selector = agent.candidate_portfolio
    buying = SessionState.create("buy", {})
    buying.record_turn(1, "I need an exact black cotton shirt.", "buying", ("black", "cotton", "shirt"))
    browsing = SessionState.create("browse", {})
    browsing.record_turn(1, "Show me some ideas.", "browsing", ("ideas",))

    buying_result = selector.select(buying, candidates, 10)
    browsing_result = selector.select(browsing, candidates, 10)

    assert buying_result.identifiers == tuple(identifier for identifier, _ in candidates[:10])
    assert browsing_result.identifiers[:7] == tuple(identifier for identifier, _ in candidates[:7])
    assert any(identifier not in {item for item, _ in candidates[:10]} for identifier in browsing_result.identifiers)
    signatures = {agent.facets.signature(identifier) for identifier in browsing_result.identifiers}
    assert len(signatures) > 1


def test_portfolio_tail_avoids_negative_constraint_conflicts(tmp_path: Path) -> None:
    agent, candidates = _portfolio_context(tmp_path)
    state = SessionState.create("negative", {})
    state.record_turn(2, "Anything except red.", "browsing", ("except", "red"))
    state.negative_constraints.append(
        Constraint("color", "red", ("red",), 2, status="negative", confidence=1.0)
    )
    red_identifier = "PORTFOLIO_10"

    result = agent.candidate_portfolio.select(state, candidates, 10)

    assert red_identifier not in result.identifiers[7:]


def test_override_portfolio_keeps_current_intent_at_the_front(tmp_path: Path) -> None:
    agent, candidates = _portfolio_context(tmp_path)
    state = SessionState.create("override", {})
    state.record_turn(3, "Actually I need shirts.", "override", ("shirts",))
    state.replacement_scope = "ambiguous"
    state.override_confidence = 0.7

    result = agent.candidate_portfolio.select(state, candidates, 10)

    assert result.identifiers[:3] == tuple(identifier for identifier, _ in candidates[:3])
