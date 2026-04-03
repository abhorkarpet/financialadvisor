# Smart Retire AI v12.2.0 Release Notes

**Release Date:** April 2026
**Version:** 12.2.0
**Previous Version:** 12.1.0

---

## 🎯 Release Overview

This release delivers two quality-of-life improvements to the **Simple Planning** chat experience: personalized avatars for the advisor and user, and a fix that prevents completed chat sessions from hijacking the "Back to Setup" navigation after switching to detailed planning mode.

---

## 🎨 UI/UX Improvements

### Chat Avatars *(introduced in 12.1.0)*
- The chat advisor now displays a **🧑‍💼 advisor emoji avatar** for all assistant messages.
- The user's messages now display a **🧑 person emoji avatar**.
- Previously both roles used Streamlit's generic default icons.

---

## 🐛 Bug Fixes

### Back to Setup routing after mode switch
- **Fixed**: A user who completed Simple Planning (chat) and then switched to Detailed Planning could finish onboarding and click "← Back to Setup" only to be sent back to the chat page instead of the onboarding form.
- **Root cause**: The `chat_complete` session flag is global and was never cleared on mode switch, so the back button always routed to `chat_mode` once it was set.
- **Fix**: Navigation to results now records a `results_source` key (`'onboarding'` or `'chat_mode'`) at the point of transition. The back button uses this explicit source instead of the stale `chat_complete` flag.

### Chat results pane — numeric value parsing
- **Fixed**: `int()` / `float()` conversions on model-extracted fields (`retirement_age`, `life_expectancy`, `target_income`, `tax_rate`, `growth_rate`, `inflation_rate`, `legacy_goal`, `life_expenses`) raised `ValueError` when the LLM returned formatted strings (e.g. `"1,20,000"`, `"₹50,000"`, `"65 years"`), crashing the live results pane.
- **Fix**: Introduced `_to_float` / `_to_int` helpers that strip commas, `$`, and `₹` before conversion and return a safe fallback on failure. Validation now distinguishes unparseable values (shows a re-entry prompt) from logically invalid values (e.g. life expectancy ≤ retirement age).

---

## 📦 Files Changed

- `fin_advisor.py` — Version 12.2.0; chat avatars, `results_source` routing, `_to_float`/`_to_int` helpers
- `setup.py` — Version bumped to 12.2.0
- `financialadvisor/__init__.py` — Version bumped to 12.2.0
- `RELEASE_NOTES_v12.2.0.md` — This file
