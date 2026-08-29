# Implementation notes

## Reproducibility and protected assets

The official evaluator, public set, API contract, and evaluation config were copied directly from the official Participant Kit Release. Initial SHA256 values are stored in `artifacts/metrics/official_sha256_initial.json` and verified by `scripts/verify_official_files.py`.

The frozen catalog passed a full structural and integrity scan: 50,000 valid JSON objects, 50,000 non-empty unique `parent_asin` values, zero duplicates, all participant-visible fields present, and the expected official SHA256. No alternate catalog is merged into it.

## Deterministic core

The evaluator/core uses only the Python standard library. SQLite FTS5 uses the Porter/unicode61 tokenizer and deterministic BM25 ordering with `parent_asin` as the final tie-break. Weighted RRF, constraint reranking, cache eviction, clarification, and popularity fallback have no random component.

The `starter.Agent` adapter resolves `src` using `pathlib.Path`; no drive letter or workspace-specific absolute path is embedded. Project text files are read as UTF-8. `CatalogIndex` is constructed once per Agent and maintains bounded search/document caches so later sessions do not repeat identical FTS work.

## Constraint and query handling

The extractor uses general token dictionaries and regular expressions, never public sample strings, sample IDs, target identifiers, or label-derived lookup tables. Genuine no-preference and no-additional-preference messages are handled before query construction, so feedback language does not become product terms. The former supersedes the named slot; the latter records that the slot has no undisclosed value while preserving active constraints.

Threshold budgets are represented as structured constraints and scored against catalog price when a price exists. The highest-weight current-message route excludes the threshold number to avoid treating `$80` as a match for unrelated `80% nylon` text. Category evidence is checked primarily in title/category fields during reranking.

Override handling is slot-aware. General contrast forms such as `X instead of Y`, `Y rather than X`, `not X but Y`, `switch from X to Y`, `no longer X`, and `anything except X` are split into old/new clauses before extraction. Attribute changes clear only the affected slot. Category changes retain compatible budget/use-case context while clearing category-dependent size, style, brand, and feature slots. Explicitly rejected values receive bounded ranking penalties rather than unsafe hard exclusion.

When replacement scope is genuinely ambiguous, the state keeps prior context and constructs two bounded hypotheses instead of erasing the conversation. Current-turn evidence has the highest override weight; stable context and profile evidence are reduced. Constraint status, confidence, source turn, superseded values, negatives, and replacement events remain internal state for tests and the optional debug panel, never the official response.

## Output guarantees

`respond` rejects an uninitialized session, safely normalizes malformed turn/top-k values, always returns a string message and list, emits only legal clarification attributes, validates every identifier against the frozen catalog, removes duplicates, caps output at `top_k`, and reports zero non-negative token usage.

## Candidate facets and question value

`CandidateFacetIndex` derives a conservative read-only view from product fields already held by `CatalogIndex`. It does not invent missing values. Category and store remain normalized phrases; color, material, style, and use case use general vocabularies; size requires contextual evidence; price is reduced to a coarse band; and feature terms exclude values already represented by another facet. The cache is bounded at 8,192 products and is populated only for products entering a candidate pool.

The Question Value Estimator considers only legal specific attributes that are not already active, asked, declined, or exhausted. Coverage measures how often a facet is evidenced in the bounded candidate set. Partition gain uses normalized entropy for single-valued facets and the strongest bounded binary partition for multi-valued feature/use-case terms. Route relevance, candidate-score uncertainty, override ambiguity, and remaining turns scale the result. `other` is the only repeatable attribute, is capped at two asks, and stops after an exhausted response. This state is available to the optional debug view but never appears in the official Agent response.

## Evidence Fingerprint retrieval

`EvidenceFingerprintIndex` builds a query-only in-memory SQLite reverse index from the same immutable product records used by FTS5. It indexes only visible feature strings, detail key/value pairs, detected material and color, and available price evidence. Whitespace and surrounding separators are normalized independently to the published 180-character contract; no evaluator module is imported.

Lookup supports an exact clause, deterministic weighted unions, and multi-clause intersections. Ranking discounts high-collision keys, rewards independent exact matches, caps broad postings, and retains field provenance. Current-turn clauses receive more weight than compatible historical clauses. Declines and replacements move affected evidence out of the active query, while the existing negative and superseded penalties remain bounded safeguards.

## Adaptive Top-10 portfolio

Retrieval now retains a bounded scored pool after the existing lexical reranker. High-confidence Buying preserves the original Top K ordering. Early vague Browsing protects the first seven ranks at `top_k=10` and uses the lower three positions for deterministic facet coverage; after useful constraints accumulate, the precision core grows. Override and no-preference paths use more conservative exploration. Tail gain combines normalized relevance, current and active constraint coverage, new facet coverage, near-duplicate similarity, and bounded negative/superseded penalties. Final identifiers remain unique, catalog-valid, and rank ordered.

The earlier ranking path remains available as a lexical control mode. It uses the same catalog, state reducer, query builder, RRF, and reranker without Question Value or portfolio selection.

## Presentation isolation

FastAPI is an optional thin adapter. It lazily creates the same Agent core, serializes access with an `RLock`, maintains isolated demo sessions, and enriches catalog-valid identifiers for product cards. React uses only the public demo endpoints. Neither layer is imported by `starter.agent` or required by the evaluator.

The browser QA pass covered session creation, a budget-constrained search, a second-turn intent override, live debug state, product enrichment, session reset, metrics rendering, navigation, and console errors. Runtime screenshots/reports are stored under ignored `artifacts/runtime/`.

## Evaluation hygiene

Only the unchanged evaluator reads public ground truth and simulator state. The Agent has no runtime path to labels or evaluator internals, contains no sample-specific rules, and never modifies or augments the catalog. The repository retains compact aggregate metric summaries. The current implementation combines the Phase 3 decision policy with corrected clarification semantics, bounded repeated `other`, and catalog-derived exact evidence retrieval. Its selectable `phase3` mode omits all Phase 4 behavior. Rejected rank-recovery and more aggressive repeat policies are not part of the default runtime; previously rejected adaptive-profile, catalog-prior, and semantic experiments also remain absent.
