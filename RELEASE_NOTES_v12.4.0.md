# Smart Retire AI v12.4.0 Release Notes

**Release Date:** April 2026
**Version:** 12.4.0
**Previous Version:** 12.2.0

---

## Release Overview

This release is a stabilization pass focused on retirement tax correctness, safer account classification, and cleaner contributor workflows. The main change is a move away from name-based tax guessing toward explicit account tax behavior across projections, CSV imports, and AI-assisted statement review.

---

## Core Improvements

### Explicit tax behavior model
- Added an explicit `TaxBehavior` model for retirement calculations.
- Projection logic no longer decides Roth behavior by checking whether `"Roth"` appears in the account name.
- The engine now distinguishes:
  - pre-tax withdrawals
  - tax-free Roth-style withdrawals
  - brokerage capital-gains taxation
  - HSA-style split taxation
  - annuity/ordinary-income taxation
  - post-tax cash or savings accounts with no additional withdrawal tax

### Safer asset conversion paths
- CSV upload, AI-edited account tables, and manual asset setup now share the same tax-treatment mapping helpers.
- `Tax-Deferred`, `Tax-Free`, and `Post-Tax` UI labels now map deterministically to explicit internal tax behavior.
- Savings and cash-style post-tax accounts are no longer implicitly treated like brokerage accounts.

---

## Quality Improvements

### Testing and regression coverage
- The `--run-tests` entrypoint now discovers the canonical suite in `tests/test_fin_advisor.py`.
- Added regression coverage for:
  - Roth / tax-free handling
  - brokerage gains-only taxation
  - cash-style post-tax accounts
  - HSA split treatment
  - CSV/editor row conversion into internal assets

### Docs and release consistency
- Updated in-app and package version references to `12.4.0`.
- Aligned test commands across contributor docs to use:
  - `python3 fin_advisor.py --run-tests`
- Removed stale historical release content from the local testing guide.

### Warning cleanup
- Fixed the Social Security help text string that was producing a Python `SyntaxWarning` during test runs.

---

## Files Changed

- `fin_advisor.py` — version bump, shared tax mapping helpers, CSV/AI/manual asset cleanup, warning fix, unified test discovery
- `financialadvisor/domain/models.py` — explicit `TaxBehavior` enum and backward-compatible inference helpers
- `financialadvisor/core/tax_engine.py` — tax calculation based on explicit behavior with legacy fallback
- `financialadvisor/core/projector.py` — explicit tax behavior for default legacy asset construction
- `tests/test_fin_advisor.py` — expanded regression coverage
- `README.md`, `CLAUDE.md`, `TESTING.md` — doc/version/test command cleanup
- `setup.py`, `financialadvisor/__init__.py` — version bumped to `12.4.0`
