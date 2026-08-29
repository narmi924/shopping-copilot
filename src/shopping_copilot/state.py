"""Per-session state and explicit state transitions."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
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
    negative_constraints: list[Constraint] = field(default_factory=list)
    current_turn_constraints: tuple[Constraint, ...] = ()
    asked_attributes: set[str] = field(default_factory=set)
    declined_attributes: set[str] = field(default_factory=set)
    last_asked_attribute: str | None = None
    current_retrieval_terms: tuple[str, ...] = ()
    stable_category_terms: tuple[str, ...] = ()
    override_count: int = 0
    override_events: list[OverrideEvent] = field(default_factory=list)
    replacement_scope: str | None = None
    override_confidence: float = 0.0
    override_hypotheses: dict[str, tuple[str, ...]] = field(default_factory=dict)
    last_recommendation_ids: tuple[str, ...] = ()
    last_candidate_count: int = 0
    last_retrieval_sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_ranking_scores: tuple[tuple[str, float], ...] = ()
    last_question_decision: dict[str, Any] = field(default_factory=dict)
    last_portfolio_decision: dict[str, Any] = field(default_factory=dict)

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
        self.current_turn_constraints = tuple(extraction.constraints)
        self.replacement_scope = None
        self.override_confidence = 0.0
        self.override_hypotheses.clear()
        if extraction.category_terms:
            self.stable_category_terms = unique_terms(
                (*self.stable_category_terms, *extraction.category_terms),
                limit=24,
            )
        for constraint in extraction.constraints:
            self.declined_attributes.discard(constraint.attribute)
            self.negative_constraints = [
                negative
                for negative in self.negative_constraints
                if not (
                    negative.attribute == constraint.attribute
                    and set(negative.terms).intersection(constraint.terms)
                )
            ]
            bucket = self.active_constraints.setdefault(constraint.attribute, [])
            if any(existing.terms == constraint.terms for existing in bucket):
                continue
            bucket.append(constraint)

    def mark_declined(self, attributes: set[str]) -> None:
        for attribute in attributes:
            self.declined_attributes.add(attribute)
            removed = self.active_constraints.pop(attribute, [])
            self.superseded_constraints.extend(replace(item, status="superseded") for item in removed)
            self.negative_constraints = [
                item for item in self.negative_constraints if item.attribute != attribute
            ]

    def apply_override(self, extraction: ConstraintExtraction, turn: int, user_message: str) -> None:
        self.current_turn_constraints = tuple(extraction.constraints)
        replacement = extraction.replacement
        replacement_type = replacement.replacement_type if replacement else str(
            extraction.metadata.get("override_scope") or "ambiguous"
        )
        confidence = replacement.confidence if replacement else 0.55
        self.replacement_scope = replacement_type
        self.override_confidence = confidence
        self.override_hypotheses.clear()

        if extraction.decline_only:
            self.override_count += 1
            self.override_events.append(
                OverrideEvent(
                    turn=int(turn),
                    user_message=str(user_message),
                    superseded=(),
                    replacement_terms=(),
                    replacement_type="decline",
                    confidence=confidence,
                )
            )
            return

        preserved_attributes = {"category", "use_case"}
        removed: list[Constraint] = []
        old_category_terms = set(self.stable_category_terms)
        new_category_terms = set(extraction.category_terms)
        category_changed = bool(
            old_category_terms
            and new_category_terms
            and old_category_terms.isdisjoint(new_category_terms)
        )
        if category_changed and replacement_type in {"ambiguous", "attribute"}:
            replacement_type = "category"
            self.replacement_scope = replacement_type
        if replacement_type == "category":
            self.stable_category_terms = ()

        affected_slots = set(replacement.affected_slots if replacement else ())
        if "use_case" in affected_slots:
            old_use_case_terms = {
                term
                for item in extraction.negative_constraints
                if item.attribute == "use_case"
                for term in item.terms
            }
            self.stable_category_terms = tuple(
                term for term in self.stable_category_terms if term not in old_use_case_terms
            )
            category_bucket = self.active_constraints.get("category", [])
            cleaned_categories: list[Constraint] = []
            for constraint in category_bucket:
                remaining_terms = tuple(term for term in constraint.terms if term not in old_use_case_terms)
                if remaining_terms:
                    cleaned_categories.append(
                        replace(constraint, value=" ".join(remaining_terms), terms=remaining_terms)
                    )
                else:
                    removed.append(constraint)
            if cleaned_categories:
                self.active_constraints["category"] = cleaned_categories
            else:
                self.active_constraints.pop("category", None)
        if replacement_type == "global":
            attributes_to_remove = set(self.active_constraints) - preserved_attributes
        elif replacement_type == "category":
            attributes_to_remove = {"category", "size", "style", "brand", "feature"}
        elif replacement_type == "negative":
            attributes_to_remove = set()
            for negative in extraction.negative_constraints:
                bucket = self.active_constraints.get(negative.attribute, [])
                retained: list[Constraint] = []
                for constraint in bucket:
                    if set(constraint.terms).intersection(negative.terms):
                        removed.append(constraint)
                    else:
                        retained.append(constraint)
                if retained:
                    self.active_constraints[negative.attribute] = retained
                else:
                    self.active_constraints.pop(negative.attribute, None)
        elif replacement_type == "attribute":
            attributes_to_remove = affected_slots or {
                constraint.attribute
                for constraint in extraction.constraints
                if constraint.attribute not in preserved_attributes | {"feature"}
            }
        else:
            attributes_to_remove = affected_slots
        for attribute in sorted(attributes_to_remove):
            removed.extend(self.active_constraints.pop(attribute, []))
        superseded = [replace(item, status="superseded") for item in removed]
        self.superseded_constraints.extend(superseded)
        for negative in extraction.negative_constraints:
            if any(
                existing.attribute == negative.attribute and existing.terms == negative.terms
                for existing in self.negative_constraints
            ):
                continue
            self.negative_constraints.append(negative)
        self.override_count += 1
        self.merge_constraints(extraction)
        self.replacement_scope = replacement_type
        self.override_confidence = confidence
        if replacement_type == "ambiguous":
            non_category_terms = [
                term
                for attribute, constraints in self.active_constraints.items()
                if attribute != "category"
                for constraint in constraints
                for term in constraint.terms
            ]
            self.override_hypotheses = {
                "attribute": unique_terms(
                    (*extraction.retrieval_terms, *non_category_terms, *self.stable_category_terms),
                    limit=48,
                ),
                "category": unique_terms(
                    (*extraction.retrieval_terms, *extraction.category_terms, *self.stable_category_terms),
                    limit=48,
                ),
            }
        self.override_events.append(
            OverrideEvent(
                turn=int(turn),
                user_message=str(user_message),
                superseded=tuple(superseded),
                replacement_terms=extraction.retrieval_terms,
                negative=tuple(extraction.negative_constraints),
                replacement_type=replacement_type,
                confidence=confidence,
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

    def negative_constraint_terms(self) -> tuple[str, ...]:
        return unique_terms(
            term
            for constraint in self.negative_constraints
            if constraint.attribute not in self.declined_attributes
            for term in constraint.terms
        )

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

    def set_decision_debug(
        self,
        *,
        question: dict[str, Any] | None = None,
        portfolio: dict[str, Any] | None = None,
    ) -> None:
        self.last_question_decision = copy.deepcopy(question or {})
        self.last_portfolio_decision = copy.deepcopy(portfolio or {})
