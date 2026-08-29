"""Per-session state and explicit state transitions."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from .models import Constraint, ConstraintExtraction, OverrideEvent, TurnRecord
from .text import safe_profile_terms, unique_terms


def _safe_profile_copy(profile: object) -> dict[str, Any]:
    if not isinstance(profile, dict):
        return {}
    try:
        copied = copy.deepcopy(profile)
    except Exception:
        copied = {str(key): value for key, value in profile.items() if isinstance(value, (str, int, float, bool, type(None)))}
    return copied if isinstance(copied, dict) else {}


@dataclass(slots=True)
class SessionState:
    session_id: str
    user_profile: dict[str, Any]
    turn_history: list[TurnRecord] = field(default_factory=list)
    current_intent_route: str = "browsing"
    active_constraints: dict[str, list[Constraint]] = field(default_factory=dict)
    superseded_constraints: list[Constraint] = field(default_factory=list)
    asked_attributes: set[str] = field(default_factory=set)
    declined_attributes: set[str] = field(default_factory=set)
    last_asked_attribute: str | None = None
    current_retrieval_terms: tuple[str, ...] = ()
    stable_category_terms: tuple[str, ...] = ()
    override_count: int = 0
    override_events: list[OverrideEvent] = field(default_factory=list)
    last_recommendation_ids: tuple[str, ...] = ()
    last_candidate_count: int = 0
    last_retrieval_sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_ranking_scores: tuple[tuple[str, float], ...] = ()

    @classmethod
    def create(cls, session_id: str, user_profile: object) -> "SessionState":
        return cls(session_id=str(session_id), user_profile=_safe_profile_copy(user_profile))

    @property
    def profile_terms(self) -> tuple[str, ...]:
        return safe_profile_terms(self.user_profile)

    def record_turn(
        self,
        turn: int,
        user_message: str,
        intent_route: str,
        retrieval_terms: tuple[str, ...],
        declined_attributes: set[str] | None = None,
    ) -> None:
        self.current_intent_route = intent_route
        self.current_retrieval_terms = retrieval_terms
        self.turn_history.append(
            TurnRecord(
                turn=int(turn),
                user_message=str(user_message),
                intent_route=intent_route,
                retrieval_terms=retrieval_terms,
                declined_attributes=tuple(sorted(declined_attributes or set())),
            )
        )

    def merge_constraints(self, extraction: ConstraintExtraction) -> None:
        if extraction.category_terms:
            self.stable_category_terms = unique_terms(
                (*self.stable_category_terms, *extraction.category_terms),
                limit=24,
            )
        for constraint in extraction.constraints:
            self.declined_attributes.discard(constraint.attribute)
            bucket = self.active_constraints.setdefault(constraint.attribute, [])
            if any(existing.terms == constraint.terms for existing in bucket):
                continue
            bucket.append(constraint)

    def mark_declined(self, attributes: set[str]) -> None:
        for attribute in attributes:
            self.declined_attributes.add(attribute)
            removed = self.active_constraints.pop(attribute, [])
            self.superseded_constraints.extend(removed)

    def apply_override(self, extraction: ConstraintExtraction, turn: int, user_message: str) -> None:
        preserved_attributes = {"category", "use_case"}
        removed: list[Constraint] = []
        global_reset = extraction.metadata.get("override_scope") == "global"
        old_category_terms = set(self.stable_category_terms)
        new_category_terms = set(extraction.category_terms)
        category_changed = bool(
            not global_reset
            and old_category_terms
            and new_category_terms
            and old_category_terms.isdisjoint(new_category_terms)
        )
        if category_changed:
            preserved_attributes.discard("category")
            self.stable_category_terms = ()
        old_use_case_terms = {
            term
            for constraint in self.active_constraints.get("use_case", [])
            for term in constraint.terms
        }
        new_use_case_terms = {
            term
            for constraint in extraction.constraints
            if constraint.attribute == "use_case"
            for term in constraint.terms
        }
        use_case_changed = bool(
            not global_reset
            and old_use_case_terms
            and new_use_case_terms
            and old_use_case_terms.isdisjoint(new_use_case_terms)
        )
        if use_case_changed:
            preserved_attributes.discard("use_case")
            category_bucket = self.active_constraints.get("category", [])
            retained_categories: list[Constraint] = []
            for constraint in category_bucket:
                if old_use_case_terms.intersection(constraint.terms):
                    removed.append(constraint)
                else:
                    retained_categories.append(constraint)
            if retained_categories:
                self.active_constraints["category"] = retained_categories
            else:
                self.active_constraints.pop("category", None)
            self.stable_category_terms = tuple(
                term for term in self.stable_category_terms if term not in old_use_case_terms
            )
        replacement_attributes = {
            constraint.attribute
            for constraint in extraction.constraints
            if constraint.attribute not in preserved_attributes
        }
        if global_reset or not replacement_attributes:
            attributes_to_remove = set(self.active_constraints) - preserved_attributes
        else:
            attributes_to_remove = replacement_attributes
        for attribute in sorted(attributes_to_remove):
            removed.extend(self.active_constraints.pop(attribute, []))
        self.superseded_constraints.extend(removed)
        self.override_count += 1
        self.merge_constraints(extraction)
        self.override_events.append(
            OverrideEvent(
                turn=int(turn),
                user_message=str(user_message),
                superseded=tuple(removed),
                replacement_terms=extraction.retrieval_terms,
            )
        )

    def active_constraint_terms(self) -> tuple[str, ...]:
        ordered: list[str] = []
        for attribute in ("material", "color", "size", "style", "brand", "budget", "feature", "use_case", "category"):
            if attribute in self.declined_attributes:
                continue
            for constraint in self.active_constraints.get(attribute, []):
                ordered.extend(constraint.terms)
        return unique_terms(ordered, limit=100)

    def stable_context_terms(self) -> tuple[str, ...]:
        use_case_terms = [
            term
            for constraint in self.active_constraints.get("use_case", [])
            for term in constraint.terms
        ]
        return unique_terms((*self.stable_category_terms, *use_case_terms), limit=40)

    def mark_asked(self, attribute: str | None) -> None:
        self.last_asked_attribute = attribute
        if attribute:
            self.asked_attributes.add(attribute)

    def set_recommendations(self, identifiers: list[str]) -> None:
        self.last_recommendation_ids = tuple(identifiers)

    def set_retrieval_debug(
        self,
        candidate_count: int,
        sources: dict[str, dict[str, Any]],
        ranking_scores: list[tuple[str, float]],
    ) -> None:
        self.last_candidate_count = max(0, int(candidate_count))
        self.last_retrieval_sources = copy.deepcopy(sources)
        self.last_ranking_scores = tuple((str(identifier), float(score)) for identifier, score in ranking_scores)
