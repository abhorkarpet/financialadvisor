# Smart Retire AI v16.0.0 Release Notes

**Release Date:** May 2026
**Version:** 16.0.0
**Previous Version:** 15.8.0

---

## Release Overview

v16.0.0 is the Detailed Planning chat advisor release. It ships two new AI-powered conversational advisors inside Detailed Planning mode — one for collecting personal info during setup, and one for answering questions and applying what-if changes after results are computed. It also introduces a formal `TaxBehavior` enum that replaces name-substring inference throughout the tax engine, adds seamless cross-mode switching between Detailed and Simple Planning, expands the statement processor into a standalone module pair (`StatementProcessor` / `processor_factory`), and delivers a major test expansion: a new e2e suite and ~1,000 additional unit-test lines.

---

## Features / Changes

### Detailed Planning — setup chat advisor (`chat_with_setup_advisor`)

A new GPT-4.1-mini advisor is embedded in the Detailed Planning personal-info step. It walks users through entering age, retirement goal, and related parameters conversationally. The advisor is driven by a new external system prompt file (`integrations/detailed_setup_system_prompt.txt`) that can be tuned independently of the code.

### Detailed Planning — post-results chat advisor (`chat_with_results_advisor`)

After projection results are displayed, users can ask the AI advisor questions about their portfolio. The advisor understands the full computation context (corpus size, withdrawal schedule, Monte Carlo summary, asset breakdown) via `build_detailed_chat_context` injected as a per-turn system message. It can also propose what-if parameter changes by emitting a structured `__whatif__` JSON block that the UI applies directly — letting users say "what if I retire at 62?" and immediately see updated projections.

### Calculation context injection (`financialadvisor/core/chat_context.py`)

New module `build_detailed_chat_context` formats ~1,100 tokens of structured context from a projection result into a compact string injected as a system message each turn. Includes: corpus size, years in retirement, annual withdrawal, Monte Carlo survival rate, asset breakdown, IRS contribution maxes, and what-if parameter values. The Simple Planning advisor also now accepts an optional `calc_context` parameter for the same purpose.

### `TaxBehavior` enum and explicit tax logic

`financialadvisor/domain/models.py` gains a `TaxBehavior` enum with seven values: `PRE_TAX`, `TAX_FREE`, `CAPITAL_GAINS`, `HSA_SPLIT`, `ORDINARY_INCOME`, `INTEREST_INCOME`, `NO_ADDITIONAL_TAX`. Helper functions `infer_tax_behavior` and `infer_asset_type_from_name` derive behavior from asset type and name for backward compatibility with legacy callers. The tax engine (`tax_engine.py`) now dispatches on `TaxBehavior` instead of inspecting the `AssetType` enum and asset name substrings.

### Cross-mode switching: Detailed → Simple Planning

New `switch_to_simple_planning_from_onboarding` function in `fin_advisor.py` moves a user from Detailed Planning into chat mode while seeding `chat_fields` with matching values (birth year, retirement age, life expectancy, target income, tax/growth/inflation rates, legacy goal) already entered. A field map `_CHAT_TO_DETAILED_FIELD_MAP` and constant `_DETAILED_PLANNING_RESET_KEYS` handle the reverse direction as well.

### Statement processor modularised

`integrations/statement_processor.py` and `integrations/processor_factory.py` are new modules that separate the Python-based PDF statement processor from the n8n client. `get_processor` and `check_processor_configured` in `processor_factory` select between n8n and the Python processor based on environment variables. `fin_advisor.py` now imports from this factory instead of directly from `n8n_client`.

### Detailed Planning system prompts externalised

Two new text files hold GPT system prompts that were previously inline or absent:
- `integrations/detailed_setup_system_prompt.txt` — personal-info collection advisor
- `integrations/detailed_planning_system_prompt.txt` — post-results what-if advisor

Both load at runtime via `pathlib.Path`, making prompt iteration possible without touching Python source.

### Release notes extraction helper

`extract_release_overview` function in `fin_advisor.py` parses a release notes markdown file and returns just the Release Overview section (with or without the heading). Used to surface the overview in the app splash screen.

### E2E test suite

New `tests/e2e/` package with four test modules covering the main user journeys:
- `test_simple_planning.py` — chat-based Simple Planning flow
- `test_detailed_planning.py` — Detailed Planning asset entry and projection
- `test_csv_upload.py` — CSV statement upload via Python processor
- `test_results_actions.py` — results-page actions (PDF, Monte Carlo, what-if)

`pytest.ini` and `requirements-test.txt` are added; the existing `tests/test_fin_advisor.py` excludes e2e tests from the unit test discovery path.

---

## Bug Fixes

