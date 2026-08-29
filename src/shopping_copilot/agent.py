"""Offline, state-aware Shopping Copilot Agent implementation."""

from __future__ import annotations

from pathlib import Path

from .catalog import CatalogIndex
from .clarification import ClarificationPolicy
from .constraints import ConstraintExtractor
from .intent import IntentRouter
from .models import ALLOWED_ATTRIBUTES
from .retrieval.lexical import MultiRouteLexicalRetriever
from .state import SessionState
from .text import normalize_whitespace


class Agent:
    """Required competition interface backed only by local deterministic logic."""

    def __init__(self, catalog_path: str | Path = "data/catalog.jsonl") -> None:
        self.catalog_path = Path(catalog_path)
        self.catalog = CatalogIndex(self.catalog_path)
        self.extractor = ConstraintExtractor()
        self.intent_router = IntentRouter()
        self.retriever = MultiRouteLexicalRetriever(self.catalog)
        self.clarification_policy = ClarificationPolicy()
        self._sessions: dict[str, SessionState] = {}

    @property
    def sessions(self) -> dict[str, SessionState]:
        return self._sessions

    def get_state(self, session_id: str) -> SessionState:
        try:
            return self._sessions[str(session_id)]
        except KeyError as exc:
            raise RuntimeError("reset must be called before respond") from exc

    def reset(self, session_id: str, user_profile: dict) -> None:
        identifier = str(session_id)
        if not identifier:
            raise ValueError("session_id must be a non-empty string")
        self._sessions[identifier] = SessionState.create(identifier, user_profile)

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        state = self.get_state(str(session_id))
        message = normalize_whitespace(user_message)
        try:
            safe_turn = int(turn)
        except (TypeError, ValueError):
            safe_turn = len(state.turn_history) + 1
        try:
            safe_top_k = max(0, int(top_k))
        except (TypeError, ValueError):
            safe_top_k = 0

        extraction = self.extractor.extract(message, safe_turn, state.last_asked_attribute)
        route = self.intent_router.route(message, extraction)
        if extraction.declined_attributes:
            state.mark_declined(extraction.declined_attributes)
        if route == "override":
            state.apply_override(extraction, safe_turn, message)
        elif not extraction.decline_only:
            state.merge_constraints(extraction)
        state.record_turn(
            safe_turn,
            message,
            route,
            extraction.retrieval_terms,
            extraction.declined_attributes,
        )

        retrieval = self.retriever.retrieve_with_diagnostics(state, safe_top_k)
        identifiers = retrieval.identifiers
        identifiers = list(dict.fromkeys(item for item in identifiers if self.catalog.contains(item)))[:safe_top_k]
        state.set_recommendations(identifiers)
        valid_scores = [
            (identifier, score)
            for identifier, score in retrieval.ranking_scores
            if identifier in identifiers
        ]
        state.set_retrieval_debug(retrieval.candidate_count, retrieval.sources, valid_scores)
        ask_attribute = self.clarification_policy.choose(state)
        if ask_attribute not in ALLOWED_ATTRIBUTES:
            ask_attribute = None
        state.mark_asked(ask_attribute)
        return {
            "message": self.clarification_policy.message(ask_attribute, len(identifiers)),
            "ask_attribute": ask_attribute,
            "recommendations": [{"parent_asin": parent_asin} for parent_asin in identifiers],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }

    def debug_snapshot(self, session_id: str) -> dict:
        """Return presentation-safe diagnostics without changing evaluator output."""

        state = self.get_state(session_id)
        return {
            "session_id": state.session_id,
            "detected_route": state.current_intent_route,
            "active_constraints": {
                attribute: [constraint.value for constraint in constraints]
                for attribute, constraints in sorted(state.active_constraints.items())
            },
            "superseded_constraints": [
                {"attribute": constraint.attribute, "value": constraint.value}
                for constraint in state.superseded_constraints
            ],
            "asked_attributes": sorted(state.asked_attributes),
            "declined_attributes": sorted(state.declined_attributes),
            "last_asked_attribute": state.last_asked_attribute,
            "candidate_count": state.last_candidate_count,
            "retrieval_sources": state.last_retrieval_sources,
            "final_ranking_scores": [
                {"parent_asin": identifier, "score": round(score, 6)}
                for identifier, score in state.last_ranking_scores
            ],
            "override_count": state.override_count,
            "turn_count": len(state.turn_history),
        }
