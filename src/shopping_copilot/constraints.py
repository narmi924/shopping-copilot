"""Lightweight extraction of shopping constraints from customer messages."""

from __future__ import annotations

import re

from .models import Constraint, ConstraintExtraction
from .text import (
    extract_category_terms,
    find_declined_attributes,
    is_decline_message,
    lexical_terms,
    normalize_whitespace,
    retrieval_terms,
    unique_terms,
)


MATERIALS = {
    "canvas", "cashmere", "cotton", "denim", "fabric", "fleece", "leather", "linen",
    "mesh", "nylon", "polyester", "rayon", "rubber", "silk", "spandex", "suede", "wool",
}
COLORS = {
    "beige", "black", "blue", "bronze", "brown", "burgundy", "coral", "cream", "gold",
    "gray", "grey", "green", "ivory", "khaki", "lavender", "maroon", "navy", "orange",
    "pink", "purple", "red", "rose", "silver", "tan", "teal", "turquoise", "white", "yellow",
}
STYLES = {
    "athletic", "bohemian", "casual", "classic", "formal", "minimalist", "modern", "retro",
    "slim", "sporty", "streetwear", "traditional", "vintage", "western",
}
USE_CASES = {
    "beach", "business", "camping", "cycling", "dance", "everyday", "festival", "gym", "hiking",
    "outdoor", "party", "rain", "running", "school", "skiing", "sports", "travel",
    "wedding", "winter", "work", "workout", "yoga",
}

OVERRIDE_MARKERS = (
    re.compile(r"\bactually\b", re.IGNORECASE),
    re.compile(r"\binstead\b", re.IGNORECASE),
    re.compile(r"\bchanged?\s+my\s+mind\b", re.IGNORECASE),
    re.compile(r"\bignore\s+(?:all\s+)?(?:of\s+)?my\s+(?:earlier|previous|prior)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+i\s+(?:really\s+)?need\s+is\b", re.IGNORECASE),
    re.compile(r"\bno\s+longer\s+(?:want|need|prefer)\b", re.IGNORECASE),
    re.compile(r"\bprefer\b.+\brather\s+than\b", re.IGNORECASE),
)

GLOBAL_OVERRIDE_RE = re.compile(
    r"\b(?:ignore|forget|discard)\s+(?:all\s+)?(?:of\s+)?my\s+(?:earlier|previous|prior)\b|\bstart\s+over\b",
    re.IGNORECASE,
)

