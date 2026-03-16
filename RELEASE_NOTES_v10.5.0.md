# Smart Retire AI v10.5.0 Release Notes

**Release Date:** March 2026
**Version:** 10.5.0
**Previous Version:** 10.1.0

---

## 🎯 Release Overview

This is a **major feature release** introducing the **Income Goal Calculator** — a reverse planning mode that answers *"I want $X/year in retirement — how much do I need to save?"* — alongside several quality-of-life improvements to onboarding, state management, and UI consistency.

**Highlights:**
- 🔁 **Income Goal Calculator** — Enter a target after-tax income, get the required pre-tax portfolio instantly
- ⚡ **Live results** — Calculator updates automatically as you change inputs; results appear at the top of the page
- 🔗 **Shared state** — Values entered in the Income Goal Calculator carry forward to Personal Info and the What-If analysis, and vice versa
- 🧹 **Cleaner pages** — Title and legal disclaimer now shown only on the splash page
- 🐛 **Zero-income + legacy fix** — Reverse calculator now correctly handles "no income needed, but I want to leave money behind"

---

## ✨ New Features

### 1. Income Goal Calculator

A new reverse planning mode accessible from Step 2. Instead of entering accounts to get income, you enter a desired income to get the required portfolio.

**How to access:**
- When you reach Step 2, a popup asks how you'd like to plan
- Choose **"I have an income goal — show how much I need"**
- The mode label and a **Change** button appear at the top so you can switch at any time

**Inputs:**

| Field | Notes |
|---|---|
| Desired after-tax annual income | Pre-filled from Personal Info income goal |
| Retirement tax rate | Slider; uniform pre-tax treatment assumed (v1) |
| Legacy / end-of-life goal | Pre-filled from Personal Info |
| One-time expenses at retirement | Lump-sum deducted before simulation |
| Retirement age | Pre-filled from Personal Info |
| Life expectancy | Pre-filled from Personal Info |
| Portfolio growth rate | Slider |
| Inflation rate | Slider |

Every field has a **?** tooltip and a summary info box below it confirming the selected value — matching the style of the Personal Information step.

**Results (shown at top of page, live-updating):**
- Required pre-tax portfolio at retirement
- Modeled first-year after-tax income (verified by simulation)
- Assumptions summary (growth, inflation, tax rate, years in retirement)
- Notes for legacy goal and one-time expenses when set

