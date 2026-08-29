from __future__ import annotations


def _ids(response: dict) -> list[str]:
    return [item["parent_asin"] for item in response["recommendations"]]


def test_prior_constraints_survive_a_no_preference_turn(agent) -> None:
    agent.reset("session", {})
    first = agent.respond(
        "session",
        "I'm looking for athletic shoes. A key requirement is: red cotton running.",
        1,
        4,
    )
    second = agent.respond(
        "session",
        "I don't have a preference for brand; please use your judgment.",
        2,
        4,
    )

    state = agent.get_state("session")
    assert "red" in state.active_constraint_terms()
    assert "cotton" in state.active_constraint_terms()
    assert state.current_retrieval_terms == ()
    assert "brand" in state.declined_attributes
    assert _ids(first)[0] == "A_RED_COTTON_SHOE"
    assert _ids(second)[0] == "A_RED_COTTON_SHOE"


def test_new_constraint_accumulates_with_stable_category(agent) -> None:
    agent.reset("session", {})
    agent.respond("session", "I'm looking for hiking boots, but I'm still exploring.", 1, 4)
    response = agent.respond("session", "For that, what matters is: waterproof mesh.", 2, 4)
    state = agent.get_state("session")
    assert "hiking" in state.stable_category_terms
    assert response["recommendations"][0]["parent_asin"] == "A_GREEN_HIKING_SHOE"
