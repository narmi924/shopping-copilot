"""Thin FastAPI presentation adapter over the unchanged Agent interface."""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from shopping_copilot.agent import Agent


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG_PATH = PROJECT_ROOT / "data" / "catalog.jsonl"
DEFAULT_METRICS_PATH = PROJECT_ROOT / "artifacts" / "metrics" / "v2_final_offline.json"
BASELINE_METRICS_PATH = PROJECT_ROOT / "artifacts" / "metrics" / "official_baseline.json"


class CreateSessionRequest(BaseModel):
    user_profile: dict[str, Any] = Field(default_factory=dict)


class TurnRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=10)


@dataclass(slots=True)
class DemoSession:
    turn: int = 0


def _metric_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "sample_count": payload.get("sample_count", 0),
        "hit_rate_at_10": payload.get("hit_rate_at_10", 0.0),
        "mrr": payload.get("mrr", 0.0),
        "mttc": payload.get("mttc"),
        "efficiency": payload.get("efficiency", 0.0),
        "recommended_technical_score": payload.get("recommended_technical_score", 0.0),
        "scenario_metrics": payload.get("scenario_metrics", {}),
        "reported_token_usage": payload.get("reported_token_usage", {}),
    }


class DemoService:
    """Owns presentation sessions while delegating all reasoning to Agent."""

    def __init__(
        self,
        catalog_path: Path,
        metrics_path: Path,
        baseline_metrics_path: Path,
        agent: Agent | None = None,
    ) -> None:
        self.catalog_path = Path(catalog_path)
        self.metrics_path = Path(metrics_path)
        self.baseline_metrics_path = Path(baseline_metrics_path)
        self._agent = agent
        self._sessions: dict[str, DemoSession] = {}
        self._lock = threading.RLock()

    @property
    def loaded(self) -> bool:
        return self._agent is not None

    def _get_agent(self) -> Agent:
        if self._agent is None:
            self._agent = Agent(self.catalog_path)
        return self._agent

    def create_session(self, user_profile: dict[str, Any]) -> str:
        with self._lock:
            identifier = uuid.uuid4().hex
            self._get_agent().reset(identifier, user_profile)
            self._sessions[identifier] = DemoSession()
            return identifier

    def turn(self, session_id: str, request: TurnRequest) -> dict[str, Any]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)
            session.turn += 1
            agent = self._get_agent()
            response = agent.respond(session_id, request.message, session.turn, request.top_k)
            debug = agent.debug_snapshot(session_id)
            score_by_id = {
                item["parent_asin"]: item["score"]
                for item in debug["final_ranking_scores"]
            }
            products: list[dict[str, Any]] = []
            for item in response["recommendations"]:
                identifier = item["parent_asin"]
                product = agent.catalog.get_product(identifier)
                if product is None:
                    continue
                products.append(
                    {
                        "parent_asin": product.parent_asin,
                        "title": product.title or "Untitled product",
                        "price": product.price,
                        "categories": list(product.categories),
                        "store": product.store or "Independent seller",
                        "average_rating": product.average_rating,
                        "rating_number": product.rating_number,
                        "feature": product.features[0] if product.features else "",
                        "ranking_score": score_by_id.get(identifier, 0.0),
                    }
                )
            return {
                "session_id": session_id,
                "turn": session.turn,
                "message": response["message"],
                "ask_attribute": response["ask_attribute"],
                "recommendations": products,
                "debug": debug,
            }

    def metrics(self) -> dict[str, Any]:
        if not self.metrics_path.is_file() or not self.baseline_metrics_path.is_file():
            raise FileNotFoundError("Evaluation metrics are not available")
        candidate = json.loads(self.metrics_path.read_text(encoding="utf-8"))
        baseline = json.loads(self.baseline_metrics_path.read_text(encoding="utf-8"))
        return {
            "candidate": _metric_summary(candidate),
            "baseline": _metric_summary(baseline),
            "label": "Final offline agent",
        }


def create_app(
    *,
    agent: Agent | None = None,
    catalog_path: Path | None = None,
    metrics_path: Path | None = None,
    baseline_metrics_path: Path | None = None,
) -> FastAPI:
    configured_catalog = catalog_path or Path(os.environ.get("SHOPPING_COPILOT_CATALOG", DEFAULT_CATALOG_PATH))
    service = DemoService(
        configured_catalog,
        metrics_path or DEFAULT_METRICS_PATH,
        baseline_metrics_path or BASELINE_METRICS_PATH,
        agent=agent,
    )
    application = FastAPI(
        title="Shopping Copilot Demo API",
        version="2.4.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    application.state.demo_service = service
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @application.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "mode": "offline",
            "catalog_ready": service.catalog_path.is_file(),
            "catalog_loaded": service.loaded,
        }

    @application.post("/api/sessions", status_code=201)
    def create_session(request: CreateSessionRequest) -> dict[str, Any]:
        try:
            identifier = service.create_session(request.user_profile)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"session_id": identifier, "turn": 0}

    @application.post("/api/sessions/{session_id}/turns")
    def run_turn(session_id: str, request: TurnRequest) -> dict[str, Any]:
        try:
            return service.turn(session_id, request)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc

    @application.get("/api/metrics")
    def metrics() -> dict[str, Any]:
        try:
            return service.metrics()
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return application


app = create_app()
