from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_LABEL_NAMES = {
    "public_set",
    "ground_truth",
    "intent_card",
    "behavior",
    "scenario_type",
    "sample_id",
}


def _runtime_sources() -> list[Path]:
    return [
        *sorted((PROJECT_ROOT / "src" / "shopping_copilot").rglob("*.py")),
        PROJECT_ROOT / "starter" / "agent.py",
    ]


def test_runtime_sources_do_not_reference_labels_or_evaluator_modules() -> None:
    for path in _runtime_sources():
        source = path.read_text(encoding="utf-8")
        lowered = source.lower()
        identifiers = set(re.findall(r"[a-z_][a-z0-9_]*", lowered))
        assert not (FORBIDDEN_LABEL_NAMES & identifiers)

        tree = ast.parse(source, filename=str(path))
        imported_modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported_modules.update(
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        assert not any(name == "evaluator" or name.startswith("evaluator.") for name in imported_modules)


def test_agent_runs_with_only_adapter_implementation_and_catalog(
    tmp_path: Path,
    catalog_path: Path,
) -> None:
    isolated = tmp_path / "isolated-runtime"
    shutil.copytree(PROJECT_ROOT / "src" / "shopping_copilot", isolated / "src" / "shopping_copilot")
    shutil.copytree(PROJECT_ROOT / "starter", isolated / "starter")
    shutil.copy2(catalog_path, isolated / "catalog.jsonl")

    script = """
import json
from pathlib import Path
from starter.agent import Agent

agent = Agent(Path("catalog.jsonl"))
agent.reset("isolated", {"summary": "travel"})
response = agent.respond("isolated", "I need a navy travel backpack.", 1, 3)
assert isinstance(response["message"], str)
assert len(response["recommendations"]) <= 3
assert all(item["parent_asin"] for item in response["recommendations"])
print(json.dumps({"count": len(response["recommendations"])}))
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(isolated / "src"), str(isolated)))
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=isolated,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["count"] > 0
    assert not (isolated / "data" / "public_set.jsonl").exists()
    assert not (isolated / "evaluator").exists()
