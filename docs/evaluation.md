# Evaluation

All reported results use the unmodified evaluator and 200-session public set from
the official Participant Kit. The Agent reads only its documented inputs and the
frozen catalog. It does not read labels, scenario metadata, or evaluator state at
runtime, and it reports zero model-token usage.

## Environment

- Completed: 2026-08-29
- Python: CPython 3.13.1
- uv: 0.12.5
- OS: Microsoft Windows 10.0.26200, x64
- Evaluator command: `uv run python -m evaluator.local_evaluator`
- Test command: `uv run --extra test --extra demo python -m pytest`

Metric summaries are versioned in:

- `artifacts/metrics/official_baseline.json`
- `artifacts/metrics/v2_final_offline.json`

These files intentionally contain aggregate results rather than per-session
evaluator output.

## Official baseline reproduction

Before changing `starter/agent.py`, the weak-BM25 starter completed all 200
sessions in 24.204 seconds. Its published metrics were reproduced exactly.

| Metric | Value |
|---|---:|
| Hit Rate@10 | 0.125000 |
| MRR | 0.068034 |
| MTTC | 9.810000 |
| Efficiency | 0.119000 |
| Recommended TechnicalScore | 0.106710 |

| Scenario | Sessions | Hit Rate@10 | MRR | MTTC |
|---|---:|---:|---:|---:|
| Buying | 80 | 0.237500 | 0.126508 | 8.625000 |
| Browsing | 80 | 0.025000 | 0.004514 | 10.750000 |
| Intent Override | 30 | 0.133333 | 0.104167 | 10.066667 |
| Boundary | 10 | 0.000000 | 0.000000 | 11.000000 |

## V1 stateful lexical agent

The first implementation tested whether explicit session state, active
constraints, conservative override handling, multiple lexical routes, and
non-repeating clarification could improve a stateless lexical baseline.

V1 added:

- a one-pass in-memory SQLite FTS5 catalog index;
- isolated session state and explicit state transitions;
- constraint and no-preference extraction;
- Buying, Browsing, and Intent Override routing;
- current, active-constraint, stable-context, and low-weight profile queries;
- deterministic weighted Reciprocal Rank Fusion;
- simultaneous clarification and Top K recommendations.

| Metric | Baseline | V1 | Absolute change |
|---|---:|---:|---:|
| Hit Rate@10 | 0.125000 | 0.595000 | +0.470000 |
| MRR | 0.068034 | 0.373899 | +0.305865 |
| MTTC | 9.810000 | 5.960000 | -3.850000 |
| Efficiency | 0.119000 | 0.504000 | +0.385000 |
| Recommended TechnicalScore | 0.106710 | 0.510470 | +0.403760 |

| Scenario | Baseline HR@10 | V1 HR@10 | Change |
|---|---:|---:|---:|
| Buying | 0.237500 | 0.687500 | +0.450000 |
| Browsing | 0.025000 | 0.612500 | +0.587500 |
| Intent Override | 0.133333 | 0.300000 | +0.166667 |
| Boundary | 0.000000 | 0.600000 | +0.600000 |

## Final offline agent

The final version keeps the V1 state model and adds bounded strict/broad
retrieval, deterministic search caches, field-aware constraint coverage,
structured budget scoring, and conservative global-versus-slot override
reduction. The selected configuration favors general rules and hidden-test
robustness over maximizing one public run.

The representative final evaluator run completed in 138.458 seconds.

| Metric | Baseline | Final | Absolute change |
|---|---:|---:|---:|
| Hit Rate@10 | 0.125000 | 0.835000 | +0.710000 |
| MRR | 0.068034 | 0.515817 | +0.447783 |
| MTTC | 9.810000 | 3.890000 | -5.920000 |
| Efficiency | 0.119000 | 0.711000 | +0.592000 |
| Recommended TechnicalScore | 0.106710 | 0.714445 | +0.607735 |

| Scenario | Baseline HR@10 | Final HR@10 | Change | Baseline MRR | Final MRR |
|---|---:|---:|---:|---:|---:|
| Buying | 0.237500 | 0.937500 | +0.700000 | 0.126508 | 0.576538 |
| Browsing | 0.025000 | 0.925000 | +0.900000 | 0.004514 | 0.564732 |
| Intent Override | 0.133333 | 0.366667 | +0.233334 | 0.104167 | 0.190635 |
| Boundary | 0.000000 | 0.700000 | +0.700000 | 0.000000 | 0.614286 |

## Interpretation

History-aware retrieval produces the largest improvements for Buying and
Browsing sessions. Declined-attribute handling and stable query retention also
raise Boundary performance without feeding conversational filler into FTS.

Intent Override improves over the starter but remains the weakest route. A
deterministic rule set cannot always infer whether a paraphrase replaces one
attribute or changes the product category. The implementation therefore clears
soft constraints conservatively, preserves stable context only when compatible,
and gives the replacement side the highest retrieval priority.

## Current limitations

1. Lexical rules cannot resolve arbitrary paraphrases or product synonyms.
2. Missing catalog prices prevent strict enforcement of some budget constraints.
3. Cold startup parses 50,000 JSONL rows and builds an in-memory FTS5 index.

Dense retrieval, neural reranking, external LLMs, and remote services are outside
the current offline implementation.
