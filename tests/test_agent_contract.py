from __future__ import annotations

import pytest

from shopping_copilot.models import ALLOWED_ATTRIBUTES
from starter.agent import Agent as StarterAgent


def test_adapter_exports_core_agent() -> None:
    assert StarterAgent.__module__ == "shopping_copilot.agent"


def test_respond_requires_reset(agent) -> None:
    with pytest.raises(RuntimeError, match="reset must be called"):
        agent.respond("missing", "running shoes", 1, 10)


def test_response_contract_is_safe_and_catalog_valid(agent) -> None:
    agent.reset("session", {"preference_tags": ["running"], "summary": "likes athletic shoes"})
    response = agent.respond("session", "I need red cotton running shoes.", 1, 3)

    assert isinstance(response["message"], str)
    assert response["ask_attribute"] in ALLOWED_ATTRIBUTES | {None}
    assert isinstance(response["recommendations"], list)
    assert len(response["recommendations"]) <= 3
    identifiers = [item["parent_asin"] for item in response["recommendations"]]
    assert len(identifiers) == len(set(identifiers))
    assert all(agent.catalog.contains(identifier) for identifier in identifiers)
    assert response["usage"] == {"prompt_tokens": 0, "completion_tokens": 0}


def test_non_positive_top_k_returns_no_recommendations(agent) -> None:
    agent.reset("session", {})
    assert agent.respond("session", "", 1, 0)["recommendations"] == []
    assert agent.respond("session", "", 1, -2)["recommendations"] == []


def test_empty_message_and_unknown_profile_fields_do_not_crash(agent) -> None:
    agent.reset("session", {"unknown": {"shape": [1, 2]}, "preference_tags": None})
    response = agent.respond("session", "", 1, 10)
    assert isinstance(response["message"], str)
    assert len(response["recommendations"]) <= 10


def test_invalid_turn_and_top_k_values_are_normalized(agent) -> None:
    agent.reset("session", {})
    response = agent.respond("session", "desk lamp", None, "not-a-number")

    assert response["recommendations"] == []
    assert agent.get_state("session").turn_history[-1].turn == 1


def test_debug_snapshot_is_internal_and_presentation_safe(agent) -> None:
    agent.reset("session", {})
    response = agent.respond("session", "I need red cotton running shoes.", 1, 3)
    debug = agent.debug_snapshot("session")

    assert "debug" not in response
    assert debug["detected_route"] == "buying"
    assert debug["candidate_count"] >= len(response["recommendations"])
    assert debug["retrieval_sources"]
    assert len(debug["final_ranking_scores"]) == len(response["recommendations"])
