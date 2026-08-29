# Shopping Copilot — Track 4

Shopping Copilot is an offline-first, state-aware conversational search and recommendation agent for TechJam Track 4. The official headless entry point remains `from starter.agent import Agent`; the FastAPI and React demo is an optional presentation layer over the same deterministic core.

The runtime calls no LLM, remote service, model, or production database. Product identifiers always come from the frozen 50,000-item catalog.

## Evaluated result

The unchanged official evaluator completed all 200 public sessions with zero model tokens.

| Metric | Official baseline | Current offline Agent | Absolute change |
|---|---:|---:|---:|
| Hit Rate@10 | 0.125000 | 0.840000 | +0.715000 |
| MRR | 0.068034 | 0.519359 | +0.451325 |
| MTTC (lower is better) | 9.810000 | 3.865000 | -5.945000 |
| Efficiency | 0.119000 | 0.713500 | +0.594500 |
| Recommended TechnicalScore | 0.106710 | 0.718508 | +0.611798 |

| Scenario | Baseline HR@10 | Current HR@10 | Change |
|---|---:|---:|---:|
| Buying | 0.237500 | 0.937500 | +0.700000 |
| Browsing | 0.025000 | 0.925000 | +0.900000 |
| Intent Override | 0.133333 | 0.400000 | +0.266667 |
| Boundary | 0.000000 | 0.700000 | +0.700000 |

The current configuration favors general budget and replacement safeguards over selecting rules for one public evaluation run. It was selected using public aggregates, generic metamorphic tests, and a private catalog-derived stress benchmark intended to reduce public-set overfitting risk. That synthetic benchmark is not an organizer holdout and is not evidence of private-set performance. Reproduction details and the V1-to-current progression are recorded in [docs/evaluation.md](docs/evaluation.md).

## Project layout

```text
shopping-copilot/
├── data/                    versioned public set + ignored frozen catalog
├── docs/official/           byte-identical official contract and rules
├── evaluator/               byte-identical official evaluator
├── starter/agent.py         thin official-interface adapter
├── src/shopping_copilot/    state, intent, constraints, retrieval, policy
├── tests/                   fast temporary-catalog and API tests
├── scripts/                 catalog, hash, and result verification
├── artifacts/metrics/       compact baseline and current metric summaries
├── demo/backend/            optional thin FastAPI adapter
└── frontend/                optional React + Vite + Ant Design demo
```

## Requirements

- Python `>=3.10` (verified with CPython `3.13.1`)
- uv `0.12.5` or ordinary `venv`/pip
- SQLite with FTS5 (included in the verified Python build)
- Node.js for the optional frontend (verified with Node `24.15.0`, npm `11.1.0`)

The evaluator/core has no third-party runtime dependency. FastAPI, pytest, and frontend packages are optional layers.

## Setup

PowerShell with uv:

```powershell
uv sync --extra test --extra demo
```

Ordinary Python:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[test,demo]"
```

Download `catalog.jsonl.gz` and `SHA256SUMS` from the official [Participant Kit Release](https://github.com/TechJam2026/techjam-conversational-search/releases/tag/participant-kit):

```powershell
$release = "https://github.com/TechJam2026/techjam-conversational-search/releases/download/participant-kit"
Invoke-WebRequest "$release/catalog.jsonl.gz" -OutFile data\catalog.jsonl.gz
Invoke-WebRequest "$release/SHA256SUMS" -OutFile data\SHA256SUMS

$checksumLine = @(Get-Content data\SHA256SUMS | Where-Object { $_ -match "catalog\.jsonl\.gz$" })
if ($checksumLine.Count -ne 1) { throw "catalog.jsonl.gz checksum entry not found" }
$expected = ($checksumLine[0] -split "\s+")[0].ToLowerInvariant()
$actual = (Get-FileHash data\catalog.jsonl.gz -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "catalog.jsonl.gz checksum mismatch" }
```

After the checksum passes, decompress the catalog with the Python standard library:

```powershell
@'
import gzip
import shutil
from pathlib import Path

source = Path("data/catalog.jsonl.gz")
target = Path("data/catalog.jsonl")
with gzip.open(source, "rb") as compressed, target.open("wb") as output:
    shutil.copyfileobj(compressed, output)
'@ | uv run python -
```

Validate its row count, identifiers, visible fields, and SHA256 without printing product records:

```powershell
uv run python scripts\inspect_catalog.py data\catalog.jsonl
```

The expected uncompressed SHA256 is `da979b05a68af864cb0dcf9ee6a81c010c7e66a57978ad286c7a2e005fc69a67`. `data/catalog.jsonl` is required locally but ignored by Git and must not be committed.

## Test and evaluate

```powershell
uv run --extra test --extra demo python -m pytest
uv run python -m evaluator.local_evaluator
uv run python scripts\verify_official_files.py
```

The adapter resolves `src` with `pathlib.Path`, so an installed project also works with ordinary `python -m evaluator.local_evaluator`.

## Run the optional demo

Terminal 1:

```powershell
uv run --extra demo uvicorn demo.backend.app:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
Set-Location frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173`. The UI provides conversation, enriched Top 10 product cards, a live Agent state/debug panel, and baseline/current evaluation metrics. It never participates in official evaluation.

## Implemented

- isolated `SessionState`, safe profile copies, deterministic reset semantics, and bounded diagnostics;
- history-aware current/constraint/stable/profile retrieval routes;
- Buying, Browsing, and Intent Override routing with slot-aware attribute/category replacement;
- explicit negative constraints, constraint provenance, and bounded dual hypotheses for ambiguous overrides;
- no-preference/declined-attribute handling that does not contaminate queries;
- in-memory SQLite FTS5, strict and broad retrieval tracks, weighted RRF, and bounded constraint-coverage reranking;
- structured budget scoring, deterministic fallbacks, catalog membership validation, and deduplication;
- clarification that does not repeat asked/declined attributes and always accompanies recommendations when candidates exist;
- optional FastAPI session adapter and React demo using the same Agent instance contract.

## Not implemented

- dense embeddings or dense retrieval;
- neural semantic reranking;
- external LLM calls;
- production authentication, commerce, inventory, or database services.

## Limitations

The slot vocabulary and regex rules cannot resolve every paraphrase, lexical retrieval cannot bridge arbitrary synonyms, and missing catalog prices limit strict budget filtering. Intent Override remains the weakest public scenario despite the phase-two gain. The first Agent construction loads and indexes the full catalog in memory; later turns benefit from bounded deterministic query/document caches.

This repository excludes the catalog, secrets, virtual environments, caches, `results.json`, `node_modules`, and frontend build output.
