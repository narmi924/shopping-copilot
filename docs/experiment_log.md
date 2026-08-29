# Experiment log

This log contains aggregate, reproducible conclusions only. Per-session labels,
target identifiers, conversations, rankings, and generated benchmark cases are
kept outside the public repository.

## 2026-08-29 — Phase-two control

- Source commit: `5a2277ea9e9550a0fe961d680e77181dc7d03d3e`
- Environment: CPython 3.13.1, uv 0.12.5, Windows 10.0.26200 x64
- Command: `uv run python -m evaluator.local_evaluator`
- Wall clock: 67.169 seconds
- Approximate peak process-tree working set: 565.11 MiB
- Tests: 33 passed
- Decision: keep as the immutable comparison control

| Metric | Value |
|---|---:|
| Hit Rate@10 | 0.835000 |
| MRR | 0.515817 |
| MTTC | 3.890000 |
| Efficiency | 0.711000 |
| Recommended TechnicalScore | 0.714445 |

The private control-miss replay produced the following general diagnostic
counts. Tags are heuristic and non-exclusive; they guide generic design rather
than prove a single cause.

| Diagnostic | Count |
|---|---:|
| Target retrieved below Top 10 (primary) | 25 |
| Target never entered a lexical candidate pool | 1 |
| New replacement slot not extracted (primary) | 5 |
| Old-attribute contamination (primary or contributing) | 4 |
| Missing or ambiguous price evidence | 5 |
| Lexical synonym gap | 2 |

## 2026-08-29 — Override V2 (accepted)

Hypothesis: parsing replacement scope at the slot boundary and applying bounded
violation-aware reranking will improve Intent Override without weakening ordinary
Buying or Browsing.

Implementation summary:

- structured old/new contrast parsing and replacement confidence;
- active, superseded, negative, declined, and current-turn constraint state;
- attribute versus category cleanup with compatible-context retention;
- two bounded retrieval hypotheses for ambiguous replacements;
- higher current-turn priority and capped negative/superseded penalties on
  override turns only;
- no external model, API, data, or runtime dependency.

| Metric | Control | Candidate | Change |
|---|---:|---:|---:|
| Hit Rate@10 | 0.835000 | 0.840000 | +0.005000 |
| MRR | 0.515817 | 0.519359 | +0.003542 |
| MTTC | 3.890000 | 3.865000 | -0.025000 |
| Recommended TechnicalScore | 0.714445 | 0.718508 | +0.004063 |
| Official wall clock (seconds) | 67.169 | 64.154 | -3.015 |

The final verification repeat took 71.935 seconds, or 1.071 times control; both
complete runs remained below the 1.25 acceptance limit.

| Public scenario | Control hits | Candidate hits | Control HR@10 | Candidate HR@10 |
|---|---:|---:|---:|---:|
| Buying | 75 | 75 | 0.937500 | 0.937500 |
| Browsing | 74 | 74 | 0.925000 | 0.925000 |
| Intent Override | 11 | 12 | 0.366667 | 0.400000 |
| Boundary | 7 | 7 | 0.700000 | 0.700000 |

On the private 160-session unseen-target synthetic benchmark, overall HR@10
rose from 0.625000 (100 hits) to 0.687500 (110 hits). Intent Override rose from
0.475000 (19/40) to 0.725000 (29/40), and Override MRR rose from 0.229167 to
0.517599. Buying, Browsing, and Boundary hit counts were unchanged. This
benchmark is a synthetic stress test, not an organizer holdout.

Decision: accepted. Every gate passed, including protected-file integrity,
runtime isolation, 49 tests, public score, ordinary-scenario hit preservation,
public Override MRR/hits, synthetic Override improvement, and runtime.

## 2026-08-29 — Catalog-derived latent semantic route (rejected)

Hypothesis: word TF-IDF reduced to 96 deterministic SVD components can bridge
open-ended browsing and ambiguous replacement vocabulary while retaining the
lexical path.

- Index build: 16.558 seconds
- Ignored serialized size: 32,962,470 bytes
- Approximate build peak: 884.812 MiB
- Combined official wall clock: 72.942 seconds
- Combined public TechnicalScore: 0.718325
- Synthetic Browsing: 11/40 for both Override V2 and the hybrid
- Synthetic Browsing MRR: 0.143750 to 0.146071 (+0.002321)
- Combined public Intent Override: 11/30, down from Override V2's 12/30

Decision: rejected. The intended unseen-target Browsing slice did not meet the
minimum improvement gate, the public Override hit gain disappeared, and the
dependency/cache/memory cost was therefore not justified. No semantic code,
dependency, matrix, or cache is included in the selected implementation.
