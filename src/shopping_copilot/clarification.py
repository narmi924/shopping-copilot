"""Deterministic clarification selection and customer-facing wording."""

from __future__ import annotations

from .state import SessionState


QUESTIONS = {
    "category": "Which product category should I narrow this to?",
    "material": "Is there a material preference I should prioritize?",
    "color": "Is there a color preference I should prioritize?",
    "size": "What size or fit should I prioritize?",
    "style": "Which style should I prioritize?",
    "brand": "Is there a brand preference I should prioritize?",
    "budget": "What budget should I keep in mind?",
    "feature": "Which feature matters most to you?",
    "use_case": "What will you mainly use it for?",
    "other": "What other requirement should I prioritize?",
}


class ClarificationPolicy:
    ROUTE_ORDER = {
        "buying": ("feature", "other", "material", "color", "size", "budget", "brand", "style", "use_case", "category"),
        "browsing": ("feature", "other", "use_case", "style", "material", "color", "size", "brand", "budget", "category"),
        "override": ("feature", "other", "material", "color", "size", "budget", "brand", "style", "use_case", "category"),
    }

    def choose(self, state: SessionState) -> str | None:
        order = self.ROUTE_ORDER.get(state.current_intent_route, self.ROUTE_ORDER["browsing"])
        active = {name for name, values in state.active_constraints.items() if values}
        for attribute in order:
            if attribute in state.asked_attributes or attribute in state.declined_attributes:
                continue
            if attribute != "other" and attribute in active:
                continue
            return attribute
        return None

    def message(self, ask_attribute: str | None, recommendation_count: int) -> str:
        if ask_attribute is None:
            return (
                "Here are the strongest matches from the preferences shared so far."
                if recommendation_count
                else "I could not find a strong match from the preferences shared so far."
            )
        prefix = "I found several options." if recommendation_count else "I need one more detail."
        return f"{prefix} {QUESTIONS[ask_attribute]}"
