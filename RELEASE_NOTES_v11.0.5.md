# Smart Retire AI v11.0.5 Release Notes

**Release Date:** March 2026
**Version:** 11.0.5
**Previous Version:** 10.6.0

---

## 🎯 Release Overview

This release covers all changes since v10.6.0 across two increments — **v11.0.0** (India Corpus Planning) and **v11.0.5** (INR formatting polish and analytics).

**Highlights:**
- 🇮🇳 **India Corpus Planning** — full ₹ INR experience for Indian users (NPS, EPF, PPF, Equity MF context)
- 🔢 **Indian number formatting** — amounts displayed as ₹6,00,000 (lakhs/crores) not ₹600,000
- 🔄 **Smart country switching** — all defaults reset instantly when switching between US and India
- 📊 **Analytics updated** — `country` property on all onboarding events; new `country_selected` event

---

## 🇮🇳 v11.0.0 — India Corpus Planning

### Country selector
A **Country selector** (`🇺🇸 United States` / `🇮🇳 India`) was added at the top of the Personal Information step. Selecting India activates a fully localized experience.

### Mode gating
India users see **only the Corpus Calculator** (Income Goal → Corpus). The "I know my assets" flow and planning mode dialog are suppressed — they require US-specific account types (401k, IRA, Roth).

### Currency & terminology
- All currency displays switch to **₹ (INR)**
- "Portfolio" → **"Corpus"** throughout
- "Required Pre-Tax Portfolio" → **"Required Corpus at Retirement"**
- "Social Security" expander → **"Pension / NPS Annuity"** expander (explains NPS 60/40 rule, EPF pension, EPFO portal, worked ₹ example)

### India defaults

| Parameter | India | US |
|---|---|---|
| Retirement age | 60 | 65 |
| Life expectancy | 85 | 90 |
| Corpus growth rate | 10% | 4% |
| Inflation rate | 7% | 3% |
| Retirement tax rate | 10% | 22% |
| Default investment growth | 10% | 7% |
| Income goal | ₹6,00,000/yr | $60,000/yr |

### India-localized help text
- Income ranges in ₹ lakhs (₹3L–₹12L+), expense/legacy ranges in lakhs/crores
- Life expectancy stats for India (birth ~72 yrs, plan to 85–90)
- Growth guidance: debt MF (6–7%), balanced MF (8–10%), equity MF (10–12%), SWP strategy
- Inflation guidance: India long-run CPI ~5–7%, RBI target 4%

### Advanced Settings sidebar (India-aware)
- Current & Retirement Tax Rate sliders default to 10% (India New Tax Regime brackets in help)
- Inflation slider defaults to 7% (max 15%, RBI context in help)
- Investment Growth Rate slider defaults to 10% (Indian MF ranges in help)
- Sidebar sliders use country-suffixed widget keys so they re-initialize correctly on country switch

### Smart country switching
Switching country triggers `st.rerun()` after:
- All backing session state keys updated to country-appropriate values
- All Step 2 widget keys + income goal input key cleared so sliders/inputs re-initialize from new defaults
- Sidebar sliders auto-rotate via country-suffixed keys (avoids Streamlit "cannot modify after instantiation" error)

### Splash screen
"Key Features" section now includes:
> 🇮🇳 **India Corpus Planning** — Full ₹ INR support with Indian defaults — calculate the corpus you need for retirement in India

---

## 🔢 v11.0.5 — INR Formatting Polish & Analytics

### Indian number formatting
New `_fmt_inr()` / `_fmt_currency()` helpers format amounts in the Indian numbering system (last 3 digits, then groups of 2):

| Value | Before | After |
|---|---|---|
| 6,00,000 | ₹600,000 | ₹6,00,000 |
| 85,89,300 | ₹8,589,300 | ₹85,89,300 |
| 1,00,00,000 | ₹10,000,000 | ₹1,00,00,000 |

Applied to all 10 currency display points: income target, legacy goal, one-time deduction, results metrics, and caption strings.

US dollar formatting (`$600,000`) is unchanged.

### Analytics updates
- `track_onboarding_step_started` updated to accept `**kwargs` so `country` can be passed
- **New event**: `country_selected` — fires on every country switch with `country` and `previous_country` properties; also sets `country` as a **PostHog user property** (segments all future events for that user)
- `country` property added to: `onboarding_step1_started`, `onboarding_step1_completed`, `onboarding_step2_started`, `onboarding_step2_completed`, `onboarding_completed`
- `onboarding_completed` also sets `country` as a user property

---

## 📦 Files Changed

- `fin_advisor.py` — Version bump to 11.0.5; all India mode implementation and INR formatting
- `financialadvisor/__init__.py` — `__version__` bumped to 11.0.5
- `setup.py` — `version` bumped to 11.0.5
- `financialadvisor/utils/analytics.py` — `track_onboarding_step_started` accepts `**kwargs`
- `RELEASE_NOTES_v11.0.5.md` — This file
