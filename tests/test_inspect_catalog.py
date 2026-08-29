from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.inspect_catalog import VISIBLE_FIELDS, inspect


def _product(parent_asin: str) -> dict:
    product = {field: None for field in VISIBLE_FIELDS}
    product.update(
        {
            "parent_asin": parent_asin,
            "title": "Test product",
            "features": [],
            "description": [],
            "price": 10.0,
            "categories": ["Test"],
            "details": {},
            "average_rating": 4.0,
            "rating_number": 1,
            "store": "Test store",
        }
    )
    return product


def _write_catalog(path: Path, products: list[dict]) -> str:
    payload = "".join(json.dumps(product) + "\n" for product in products)
    path.write_bytes(payload.encode("utf-8"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_inspect_accepts_matching_catalog(tmp_path: Path) -> None:
    path = tmp_path / "catalog.jsonl"
    expected_hash = _write_catalog(path, [_product("A"), _product("B")])

    result = inspect(path, expected_rows=2, expected_sha256=expected_hash)

    assert result["valid"] is True
    assert result["rows"] == 2
    assert result["unique_parent_asin"] == 2
    assert result["missing_fields"] == {}
    assert result["sha256_matches"] is True


def test_inspect_rejects_duplicates_and_missing_fields(tmp_path: Path) -> None:
    path = tmp_path / "catalog.jsonl"
    incomplete = _product("A")
    del incomplete["store"]
    _write_catalog(path, [_product("A"), incomplete])

    result = inspect(path, expected_rows=2)

    assert result["valid"] is False
    assert result["duplicate_parent_asin_values"] == 1
    assert result["missing_fields"] == {"store": 1}


def test_inspect_rejects_wrong_hash_or_row_count(tmp_path: Path) -> None:
    path = tmp_path / "catalog.jsonl"
    _write_catalog(path, [_product("A")])

    result = inspect(path, expected_rows=2, expected_sha256="0" * 64)

    assert result["valid"] is False
    assert result["row_count_matches"] is False
    assert result["sha256_matches"] is False


def test_inspect_requires_a_regular_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        inspect(tmp_path)
