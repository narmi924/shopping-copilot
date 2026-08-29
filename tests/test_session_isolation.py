from __future__ import annotations


def test_sessions_do_not_share_history_constraints_or_questions(agent) -> None:
    agent.reset("red", {"summary": "runner"})
    agent.reset("coat", {"summary": "winter commuter"})

    red_response = agent.respond("red", "I need red cotton running shoes.", 1, 3)
    coat_response = agent.respond("coat", "I need a black wool winter coat.", 1, 3)

    red_state = agent.get_state("red")
    coat_state = agent.get_state("coat")
    assert red_state is not coat_state
    assert red_state.turn_history[0].user_message != coat_state.turn_history[0].user_message
    assert "red" in red_state.active_constraint_terms()
    assert "red" not in coat_state.active_constraint_terms()
    assert "wool" in coat_state.active_constraint_terms()
    assert red_response["recommendations"][0]["parent_asin"] == "A_RED_COTTON_SHOE"
    assert coat_response["recommendations"][0]["parent_asin"] == "B_BLACK_WOOL_COAT"
