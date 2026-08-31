# Evaluation

All official public results use the unmodified evaluator and 200-session public
set from the official Participant Kit. Development diagnostics are labeled
separately and are not organizer evaluations. The selected Agent reads only its
documented inputs and the frozen catalog. It does not read labels, scenario
metadata, or evaluator state at runtime, and it reports zero model-token usage.

## Environment

- Completed: 2026-08-29
- Python: CPython 3.13.1
- uv: 0.12.5
- OS: Microsoft Windows 10.0.26200, x64
- Evaluator command: `uv run python -m evaluator.local_evaluator`
- Test command: `uv run --extra test --extra demo python -m pytest`

## Final evaluation freeze

The Devpost-submitted Git commit is the frozen solution. After the 800-session
final package is released following the submission deadline, that commit must
be run with the unmodified official evaluator; the complete `results.json`,
commit SHA, environment, and execution details must be retained. The official
policy permits network and external API use and does not require an offline
fallback, but those permissions do not change this selected offline runtime.
See the byte-identical [official final-evaluation FAQ](official/final_evaluation_faq.md).

Metric summaries are versioned in:

- `artifacts/metrics/official_baseline.json`
- `artifacts/metrics/v2_final_offline.json`
- `artifacts/metrics/phase2_override_v2.json`
- `artifacts/metrics/phase3_decision_policy.json`
- `artifacts/metrics/phase4_protocol_evidence.json`

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

## Phase-three decision policy

Phase three tested whether better dialogue decisions and Top-10 set construction
could address the dominant retrieved-below-Top-10 failure mode. It added a
read-only candidate facet view, a Question Value Estimator, and a lower-rank
exploration tail while retaining the existing lexical index, constraint ledger,
reranker, and zero-token offline runtime.

| Metric | Override V2 control | Decision policy | Change |
|---|---:|---:|---:|
| Hit Rate@10 | 0.840000 | 0.915000 | +0.075000 |
| MRR | 0.519359 | 0.561236 | +0.041877 |
| MTTC | 3.865000 | 4.400000 | +0.535000 |
| Efficiency | 0.713500 | 0.660000 | -0.053500 |
| Recommended TechnicalScore | 0.718508 | 0.757871 | +0.039363 |

| Scenario | Control hits | Current hits | Control HR@10 | Current HR@10 | Current MRR |
|---|---:|---:|---:|---:|---:|
| Buying | 75 | 75 | 0.937500 | 0.937500 | 0.528309 |
| Browsing | 74 | 75 | 0.925000 | 0.937500 | 0.566190 |
| Intent Override | 12 | 25 | 0.400000 | 0.833333 | 0.607037 |
| Boundary | 7 | 8 | 0.700000 | 0.800000 | 0.647619 |

### Two unseen-target checks

The unchanged broad stress benchmark retained its 160 sessions and 40 sessions
per scenario. The second target-like benchmark used 200 different catalog
targets while approximately matching aggregate public-target category,
popularity, rating, price-presence, completeness, and field-availability
distributions. Both use fixed seeds, exclude all public target identifiers, and
keep targets and per-session output outside this repository.

| Benchmark/slice | Control hits | Current hits | Control HR@10 | Current HR@10 | Control MRR | Current MRR |
|---|---:|---:|---:|---:|---:|---:|
| Broad overall | 110/160 | 114/160 | 0.687500 | 0.712500 | 0.468108 | 0.465191 |
| Broad Browsing | 11/40 | 13/40 | 0.275000 | 0.325000 | 0.143750 | 0.126528 |
| Target-like overall | 197/200 | 194/200 | 0.985000 | 0.970000 | 0.623685 | 0.647260 |
| Target-like Browsing | 79/80 | 76/80 | 0.987500 | 0.950000 | 0.528909 | 0.591319 |

Target-like Browsing MRR improved by 0.062410 and MTTC improved from 4.987500
to 3.625000. Broad Browsing added two hits, although its MRR decreased. These
are synthetic stress results, not organizer holdouts and not evidence of
private-set performance.

The final accepted official run took 78.414 seconds, 1.230 times its paired
control, and used approximately 572.379 MiB peak working set. All 57 tests passed. A
separate adaptive-profile experiment had no unseen-target benefit. A bounded
catalog prior regressed the target-like benchmark and exceeded the runtime gate.
Neither rejected component is present in the current runtime.

## Phase-four protocol evidence

