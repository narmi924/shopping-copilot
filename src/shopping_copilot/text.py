"""Deterministic text normalization helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation


TOKEN_RE = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*", re.IGNORECASE)
SPACE_RE = re.compile(r"\s+")
PRICE_RE = re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)")
THRESHOLD_BUDGET_RE = re.compile(
    r"\b(?:under|below|less\s+than|maximum|max|up\s+to)\s*\$?\s*(\d+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)

STOPWORDS = {
    "a", "about", "additional", "an", "and", "are", "as", "at", "be",
    "but", "by", "can", "could", "do", "does", "for", "from", "had",
    "has", "have", "having", "i", "if", "in", "is", "it", "its", "me",
    "my", "of", "on", "or", "please", "some", "that", "the", "their",
    "them", "these", "they", "this", "those", "to", "was", "were", "will",
    "with", "would", "you", "your",
}

CONVERSATION_NOISE = {
    "actually", "ask", "attribute", "closest", "different", "earlier", "exploring",
    "found", "here", "ignore", "judgement", "judgment", "key", "looking", "matters",
    "around", "below", "budget", "instead", "maximum", "need", "options", "preference",
    "preferences", "prioritize", "quite", "requirement", "requirements", "right", "specific",
    "still", "under", "use", "want", "what", "yet",
}

DECLINE_PATTERNS = (
    re.compile(r"\bno\s+preference\b", re.IGNORECASE),
    re.compile(r"\b(?:do\s+not|don['’]?t)\s+have\s+(?:a\s+)?preference\b", re.IGNORECASE),
    re.compile(r"\b(?:use|trust)\s+your\s+(?:best\s+)?judg(?:e)?ment\b", re.IGNORECASE),
    re.compile(r"\b(?:anything|either)\s+is\s+fine\b", re.IGNORECASE),
    re.compile(r"\bno\s+strong\s+feelings?\b", re.IGNORECASE),
    re.compile(r"\bindifferent\s+(?:to|about)\b", re.IGNORECASE),
    re.compile(r"\b(?:stop|don['’]?t\s+keep)\s+asking\b", re.IGNORECASE),
)

EXHAUSTED_PREFERENCE_RE = re.compile(
    r"\b(?:do\s+not|don['’]?t)\s+have\s+(?:an?\s+)?additional\s+preference\b|"
    r"\bno\s+additional\s+preference\b",
    re.IGNORECASE,
)

NO_QUESTION_FEEDBACK_RE = re.compile(
    r"\b(?:ask|tell)\s+me\s+(?:about\s+)?(?:one\s+)?specific\s+attribute\b",
    re.IGNORECASE,
)

CATEGORY_HINTS = {
    "accessories", "apparel", "backpack", "backpacks", "bag", "bags", "belt", "belts",
    "blazer", "blazers", "blouse", "blouses", "boot", "boots", "bra", "bras", "cap",
    "caps", "cardigan", "cardigans", "clothing", "coat", "coats", "costume", "costumes",
    "dress", "dresses", "earring", "earrings", "fashion", "glove", "gloves", "hat", "hats",
    "hoodie", "hoodies", "jacket", "jackets", "jeans", "jewelry", "leggings", "necklace",
    "necklaces", "pants", "purse", "purses", "ring", "rings", "sandal", "sandals", "scarf",
    "scarves", "shirt", "shirts", "shoe", "shoes", "shorts", "skirt", "skirts", "slipper",
    "slippers", "sneaker", "sneakers", "sock", "socks", "suit", "suits", "sweater",
    "sweaters", "sweatshirt", "sweatshirts", "swimwear", "tie", "ties", "top", "tops",
    "trouser", "trousers", "underwear", "uniform", "uniforms", "vest", "vests", "wallet",
    "wallets", "watch", "watches",
}

CATEGORY_CONTEXT = CATEGORY_HINTS | {
    "athletic", "baby", "boy", "boys", "child", "children", "girl", "girls", "kid", "kids",
    "hiking", "ladies", "lady", "men", "mens", "outdoor", "running", "travel", "unisex",
    "walking", "winter", "women", "womens", "workout",
}

ATTRIBUTE_NAMES = {
    "category", "material", "color", "size", "style", "brand", "budget", "feature", "use_case", "other"
}


def normalize_whitespace(value: object) -> str:
    return SPACE_RE.sub(" ", str(value or "")).strip()


def normalize_evidence_key(value: object, *, limit: int = 180) -> str:
    """Normalize a complete evidence value using the released catalog contract."""

    return normalize_whitespace(value).strip(" -;,.\t\n")[: max(0, int(limit))].rstrip()


def flatten_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(f"{key} {flatten_text(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple, set, frozenset)):
        return " ".join(flatten_text(item) for item in value)
    return str(value)


def unique_terms(values: Iterable[str], limit: int = 80) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        term = value.lower().strip()
        if not term or term in seen:
            continue
        seen.add(term)
        result.append(term)
        if len(result) >= limit:
            break
    return tuple(result)


def is_decline_message(text: str) -> bool:
    return any(pattern.search(text) for pattern in DECLINE_PATTERNS)


def is_exhausted_message(text: str) -> bool:
    """Return whether a slot has no undisclosed value without retracting old evidence."""

    return bool(EXHAUSTED_PREFERENCE_RE.search(text))


def is_no_question_feedback(text: str) -> bool:
    return bool(NO_QUESTION_FEEDBACK_RE.search(text))


def find_declined_attributes(text: str, last_asked: str | None = None) -> set[str]:
    if not is_decline_message(text):
        return set()
    lowered = text.lower().replace("use case", "use_case")
    mentioned = {attribute for attribute in ATTRIBUTE_NAMES if re.search(rf"\b{re.escape(attribute)}\b", lowered)}
    if mentioned:
        return mentioned
    return {last_asked} if last_asked in ATTRIBUTE_NAMES else set()


def find_exhausted_attributes(text: str, last_asked: str | None = None) -> set[str]:
    if not is_exhausted_message(text):
        return set()
    lowered = text.lower().replace("use case", "use_case")
    mentioned = {attribute for attribute in ATTRIBUTE_NAMES if re.search(rf"\b{re.escape(attribute)}\b", lowered)}
    if mentioned:
        return mentioned
    return {last_asked} if last_asked in ATTRIBUTE_NAMES else set()


def _price_token(raw: str) -> str | None:
    try:
        value = Decimal(raw).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    whole, fraction = f"{value:.2f}".split(".")
    return f"price{whole}_{fraction}"


def lexical_terms(text: str, *, limit: int = 80, include_price_tokens: bool = True) -> tuple[str, ...]:
    lowered = normalize_whitespace(text).lower().replace("’", "'")
    values = [
        token.lower()
        for token in TOKEN_RE.findall(lowered)
        if len(token) > 1 and token.lower() not in STOPWORDS and token.lower() not in CONVERSATION_NOISE
    ]
    if include_price_tokens:
        for match in PRICE_RE.finditer(lowered):
            prefix = lowered[max(0, match.start() - 18):match.start()]
            if re.search(r"\b(?:under|below|less\s+than|maximum|max|up\s+to)\s*$", prefix):
                continue
            token = _price_token(match.group(1))
            if token:
                values.insert(0, token)
    return unique_terms(values, limit)


def retrieval_terms(
    text: str,
    *,
    limit: int = 80,
    protocol_feedback: bool = True,
) -> tuple[str, ...]:
    if is_decline_message(text) or (protocol_feedback and is_exhausted_message(text)):
        return ()
    terms = list(lexical_terms(text, limit=limit))
    for match in THRESHOLD_BUDGET_RE.finditer(text):
        threshold_tokens = set(TOKEN_RE.findall(match.group(1).lower()))
        terms = [term for term in terms if term not in threshold_tokens]
    return unique_terms(terms, limit=limit)


def extract_category_terms(text: str) -> tuple[str, ...]:
    lowered = normalize_whitespace(text).lower()
    patterns = (
        re.compile(
            r"\b(?:looking|searching|shopping)\s+for\s+(.+?)(?=\s*,\s*(?:but|and)\b|\.\s|\s+a\s+key\s+requirement|$)",
            re.IGNORECASE,
        ),
        re.compile(r"\b(?:need|want)\s+(?:a|an|some)?\s*(.+?)(?=\s+with\b|\s+that\b|[,.]|$)", re.IGNORECASE),
    )
    for pattern in patterns:
        match = pattern.search(lowered)
        if match:
            terms = lexical_terms(match.group(1), limit=20, include_price_tokens=False)
            if terms:
                category_only = unique_terms((term for term in terms if term in CATEGORY_CONTEXT), limit=20)
                return category_only or terms
    tokens = lexical_terms(lowered, limit=50, include_price_tokens=False)
    return unique_terms((token for token in tokens if token in CATEGORY_HINTS), limit=12)


def price_index_text(value: object) -> str:
    if value in (None, ""):
        return ""
    raw = str(value).strip().replace("$", "")
    token = _price_token(raw)
    if not token:
        return raw
    whole = token.removeprefix("price").split("_", 1)[0]
    return f"{raw} {token} price{whole}"


def safe_profile_terms(profile: object, *, limit: int = 40) -> tuple[str, ...]:
    if not isinstance(profile, dict):
        return ()
    values: list[str] = []
    tags = profile.get("preference_tags")
    if isinstance(tags, (list, tuple)):
        values.extend(str(item) for item in tags if isinstance(item, (str, int, float)))
    summary = profile.get("summary")
    if isinstance(summary, str):
        values.append(summary)
    return lexical_terms(" ".join(values), limit=limit)
