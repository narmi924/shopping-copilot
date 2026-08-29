from __future__ import annotations

import json

from fastapi.testclient import TestClient

from demo.backend.app import create_app
from shopping_copilot.agent import Agent


def _metrics(path) -> None:
    payload = {
        "sample_count": 200,
        "hit_rate_at_10": 0.85,
        "mrr": 0.516187,
        "mttc": 3.825,
        "efficiency": 0.7175,
        "recommended_technical_score": 0.723356,
        "scenario_metrics": {"buying": {"hit_rate_at_10": 0.925}},
        "reported_token_usage": {"total_tokens": 0},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_demo_health_session_turn_and_debug(catalog_path, tmp_path) -> None:
    metrics_path = tmp_path / "metrics.json"
    baseline_path = tmp_path / "baseline.json"
    _metrics(metrics_path)
    _metrics(baseline_path)
    client = TestClient(
        create_app(
            agent=Agent(catalog_path),
            metrics_path=metrics_path,
            baseline_metrics_path=baseline_path,
        )
    )

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["mode"] == "offline"

    created = client.post(
        "/api/sessions",
        json={"user_profile": {"preference_tags": ["running"], "summary": "active shopper"}},
    )
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    turn = client.post(
        f"/api/sessions/{session_id}/turns",
        json={"message": "I need red cotton running shoes.", "top_k": 3},
    )
    assert turn.status_code == 200
    payload = turn.json()
    assert payload["turn"] == 1
    assert payload["ask_attribute"]
    assert payload["recommendations"][0]["parent_asin"] == "A_RED_COTTON_SHOE"
    assert payload["recommendations"][0]["title"]
    assert payload["debug"]["detected_route"] == "buying"
    assert payload["debug"]["retrieval_sources"]
    assert "negative_constraints" in payload["debug"]
    assert "exhausted_attributes" in payload["debug"]
    assert payload["debug"]["question_value"]["attribute"] == payload["ask_attribute"]
    assert payload["debug"]["candidate_portfolio"]["precision_count"] > 0

    evidence_turn = client.post(
        f"/api/sessions/{session_id}/turns",
        json={
            "message": "For that, what matters is: breathable cotton upper.",
            "top_k": 3,
        },
    )
    assert evidence_turn.status_code == 200
    evidence_source = evidence_turn.json()["debug"]["retrieval_sources"]["evidence"]
    assert evidence_source["mode"] == "exact-evidence"
    assert evidence_source["candidate_count"] == 1

    metrics = client.get("/api/metrics")
    assert metrics.status_code == 200
    assert metrics.json()["candidate"]["recommended_technical_score"] == 0.723356


def test_demo_rejects_unknown_session(catalog_path) -> None:
    client = TestClient(create_app(agent=Agent(catalog_path)))
    response = client.post(
        "/api/sessions/missing/turns",
        json={"message": "running shoes", "top_k": 10},
    )
    assert response.status_code == 404
