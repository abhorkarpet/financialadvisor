# Smart Retire AI v12.0.0 Release Notes

**Release Date:** March 2026
**Version:** 12.0.0
**Previous Version:** 11.0.5

---

## 🎯 Release Overview

This release introduces **Simple Planning** — a conversational chat interface for users who
want to quickly find out how much they need to retire without filling in a detailed form.

**Highlights:**
- 💬 **Simple Planning mode** — answer 3 questions in a chat; get your required corpus/portfolio instantly
- 🤖 **GPT-4.1-mini integration** — collects fields conversationally in 2–3 exchanges
- 📊 **Live results panel** — required portfolio updates in real time as you answer
- 🗂️ **Mode selection upfront** — clear cards replace the buried mid-onboarding dialog
- 📥 **Export** — PDF report (results + assumptions) and markdown chat transcript

---

## 💬 Simple Planning Mode

### Mode selection cards
After the splash screen, users now choose between two clear cards:
- **💬 Simple Planning** — conversational chat → corpus estimate in under a minute
- **📊 Detailed Planning** — existing form-based flow for users with full asset breakdowns

The previous planning mode dialog (buried mid-onboarding) has been replaced by this upfront selection.

### Chat + Live Results split-pane
The Simple Planning page is a side-by-side layout:
- **Left**: scrollable chat history + input box
- **Right**: live Required Portfolio / Corpus metric that updates as fields are confirmed

The advisor collects everything in 2–3 exchanges:
1. **Turn 1** (opening): asks country, birth year, and target income together
2. **Turn 2**: confirms all country-specific defaults in one block (retirement age, life expectancy, tax rate, growth rate, inflation, legacy)
3. **Turn 3**: user confirms or adjusts → calculation is complete

### Country-aware from the first message
The system prompt is built with the correct currency ($ or ₹) as soon as the user's first message mentions a country — no waiting for field extraction to complete.

### Monthly vs. annual income clarification
If the user enters an amount that is clearly a monthly figure (below $20,000/yr for US, ₹1,50,000/yr for India), the advisor asks for clarification and multiplies by 12 if confirmed monthly.

### India / US defaults

| Parameter | India | US |
|---|---|---|
| Retirement age | 60 | 65 |
| Life expectancy | 85 | 90 |
| Growth rate | 10% | 4% |
| Inflation rate | 7% | 3% |
| Tax rate | 10% | 22% |

---

## 📥 Export

### PDF Report (right panel)
"📥 Download PDF Report" generates a ReportLab PDF with:
- Required Portfolio / Corpus metric
- Modeled first-year after-tax income
- Full assumptions table
- Disclaimer

### Chat Transcript (left panel)
"⬇ Download transcript" generates a markdown `.md` file with:
- Full conversation (You / Advisor labels)
- Confirmed plan summary at the bottom

---

## 🐛 Bug Fixes

- **Double opening message**: the greeting was rendered twice on first load (direct render + history loop). Fixed by appending to session state before the render loop.
- **Wrong currency in clarification**: monthly/annual question used `$` even for India users on the first message. Fixed by detecting country from the user's message text before building the system prompt.
- **Re-asking birth year on country switch**: LLM would re-request already-confirmed fields when country changed. Fixed via explicit system prompt rule.
- **$200k flagged as ambiguous**: threshold for monthly/annual check was too loose. Now only triggers below $20,000 (US) or ₹1,50,000 (India).

---

## 📦 Files Changed

- `fin_advisor.py` — Version 12.0.0; mode selection, chat mode page, routing, session state
- `integrations/chat_advisor.py` — New: GPT-4.1-mini integration, system prompt, field extraction
- `requirements.txt` — Added `openai>=1.0.0`
- `.env.example` — Added `OPENAI_API_KEY=`
- `setup.py` — Version bumped to 12.0.0
- `RELEASE_NOTES_v12.0.0.md` — This file

---

## ⚙️ Setup

Add to `.env`:
```
OPENAI_API_KEY=sk-...
```

Install new dependency:
```
pip install openai>=1.0.0
```
