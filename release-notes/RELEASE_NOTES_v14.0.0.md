# Smart Retire AI v14.0.0 Release Notes

**Release Date:** April 2026
**Version:** 14.0.0
**Previous Version:** 13.0.0

---

## Release Overview

v14.0 replaces the mandatory n8n dependency for financial statement processing with a built-in pure Python pipeline. The new processor extracts, classifies, deduplicates, and tax-buckets accounts entirely in process — no external workflow service required. n8n remains supported and can be re-enabled at any time via a single environment variable, making the switch zero-risk.

---

## New Features

### Pure Python Statement Processor (`integrations/statement_processor.py`)

A full drop-in replacement for the n8n webhook pipeline, with identical input/output contracts.

- **Full-document extraction** — all PDF pages are joined into a single string and sent as one GPT-4.1-mini call per file, preserving cross-page context that n8n's page-per-call mode lost.
- **Automatic chunking** — files exceeding ~150K characters fall back to consecutive 5-page chunks rather than single pages, retaining local context.
- **Single-pass account processing** — each extracted account is classified, pruning-flagged, and tax-bucket decomposed in a single pass rather than three separate O(n) scans.
- **Tax classification** — maps `checking`, `savings`, `brokerage`, `401k`, `ira`, `roth_401k`, `roth_ira`, `hsa`, `stock_plan`, and 529 accounts to `post_tax` / `tax_deferred` / `tax_free` with confidence scores.
- **Tax bucket decomposition** — for 401k/403b/457 accounts, decomposes `_raw_tax_sources` into Traditional, Roth in-plan, and After-Tax 401k buckets. Reconciliation warning emitted if bucket sum diverges from ending balance by more than $0.01.
- **Pruning logic** — removes cash/money-market accounts that are sub-accounts of a larger brokerage position at the same institution; removes unvested stock plan grants (null balance).
- **AI retry with exponential backoff** — up to 2 retries on `RateLimitError` / `APIError`, sleeping `2^attempt` seconds between attempts.
- **Scanned page handling** — pages yielding fewer than 50 non-whitespace characters are skipped with a user-visible warning rather than passed to the AI.
- **Return dict** — identical schema to `N8NClient`: `success`, `data`, `format`, `rows_extracted`, `has_data`, `warnings`, `execution_time`.

### Account-Number-Based Deduplication

The deduplication fingerprint now prioritises `account_number_last4` over account name when available.

**Before:**
```
fingerprint = institution | account_name | account_type | currency
```

**After:**
```
# when last4 is present:
fingerprint = institution | last4 | account_type

# fallback when last4 is absent:
fingerprint = institution | account_name | account_type | currency
```

This eliminates a class of silent data loss where the AI assigned a generic name (e.g. "Brokerage Account") to two structurally different accounts at the same institution across separate statement files — causing the earlier-dated account to be dropped by dedup.

### Institution Name Normalisation (`_normalize_institution`)

A module-level helper strips common generic suffix words (`brokerage`, `financial`, `bank`, `services`, `investment`, `securities`, `advisors`, `wealth`, `management`, etc.) before comparing institution names, so "Fidelity Brokerage Services" and "Fidelity Investments" resolve to the same canonical key `fidelity`.

### Processor Factory (`integrations/processor_factory.py`)

```python
# returns StatementProcessor when PYTHON_STATEMENT_PROCESSOR=true|1|yes
# returns N8NClient otherwise
get_processor()
```

A single env-var toggle selects the active backend at startup. No code changes required to switch.

### `fin_advisor.py` wired to factory

The main app now calls `get_processor()` instead of `N8NClient()` directly.

- Import block updated — `N8NClient` class removed (unused); `StatementProcessor`, `StatementProcessorError`, and `get_processor` imported.
- Processor init: `N8NClient()` → `get_processor()`.
- Error handling: `except N8NError` → `except (N8NError, StatementProcessorError)` with updated help text covering both config paths.

---

## Configuration

```
# .env
OPENAI_API_KEY=sk-...              # required for Python processor (and chat advisor)
PYTHON_STATEMENT_PROCESSOR=true    # omit or set false to use n8n instead
```

When `PYTHON_STATEMENT_PROCESSOR` is unset, `N8N_WEBHOOK_URL` is used as before — existing n8n deployments require no changes.

---

## Files Changed

| File | Change |
|---|---|
| `integrations/statement_processor.py` | **NEW** — pure Python PDF extraction, classification, dedup, tax buckets |
| `integrations/processor_factory.py` | **NEW** — env-var-driven processor selector |
| `integrations/__init__.py` | Export `StatementProcessor`, `StatementProcessorError`, `get_processor` |
| `statement_uploader.py` | Factory swap, `StatementProcessorError` catch, Python-mode UI branches |
| `fin_advisor.py` | Import update, factory swap, broadened error catch |
| `.env.example` | `PYTHON_STATEMENT_PROCESSOR` entry added |
| `README.md` | Version bump, processor docs, env var table updated |
| `RELEASE_NOTES_v14.0.0.md` | This file |
| `CLAUDE.md` | Version updated to 14.0.0 |