### Tax engine: Roth detection no longer relies on name substring

Previously, post-tax Roth accounts were identified by checking `"Roth" in asset.name`. This silently failed for any account whose name didn't include the word "Roth". The new `TaxBehavior` enum, set explicitly on `Asset` construction or inferred via `infer_tax_behavior`, makes tax treatment authoritative and independent of naming conventions.

### `track_statement_upload` signature broadened

The fallback no-op stub for `track_statement_upload` now accepts `**kwargs` and has defaults for `num_statements` and `num_accounts`, matching the real analytics implementation. Callers that pass extra keyword arguments no longer raise `TypeError` when analytics is unavailable.

### `track_feature_usage` removed

`track_feature_usage` was imported from analytics and stubbed in the fallback block but never called anywhere in the codebase. Both the import and the stub have been removed.

### E2E tests excluded from unit test discovery

`fin_advisor.py --run-tests` and the CI unit-test step previously picked up e2e tests, which require a live server. A `testpaths` exclusion in `pytest.ini` and a `fix: exclude e2e tests from unit test discovery` commit ensure unit tests run in isolation.

---

## UI Changes

### Post-results chat panel in Detailed Planning

A chat input and message history are now rendered on the results page in Detailed Planning mode. The panel is hidden while the advisor is computing and shown once a response arrives. What-if changes proposed by the advisor are applied to the live projection without requiring the user to navigate back to the inputs form.

### "Switch to Simple Planning" entry point preserved across onboarding

The Detailed Planning onboarding flow now exposes a "Switch to Simple Planning" button that uses `switch_to_simple_planning_from_onboarding`, carrying over any already-entered values so the user doesn't start from scratch.

---

## Files Changed

| File | Change |
|---|---|
| `fin_advisor.py` | Added `extract_release_overview`, `switch_to_simple_planning_from_onboarding`, `_CHAT_TO_DETAILED_FIELD_MAP`, `_DETAILED_PLANNING_RESET_KEYS`; post-results chat panel; import from `processor_factory`; `chat_with_setup_advisor` and `chat_with_results_advisor` wired in; version bumped to 16.0.0 |
| `financialadvisor/__init__.py` | Version bumped to 16.0.0 |
| `financialadvisor/domain/models.py` | Added `TaxBehavior` enum, `infer_tax_behavior`, `infer_asset_type_from_name`, `_normalize_asset_type`, `_normalize_tax_behavior` |
| `financialadvisor/core/chat_context.py` | New — `build_detailed_chat_context` |
| `financialadvisor/core/tax_engine.py` | Rewritten to dispatch on `TaxBehavior` instead of `AssetType` + name check |
| `financialadvisor/core/projector.py` | Minor updates to pass `TaxBehavior` through projection |
| `financialadvisor/utils/analytics.py` | `track_statement_upload` signature updated; `track_feature_usage` removed |
| `integrations/chat_advisor.py` | Added `chat_with_setup_advisor`, `chat_with_results_advisor`, `_parse_whatif_block`, `_load_results_advisor_prompt`, `_load_detailed_setup_prompt`; `calc_context` parameter on `chat_with_advisor`; max_tokens raised 600 → 900 |
| `integrations/detailed_planning_system_prompt.txt` | New — post-results what-if advisor system prompt |
| `integrations/detailed_setup_system_prompt.txt` | New — setup personal-info advisor system prompt |
| `integrations/statement_processor.py` | New — `StatementProcessor`, `StatementProcessorError` |
| `integrations/processor_factory.py` | New — `get_processor`, `check_processor_configured` |
| `integrations/__init__.py` | Exports `StatementProcessor`, `StatementProcessorError`, `get_processor` |
| `integrations/n8n_client.py` | Minor cleanup |
| `statement_uploader.py` | Expanded to use `processor_factory`; additional upload UI states |
| `tests/e2e/__init__.py` | New — e2e package marker |
| `tests/e2e/conftest.py` | New — shared e2e fixtures |
| `tests/e2e/test_simple_planning.py` | New |
| `tests/e2e/test_detailed_planning.py` | New |
| `tests/e2e/test_csv_upload.py` | New |
| `tests/e2e/test_results_actions.py` | New |
| `tests/test_fin_advisor.py` | ~490 lines of new unit tests |
| `tests/test_statement_processor.py` | New — ~570 lines of statement processor tests |
| `pytest.ini` | New — configures testpaths and e2e exclusion |
| `requirements-test.txt` | New — test-only dependencies |
| `setup.py` | Version bumped to 16.0.0 |
| `CLAUDE.md` | Version updated to 16.0.0 |
| `README.md` | Version updated to 16.0.0 |
| `RELEASE_NOTES_v16.0.0.md` | This file |
