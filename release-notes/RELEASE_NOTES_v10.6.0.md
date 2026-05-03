# Smart Retire AI v10.6.0 Release Notes

**Release Date:** March 2026
**Version:** 10.6.0
**Previous Version:** 10.5.0

---

## 🎯 Release Overview

This is a **financial accuracy release** that fixes a fundamental calculation error in the retirement income simulator. The Income Goal Calculator (and all withdrawal-based calculations) now use the **annuity due** methodology — the industry-standard approach used by Certified Financial Planners — rather than the ordinary annuity (end-of-year) model that was previously in use.

**Highlights:**
- ✅ **CFP-accurate corpus calculation** — Income Goal Calculator now matches the result produced by a CFP's Excel model for identical inputs
- 📈 **Annuity due simulation** — Withdrawals now correctly occur at the START of each year, matching real retirement cash flow behavior
- 🔁 **Consistent methodology** — Forward analysis, What-If analysis, and the Income Goal Calculator all benefit from the same fix

---

## 🐛 Bug Fix: Ordinary Annuity → Annuity Due

### What was wrong

The retirement income simulator grew the portfolio for a full year **before** making the first withdrawal. This is the "ordinary annuity" (end-of-year) model, which assumes a retiree waits 12 months before receiving their first dollar of income.

In practice, retirees need income **on Day 1 of retirement**. The correct model is the **annuity due** (beginning-of-year), where withdrawals occur at the start of each period and the remaining balance grows over the year.

### Impact on results

For a representative scenario (10% portfolio growth, 7% inflation, 10% tax rate, 35 years in retirement):

| | Before (v10.5) | After (v10.6) | CFP Excel |
|---|---|---|---|
| Required corpus for $34,000/yr after-tax | $780,846 | **$858,930** | $858,930 ✓ |

The fix closes a ~10% underestimate in the required retirement corpus. The math is exact:

```
$780,846 × (1 + 7% inflation) × (1 + 2.80% real return) = $858,930
```

Where `2.80%` is the **Real Rate of Return** from the Fisher equation: `(1 + 10%) / (1 + 7%) − 1`.

### What changed in the code

A single structural change in `simulate_retirement()`: the portfolio growth step was moved from **before** withdrawals to **after** withdrawals.

```
Old order: Grow portfolio → Take RMD → Withdraw (ordinary annuity)
New order: Take RMD → Withdraw → Grow portfolio (annuity due ✓)
```

### Secondary improvements (all correct)

- **RMD computation** now uses the start-of-year balance, which is more accurate (IRS RMDs are based on prior year-end balance)
- **Brokerage capital gains fraction** is computed on the start-of-year balance (correct for start-of-year withdrawals)
- **Forward analysis** and **What-If analysis** inherit the fix — sustainable income figures are slightly more conservative, which is the correct direction

---

## 🔢 Methodology Notes

The annuity due formula used by the CFP's Excel model:

```
RoR  = ((1 + portfolio_return) / (1 + inflation)) − 1      ← Fisher equation
PMT  = after_tax_income / (1 − tax_rate)                    ← gross-up for tax
PV   = PMT × [1 − (1+RoR)^−n] / RoR × (1+RoR)             ← annuity due (type=1)
```

The app's year-by-year simulation now produces identical results to this formula.

---

## 📦 Files Changed

- `fin_advisor.py` — Version bump to 10.6.0; `simulate_retirement()` withdrawal order fixed
- `RELEASE_NOTES_v10.6.0.md` — This file
