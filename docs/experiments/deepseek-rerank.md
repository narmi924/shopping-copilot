# Guarded DeepSeek reranker experiment

## Hypothesis

A language model might improve the ordering of already retrieved candidates when lexical and catalog-evidence routes had found the target but ranked it below the recommendation cutoff.

## Guarded design

The development-only experiment placed DeepSeek behind the selected deterministic Agent as a bounded candidate reranker. It could reorder only a fixed candidate set, received opaque candidate indices rather than ASINs, and could not create a product identifier. Constraint extraction, conversation state, Question Value, and candidate generation did not change. Missing credentials, transport errors, timeouts, malformed output, duplicates, invalid indices, or any other rejected response fell back to the selected offline ranking.

## Aggregate diagnostics

These were catalog-derived, exact-policy unseen-target development diagnostics. The 200-session screening was not the official public set, and the 800-session confirmation was not the organizer final evaluation.

| Diagnostic | Deterministic control | LLM candidate | Change |
|---|---:|---:|---:|
| 200-session TechnicalScore | 0.836591 | 0.841916 | +0.005325 |
| 800-session TechnicalScore | 0.818712 | 0.819705 | +0.000993 |
| 800-session hits | 745 / 800 | 746 / 800 | +1 |
| 800-session MRR | 0.683708 | 0.682518 | -0.001190 |

The larger confirmation also lost two Buying hits. Strict JSON ranking validity was 844 / 862, or 97.91%, below the 99% reliability gate. The approximate cost of preflight, shadow checks, screening, and the first larger confirmation was US$2.084.

## Decision

The keep gates required a meaningful larger-set score gain, scenario preservation, and at least 99% strict structured-output validity. The 200-session gain passed its screening threshold, but the 800-session gain was negligible, MRR regressed, Buying lost hits, and output validity failed its gate. The candidate was rejected. Later 800-session seeds and the official public evaluator were deliberately not run after those failures.

No DeepSeek client, API dependency, model configuration, credential requirement, response cache, or runtime network path is included in the selected system. This result strengthens the evidence-based decision to keep the submitted Agent deterministic, offline, zero-token, and free of external-service cost.
