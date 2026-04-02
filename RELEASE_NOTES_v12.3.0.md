# Smart Retire AI v12.3.0 Release Notes

**Release Date:** April 2026
**Version:** 12.3.0
**Previous Version:** 12.2.0

---

## 🎯 Release Overview

This release adds **calculation transparency** to the Simple Planning chat: when a user asks how their required corpus or portfolio was calculated, the advisor now walks through the full step-by-step math using the actual computed numbers — gross income before tax, the annuity present-value factor, and the year-by-year simulation method — citing the Present Value of a Growing Annuity formula (CFA curriculum, Investopedia). It also improves the first-run experience by replacing the auto-popup "What's New" dialog with a collapsed inline expander on the splash page.

---

## ✨ New Features

### Chat calculation explanation
- The Simple Planning advisor can now explain exactly how the required corpus/portfolio number was calculated when asked (e.g. "how did you come up with that?", "walk me through the math").
- Explanation covers: gross income needed before tax (`target ÷ (1 − tax_rate)`), the annuity PV factor derived from growth rate, inflation, and years in retirement, and the year-by-year simulation method used to find the precise corpus.
- Formula is attributed to the **Present Value of a Growing Annuity** (CFA curriculum, Investopedia) so users can verify it independently.
- Works for both 🇮🇳 India (₹, corpus) and 🇺🇸 US (\$, portfolio) — all values are country-specific.

---

## 🐛 Bug Fixes

### Chat response — dollar sign LaTeX rendering
- **Fixed**: GPT responses containing `$` amounts (e.g. `$256,410`) were rendered as LaTeX math by Streamlit, producing garbled inline code formatting.
- **Fix**: Assistant messages are post-processed before storage to escape bare `$` as `\$`, which Streamlit renders as a plain dollar sign.

---

## 🎨 UI/UX Improvements

### Release notes — splash page expander instead of auto-popup
- The "What's New" dialog no longer auto-opens on every session load.
- A collapsed `🆕 What's new in vX.Y.Z` expander now appears on the splash/welcome page below the "Get Started" button — visible when the user wants it, unobtrusive otherwise.
- The footer "What's new" button on all other pages is retained for users who want to re-read the full release notes at any time.

---

## 🔧 Internal Changes

### Chat advisor — calculation context injection
- `chat_with_advisor()` accepts a new `calc_context: Optional[str]` parameter. When provided, it is injected as a second system message (not shown in the chat UI) giving GPT the actual computed values and formula breakdown to reference.
- Intermediate values computed on each render: gross income, PV factor, real return. Stored in `st.session_state.chat_calc_context`.
- `max_tokens` raised from 600 → 900 to accommodate detailed explanations.

---

## 📦 Files Changed

- `fin_advisor.py` — version 12.3.0; calc context computation, `$` escaping, splash expander, removed auto-popup
- `integrations/chat_advisor.py` — `calc_context` param, updated system prompt (explanation rules, no-backtick instruction), `max_tokens` 600 → 900
- `setup.py` — version bumped to 12.3.0
- `financialadvisor/__init__.py` — version bumped to 12.3.0
- `RELEASE_NOTES_v12.3.0.md` — this file
