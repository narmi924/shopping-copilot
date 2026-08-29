from __future__ import annotations

import json
from pathlib import Path

from shopping_copilot.agent import Agent


def _agent_with_color_variants(tmp_path: Path) -> Agent:
    products = [
        {
            "parent_asin": "BLACK_COAT",
            "title": "Black Wool Classic Coat",
            "categories": ["Women", "Coats"],
            "features": ["warm wool tailored winter coat"],
            "details": {"Color": "Black", "Material": "Wool"},
            "store": "North Tailoring",
            "description": ["classic coat for winter work"],
            "price": 80,
            "average_rating": 4.5,
            "rating_number": 50,
        },
        {
            "parent_asin": "WHITE_COAT",
            "title": "White Wool Classic Coat",
            "categories": ["Women", "Coats"],
            "features": ["warm wool tailored winter coat"],
            "details": {"Color": "White", "Material": "Wool"},
            "store": "North Tailoring",
            "description": ["classic coat for winter work"],
            "price": 80,
            "average_rating": 4.5,
            "rating_number": 50,
        },
        {
            "parent_asin": "BLUE_SHOE",
            "title": "Blue Leather Walking Shoes",
            "categories": ["Women", "Walking Shoes"],
            "features": ["cushioned leather walking sole"],
            "details": {"Color": "Blue", "Material": "Leather"},
            "store": "Walk Lab",
            "description": ["everyday walking shoe"],
            "price": 55,
            "average_rating": 4.5,
            "rating_number": 50,
        },
    ]
    path = tmp_path / "metamorphic-catalog.jsonl"
    path.write_text("".join(json.dumps(item) + "\n" for item in products), encoding="utf-8")
    return Agent(path)


def _ids(response: dict) -> list[str]:
    return [item["parent_asin"] for item in response["recommendations"]]


def test_replacing_black_with_white_demotes_rejected_value(tmp_path: Path) -> None:
    agent = _agent_with_color_variants(tmp_path)
    agent.reset("replace", {})
    agent.respond("replace", "I need a black wool coat.", 1, 3)
    response = agent.respond("replace", "Choose white instead of black.", 2, 3)

    state = agent.get_state("replace")
    assert _ids(response).index("WHITE_COAT") < _ids(response).index("BLACK_COAT")
    assert "black" not in state.active_constraint_terms()
    assert "white" in state.active_constraint_terms()


def test_no_preference_for_color_preserves_material(tmp_path: Path) -> None:
    agent = _agent_with_color_variants(tmp_path)
    agent.reset("decline", {})
    agent.respond("decline", "I need a black wool coat.", 1, 3)
    agent.respond("decline", "I am indifferent to color; use your judgment.", 2, 3)
    state = agent.get_state("decline")

    assert "color" in state.declined_attributes
    assert "wool" in state.active_constraint_terms()


def test_equivalent_paraphrases_produce_materially_similar_candidates(tmp_path: Path) -> None:
    agent = _agent_with_color_variants(tmp_path)
    agent.reset("one", {})
    first = agent.respond("one", "I need blue leather walking shoes under $60.", 1, 3)
    agent.reset("two", {})
    second = agent.respond(
        "two",
        "I'm shopping for walking shoes. They should be leather, blue, and below $60.",
        1,
        3,
    )

    assert len(set(_ids(first)) & set(_ids(second))) >= 2
    assert _ids(first)[0] == _ids(second)[0] == "BLUE_SHOE"


def test_explicit_negative_never_improves_rejected_variant(tmp_path: Path) -> None:
    agent = _agent_with_color_variants(tmp_path)
    agent.reset("negative", {})
    before = agent.respond("negative", "I need a wool coat.", 1, 3)
    after = agent.respond("negative", "Anything except black; white is preferred.", 2, 3)

    assert _ids(after).index("BLACK_COAT") >= _ids(before).index("BLACK_COAT")
    assert _ids(after).index("WHITE_COAT") < _ids(after).index("BLACK_COAT")


def test_same_inputs_are_deterministic_and_catalog_valid(tmp_path: Path) -> None:
    agent = _agent_with_color_variants(tmp_path)
    outputs: list[dict] = []
    for session_id in ("deterministic-a", "deterministic-b"):
        agent.reset(session_id, {"summary": "winter work"})
        outputs.append(agent.respond(session_id, "I need a white wool coat.", 1, 10))

    assert outputs[0] == outputs[1]
    identifiers = _ids(outputs[0])
    assert len(identifiers) == len(set(identifiers))
    assert all(agent.catalog.contains(identifier) for identifier in identifiers)
