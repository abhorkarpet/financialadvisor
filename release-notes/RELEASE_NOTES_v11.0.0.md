# Smart Retire AI v11.0.0 Release Notes

**Release Date:** March 2026
**Version:** 11.0.0
**Previous Version:** 10.6.0

---

## 🎯 Release Overview

This is a **major release** that introduces **India mode** — full support for retirement corpus planning in India with ₹ INR currency, Indian financial terminology, and India-appropriate defaults. This is the first version of Smart Retire AI to support a non-US market.

**Highlights:**
- 🇮🇳 **India Corpus Planning** — complete ₹ INR experience for Indian users including NPS, EPF, PPF, and Equity MF context
- 🔄 **Smart country switching** — all defaults (inflation, growth rate, tax rate, retirement age) reset instantly when switching between US and India
- 📐 **Consistent terminology** — "Corpus" replaces "Portfolio" throughout the India experience; "Pension/NPS" replaces "Social Security"
- 🗂️ **Sidebar aware** — Advanced Settings sidebar reflects country-appropriate defaults for all sliders

---

## 🇮🇳 Feature: India Corpus Planning

### What's new

A **Country selector** (`🇺🇸 United States` / `🇮🇳 India`) has been added at the top of the Personal Information step. Selecting India activates a fully localized experience:

#### Mode gating
- India users see **only the Corpus Calculator** (Income Goal → Corpus) — the "I know my assets" flow is not shown, as it requires US-specific account types (401k, IRA, Roth)
- The planning mode dialog and "Change" button are suppressed for India

#### Currency & terminology
- All currency displays switch to **₹ (INR)**
- "Portfolio" → **"Corpus"** in all labels, metrics, and captions
- "Required Pre-Tax Portfolio" → **"Required Corpus at Retirement"**
- "Social Security" expander → **"Pension / NPS Annuity"** expander

#### India-specific defaults

| Parameter | India | US |
|---|---|---|
| Retirement age | 60 | 65 |
| Life expectancy | 85 | 90 |
| Corpus growth rate | 10% | 4% |
| Inflation rate | 7% | 3% |
| Retirement tax rate | 10% | 22% |
| Default investment growth | 10% | 7% |
| Income goal | ₹6,00,000/yr | $60,000/yr |

#### India-localized help text
- Income ranges in ₹ lakhs (₹3L–₹12L+)
- Expense/legacy ranges in ₹ lakhs/crores
- Life expectancy context for India (birth ~72 yrs, plan to 85–90)
- Growth rate guidance: debt MF (6–7%), balanced MF (8–10%), equity MF (10–12%), SWP strategy
- Inflation guidance: India long-run CPI ~5–7%, RBI target 4%

#### Pension / NPS Annuity expander (replaces Social Security)
Explains:
- NPS: 60% lump sum tax-free, 40% mandatory annuity (~5–6%/yr)
- EPF Pension (EPS): monthly pension from age 58, check via EPFO portal
- How to offset pension income from the corpus target (worked ₹ example)

#### Advanced Settings sidebar (India-aware)
- **Current & Retirement Tax Rate** sliders default to 10% with India New Tax Regime brackets
- **Inflation** slider defaults to 7% with RBI context
- **Investment Growth Rate** slider defaults to 10% with Indian MF ranges
- All help expanders show India-specific guidance

### Smart country switching
Switching country resets all affected defaults immediately via `st.rerun()`:
- Backing session state keys updated before rerun
- All Step 2 widget keys cleared so sliders re-initialize from new defaults
- Sidebar sliders use country-suffixed widget keys (e.g. `sidebar_current_tax_rate_India`) — a key change forces Streamlit to create a fresh widget with the correct default, bypassing the widget-state cache

### Splash screen update
The "Key Features" section on the welcome screen now includes:
> 🇮🇳 **India Corpus Planning** — Full ₹ INR support with Indian defaults — calculate the corpus you need for retirement in India

---

## 📦 Files Changed

- `fin_advisor.py` — Version bump to 11.0.0; India mode implementation throughout
- `RELEASE_NOTES_v11.0.0.md` — This file
