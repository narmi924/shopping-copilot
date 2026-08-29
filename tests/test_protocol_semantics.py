from __future__ import annotations

from evaluator import local_evaluator as simulator
from shopping_copilot.agent import Agent
from shopping_copilot.clarification import ClarificationPolicy
from shopping_copilot.constraints import extract_evidence_clauses
from shopping_copilot.evidence import product_evidence
from shopping_copilot.question_value import QuestionValueEstimator
from shopping_copilot.models import ALLOWED_ATTRIBUTES
from shopping_copilot.state import SessionState


def _sample(scenario: str = "buying") -> dict:
    return {
        "scenario_type": scenario,
        "intent_card": {
            "hard_constraints": ["cotton", "color: blue"],
            "soft_preferences": ["machine washable", "zip pockets"],
        },
        "behavior": {"scenario_type": scenario},
    }


def test_released_simulator_distinguishes_declined_and_exhausted_feedback() -> None:
    boundary_reply, boundary_used = simulator.customer_reply(
        _sample("boundary"), "color", set(), False
    )
    exhausted_reply, _ = simulator.customer_reply(
        _sample(), "brand", set(), False
    )

    assert boundary_reply == "I don't have a preference for color; please use your judgment."
    assert boundary_used is True
    assert exhausted_reply == "I don't have an additional preference for brand."


def test_released_simulator_repeated_other_discloses_two_then_remaining_values() -> None:
    disclosed: set[str] = set()

    first, _ = simulator.customer_reply(_sample(), "other", disclosed, False)
    second, _ = simulator.customer_reply(_sample(), "other", disclosed, False)
    third, _ = simulator.customer_reply(_sample(), "other", disclosed, False)

    assert first == "For that, what matters is: cotton; color: blue."
    assert second == "For that, what matters is: machine washable; zip pockets."
    assert third == "I don't have an additional preference for other."


def test_released_intent_card_uses_visible_catalog_evidence() -> None:
    product = {
        "title": "Blue Cotton Jacket",
        "categories": ["Clothing", "Jackets"],
        "features": ["machine washable"],
        "details": {"Closure": "zipper"},
        "store": "Example",
        "description": ["everyday outerwear"],
        "price": 45.0,
    }

    card = simulator.intent_card(product)
    evidence = [*card["hard_constraints"], *card["soft_preferences"]]

    assert evidence[:2] == ["cotton", "color: blue"]
    assert "machine washable" in evidence
    assert "Closure: zipper" in evidence


def test_no_additional_preference_preserves_active_constraint(catalog_path) -> None:
    agent = Agent(catalog_path, policy_mode="protocol_evidence")
    agent.reset("session", {})
    agent.respond("session", "I need blue leather walking shoes.", 1, 5)

    response = agent.respond(
        "session",
        "I don't have an additional preference for color.",
        2,
        5,
    )
    state = agent.get_state("session")

    assert "color" in state.exhausted_attributes
    assert "color" not in state.declined_attributes
    assert "blue" in state.active_constraint_terms()
    assert response["ask_attribute"] != "color"


def test_genuine_decline_removes_active_constraint(catalog_path) -> None:
    agent = Agent(catalog_path, policy_mode="protocol_evidence")
    agent.reset("session", {})
    agent.respond("session", "I need blue leather walking shoes.", 1, 5)
    agent.respond(
        "session",
        "I don't have a preference for color; please use your judgment.",
        2,
        5,
    )
    state = agent.get_state("session")

    assert "color" in state.declined_attributes
    assert "color" not in state.exhausted_attributes
    assert "blue" not in state.active_constraint_terms()
    assert "leather" in state.active_constraint_terms()


def test_decline_supersedes_exact_evidence_for_the_same_attribute(catalog_path) -> None:
    agent = Agent(catalog_path, policy_mode="protocol_evidence")
    agent.reset("session", {})
    agent.respond("session", "A key requirement is: color: blue.", 1, 5)

    before = agent.get_state("session")
    assert before.active_evidence[0].attribute == "color"
    agent.respond(
        "session",
        "I don't have a preference for color; please use your judgment.",
        2,
        5,
    )
    state = agent.get_state("session")

    assert not state.active_evidence
    assert state.superseded_evidence[0].normalized_key == "color: blue"
    assert "color: blue" not in {value for value, _ in state.evidence_query_clauses()}


def test_override_does_not_reintroduce_superseded_exact_evidence(catalog_path) -> None:
    agent = Agent(catalog_path, policy_mode="protocol_evidence")
    agent.reset("session", {})
    agent.respond("session", "A key requirement is: color: blue.", 1, 5)
    agent.respond(
        "session",
        "Actually, switch from blue to red. What I need is: color: red.",
        2,
        5,
    )
    state = agent.get_state("session")
    evidence = {value for value, _ in state.evidence_query_clauses()}

    assert "color: blue" not in evidence
    assert "color: red" in evidence
    assert any(item.normalized_key == "color: blue" for item in state.superseded_evidence)


def test_no_question_feedback_does_not_change_constraints(catalog_path) -> None:
    agent = Agent(catalog_path, policy_mode="protocol_evidence")
    agent.reset("session", {})
    agent.respond("session", "I need blue leather walking shoes.", 1, 5)
    before = agent.get_state("session").active_constraint_terms()
    previous_retrieval_terms = agent.get_state("session").current_retrieval_terms
    previous_current_constraints = agent.get_state("session").current_turn_constraints

    agent.respond(
        "session",
        "Those options are not quite right yet. Ask me about one specific attribute.",
        2,
        5,
    )
    state = agent.get_state("session")

    assert state.active_constraint_terms() == before
    assert state.current_turn_constraints == previous_current_constraints
    assert state.current_retrieval_terms == previous_retrieval_terms
    assert "one" not in state.current_retrieval_terms
    assert state.turn_history[-1].feedback_event == "no_question"


