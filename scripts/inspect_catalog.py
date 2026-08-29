"""Validate the official catalog without printing product content."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


OFFICIAL_CATALOG_ROWS = 50_000
OFFICIAL_CATALOG_SHA256 = (
    "da979b05a68af864cb0dcf9ee6a81c010c7e66a57978ad286c7a2e005fc69a67"
)
VISIBLE_FIELDS = (
    "parent_asin",
    "title",
    "features",
    "description",
    "price",
    "categories",
    "details",
    "average_rating",
    "rating_number",
    "store",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect(
    path: Path,
    *,
    expected_rows: int | None = None,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Return structural and integrity statistics for a JSONL catalog."""

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Catalog is not a regular file: {path}")

    actual_sha256 = sha256(path)
    type_counts = {field: Counter() for field in VISIBLE_FIELDS}
    missing_fields: Counter[str] = Counter()
    identifiers: Counter[str] = Counter()
    rows = 0
    errors = 0
    invalid_identifiers = 0

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            rows += 1
            try:
                product = json.loads(line)
            except json.JSONDecodeError:
                errors += 1
                continue
            if not isinstance(product, dict):
                errors += 1
                continue

            identifier = product.get("parent_asin")
            if not isinstance(identifier, str) or not identifier.strip():
                invalid_identifiers += 1
            else:
                identifiers[identifier] += 1

            for field in VISIBLE_FIELDS:
                if field not in product:
                    missing_fields[field] += 1
                type_counts[field][type(product.get(field)).__name__] += 1

    duplicate_values = sum(1 for count in identifiers.values() if count > 1)
    row_count_matches = expected_rows is None or rows == expected_rows
    sha256_matches = (
        expected_sha256 is None
        or actual_sha256.casefold() == expected_sha256.casefold()
    )
    valid = not any(
        (
            errors,
            invalid_identifiers,
            duplicate_values,
            sum(missing_fields.values()),
            not row_count_matches,
            not sha256_matches,
        )
    )

    return {
        "path": str(path),
        "sha256": actual_sha256,
        "sha256_matches": sha256_matches,
        "rows": rows,
        "row_count_matches": row_count_matches,
        "json_or_shape_errors": errors,
        "invalid_parent_asin": invalid_identifiers,
        "unique_parent_asin": len(identifiers),
        "duplicate_parent_asin_values": duplicate_values,
        "missing_fields": dict(sorted(missing_fields.items())),
        "field_types": {
            field: dict(sorted(counts.items()))
            for field, counts in type_counts.items()
        },
        "valid": valid,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate the frozen official catalog without printing records."
    )
    parser.add_argument(
        "catalog",
        nargs="?",
        type=Path,
        default=Path("data/catalog.jsonl"),
    )
    args = parser.parse_args()
    result = inspect(
        args.catalog,
        expected_rows=OFFICIAL_CATALOG_ROWS,
        expected_sha256=OFFICIAL_CATALOG_SHA256,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
