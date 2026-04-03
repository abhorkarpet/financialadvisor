# Smart Retire AI v10.1.0 Release Notes

**Release Date:** March 2026
**Version:** 10.1.0
**Previous Version:** 10.0.0

---

## 🎯 Release Overview

This is a **minor release** building on the v10.0.0 simulation engine. It corrects a capital-gains tax over-calculation introduced in the brokerage cost-basis formula, adds educational content around Required Minimum Distributions, and delivers a set of quality-of-life improvements to navigation, number formatting, and form state retention.

**Highlights:**
- 🐛 **Brokerage tax fix** — Cost basis now correctly includes the account's initial balance, ending overstated capital gains
- 📖 **RMD education** — New collapsible explainer with a plain-English summary and official IRS link
- 🏠 **Home button** — Persistent sidebar shortcut back to the Results page from any sub-page
- 💲 **Comma-formatted numbers** — Year-by-year withdrawal table now shows `$1,234,567` not `$1234567`
- 🏷️ **Readable asset labels** — Asset type dropdown shows "Pre-Tax / After-Tax / Tax-Deferred" instead of raw enum values
- 💾 **Setup form persistence** — Configuration method and asset count survive back-navigation

---

## 🐛 Bug Fixes

### 1. Brokerage Account Capital Gains Overstated

**Severity:** High — affected all users with a non-zero starting brokerage balance.

**Root Cause:**
When calculating taxable gains on brokerage accounts, the cost basis was computed as contributions only, excluding the account's initial balance:

```python
# v10.0.0 (incorrect)
gains = max(0, future_value - total_contributions)
```

This meant the full opening balance was treated as untaxed gain, inflating capital-gains tax on every brokerage projection.

**Fix (`financialadvisor/core/tax_engine.py`):**

```python
# v10.1.0 (correct)
cost_basis = asset.current_balance + total_contributions
gains = max(0, future_value - cost_basis)
```

**Impact:**
- After-tax brokerage values will be **higher** than in v10.0.0 for any account with an existing balance at analysis time.
- The larger the starting balance relative to contributions, the larger the correction.
- Pre-tax and Roth accounts are unaffected.

**Example:**

| Scenario | v10.0.0 | v10.1.0 |
|----------|---------|---------|
| $50,000 starting balance, $3,000/yr × 20 yrs at 7% | Over-taxes the $50K as pure gain | Correctly treats $50K as already-paid basis |

**Related cleanup:** The disclaimer warnings about brokerage taxation assumptions that appeared in the PDF report and asset breakdown table have been removed, as the underlying limitation is resolved.

---

## ✨ New Features

### 1. RMD Explanation in the Retirement Income Expander

The "📊 How Is Retirement Income Calculated?" expander now includes a dedicated collapsible section:

> **ℹ️ What is a Required Minimum Distribution (RMD)?**

