# Optional product demo

The demo is an additive presentation layer. Official evaluation continues to import `starter.agent.Agent` and never starts FastAPI or React.

```text
React + Vite + Ant Design
  -> thin FastAPI session adapter
  -> same offline Agent core
  -> conversation + Top 10 product cards in one workspace
  -> compact shopping context + on-demand explainability
  -> on-demand evaluation summary
```

## Start locally

From `shopping-copilot`:

```powershell
uv run --extra demo uvicorn demo.backend.app:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
Set-Location frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to the local service.

The API owns presentation session IDs and serializes access to one lazily loaded Agent. Product card metadata is read from the same immutable catalog. The default UI is customer-facing: conversation, current turn, the attribute being refined, active shopping context, and the ranked shortlist stay visible. The on-demand context drawer distinguishes active, superseded, negative, declined, and exhausted state; it also shows the selected question's bounded factors, exact-evidence contribution, candidate count, ranking scores, and precision/exploration allocation. Benchmark comparisons remain in a separate modal instead of occupying the shopping workspace. Debug output contains only participant-owned state and presentation-safe retrieval scores; evaluator labels, raw catalog records, and private experiment data are never exposed.

Useful endpoints:

- `GET /api/health`
- `POST /api/sessions`
- `POST /api/sessions/{session_id}/turns`
- `GET /api/metrics`
- `GET /api/docs`

This scope intentionally excludes login, payment, cart, orders, inventory, administration, generated images, and production databases.
