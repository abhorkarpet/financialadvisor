# Smart Retire AI v10.0.0 Release Notes

**Release Date:** March 3, 2026
**Version:** 10.0.0
**Previous Version:** 9.1.0

---

## 🎯 Release Overview

This is a **major release** focused on making retirement projections significantly more accurate. The core calculation engine has been rewritten to model how retirement income is actually withdrawn — with proper Required Minimum Distribution (RMD) enforcement, tax-aware withdrawal sequencing across account types, and a live year-by-year Cash Flow Projection.

**Highlights:**
- 📅 **Required Minimum Distributions (RMDs)** — IRS Uniform Lifetime Table (2024) enforced from age 73
- 🔀 **Withdrawal sequencing** — RMD → Brokerage → Roth → Pre-tax drawdown order
- 📊 **Cash Flow Projection** — Year-by-year table of income, withdrawals, and tax paid
- 🏛️ **Legacy Goal** — Set a target portfolio balance to leave behind
- 🗑️ **Removed Tax Rate (%) CSV column** — Tax rates are now auto-derived from account type
- ⚠️ **Smarter CSV parsing** — Handles `$`, `,`, `%`, and decimal fractions; surfaces warnings
- 📄 **Cash flow table in PDF reports**
- 📋 **What's New dialog** — This screen, auto-shown on first visit each session

---

## 🚨 Breaking Changes

### CSV Upload Template: `Tax Rate (%)` Column Removed

**Previous Behavior (v9.1.0):**
- CSV template included a `Tax Rate (%)` column
- Users had to know and enter the correct capital gains rate per account

**New Behavior (v10.0.0):**
- `Tax Rate (%)` column removed from the template and parser
- Rate is now auto-derived from the account type:
  - **POST_TAX (non-Roth / brokerage):** 15% long-term capital gains
  - **PRE_TAX, Roth, TAX_DEFERRED:** 0% (rate is unused — withdrawals are taxed as ordinary income at retirement)

**Migration Path:**
If you have a saved CSV with a `Tax Rate (%)` column, simply delete that column before uploading. The file will parse correctly.

---

### `parse_uploaded_csv()` Now Returns a Tuple

**Previous:** returned `List[Asset]`
**New:** returns `(List[Asset], List[str])` — the second element is a list of human-readable warning messages surfaced to the user.

---

## ✨ Major Features

### 1. Required Minimum Distributions (RMDs)

Starting at age 73, the IRS requires withdrawals from pre-tax accounts (401k, Traditional IRA, and tax-deferred accounts). The simulation now enforces this using the **IRS Uniform Lifetime Table (2024)** from Publication 590-B.

**How it works:**
- Each year from age 73 onward, the pre-tax balance is divided by the IRS distribution period for that age
- The RMD is withdrawn first, before any voluntary withdrawals
- Ordinary income tax is applied at the retirement tax rate
- If the RMD after-tax amount exceeds spending needs, the surplus is reinvested into the brokerage account (with full cost basis)

**Example (age 75, $500,000 pre-tax):**
```
Distribution period: 24.6
RMD = $500,000 / 24.6 = $20,325
After-tax RMD (at 22%) = $15,854
```

---

### 2. Tax-Aware Withdrawal Sequencing

Withdrawals are now drawn in a tax-efficient order each year:

```
1. RMD from pre-tax (forced, if age ≥ 73)
2. Taxable brokerage (capital gains on gains portion only)
3. Roth IRA (tax-free)
4. Additional pre-tax if still short (ordinary income tax)
```

Capital gains tax on brokerage withdrawals is applied only to the **gains fraction** (market value minus cost basis), not the entire withdrawal.

---

### 3. `find_sustainable_withdrawal()` with Legacy Goal

A binary search algorithm finds the maximum sustainable annual withdrawal that:
- Funds inflation-adjusted income for the full retirement period
- Leaves at least `legacy_goal` dollars in the portfolio at life expectancy

**Legacy Goal** is a new user-facing field: set it to $0 (default, portfolio runs to zero) or a positive amount to preserve an estate.

---

### 4. Cash Flow Projection (Live & in PDF)

The "Coming Soon" Cash Flow Projection button is now fully implemented.

**What it shows (year-by-year table):**