**Social Security guidance** — A collapsible expander explains how to subtract estimated SS benefits from your income target, with links to [ssa.gov/myaccount](https://www.ssa.gov/myaccount) and the SSA Quick Calculator.

**Why:** Many users know what income they want in retirement but don't know how much to save. The forward calculator can't answer this directly — it requires trial and error. The Income Goal Calculator solves it in one step.

---

### 2. Cleaner UI on Non-Onboarding Pages

The main app title and the legal disclaimer expander are now shown **only on the splash page**.

**Before:** Title and disclaimer rendered on every page — onboarding, results, detailed analysis, and Monte Carlo.

**After:** All pages after the splash load without the title or disclaimer.

**Why:** Repeating the title and disclaimer on every page added visual noise and made the app feel unpolished on sub-pages.

---

## 🐛 Bug Fixes

### 1. Zero Income + Legacy Goal Returning Wrong Portfolio

**Severity:** High — affected users who wanted to model "no income, but leave money behind."

**Root Cause:**
When `target_after_tax_income = 0`, the reverse calculator short-circuited and returned only `life_expenses` as the required portfolio, ignoring any `legacy_goal` entirely.

**Fix:**
When income is zero but a legacy goal is set, the calculator now computes the present value of the legacy target — how much you need today to grow into that amount by end of life with zero withdrawals — and adds one-time expenses on top.

**Impact:** Users modeling a legacy-only scenario (e.g., "I don't need income but want to leave $500K") now receive a correct, non-zero portfolio figure.

---

### 2. Stale Results After Input Changes

**Severity:** Medium — could cause users to misread old results as current.

**Root Cause:**
Results were stored in a session state cache with no connection to the inputs that produced them. After calculating once, changing any input — income, tax rate, ages, growth rate — continued showing the old result until the button was pressed again.

**Fix:**
The cache and Calculate button have been removed entirely. The calculation now runs on every render, so results always reflect the current inputs.

---

### 3. Legacy Goal Not Carried from Personal Info

**Severity:** Medium — the legacy goal entered in Step 1 was silently ignored in the Income Goal Calculator.

**Root Cause:**
The Income Goal Calculator was reading from an intermediate session state key that is initialised to `0` at app startup — before Step 1 runs. So the value entered in Personal Info never reached the calculator.

**Fix:**
The calculator now reads directly from the key written by Step 1, ensuring the value carries through correctly.

---

### 4. Income Goal Calculator Not Rendering

**Severity:** Medium — selecting the second planning mode showed a blank page.

**Root Cause:**
A typo in the planning mode dialog didn't match the routing condition, so the Income Goal Calculator block was never entered.

**Fix:**
Both the dialog option and the routing check now use the same label.

---

### 5. What-If Reset Hardcoded Wrong Tax Rate

**Severity:** Low.

The "Reset to Baseline Values" button in the What-If analysis was restoring the retirement tax rate to 25% instead of the correct default of 22%. Fixed.

---

## 🎨 UI/UX Improvements

### 1. Live Results at Top of Page

Results now appear above the input fields. Since calculation is instant, there is no button to press — the required portfolio and confirmed income update as you adjust any control.

---

### 2. Shared State Across All Modes

Values changed in the Income Goal Calculator now propagate to Personal Info and the What-If analysis (and vice versa), so you never have to re-enter the same number in a different section.

| Field | Also updates |
|---|---|
| Income target | Personal Info income goal, What-If income goal |
| Legacy goal | Personal Info legacy goal, What-If legacy goal |
| One-time expenses | Personal Info expenses, What-If expenses |
| Retirement age | Personal Info retirement age, What-If retirement age |
| Life expectancy | Personal Info life expectancy, What-If life expectancy |
| Tax rate | What-If retirement tax rate |
| Growth rate | What-If growth rate |
| Inflation rate | What-If inflation rate |

---

### 3. Step 2 Header and Navigation

- Step 2 section heading reduced in size to reduce visual weight
- Step 1 "Next" button now reads **"Next: Planning Mode & Asset Configuration →"** to reflect the mode-selection step that follows

---

### 4. Key Features Updated on Splash Page

The splash page Key Features grid now includes:

> **🔁 Income Goal Calculator** — Know your target income? Calculate the pre-tax portfolio you need to save

---

### 5. Default Retirement Tax Rate: 25% → 22%

The default retirement tax rate used across the app has been corrected from 25% to **22%**, aligning with the Personal Information step default and the typical effective rate for most retirees.

---

## 📊 Technical Details

### Files Modified

| File | Change |
|------|--------|
| `fin_advisor.py` | All feature and bug fix changes |
| `financialadvisor/__init__.py` | Version bump to 10.5.0 |
| `setup.py` | Version bump to 10.5.0 |

### Session State Keys Added

| Key | Description |
|-----|-------------|
| `planning_mode_choice` | Stores the user's selected planning mode (forward or reverse) |

### Session State Keys Removed

| Key | Reason |
|-----|--------|
| `_goal_result_cache` | No longer needed — calculation runs live on every render |
| `_goal_result_cache_key` | No longer needed |

---

## 🔄 Migration Guide

### From v10.1.0 to v10.5.0

**No breaking changes.** Drop-in replacement.

**What users will notice:**

1. **New planning mode dialog at Step 2** — First-time visitors to Step 2 will see a popup asking which mode to use. Returning users can press "Change" to switch modes at any time.

2. **Title and disclaimer gone from onboarding/results pages** — This is intentional. The splash page still shows both.

3. **Legacy goal now pre-filled** — If you previously used the Income Goal Calculator and saw a legacy goal of $0, re-entering the value in Personal Info will now carry through correctly.

---

## ✅ Release Checklist

- [x] Version bumped to 10.5.0 in `fin_advisor.py`, `financialadvisor/__init__.py`, `setup.py`
- [x] `find_required_portfolio()` added with binary search, `life_expenses` support, and correct zero-income + legacy handling
- [x] Planning mode popup dialog added
- [x] Legal disclaimer dialog added; title + disclaimer removed from non-splash pages
- [x] Income Goal Calculator inputs match Personal Info style (tooltips + info boxes)
- [x] Results container moved to top of page
- [x] Calculate button removed; live calculation on every render
- [x] Session state sync block added for all shared fields
- [x] Legacy goal reads from `legacy_goal` directly
- [x] Default retirement tax rate corrected to 22% (session state init + What-If reset)
- [x] Step 2 heading size reduced
- [x] Step 1 Next button label updated
- [x] Splash page Key Features updated to include Income Goal Calculator
- [x] RELEASE_NOTES_v10.5.0.md created

---

## 🔗 Related Documentation

- **v10.1.0 Release Notes:** `RELEASE_NOTES_v10.1.0.md`
- **v10.0.0 Release Notes:** `RELEASE_NOTES_v10.0.0.md`

---

**Ready for deployment** 🚀
