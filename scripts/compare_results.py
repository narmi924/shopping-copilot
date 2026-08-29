"""Compare aggregate and scenario metrics from two evaluator outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


METRICS = ("hit_rate_at_10", "mrr", "mttc")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    rows: dict[str, dict[str, float]] = {}
    sections = ["overall", *sorted(set(baseline.get("scenario_metrics", {})) | set(candidate.get("scenario_metrics", {})))]
    for section in sections:
        old = baseline if section == "overall" else baseline.get("scenario_metrics", {}).get(section, {})
        new = candidate if section == "overall" else candidate.get("scenario_metrics", {}).get(section, {})
        rows[section] = {
            metric: round(float(new.get(metric, 0.0)) - float(old.get(metric, 0.0)), 6)
            for metric in METRICS
        }
    rows["overall"]["recommended_technical_score"] = round(
        float(candidate.get("recommended_technical_score", 0.0))
        - float(baseline.get("recommended_technical_score", 0.0)),
        6,
    )
    print(json.dumps(rows, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
