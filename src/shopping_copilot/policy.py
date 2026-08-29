"""Small, deterministic policy configurations used by controlled experiments."""

from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_POLICY_MODE = "protocol_evidence"
POLICY_ENVIRONMENT_VARIABLE = "SHOPPING_COPILOT_POLICY_MODE"


@dataclass(frozen=True, slots=True)
class PolicyConfig:
    """Feature switches and bounded knobs for the dialogue decision layer."""

    name: str
    question_value: bool = False
    candidate_portfolio: bool = False
    response_semantics: bool = False
    evidence_fingerprint: bool = False
    other_max_asks: int = 1
    other_min_remaining_turns: int = 3
    other_routes: tuple[str, ...] = ("buying", "browsing", "override")
    other_value_floor: float = 0.0
    question_candidate_limit: int = 60
    portfolio_candidate_limit: int = 80
    browsing_precision_fraction: float = 0.70
    browsing_refined_fraction: float = 0.85
    override_precision_fraction: float = 0.75
    buying_precision_fraction: float = 0.95
    exploration_relevance_weight: float = 0.76
    exploration_novelty_weight: float = 0.24

    @classmethod
    def for_name(cls, raw_name: object) -> "PolicyConfig":
        name = str(raw_name or "control").strip().lower().replace("-", "_")
        modes = {
            "control": {},
            "question": {"question_value": True},
            "portfolio": {"candidate_portfolio": True},
            "question_portfolio": {
                "question_value": True,
                "candidate_portfolio": True,
            },
            "phase3": {
                "question_value": True,
                "candidate_portfolio": True,
            },
            "protocol_evidence": {
                "question_value": True,
                "candidate_portfolio": True,
                "response_semantics": True,
                "evidence_fingerprint": True,
                "other_max_asks": 2,
                "other_value_floor": 0.18,
            },
        }
        if name not in modes:
            valid = ", ".join(sorted(modes))
            raise ValueError(f"Unknown policy mode {name!r}; expected one of: {valid}")
        return cls(name=name, **modes[name])

    @classmethod
    def resolve(cls, explicit_name: str | None = None) -> "PolicyConfig":
        """Resolve an explicit mode, then an experiment override, then the default."""

        name = explicit_name
        if name is None:
            name = os.environ.get(POLICY_ENVIRONMENT_VARIABLE, DEFAULT_POLICY_MODE)
        return cls.for_name(name)
