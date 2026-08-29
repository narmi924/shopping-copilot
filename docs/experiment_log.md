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

## 2026-08-30 — Decision-aware dialogue and Top-10 portfolio

Control source: `1bc3ac74d9e2e7b017ab9a93d589917bcda66adc` (the manually merged
Override V2). Environment: CPython 3.13.1, uv 0.12.5, Windows 10.0.26200 x64.
The behavior-equivalent control rerun reproduced HR@10 0.840000, MRR 0.519359,
MTTC 3.865000, and TechnicalScore 0.718508. It took 63.774 seconds and used an
approximate 556.867 MiB peak working set.

Two deterministic unseen-target benchmarks were used alongside the public
evaluator:

- the unchanged broad stress set has 160 sessions, 40 per scenario, diverse
  metadata-rich targets, fixed seed 20260829, and separate report templates;
- the target-like matched set has 200 sessions in the public 80/80/30/10
  scenario proportions and fixed seed 20260830. Its non-public targets are
  nearest aggregate matches for category group, popularity quantile, rating
  band, price presence, metadata completeness, and field availability.

Both exclude all public target identifiers. Generated conversations, scorer
targets, and per-session output remain private. Neither benchmark is an
organizer holdout or evidence of private-set performance.

The target-like control scored 197/200 overall (HR@10 0.985000, MRR 0.623685,
MTTC 3.830000). Its Browsing slice scored 79/80, HR@10 0.987500, MRR 0.528909,
and MTTC 4.987500.

### Isolated component comparison

| Candidate | Public HR@10 | Public MRR | Public MTTC | Public TechnicalScore | Broad Browsing hits | Matched Browsing hits | Matched Browsing MRR | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Override V2 control | 0.840000 | 0.519359 | 3.865000 | 0.718508 | 11/40 | 79/80 | 0.528909 | control |
| Question Value only | 0.910000 | 0.564736 | 4.430000 | 0.755821 | 11/40 | 75/80 | 0.542882 | reject |
| Candidate Portfolio only | 0.845000 | 0.516831 | 3.870000 | 0.720149 | 13/40 | 79/80 | 0.568110 | component only |
| Question Value + Portfolio | 0.915000 | 0.561236 | 4.400000 | 0.757871 | 13/40 | 76/80 | 0.591319 | accept |
| Adaptive Profile only | 0.840000 | 0.518526 | 3.865000 | 0.718258 | 11/40 | 79/80 | 0.528909 | reject |
| All three components | 0.915000 | 0.560403 | 4.400000 | 0.757621 | 13/40 | 76/80 | 0.591319 | reject |
| Accepted pair + catalog prior | 0.915000 | 0.561756 | 4.395000 | 0.758127 | 13/40 | 75/80 | 0.589534 | reject |

Question Value alone improved the public evaluator but missed the matched
Browsing gate: MRR increased only 0.013973 and four targets stopped reaching
Top 10. The portfolio alone added two broad Browsing hits and increased matched
Browsing MRR by 0.039201, which was useful but below the 0.05 standalone gate.
Together, the components raised matched Browsing MRR by 0.062410 and reduced its
MTTC by 1.362500 turns while adding two broad Browsing hits.

Adaptive Profile produced no hit, MTTC, or unseen-target change and reduced
public MRR by 0.000833. Adding it to the accepted pair produced the same
synthetic result, lower public MRR, and higher runtime. The bounded catalog
prior produced only a 0.000520 public MRR change, regressed matched Browsing,
and took 104.282 seconds (1.635 times control), so both were removed.

### Accepted aggregate

| Metric | Control | Accepted | Change |
|---|---:|---:|---:|
| Hit Rate@10 | 0.840000 | 0.915000 | +0.075000 |
| MRR | 0.519359 | 0.561236 | +0.041877 |
| MTTC | 3.865000 | 4.400000 | +0.535000 |
| Efficiency | 0.713500 | 0.660000 | -0.053500 |
| Recommended TechnicalScore | 0.718508 | 0.757871 | +0.039363 |

