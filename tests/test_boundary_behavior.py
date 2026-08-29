from __future__ import annotations

from shopping_copilot.retrieval.lexical import QueryBuilder


def test_declined_color_is_removed_and_never_asked_again(agent) -> None:
    agent.reset("session", {})
    first = agent.respond("session", "I'm looking for shoes, but I'm still exploring.", 1, 4)
    declined_attribute = first["ask_attribute"]
    assert declined_attribute == "feature"

    second = agent.respond(
        "session",
        "I don't have a preference for feature; please use your judgment.",
        2,
        4,
    )
    state = agent.get_state("session")
    assert "feature" in state.declined_attributes
    assert second["ask_attribute"] != "feature"
    assert state.current_retrieval_terms == ()
    all_terms = {term for route in QueryBuilder().build(state) for term in route.terms}
    assert not ({"no", "preference", "judgment"} & all_terms)


def test_explicit_color_decline_clears_old_color_constraint(agent) -> None:
    agent.reset("session", {})
    agent.respond("session", "I need red running shoes.", 1, 4)
    agent.respond("session", "I don't have a preference for color.", 2, 4)
    state = agent.get_state("session")
    assert "color" in state.declined_attributes
    assert "color" not in state.active_constraints
    assert "red" not in state.active_constraint_terms()


def test_indifferent_attribute_is_treated_as_declined(agent) -> None:
    agent.reset("session", {})
    agent.respond("session", "I need blue leather walking shoes.", 1, 4)
    response = agent.respond("session", "I'm indifferent to color.", 2, 4)
    state = agent.get_state("session")

    assert "color" in state.declined_attributes
    assert "leather" in state.active_constraint_terms()
    assert response["ask_attribute"] != "color"
