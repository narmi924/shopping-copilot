# Implementation notes

## Reproducibility and protected assets

The official evaluator, public set, API contract, and evaluation config were copied directly from the official Participant Kit Release. Initial SHA256 values are stored in `artifacts/metrics/official_sha256_initial.json` and verified by `scripts/verify_official_files.py`.

The frozen catalog passed a full structural and integrity scan: 50,000 valid JSON objects, 50,000 non-empty unique `parent_asin` values, zero duplicates, all participant-visible fields present, and the expected official SHA256. No alternate catalog is merged into it.

## Deterministic core

The evaluator/core uses only the Python standard library. SQLite FTS5 uses the Porter/unicode61 tokenizer and deterministic BM25 ordering with `parent_asin` as the final tie-break. Weighted RRF, constraint reranking, cache eviction, clarification, and popularity fallback have no random component.

The `starter.Agent` adapter resolves `src` using `pathlib.Path`; no drive letter or workspace-specific absolute path is embedded. Project text files are read as UTF-8. `CatalogIndex` is constructed once per Agent and maintains bounded search/document caches so later sessions do not repeat identical FTS work.

## Constraint and query handling

The extractor uses general token dictionaries and regular expressions, never public sample strings, sample IDs, target identifiers, or label-derived lookup tables. No-preference messages are handled before query construction, so decline language does not become product terms.

Threshold budgets are represented as structured constraints and scored against catalog price when a price exists. The highest-weight current-message route excludes the threshold number to avoid treating `$80` as a match for unrelated `80% nylon` text. Category evidence is checked primarily in title/category fields during reranking.

Override handling is conservative: global reset language clears soft slots but retains stable product context; slot-level replacements clear only conflicting attributes. The replacement side receives the highest-weight current route. Removed constraints and replacement terms remain in internal state for tests and the optional debug panel, never in the official response.

## Output guarantees

`respond` rejects an uninitialized session, safely normalizes malformed turn/top-k values, always returns a string message and list, emits only legal clarification attributes, validates every identifier against the frozen catalog, removes duplicates, caps output at `top_k`, and reports zero non-negative token usage.

## Presentation isolation

FastAPI is an optional thin adapter. It lazily creates the same Agent core, serializes access with an `RLock`, maintains isolated demo sessions, and enriches catalog-valid identifiers for product cards. React uses only the public demo endpoints. Neither layer is imported by `starter.agent` or required by the evaluator.

The browser QA pass covered session creation, a budget-constrained search, a second-turn intent override, live debug state, product enrichment, session reset, metrics rendering, navigation, and console errors. Runtime screenshots/reports are stored under ignored `artifacts/runtime/`.

## Evaluation hygiene

Only the unchanged evaluator reads public ground truth and simulator state. The Agent has no runtime path to labels or evaluator internals, contains no sample-specific rules, and never modifies or augments the catalog. The repository retains compact baseline and final metric summaries; the implementation uses the final generalized configuration described in `evaluation.md`.