CLAUSE_PATTERNS = (
    re.compile(r"(?:key\s+requirement\s+is|what\s+matters\s+is|what\s+i\s+(?:really\s+)?need\s+is)\s*:\s*(.+)$", re.I),
    re.compile(r"\b(?:must\s+have|require|requires|required)\s+(.+)$", re.I),
)
SIZE_RE = re.compile(
    r"\b(?:size\s*)?(xxs|xs|small|medium|large|xl|xxl|xxxl|extra\s+small|extra\s+large|\d{1,2}(?:\.5)?)\b",
    re.IGNORECASE,
)
BUDGET_RE = re.compile(
    r"\b(?:budget(?:\s+is|\s+around)?|under|below|less\s+than|up\s+to|around|about)\s*\$?\s*(\d+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
BRAND_RE = re.compile(r"\b(?:brand(?:\s+is)?|made\s+by|from)\s*[:=]?\s*([a-z0-9][a-z0-9&' -]{1,35})", re.I)


def is_override_message(text: str) -> bool:
    normalized = normalize_whitespace(text)
    return any(pattern.search(normalized) for pattern in OVERRIDE_MARKERS)


def _replacement_segment(text: str) -> str:
    """Return only the new side of a generic override when identifiable."""

    normalized = normalize_whitespace(text)
    patterns = (
        re.compile(r"\bwhat\s+i\s+(?:really\s+)?need\s+is\s*:\s*(.+)$", re.I),
        re.compile(r"\bprefer\s+(.+?)\s+rather\s+than\s+.+$", re.I),
        re.compile(r"\b(?:want|need)\s+(.+?)\s+instead\s+of\s+.+$", re.I),
        re.compile(r"\binstead\s*[,;:]?\s*(?:i\s+)?(?:would\s+)?(?:prefer|want|need)?\s*(.+)$", re.I),
        re.compile(r"\bchanged?\s+my\s+mind\b[,:;]?\s*(?:i\s+)?(?:now\s+)?(?:prefer|want|need)?\s*(.+)$", re.I),
        re.compile(r"\bno\s+longer\s+(?:want|need|prefer)\s+.+?[,;]\s*(?:i\s+)?(?:now\s+)?(?:prefer|want|need)\s+(.+)$", re.I),
    )
    for pattern in patterns:
        match = pattern.search(normalized)
        if match and match.group(1).strip(" -;,."):
            return match.group(1).strip(" -;,.")
    return normalized


def classify_constraint_text(value: str) -> str:
    lowered = value.lower()
    tokens = set(lexical_terms(lowered, include_price_tokens=False))
    if BUDGET_RE.search(lowered) or "$" in lowered:
        return "budget"
    if tokens & MATERIALS:
        return "material"
    if "color" in tokens or tokens & COLORS:
        return "color"
    if "size" in tokens or "sizing" in tokens or SIZE_RE.search(lowered):
        return "size"
    if "brand" in tokens:
        return "brand"
    if tokens & USE_CASES:
        return "use_case"
    if "style" in tokens or tokens & STYLES:
        return "style"
    return "feature"


def _constraint(attribute: str, value: str, turn: int) -> Constraint | None:
    cleaned = normalize_whitespace(value).strip(" -;,.")
    terms = () if attribute == "budget" else lexical_terms(cleaned, limit=40)
    if not cleaned or (not terms and attribute != "budget"):
        return None
    return Constraint(attribute=attribute, value=cleaned, terms=terms, source_turn=turn)


def _explicit_clauses(text: str) -> list[str]:
    normalized = normalize_whitespace(text)
    for pattern in CLAUSE_PATTERNS:
        match = pattern.search(normalized)
        if match:
            return [part.strip(" -;,.") for part in re.split(r"\s*;\s*", match.group(1)) if part.strip(" -;,.")]
    return []


class ConstraintExtractor:
    """Extracts reusable constraints without depending on evaluator state."""

    def extract(self, text: object, turn: int, last_asked: str | None = None) -> ConstraintExtraction:
        message = normalize_whitespace(text)
        override = is_override_message(message)
        analysis_message = _replacement_segment(message) if override else message
        declined = find_declined_attributes(message, last_asked)
        if is_decline_message(message):
            return ConstraintExtraction(
                declined_attributes=declined,
                decline_only=True,
                metadata={
                    "override": override,
                    "override_scope": "global" if GLOBAL_OVERRIDE_RE.search(message) else "slots",
                },
            )

        result = ConstraintExtraction(
            category_terms=extract_category_terms(analysis_message),
            retrieval_terms=retrieval_terms(analysis_message),
            metadata={
                "override": override,
                "override_scope": "global" if GLOBAL_OVERRIDE_RE.search(message) else "slots",
                "replacement_text": analysis_message if override else "",
            },
        )
        lowered = analysis_message.lower()
        tokens = set(lexical_terms(lowered, include_price_tokens=False))

        for value in sorted(tokens & MATERIALS):
            item = _constraint("material", value, turn)
            if item:
                result.constraints.append(item)
        for value in sorted(tokens & COLORS):
            item = _constraint("color", value, turn)
            if item:
                result.constraints.append(item)

        size_match = SIZE_RE.search(lowered)
        if size_match and ("size" in lowered or size_match.group(1).lower() in {"xxs", "xs", "small", "medium", "large", "xl", "xxl", "xxxl"}):
            item = _constraint("size", size_match.group(0), turn)
            if item:
                result.constraints.append(item)

        budget_match = BUDGET_RE.search(lowered)
        if budget_match:
            item = _constraint("budget", budget_match.group(0), turn)
            if item:
                result.constraints.append(item)

        brand_match = BRAND_RE.search(analysis_message)
        if brand_match:
            item = _constraint("brand", brand_match.group(1), turn)
            if item:
                result.constraints.append(item)

        for value in sorted(tokens & STYLES):
            item = _constraint("style", value, turn)
            if item:
                result.constraints.append(item)
        for value in sorted(tokens & USE_CASES):
            item = _constraint("use_case", value, turn)
            if item:
                result.constraints.append(item)
        if override and "walking" in tokens:
            item = _constraint("use_case", "walking", turn)
            if item:
                result.constraints.append(item)

        if result.category_terms:
            item = _constraint("category", " ".join(result.category_terms), turn)
            if item:
                result.constraints.append(item)

        for clause in _explicit_clauses(analysis_message):
            item = _constraint(classify_constraint_text(clause), clause, turn)
            if item:
                result.constraints.append(item)

        deduplicated: list[Constraint] = []
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for item in result.constraints:
            key = (item.attribute, item.terms)
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(item)
        result.constraints = deduplicated
        result.retrieval_terms = unique_terms(result.retrieval_terms, limit=80)
        return result
