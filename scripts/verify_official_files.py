"""Verify that protected local copies still match their recorded SHA256 values."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "artifacts" / "metrics" / "official_sha256_initial.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
    failures = 0
    for relative, expected_hash in expected.items():
        path = ROOT / Path(relative)
        actual = sha256(path)
        matches = actual == expected_hash
        failures += int(not matches)
        print(f"{'OK' if matches else 'CHANGED'}  {actual}  {relative}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