def test_repeated_other_is_bounded_and_stops_after_exhaustion(catalog_path) -> None:
    agent = Agent(catalog_path, policy_mode="protocol_evidence")
    state = SessionState.create("session", {})
    state.record_turn(1, "Show me some ideas.", "browsing", ("ideas",))
    estimator = QuestionValueEstimator(
        agent.facets,
        other_max_asks=2,
        other_min_remaining_turns=3,
    )

    first = estimator.choose(state, [])
    state.mark_asked(first.attribute)
    second = estimator.choose(state, [])
    state.mark_asked(second.attribute)
    third = estimator.choose(state, [])

    assert first.attribute == "other"
    assert second.attribute == "other"
    assert third.attribute is None
    assert state.ask_counts["other"] == 2

    state.mark_exhausted({"other"})
    assert estimator.choose(state, []).attribute is None


def test_repeated_other_uses_natural_follow_up_wording() -> None:
    policy = ClarificationPolicy()

    assert policy.message("other", 4, prior_ask_count=0).endswith(
        "What other requirement matters most?"
    )
    assert policy.message("other", 4, prior_ask_count=1).endswith(
        "Is there one more requirement I should prioritize?"
    )


def test_every_allowed_attribute_can_be_exhausted_without_losing_constraints(catalog_path) -> None:
    agent = Agent(catalog_path, policy_mode="protocol_evidence")
    agent.reset("all-slots", {})
    agent.respond("all-slots", "I need blue leather walking shoes.", 1, 5)
    before = agent.get_state("all-slots").active_constraint_terms()

    for turn, attribute in enumerate(sorted(ALLOWED_ATTRIBUTES), 2):
        agent.get_state("all-slots").last_asked_attribute = attribute
        agent.respond(
            "all-slots",
            f"I don't have an additional preference for {attribute}.",
            turn,
            5,
        )

    state = agent.get_state("all-slots")
    assert state.exhausted_attributes == set(ALLOWED_ATTRIBUTES)
    assert state.active_constraint_terms() == before


def test_repeated_other_can_be_gated_by_detected_route(catalog_path) -> None:
    agent = Agent(catalog_path, policy_mode="phase3")
    estimator = QuestionValueEstimator(
        agent.facets,
        other_max_asks=2,
        other_routes=("buying",),
    )
    buying = SessionState.create("buying", {})
    buying.record_turn(1, "I need an exact item.", "buying", ("exact",))
    browsing = SessionState.create("browsing", {})
    browsing.record_turn(1, "Show me ideas.", "browsing", ("ideas",))

    assert estimator.choose(buying, []).attribute == "other"
    buying.mark_asked("other")
    assert estimator.choose(buying, []).attribute == "other"

    assert estimator.choose(browsing, []).attribute == "other"
    browsing.mark_asked("other")
    assert estimator.choose(browsing, []).attribute is None


def test_complete_evidence_clauses_are_preserved() -> None:
    assert extract_evidence_clauses(
        "For that, what matters is: Water resistant shell; Closure Type: Full Zip."
    ) == ("Water resistant shell", "Closure Type: Full Zip")
    assert extract_evidence_clauses(
        "Actually, ignore my earlier preference. What I need is: machine washable."
    ) == ("machine washable",)


def test_evidence_normalization_matches_released_intent_card(catalog_path) -> None:
    agent = Agent(catalog_path, policy_mode="protocol_evidence")
    product = agent.catalog.get_product("A_RED_COTTON_SHOE")
    assert product is not None
    indexed = {key for key, _ in product_evidence(product)}
    raw_product = {
        "title": "Red Cotton Running Shoes",
        "categories": ["Clothing, Shoes & Jewelry", "Women", "Athletic Shoes"],
        "features": ["breathable cotton upper", "lightweight running trainer"],
        "details": {"Color": "Red", "Size": "8"},
        "store": "Stride Lab",
        "description": ["Comfortable shoes for running and gym workouts"],
        "price": 39.99,
    }
    card = simulator.intent_card(raw_product)
    disclosed = [*card["hard_constraints"], *card["soft_preferences"]]

    assert all(value in indexed for value in disclosed)


def test_evidence_index_supports_exact_lookup_and_multi_clause_ranking(catalog_path) -> None:
    agent = Agent(catalog_path, policy_mode="protocol_evidence")
    index = agent.evidence_index
    assert index is not None

    exact = index.lookup_exact("breathable cotton upper")
    ranked = index.rank(
        (("breathable cotton upper", 1.0), ("lightweight running trainer", 1.0)),
        limit=10,
    )

    assert exact == [("A_RED_COTTON_SHOE", ("feature",))]
    assert ranked[0].parent_asin == "A_RED_COTTON_SHOE"
    assert ranked[0].exact_matches == 2
    assert ranked[0].sources == ("feature",)
    assert agent.catalog.contains(ranked[0].parent_asin)
    assert index.lookup_intersection(
        ("breathable cotton upper", "lightweight running trainer"),
        limit=10,
    ) == [("A_RED_COTTON_SHOE", ("feature",))]


def test_current_exact_evidence_recovers_the_matching_product(catalog_path) -> None:
    agent = Agent(catalog_path, policy_mode="protocol_evidence")
    agent.reset("evidence", {})

    response = agent.respond(
        "evidence",
        "I'm looking for athletic shoes. A key requirement is: breathable cotton upper.",
        1,
        10,
    )

    assert response["recommendations"][0]["parent_asin"] == "A_RED_COTTON_SHOE"
    assert agent.get_state("evidence").current_evidence_clauses == (
        "breathable cotton upper",
    )
    assert agent.get_state("evidence").active_evidence[0].source_turn == 1
