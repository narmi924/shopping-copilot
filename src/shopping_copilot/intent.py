"""General rule-based intent routing."""

from __future__ import annotations

import re

from .constraints import is_override_message
from .models import ConstraintExtraction


BUYING_RE = re.compile(
    r"\b(?:need|must|require|requirement|required|under\s+\$?\d|budget|specific|exactly)\b",
    re.IGNORECASE,
)
BROWSING_RE = re.compile(
    r"\b(?:still\s+exploring|looking\s+for\s+ideas|open\s+to\s+ideas|not\s+sure|browsing|inspiration)\b",
    re.IGNORECASE,
)


class IntentRouter:
    ROUTES = frozenset({"buying", "browsing", "override"})

    def route(self, text: str, extraction: ConstraintExtraction) -> str:
        if is_override_message(text) or bool(extraction.metadata.get("override")):
            return "override"
        if BROWSING_RE.search(text):
            return "browsing"
        hard_attributes = {item.attribute for item in extraction.constraints} - {"category", "use_case"}
        if BUYING_RE.search(text) or hard_attributes:
            return "buying"
        return "browsing"
