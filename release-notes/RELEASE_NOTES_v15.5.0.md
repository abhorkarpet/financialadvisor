# Smart Retire AI v15.5.0 Release Notes

**Release Date:** May 2026
**Version:** 15.5.0
**Previous Version:** 15.0.0

---

## Release Overview

v15.5 introduces a full portfolio management dialog for chat-mode results, fixes a tax efficiency calculation bug for savings and checking accounts, and adds balance-based duplicate detection during statement merges.

---

## Bug Fixes

### Savings accounts no longer show 100% Tax Efficiency

Savings, checking, and cash accounts were previously assigned `NO_ADDITIONAL_TAX` behavior, causing the projector to report them as fully tax-free. This was incorrect: the principal and contributions are already post-tax, but **gains (interest) are taxed as ordinary income**. A new `TaxBehavior.INTEREST_INCOME` enum value captures this rule — only the gain above cost basis is taxed at the retirement marginal rate. The lump-sum projection and the withdrawal simulation now agree.

Affected accounts: any account whose name contains "savings", "checking", or "cash".

### `_asset_to_tax_treatment_label()` round-trip fixed

The function that converts an `Asset` back to a display label ("Pre-Tax", "Post-Tax", etc.) was returning "Tax-Deferred" as its default, breaking the editor round-trip for PRE_TAX and INTEREST_INCOME assets. Fixed to check `asset_type` explicitly before falling back.

---

## New Features

### "Manage Your Portfolio" dialog (chat-mode results page)

The "🏦 Adjust Assets" button on the results page now opens a **"Manage Your Portfolio"** dialog with three distinct modes:

#### Upload Additional Statements
Processes new PDF or CSV statements and merges the extracted accounts into the existing portfolio, preserving all existing names, balances, contributions, and growth rates.

The upload flow mirrors the onboarding Step 2 experience:
- **Phase 1/2 — Uploading**: progress bar advances to 25% while files are prepared
- **Phase 2/2 — AI Processing**: live per-file status updates with elapsed timing (e.g., "Analyzing Chase Brokerage.pdf with GPT-4 ⏱️ 12s"), using the `StatementProcessor` progress callback
- Completion banner shows AI processing time and total time
- Transitions automatically to the review table

#### Edit Existing Portfolio
A new direct-edit mode (no upload required) renders the current portfolio in the same data editor used by the merge-review step. All fields are editable — Account Name, Tax Treatment (selectbox), Current Balance, Annual Contribution, Growth Rate. Rows can be added or deleted (`num_rows="dynamic"`).

#### Clear All Assets
Resets all asset state and returns to onboarding Step 2 for a fresh setup.

### Balance-based duplicate detection

When merging newly extracted accounts, the dialog previously only compared account names (case-insensitive). It now also checks whether an incoming account's balance exactly matches an existing account's balance. Accounts with matching balances are skipped and surfaced as named warnings:

> *"Skipped Synchrony Bank HIGH YIELD SAVINGS ($55,445.54) — balance matches existing account High Yield Savings."*

This catches the common case where the same account appears under a slightly different label across two statements.

### Dialog state persistence across reruns

The dialog now uses the `show_adjust_assets_dialog` session state flag (same pattern as `show_detailed_asset_choice_dialog`) so that `st.rerun()` calls during Phase 1 processing transition cleanly into Phase 2 without closing the dialog prematurely.

---

## Tests

Three tests updated to reflect the `INTEREST_INCOME` behavior for savings/checking/cash accounts:

- `test_post_tax_savings_uses_interest_income` (renamed from `test_post_tax_savings_uses_no_additional_tax`)
- `test_asset_from_editor_row_savings` — expected behavior updated
- `test_parse_uploaded_csv_preserves_tax_behaviors` — savings asset now expects `INTEREST_INCOME`

All 127 tests pass.

---

## Files Changed

| File | Change |
|---|---|
| `fin_advisor.py` | "Manage Your Portfolio" dialog; balance-based dedup; `_ADJUST_EDITOR_COLUMN_CONFIG` shared config; `_assets_to_editor_df()` helper; `show_adjust_assets_dialog` flag pattern; version bump |
| `financialadvisor/domain/models.py` | `TaxBehavior.INTEREST_INCOME` added; `infer_tax_behavior()` routes savings/checking/cash to `INTEREST_INCOME` |
| `financialadvisor/core/tax_engine.py` | `apply_tax_logic()` handler for `INTEREST_INCOME` — gains-only taxed at ordinary income rate |
| `tests/test_fin_advisor.py` | 3 tests updated for `INTEREST_INCOME` behavior |
| `financialadvisor/__init__.py` | Version bumped to 15.5.0 |
| `setup.py` | Version bumped to 15.5.0 |
| `CLAUDE.md` | Version updated to 15.5.0 |
| `RELEASE_NOTES_v15.5.0.md` | This file |
