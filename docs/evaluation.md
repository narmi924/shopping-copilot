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
- `artifacts/metrics/phase2_override_v2.json`

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

## Phase-two control

The public `main` commit at the start of phase two was preserved as the control.
It combines strict/broad lexical retrieval, deterministic caches, field-aware
constraint coverage, structured budget scoring, and conservative replacement.
The controlled rerun took 67.169 seconds with an approximately 565.11 MiB peak
process-tree working set.

| Metric | Control |
|---|---:|
| Hit Rate@10 | 0.835000 |
| MRR | 0.515817 |
| MTTC | 3.890000 |
| Efficiency | 0.711000 |
| Recommended TechnicalScore | 0.714445 |

| Scenario | Hits | HR@10 | MRR |
|---|---:|---:|---:|
| Buying | 75/80 | 0.937500 | 0.576538 |
| Browsing | 74/80 | 0.925000 | 0.564732 |
| Intent Override | 11/30 | 0.366667 | 0.190635 |
| Boundary | 7/10 | 0.700000 | 0.614286 |

## Selected Override V2 experiment

The accepted phase-two candidate adds structured old/new contrast parsing,
constraint provenance, explicit negative state, category-aware cleanup,
bounded dual hypotheses for ambiguous replacements, and override-only
violation-aware reranking. It does not add a model, runtime dependency, remote
service, or non-deterministic component.

| Metric | Control | Override V2 | Change |
|---|---:|---:|---:|
| Hit Rate@10 | 0.835000 | 0.840000 | +0.005000 |
| MRR | 0.515817 | 0.519359 | +0.003542 |
| MTTC | 3.890000 | 3.865000 | -0.025000 |
| Efficiency | 0.711000 | 0.713500 | +0.002500 |
| Recommended TechnicalScore | 0.714445 | 0.718508 | +0.004063 |

| Scenario | Control hits | V2 hits | Control HR@10 | V2 HR@10 | Control MRR | V2 MRR |
|---|---:|---:|---:|---:|---:|---:|
| Buying | 75 | 75 | 0.937500 | 0.937500 | 0.576538 | 0.576538 |
| Browsing | 74 | 74 | 0.925000 | 0.925000 | 0.564732 | 0.564732 |
| Intent Override | 11 | 12 | 0.366667 | 0.400000 | 0.190635 | 0.214246 |
| Boundary | 7 | 7 | 0.700000 | 0.700000 | 0.614286 | 0.614286 |

The selected metric run completed in 64.154 seconds (0.955 times the control
wall clock); the final verification repeat took 71.935 seconds (1.071 times
control). A separate process-memory run measured approximately 557.62 MiB peak
working set. All 49 tests passed.

### Private unseen-target stress benchmark

A deterministic 160-session catalog-derived benchmark excluded all 200 public
target identifiers and used 40 sessions per scenario. It selected metadata-rich
products across diverse categories with a fixed seed and used a report template
group distinct from development diagnostics. Target identifiers existed only in
the private scorer and were never passed to the Agent.

| Scenario | Control hits | V2 hits | Control HR@10 | V2 HR@10 | Control MRR | V2 MRR |
|---|---:|---:|---:|---:|---:|---:|
| Buying | 37 | 37 | 0.925000 | 0.925000 | 0.576409 | 0.576409 |
| Browsing | 11 | 11 | 0.275000 | 0.275000 | 0.143750 | 0.143750 |
| Intent Override | 19 | 29 | 0.475000 | 0.725000 | 0.229167 | 0.517599 |
| Boundary | 33 | 33 | 0.825000 | 0.825000 | 0.634673 | 0.634673 |
| Overall | 100 | 110 | 0.625000 | 0.687500 | 0.396000 | 0.468108 |

Its TechnicalScore rose from 0.542238 to 0.604807. This is a synthetic stress
benchmark, not an organizer holdout, and it is not evidence of private-set
performance.

### Rejected latent semantic experiment

An optional catalog-derived word TF-IDF route with 96-component deterministic
SVD was tested after Override V2. The index built in 16.56 seconds, produced a
32.96 MB ignored cache, and used approximately 884.8 MiB peak memory while
building. It did not improve synthetic Browsing HR@10 (11/40 for both) and
improved Browsing MRR by only 0.002321. The combined public run also lost the
Override V2 hit gain, returning to 11/30. The experiment was rejected; its code,
dependency, and generated index are not part of the selected implementation.

## Interpretation

The public control failure analysis found that 32 of 33 missed targets entered a
lexical route but ranked below Top 10. That evidence favored bounded replacement
reranking over a larger pool. Override V2 improves both the public aggregate and
the unseen-target replacement stress cases without changing Buying, Browsing, or
Boundary hit counts. The semantic result reinforces that added complexity should
not be kept when it does not improve the intended unseen-target slice.

## Current limitations

1. Lexical rules still cannot resolve arbitrary paraphrases or product synonyms.
2. Missing catalog prices prevent strict enforcement of some budget constraints.
3. Cold startup parses 50,000 JSONL rows and builds an in-memory FTS5 index.

Dense retrieval, neural reranking, external LLMs, and remote services are outside
the current offline implementation.
