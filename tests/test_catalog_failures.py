from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import shopping_copilot.catalog as catalog_module
from shopping_copilot.catalog import CatalogIndex


def _record(parent_asin: str) -> dict[str, object]:
    return {
        "parent_asin": parent_asin,
        "title": "Test product",
        "categories": ["Test"],
        "features": [],
        "details": {},
        "store": "Test store",
        "description": [],
        "price": 10.0,
        "average_rating": 4.0,
        "rating_number": 1,
    }


def test_catalog_requires_a_regular_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Catalog file not found"):
        CatalogIndex(tmp_path / "missing.jsonl")


def test_catalog_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "catalog.jsonl"
    path.write_text("{not-json}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid catalog JSON at line 1"):
        CatalogIndex(path)


def test_catalog_rejects_duplicate_identifiers(tmp_path: Path) -> None:
    path = tmp_path / "catalog.jsonl"
    path.write_text(
        "".join(json.dumps(_record("A")) + "\n" for _ in range(2)),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate parent_asin at line 2"):
        CatalogIndex(path)


def test_catalog_explains_missing_fts5(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class ConnectionWithoutFts:
        closed = False

        def execute(self, statement: str, *_args: object) -> None:
            if "CREATE VIRTUAL TABLE" in statement:
                raise sqlite3.OperationalError("no such module: fts5")

        def cursor(self) -> "ConnectionWithoutFts":
            return self

        def close(self) -> None:
            self.closed = True

    connection = ConnectionWithoutFts()
    monkeypatch.setattr(catalog_module.sqlite3, "connect", lambda *_args, **_kwargs: connection)
    path = tmp_path / "catalog.jsonl"
    path.write_text(json.dumps(_record("A")) + "\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="SQLite FTS5 support is required"):
        CatalogIndex(path)
    assert connection.closed is True
