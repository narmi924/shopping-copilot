"""Thin compatibility adapter used by the official evaluator."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from shopping_copilot.agent import Agent  # noqa: E402


__all__ = ["Agent"]
