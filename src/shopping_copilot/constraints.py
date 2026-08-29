"""Lightweight extraction of shopping constraints from customer messages."""

from __future__ import annotations

import re

from .models import Constraint, ConstraintExtraction, Replacement
from .text import (
    extract_category_terms,
    find_declined_attributes,
    find_exhausted_attributes,
    is_decline_message,
    is_exhausted_message,
    is_no_question_feedback,
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
    re.compile(r"\bwhat\s+i\s+(?:(?:actually|really)\s+)?need\s+is\b", re.IGNORECASE),
    re.compile(r"\bno\s+longer\b", re.IGNORECASE),
    re.compile(r"\b(?:prefer|choose|want|need)\b.+\b(?:rather|better)\s+than\b", re.IGNORECASE),
    re.compile(r"\bnot\b.+\bbut\b", re.IGNORECASE),
    re.compile(r"\bswitch\s+from\b.+\bto\b", re.IGNORECASE),
    re.compile(r"\banything\s+except\b", re.IGNORECASE),
    re.compile(r"\bforget\b", re.IGNORECASE),
    re.compile(r"\b(?:rather|better)\s+than\b", re.IGNORECASE),
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
        re.compile(r"\bwhat\s+i\s+(?:(?:actually|really)\s+)?need\s+is\s*:?\s*(.+)$", re.I),
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


def _clean_clause(value: str) -> str:
    cleaned = normalize_whitespace(value).strip(" -;,.:")
    cleaned = re.sub(
        r"^(?:actually\s*[,;:]?\s*|i(?:'ve|\s+have)?\s+changed\s+my\s+mind\s*(?:and|,|:)?\s*|"
        r"i\s+|please\s+|now\s+|instead\s+|choose\s+|make\s+it\s+|"
        r"(?:would\s+)?(?:prefer|want|need)\s+|prioritize\s+|"
        r"what\s+i\s+(?:(?:actually|really)\s+)?need\s+is\s*:?\s*)+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip(" -;,.")


def _contrast_clauses(text: str) -> tuple[str, str, float]:
    """Return old clause, new clause and confidence for generic contrasts."""

    normalized = normalize_whitespace(text)
    patterns = (
        (re.compile(r"\bswitch\s+from\s+(?P<old>.+?)\s+to\s+(?P<new>.+)$", re.I), 0.98),
        (re.compile(r"\bnot\s+(?P<old>.+?)\s*,?\s+but\s+(?P<new>.+)$", re.I), 0.98),
        (re.compile(r"(?P<new>.+?)\s+instead\s+of\s+(?P<old>.+)$", re.I), 0.97),
        (re.compile(r"(?P<new>.+?)\s+(?:rather|better)\s+than\s+(?P<old>.+)$", re.I), 0.95),
        (
            re.compile(
                r"\bno\s+longer\s+(?:want|need|prefer)?\s*(?P<old>.+?)[,;.]\s*"
                r"(?:i\s+)?(?:now\s+)?(?:prefer|want|need|prioritize)?\s*(?P<new>.+)$",
                re.I,
            ),
            0.94,
        ),
        (
            re.compile(r"\bno\s+longer\s+(?:want|need|prefer)?\s*(?P<old>.+)$", re.I),
            0.92,
        ),
        (
            re.compile(
                r"\banything\s+except\s+(?P<old>.+?)(?:[,;.]\s*(?P<new>.+))?$",
                re.I,
            ),
            0.90,
        ),
        (
            re.compile(
                r"\bforget\s+(?P<old>.+?)(?:[.;]\s*(?P<new>.+))?$",
                re.I,
            ),
            0.90,
        ),
    )
    for pattern, confidence in patterns:
        match = pattern.search(normalized)
        if not match:
            continue
        old_clause = _clean_clause(match.groupdict().get("old") or "")
        new_clause = _clean_clause(match.groupdict().get("new") or "")
        if old_clause or new_clause:
            return old_clause, new_clause, confidence

    new_patterns = (
        re.compile(r"\bwhat\s+i\s+(?:(?:actually|really)\s+)?need\s+is\s*:?\s*(?P<new>.+)$", re.I),
        re.compile(r"\bchanged?\s+my\s+mind\b[,;:]?\s*(?P<new>.+)$", re.I),
        re.compile(r"\binstead\b[,;:]?\s*(?P<new>.+)$", re.I),
    )
    for pattern in new_patterns:
        match = pattern.search(normalized)
        if match and _clean_clause(match.group("new")):
            return "", _clean_clause(match.group("new")), 0.78
    return "", "", 0.0


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


def _constraint(
    attribute: str,
    value: str,
    turn: int,
    *,
    status: str = "active",
    confidence: float = 1.0,
) -> Constraint | None:
    cleaned = normalize_whitespace(value).strip(" -;,.")
    terms = () if attribute == "budget" else lexical_terms(cleaned, limit=40)
    if not cleaned or (not terms and attribute != "budget"):
        return None
    return Constraint(
        attribute=attribute,
        value=cleaned,
        terms=terms,
        source_turn=turn,
        status=status,
        confidence=max(0.0, min(1.0, float(confidence))),
    )


def _explicit_clauses(text: str) -> list[str]:
    normalized = normalize_whitespace(text)
    for pattern in CLAUSE_PATTERNS:
        match = pattern.search(normalized)
        if match:
            return [part.strip(" -;,.") for part in re.split(r"\s*;\s*", match.group(1)) if part.strip(" -;,.")]
    return []


def extract_evidence_clauses(text: object) -> tuple[str, ...]:
    """Extract complete published evidence clauses without reducing them to tokens."""

    normalized = normalize_whitespace(text)
    patterns = (
        re.compile(r"\ba\s+key\s+requirement\s+is\s*:\s*(.+)$", re.I),
        re.compile(r"\bfor\s+that\s*,?\s+what\s+matters\s+is\s*:\s*(.+)$", re.I),
        re.compile(r"\bwhat\s+i\s+(?:(?:actually|really)\s+)?need\s+is\s*:\s*(.+)$", re.I),
    )
    for pattern in patterns:
        match = pattern.search(normalized)
        if not match:
            continue
        values = [part.strip(" -;,.\t\n") for part in re.split(r"\s*;\s*", match.group(1))]
        return tuple(dict.fromkeys(value for value in values if value))
    return ()


class ConstraintExtractor:
    """Extracts reusable constraints without depending on evaluator state."""

    def extract(
        self,
        text: object,
        turn: int,
        last_asked: str | None = None,
        *,
        protocol_feedback: bool = True,
    ) -> ConstraintExtraction:
        message = normalize_whitespace(text)
        override = is_override_message(message)
        old_clause, new_clause, replacement_confidence = _contrast_clauses(message) if override else ("", "", 0.0)
        analysis_message = new_clause or (_replacement_segment(message) if override else message)
        if override and old_clause and not new_clause:
            analysis_message = ""
        declined = find_declined_attributes(message, last_asked)
        exhausted = find_exhausted_attributes(message, last_asked)
        evidence_clauses = extract_evidence_clauses(message)
        if is_decline_message(message):
            return ConstraintExtraction(
                declined_attributes=declined,
                evidence_clauses=(),
                decline_only=True,
                metadata={
                    "override": override,
                    "override_scope": "global" if GLOBAL_OVERRIDE_RE.search(message) else "slots",
                    "replacement_text": "",
                    "source_turn": max(0, int(turn)),
                },
            )
        if protocol_feedback and is_exhausted_message(message):
            return ConstraintExtraction(
                exhausted_attributes=exhausted,
                evidence_clauses=(),
                decline_only=True,
                feedback_event="exhausted",
                metadata={
                    "override": False,
                    "override_scope": "none",
                    "replacement_text": "",
                    "source_turn": max(0, int(turn)),
                },
            )

        result = ConstraintExtraction(
            category_terms=extract_category_terms(analysis_message),
            retrieval_terms=retrieval_terms(
                analysis_message,
                protocol_feedback=protocol_feedback,
            ),
            evidence_clauses=evidence_clauses,
            feedback_event="no_question" if is_no_question_feedback(message) else None,
            metadata={
                "override": override,
                "override_scope": "global" if GLOBAL_OVERRIDE_RE.search(message) else "slots",
                "replacement_text": analysis_message if override else "",
                "source_turn": max(0, int(turn)),
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

        if override:
            old_constraints = self._segment_constraints(
                old_clause,
                turn,
                status="negative",
                confidence=replacement_confidence or 0.65,
            )
            old_slots = {item.attribute for item in old_constraints}
            new_slots = {item.attribute for item in result.constraints}
            old_categories = set(extract_category_terms(old_clause))
            new_categories = set(result.category_terms)
            category_changed = bool(
                old_categories
                and new_categories
                and old_categories.isdisjoint(new_categories)
            )
            global_scope = bool(GLOBAL_OVERRIDE_RE.search(message))
            if global_scope:
                replacement_type = "global"
            elif category_changed or (new_categories and not old_clause):
                replacement_type = "category"
            elif (old_slots & new_slots) - {"feature", "category"}:
                replacement_type = "attribute"
            elif old_clause and not new_clause:
                replacement_type = "negative"
            else:
                replacement_type = "ambiguous"

            if replacement_type == "category":
                affected_slots = ("category",)
            else:
                affected = (old_slots & new_slots) - {"feature", "category"}
                if not affected and replacement_type == "attribute":
                    affected = new_slots - {"feature", "category"}
                affected_slots = tuple(sorted(affected))
            if affected_slots:
                old_constraints = [item for item in old_constraints if item.attribute in affected_slots]
            result.negative_constraints = old_constraints
            result.replacement = Replacement(
                old_clause=old_clause,
                new_clause=analysis_message,
                affected_slots=affected_slots,
                replacement_type=replacement_type,
                confidence=replacement_confidence or (0.72 if analysis_message else 0.60),
                ambiguous=replacement_type == "ambiguous",
            )
            result.metadata.update(
                {
                    "override_scope": replacement_type,
                    "old_clause": old_clause,
                    "new_clause": analysis_message,
                    "replacement_type": replacement_type,
                    "replacement_confidence": result.replacement.confidence,
                }
            )
        return result

    def _segment_constraints(
        self,
        segment: str,
        turn: int,
        *,
        status: str,
        confidence: float,
    ) -> list[Constraint]:
        if not segment:
            return []
        lowered = segment.lower()
        tokens = set(lexical_terms(lowered, include_price_tokens=False))
        items: list[Constraint] = []
        for value in sorted(tokens & MATERIALS):
            if item := _constraint("material", value, turn, status=status, confidence=confidence):
                items.append(item)
        for value in sorted(tokens & COLORS):
            if item := _constraint("color", value, turn, status=status, confidence=confidence):
                items.append(item)
        for value in sorted(tokens & STYLES):
            if item := _constraint("style", value, turn, status=status, confidence=confidence):
                items.append(item)
        for value in sorted(tokens & USE_CASES):
            if item := _constraint("use_case", value, turn, status=status, confidence=confidence):
                items.append(item)
        size_match = SIZE_RE.search(lowered)
        if size_match and "size" in lowered:
            if item := _constraint("size", size_match.group(0), turn, status=status, confidence=confidence):
                items.append(item)
        budget_match = BUDGET_RE.search(lowered)
        if budget_match:
            if item := _constraint("budget", budget_match.group(0), turn, status=status, confidence=confidence):
                items.append(item)
        brand_match = BRAND_RE.search(segment)
        if brand_match:
            if item := _constraint("brand", brand_match.group(1), turn, status=status, confidence=confidence):
                items.append(item)
        category_terms = extract_category_terms(segment)
        if category_terms:
            if item := _constraint(
                "category",
                " ".join(category_terms),
                turn,
                status=status,
                confidence=confidence,
            ):
                items.append(item)
        deduplicated: dict[tuple[str, tuple[str, ...]], Constraint] = {}
        for item in items:
            deduplicated[(item.attribute, item.terms)] = item
        return list(deduplicated.values())