**Contents:**
- Plain-English definition of RMDs
- Key facts: age-73 trigger (SECURE 2.0 Act), IRS Uniform Lifetime Table calculation, 25% penalty for missed distributions, Roth IRA exemption, reinvestment of excess RMD
- Direct link to the official IRS page: [IRS.gov — Required Minimum Distributions](https://www.irs.gov/retirement-plans/plan-participant-employee/required-minimum-distributions)

The numbered simulation steps also now spell out the full term on first use: **"Required Minimum Distributions (RMDs)"** instead of the abbreviation alone.

**Why:** User research indicated that the RMD column in the cash flow table was confusing to users who weren't familiar with the term. The explainer surfaces the information in context without cluttering the main view.

---

### 2. Home Button in Sidebar

A **"🏠 Results Dashboard"** button now appears in the sidebar whenever the user is on the Detailed Analysis or Monte Carlo pages.

**Behavior:**
- Visible only on `detailed_analysis` and `monte_carlo` pages
- Hidden on Results and Onboarding pages (not needed there)
- Sets `current_page = 'results'` and reruns — identical to the existing "← Back to Results" page-level button, but always reachable from the sidebar regardless of scroll position

**Why:** Users navigating from Results → Monte Carlo → scrolling through simulation output had no way to jump back to Results without scrolling back to the top of the page. The sidebar button provides a consistent escape hatch.

---

## 🎨 UI/UX Improvements

### 1. Cash Flow Table: Comma-Separated Currency

All dollar columns in the year-by-year withdrawal table now display with thousands separators.

| Column | v10.0.0 | v10.1.0 |
|--------|---------|---------|
| RMD | `$1234567` | `$1,234,567` |
| Brokerage W/D | `$98000` | `$98,000` |
| Tax Paid | `$4500` | `$4,500` |
| Total Portfolio | `$2400000` | `$2,400,000` |

Zero-value cells continue to display blank (not `$0`) to reduce visual noise on rows where an account type isn't drawn from.

This change applies to both the **"📊 How Is Retirement Income Calculated?"** expander on the Results page and the **Cash Flow Projection** dialog.

---

### 2. Asset Type Dropdown: Human-Readable Labels

The asset type selector in "Configure Individual Assets" previously displayed raw enum values in parentheses:

```
401(k) / Traditional IRA (pre_tax)
Roth IRA (post_tax)
HSA (Health Savings Account) (tax_deferred)
```

It now shows plain English labels separated by an em-dash:

```
401(k) / Traditional IRA — Pre-Tax
Roth IRA — After-Tax
HSA (Health Savings Account) — Tax-Deferred
Brokerage Account — After-Tax
Savings Account — After-Tax
Annuity — Tax-Deferred
```

---

### 3. Asset Setup Form State Persistence

Previously, navigating away from Step 2 (Asset Configuration) and returning would reset two key fields:

**Configuration method radio button:**
- Before: Always defaulted back to the first option ("Upload Financial Statements (AI)")
- After: Remembers the last selected method. If "Configure Individual Assets" was used, the radio button returns to that selection on next visit.

**Number of assets:**
- Before: Recalculated from `max(len(assets), 3)` on every render, forcing a minimum of 3 even if the user had set it to 1 or 2.
- After: Stored in session state (`num_assets_manual`). Whatever number the user set is preserved across navigation and Streamlit reruns.

---

## 📊 Technical Details

### Files Modified

| File | Change |
|------|--------|
| `fin_advisor.py` | Home button, table formatting, RMD expander, asset labels, form persistence |
| `financialadvisor/core/tax_engine.py` | Cost-basis bug fix |
| `financialadvisor/__init__.py` | Version bump to 10.1.0 |
| `setup.py` | Version bump to 10.1.0 |

### Session State Keys Added

| Key | Description |
|-----|-------------|
| `setup_method_radio` | Persists the selected asset configuration method (radio button) |
| `num_assets_manual` | Persists the number of assets entered in manual configuration |

### Code Quality

- `_ASSET_TYPE_LABELS` dict moved from inside the `for i in range(num_assets)` render loop to a single allocation before the loop.
- `st.popover` (requires Streamlit ≥ 1.31) replaced with `st.expander` for the RMD explainer, maintaining compatibility with Streamlit ≥ 1.28 as specified in `requirements.txt`.
- Dollar columns in the withdrawal table switched from `st.column_config.NumberColumn(format="$%d")` to `st.column_config.TextColumn` with pre-formatted strings (`f"${v:,.0f}"`), which is version-safe and guarantees comma rendering.

---

## 🔄 Migration Guide

### From v10.0.0 to v10.1.0

**No breaking changes.** Drop-in replacement.

**What users will notice:**

1. **Brokerage after-tax values may increase** — The cost-basis fix means previously overstated tax liabilities are now correct. If a projection shows a higher after-tax brokerage value than before, that is expected and more accurate.

2. **Cash Flow table looks different** — Dollar amounts now have commas. No change to underlying values.

3. **New RMD explainer in the retirement income section** — Collapsed by default, no change to layout.

4. **Sidebar home button** — Appears only on sub-pages; no change to main Results or Onboarding pages.

---

## ✅ Release Checklist

- [x] Version bumped to 10.1.0 in `fin_advisor.py`, `financialadvisor/__init__.py`, `setup.py`
- [x] Brokerage cost-basis bug fixed in `tax_engine.py`
- [x] Outdated brokerage tax disclaimer warnings removed (PDF + asset table)
- [x] RMD explainer expander added with IRS link
- [x] "Required Minimum Distributions (RMDs)" spelled out on first use in simulation steps
- [x] Cash flow table columns switched to comma-formatted strings (both dialog and expander)
- [x] Asset type labels updated to human-readable format
- [x] `setup_method_radio` key added to `st.radio` for persistence
- [x] `num_assets_manual` key added to `st.number_input` for persistence
- [x] `🏠 Results Dashboard` sidebar button added for detailed_analysis and monte_carlo pages
- [x] `_ASSET_TYPE_LABELS` moved out of render loop
- [x] `st.popover` replaced with `st.expander` for Streamlit ≥ 1.28 compatibility
- [x] CHANGELOG_10.1.0.md created

---

## 🔗 Related Documentation

- **v10.0.0 Release Notes:** `RELEASE_NOTES_v10.0.0.md`
- **v9.1.0 Release Notes:** `RELEASE_NOTES_v9.1.0.md`
- **Changelog:** `CHANGELOG_10.1.0.md`

---

**Ready for deployment** 🚀