Phase four uses commit `88b10b661431af98992d5e71493103674a53d386` as its immutable Phase 3 control. It corrects clarification feedback semantics, permits a bounded second `other` question, and adds exact catalog-derived Evidence Fingerprint retrieval. The Phase 3 policy remains selectable as `phase3`.

The fixed-seed exact-policy unseen-target benchmark contains only sample identity, scenario, independently assigned public-profile data, and a non-public catalog target before it is passed to the unchanged released evaluator. The evaluator itself materializes intent cards, behavior, opening messages, and replies. Targets are unique per run, exclude every public target, and are split evenly between aggregate-distribution-matched and catalog-wide cohorts. The scenario ratio is 40% Buying, 40% Browsing, 15% Intent Override, and 5% Boundary. It is a released-simulator diagnostic, not an organizer holdout.

### Component matrix

The public column uses all 200 official sessions. The exact-policy column is the fixed 200-session development seed; cross-seed variance is not estimated for these screening runs and was measured only after shortlisting the combined candidate.

| Candidate | Public hits | Public HR@10 | Public MRR | Public MTTC | Public TechnicalScore | Exact-policy hits | Exact-policy TechnicalScore | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Phase 3 control | 183 | 0.915000 | 0.561236 | 4.400000 | 0.757871 | 181 | 0.769433 | control |
| Response semantics | 182 | 0.910000 | 0.570617 | 4.445000 | 0.757285 | 180 | 0.766483 | reject |
| Repeated `other` twice | 188 | 0.940000 | 0.587673 | 4.370000 | 0.778902 | 181 | 0.769433 | component only |
| Evidence index | 186 | 0.930000 | 0.629732 | 4.120000 | 0.791520 | 186 | 0.802198 | component only |
| Buying rank recovery | 183 | 0.915000 | 0.561236 | 4.400000 | 0.757871 | 181 | 0.769433 | reject as behavior-equivalent |
| Semantics + repeated `other` | 184 | 0.920000 | 0.576173 | 4.415000 | 0.764552 | 180 | 0.766483 | reject |
| Semantics + evidence | 186 | 0.930000 | 0.635149 | 4.135000 | 0.792845 | 183 | 0.794675 | component only |
| Repeated `other` + evidence | 189 | 0.945000 | 0.637579 | 4.115000 | 0.801474 | 186 | 0.806402 | reject: incomplete feedback semantics |
| Full, fallback `other` | 187 | 0.935000 | 0.635704 | 4.120000 | 0.795811 | 185 | 0.802026 | shortlist |
| Protocol evidence | 188 | 0.940000 | 0.645704 | 3.985000 | 0.804011 | 186 | 0.806376 | accept |

Allowing `other` twice improved the public result from 183 to 188 hits. A third ask kept 188 hits but reduced MRR from 0.587673 to 0.587173, so the limit remains two. Restricting the second ask to detected Buying produced 188 hits; Browsing-only produced 186 and Override-only 185. There is deliberately no Boundary runtime route because the Agent cannot see scenario labels. Boundary is instead measured as an output slice and rises from 8/10 in the control to 10/10 in the accepted policy.

### Evidence index and final verification

The evidence index contains 228,307 unique normalized keys and 527,885 source-aware postings. Collision counts are 1 at p50, 3 at p95, 14 at p99, and 13,836 maximum. It built in 4.467 seconds. Across 1,000 deterministic lookups, latency was 0.043 ms at p50 and 2.303 ms at p95. An evaluation-only 1,000-product comparison checked 3,953 materialized values against the released normalizer with zero mismatched products.

| Metric | Phase 3 control | Protocol evidence | Change |
|---|---:|---:|---:|
| Hit Rate@10 | 0.915000 | 0.940000 | +0.025000 |
| MRR | 0.561236 | 0.645704 | +0.084468 |
| MTTC | 4.400000 | 3.985000 | -0.415000 |
| Efficiency | 0.660000 | 0.701500 | +0.041500 |
| Recommended TechnicalScore | 0.757871 | 0.804011 | +0.046140 |

| Scenario | Control hits | Current hits | Control MRR | Current MRR |
|---|---:|---:|---:|---:|
| Buying | 75/80 | 76/80 | 0.528309 | 0.622634 |
| Browsing | 75/80 | 77/80 | 0.566190 | 0.664474 |
| Intent Override | 25/30 | 25/30 | 0.607037 | 0.637037 |
| Boundary | 8/10 | 10/10 | 0.647619 | 0.706111 |

