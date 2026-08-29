from __future__ import annotations

from shopping_copilot.retrieval.lexical import QueryBuilder


def test_override_supersedes_old_soft_constraints_and_reranks(agent) -> None:
    agent.reset("session", {})
    agent.respond("session", "I'm looking for shoes. I prefer red cotton.", 1, 4)
    response = agent.respond(
        "session",
        "Actually, ignore my earlier preference. What I need is: blue leather.",
        2,
        4,
    )

    state = agent.get_state("session")
    superseded_terms = {term for item in state.superseded_constraints for term in item.terms}
    assert {"red", "cotton"} <= superseded_terms
    assert {"blue", "leather"} <= set(state.active_constraint_terms())
    assert state.override_count == 1
    assert len(state.override_events) == 1

    query_terms = {term for route in QueryBuilder().build(state) for term in route.terms}
    assert "red" not in query_terms
    assert "cotton" not in query_terms
    assert response["recommendations"][0]["parent_asin"] == "A_BLUE_LEATHER_SHOE"


def test_generic_instead_marker_routes_to_override(agent) -> None:
    agent.reset("session", {})
    agent.respond("session", "I want a black wool coat.", 1, 3)
    agent.respond("session", "Instead, I prefer a pink silk dress.", 2, 3)
    state = agent.get_state("session")
    assert state.current_intent_route == "override"
    assert state.override_count == 1


def test_slot_override_replaces_only_conflicting_attribute(agent) -> None:
    agent.reset("session", {})
    agent.respond("session", "I need red cotton shoes.", 1, 4)
    agent.respond("session", "Actually, I prefer blue rather than red.", 2, 4)
    state = agent.get_state("session")

    assert "cotton" in state.active_constraint_terms()
    assert "blue" in state.active_constraint_terms()
    assert "red" not in state.active_constraint_terms()
    assert state.current_retrieval_terms == ("blue",)


def test_explicit_category_override_replaces_stable_category(agent) -> None:
    agent.reset("session", {})
    agent.respond("session", "I need a black wool coat.", 1, 4)
    agent.respond("session", "Instead, I want a pink silk dress.", 2, 4)
    state = agent.get_state("session")

    assert "dress" in state.stable_category_terms
    assert "coat" not in state.stable_category_terms
    assert "category" in {item.attribute for item in state.superseded_constraints}


def test_override_uses_diverse_fusion_track(agent) -> None:
    agent.reset("session", {})
    agent.respond("session", "I need red cotton shoes.", 1, 4)
    agent.respond("session", "Actually, ignore my earlier preference. What I need is: blue leather.", 2, 4)
    debug = agent.debug_snapshot("session")

    assert debug["detected_route"] == "override"
    assert "strict" not in debug["retrieval_sources"]
    assert {"current", "constraints", "stable"} <= set(debug["retrieval_sources"])

    agent.respond("session", "For that, what matters is: cushioned walking sole.", 3, 4)
    follow_up_debug = agent.debug_snapshot("session")
    assert follow_up_debug["detected_route"] == "buying"
    assert "strict" in follow_up_debug["retrieval_sources"]


def test_slot_override_replaces_conflicting_use_case(agent) -> None:
    agent.reset("session", {})
    agent.respond("session", "I need running shoes.", 1, 4)
    agent.respond("session", "Actually, I need walking shoes instead of running shoes.", 2, 4)
    state = agent.get_state("session")

    use_case_terms = {
        term
        for constraint in state.active_constraints.get("use_case", [])
        for term in constraint.terms
    }
    assert "running" not in use_case_terms
    assert any(item.attribute == "use_case" and "running" in item.terms for item in state.superseded_constraints)
    assert "running" not in state.stable_category_terms
    assert "shoes" in state.stable_category_terms
    query_terms = {term for route in QueryBuilder().build(state) for term in route.terms}
    assert "running" not in query_terms


def test_attribute_override_keeps_generic_category_context(agent) -> None:
    agent.reset("session", {})
    agent.respond("session", "I need red shoes.", 1, 4)
    agent.respond("session", "Actually, I prefer blue rather than red shoes.", 2, 4)
    state = agent.get_state("session")

    assert "shoes" in state.stable_category_terms
    assert "blue" in state.active_constraint_terms()
    assert "red" not in state.active_constraint_terms()
