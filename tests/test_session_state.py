from __future__ import annotations


def test_reset_creates_state_and_safely_copies_profile(agent) -> None:
    profile = {"preference_tags": ["travel"], "summary": "frequent traveler"}
    agent.reset("session", profile)
    profile["preference_tags"].append("mutated")

    state = agent.get_state("session")
    assert state.session_id == "session"
    assert state.user_profile["preference_tags"] == ["travel"]


def test_reset_same_session_clears_all_old_state(agent) -> None:
    agent.reset("session", {"summary": "old"})
    agent.respond("session", "I need red cotton shoes.", 1, 3)
    assert agent.get_state("session").turn_history
    assert agent.get_state("session").active_constraints

    agent.reset("session", {"summary": "new"})
    state = agent.get_state("session")
    assert state.turn_history == []
    assert state.active_constraints == {}
    assert state.asked_attributes == set()
    assert state.override_count == 0
    assert state.user_profile["summary"] == "new"


def test_history_appends_user_turns(agent) -> None:
    agent.reset("session", {})
    agent.respond("session", "I'm looking for shoes, but I'm still exploring.", 1, 2)
    agent.respond("session", "For that, what matters is: waterproof mesh.", 2, 2)
    history = agent.get_state("session").turn_history
    assert [item.turn for item in history] == [1, 2]
    assert history[1].user_message.startswith("For that")