| Public scenario | Control hits | Accepted hits | Change |
|---|---:|---:|---:|
| Buying | 75/80 | 75/80 | 0 |
| Browsing | 74/80 | 75/80 | +1 |
| Intent Override | 12/30 | 25/30 | +13 |
| Boundary | 7/10 | 8/10 | +1 |

The accepted broad stress result was 114/160 (HR@10 0.712500, MRR 0.465191,
MTTC 2.512500), versus control 110/160, 0.687500, 0.468108, and 2.587500.
The accepted target-like result was 194/200 (HR@10 0.970000, MRR 0.647260,
MTTC 3.070000); it trades three late Browsing hits for higher overall MRR and
faster convergence. The component-selection run took 80.469 seconds (1.262
times control). After rejected code was removed, the final verification took
78.414 seconds (1.230 times control) with a 572.379 MiB approximate peak working
set. All 57 tests passed.

Decision: accept Question Value + Candidate Portfolio. It is the smallest
candidate that passed protected-file, public-score, scenario-preservation,
matched-Browsing, broad-Browsing, determinism, runtime, memory, isolation, and
test gates. The MTTC regression on the public simulator is retained as an
explicit tradeoff because both unseen-target suites provide stronger outcomes.

## 2026-08-30 — Protocol-aligned evidence and turn efficiency

Control source: `88b10b661431af98992d5e71493103674a53d386`. The hypothesis was that published clarification feedback and complete catalog-derived clauses contain enough deterministic evidence to recover rank and turn efficiency without a semantic model or larger lexical pool.

The selected implementation distinguishes declined from exhausted slots, tracks per-attribute ask counts, allows at most two useful `other` questions, and builds a query-only reverse evidence index from visible catalog fields. Exact current-turn clauses are fused with FTS candidates, while declines, replacement cleanup, negative constraints, and catalog membership remain enforced at the state/reranking boundaries.

| Experiment | Public hits | Public MRR | Public MTTC | TechnicalScore | Decision |
|---|---:|---:|---:|---:|---|
| Phase 3 control | 183 | 0.561236 | 4.400000 | 0.757871 | control |
| Response semantics | 182 | 0.570617 | 4.445000 | 0.757285 | reject |
| Repeated `other` twice | 188 | 0.587673 | 4.370000 | 0.778902 | component only |
| Evidence index | 186 | 0.629732 | 4.120000 | 0.791520 | component only |
| Buying rank recovery | 183 | 0.561236 | 4.400000 | 0.757871 | reject as redundant |
| Semantics + repeated `other` | 184 | 0.576173 | 4.415000 | 0.764552 | reject |
| Semantics + evidence | 186 | 0.635149 | 4.135000 | 0.792845 | component only |
| Repeated `other` + evidence | 189 | 0.637579 | 4.115000 | 0.801474 | reject: incomplete semantics |
| Full fallback policy | 187 | 0.635704 | 4.120000 | 0.795811 | shortlist |
| Protocol evidence | 188 | 0.645704 | 3.985000 | 0.804011 | accept |

The three paired 800-session exact-policy seeds increased mean TechnicalScore from 0.782925 to 0.837120 and added 70 hits across 2,400 unseen-target sessions. An empty-profile 400-session slice added seven hits and improved MRR by 0.113021. These are released-simulator diagnostics, not organizer holdouts.

The accepted official run completed in 70.288 seconds with a 642.070 MiB approximate peak working set. Buying MRR recovered from 0.528309 to 0.622634, public MTTC fell by 0.415 turns, all four scenario hit counts were preserved or improved, all 73 tests passed, and the protected assets remained byte-identical.

Decision: accept the protocol-evidence configuration and keep `phase3` as a selectable deterministic fallback. A third `other` question, a separate Buying rank branch, and incomplete-feedback combinations were removed.