| Year | Age | RMD | Brokerage W/D | Roth W/D | Extra Pre-Tax | Tax Paid | After-Tax Income | Total Portfolio |
|------|-----|-----|---------------|----------|---------------|----------|-----------------|-----------------|
| 1    | 65  | —   | $18,500       | —        | $3,000        | $660     | $53,840         | $1,241,000      |
| ...  | ... | ... | ...           | ...      | ...           | ...      | ...             | ...             |

The same table is also included at the end of the **PDF report**.

---

### 5. Smarter CSV Number Parsing

The CSV parser now handles a wider range of input formats without errors:

| Input | Interpreted as |
|-------|----------------|
| `25`  | 25% |
| `25%` | 25% |
| `0.25` | 25% (decimal fraction detected) |
| `$150,000` | 150,000 |
| `1` for a rate field | 1% (warning shown) |

A warning is surfaced to the user when an ambiguous value like `"1"` is entered for a rate field (it could mean 1% or 100%).

---

### 6. What's New Dialog

This dialog auto-appears on the first page load of each browser session. It can also be re-opened at any time from the **"📋 What's new in v{version}"** button in the footer.

---

## 🐛 Bug Fixes

1. **Retirement tax rate default corrected**
   - **Before:** Default was 25%
   - **After:** Default is 22% (more typical for retirees in the 22% bracket)

2. **CSV upload error on valid files with `%` or `$` characters**
   - Values like `$150,000` or `7%` now parse correctly instead of raising `ValueError`

3. **PDF report: clipped text in wide tables**
   - Account name and tax columns now use wrapped paragraphs, preventing text cutoff

---

## 📊 Technical Details

### New Functions

| Function | Description |
|----------|-------------|
| `simulate_retirement()` | Year-by-year retirement simulation with RMDs and withdrawal sequencing |
| `_rmd_distribution_period(age)` | Returns IRS Uniform Lifetime Table distribution period |
| `find_sustainable_withdrawal()` | Binary search for max sustainable withdrawal given a legacy goal |
| `cashflow_dialog()` | `@st.dialog` showing the year-by-year cash flow table |
| `whats_new_dialog()` | `@st.dialog` showing these release notes |
| `load_release_notes()` | Reads `RELEASE_NOTES_v{VERSION}.md` from the project directory |

### Session State Keys Added

| Key | Description |
|-----|-------------|
| `cashflow_sim_data` | Full year-by-year simulation output for Cash Flow dialog |
| `baseline_legacy_goal` | User's legacy goal from onboarding |
| `whatif_legacy_goal` | Legacy goal adjusted in what-if scenario panel |
| `whats_new_shown` | Flag preventing auto-show on every rerun within a session |
| `show_whats_new` | Trigger flag for the What's New dialog |

### Files Modified

- `fin_advisor.py` — Core simulation engine, CSV parser, dialogs, footer, version bump
- `financialadvisor/__init__.py` — Version bump
- `setup.py` — Version bump

---

## 🔄 Migration Guide

### From v9.1.0 to v10.0.0

**CSV Templates:**
- Remove the `Tax Rate (%)` column from any saved templates
- All other columns are unchanged

**Behavioral Changes Users Will Notice:**
1. Retirement income figures may change slightly — the new simulation accounts for RMDs, which the previous model did not
2. Cash Flow Projection button is now active (no longer "Coming Soon")
3. A legacy goal field appears in the what-if panel
4. "What's New" dialog appears on first load

---

## ✅ Release Checklist

- [x] Version bumped to 10.0.0 in `fin_advisor.py`, `financialadvisor/__init__.py`, `setup.py`
- [x] RMD simulation implemented with IRS 2024 Uniform Lifetime Table
- [x] Withdrawal sequencing (RMD → Brokerage → Roth → Pre-tax) implemented
- [x] `find_sustainable_withdrawal()` with legacy goal
- [x] Cash Flow Projection dialog implemented
- [x] Cash flow table added to PDF report
- [x] `Tax Rate (%)` column removed from CSV template and parser
- [x] Smarter number/percentage parsing with warnings
- [x] What's New dialog with auto-show on first session load
- [x] Footer "What's new" button

---

## 🔗 Related Documentation

- **v9.1.0 Release Notes:** `RELEASE_NOTES_v9.1.0.md`
- **v9.0.0 Release Notes:** `RELEASE_NOTES_v9.0.0.md`

---

**Ready for deployment** 🚀