The final exact-policy comparison used three paired seeds with 800 unique unseen targets per seed. Mean TechnicalScore increased from 0.782925 (sample variance 0.00005428) to 0.837120 (sample variance 0.00003163). Mean HR@10 rose from 0.923750 to 0.952917, mean MRR from 0.590971 to 0.704290, and mean MTTC fell from 3.812083 to 3.531250. The candidate added 70 hits across 2,400 paired sessions, with no scenario hit regression in any seed.

A separate 400-session empty-profile slice rose from 363 to 370 hits, MRR 0.567134 to 0.680155, and MTTC 4.185000 to 3.950000. This indicates that the measured gain does not depend on profile matching.

The frozen official run completed in 70.288 seconds, 1.090 times the 64.473-second control rerun, with an approximate 642.070 MiB peak working set and zero model tokens. All 73 tests passed.

## Development-only LLM reranker (rejected)

After selecting protocol evidence, a guarded DeepSeek experiment tested whether
an LLM could reorder a bounded candidate set without generating ASINs. The
200-session exact-policy unseen-target screening moved TechnicalScore from
0.836591 to 0.841916. On the first 800-session confirmation, however, the gain
shrank to 0.000993, MRR fell from 0.683708 to 0.682518, Buying lost two hits,
and strict JSON validity was 844/862 (97.91%). Both diagnostics were
catalog-derived development evaluations, not the official public set or the
organizer final set.

The experiment cost approximately US$2.084 and was stopped before later
800-session seeds or an official public-evaluator run. It was rejected under
the predeclared generalization, scenario-preservation, and reliability gates.
No model client, API dependency, credential requirement, cache, or network path
is included in the selected runtime. See the [aggregate experiment note](experiments/deepseek-rerank.md).

## Independent submission reproduction

A fresh Windows clone of public commit `75a51f240ed6421da7188ca43b2d0752fbbbbd52` was prepared using only this README and the official release assets. The compressed checksum was `07fd142631fd6b03e2b4d09988c3eb7d53720e9d57010c79db48eeaada50a8f8`; the decompressed catalog matched the expected `da979b05...fc69a67` checkpoint. Installation, catalog inspection, protected-file verification, all 73 tests, and the complete evaluator passed without a parent workspace or machine-specific project path. The clean-room evaluator reproduced every aggregate metric exactly in 72.250 seconds with an approximately 674.594 MiB sampled peak process-tree working set.

An Ubuntu/WSL smoke run used Python 3.12.3 and its native SQLite FTS5 implementation. It independently verified both catalog checksums, catalog structure, all four protected hashes, cold index construction, session reset, one real response, identifier uniqueness, and zero token usage. WSL's direct GitHub connection was unavailable during that check, so a second fresh public clone and the official release downloads were prepared by Windows Git/PowerShell before Linux execution; this portability result is a runtime smoke test rather than a fully network-independent Linux clean-room reproduction.

| Resource | Measured value |
|---|---:|
| Cold Agent construction | 7.274 s |
| Catalog load + in-memory FTS5 build | 2.731 s |
| Evidence Fingerprint build | 4.541 s |
| Evidence keys / postings | 228,307 / 527,885 |
| Evidence lookup p50 / p95 (1,000 queries) | 0.0335 ms / 1.4016 ms |
| Core runtime network calls | 0 |
| External-service cost | $0 |

After adding only failure-message, documentation, and presentation hardening, the suite increased to 78 passing tests. A final complete evaluator rerun reproduced all aggregate and scenario metrics exactly. It took 84.797 seconds under the then-current system load; this run is recorded separately rather than replacing the canonical or clean-room resource figures.

## Interpretation

The public control failure analysis found that 32 of 33 missed targets entered a
lexical route and 25 were primarily retrieved below Top 10. That evidence led to
candidate-aware questions and bounded lower-rank diversity rather than generic
recall expansion. The accepted pair passes the matched-Browsing MRR gate and
adds broad-stress Browsing hits. The rejected semantic, adaptive-profile, and
catalog-prior results reinforce that added complexity is not retained without a
measured unseen-target benefit.

## Current limitations

1. Broad-stress Browsing remains weak when the opening language shares few catalog terms.
2. Missing or inconsistent catalog facets can reduce question-value accuracy and diversity signals.
3. Cold startup parses 50,000 JSONL rows and builds an in-memory FTS5 index.

Dense retrieval, neural reranking, external LLMs, and remote services are outside
the current offline implementation.
