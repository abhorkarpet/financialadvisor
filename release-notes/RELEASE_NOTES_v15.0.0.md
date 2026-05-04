# Smart Retire AI v15.0.0 Release Notes

**Release Date:** April 2026
**Version:** 15.0.0
**Previous Version:** 14.0.0

---

## Release Overview

v15.0 consolidates the post-analysis experience into a single, cohesive results page. The redundant "View Full Details" page is eliminated, the chat panel is promoted to a primary layout element with persistent action buttons alongside it, and several noisy UI sections are collapsed or removed. Cash flow projection gains a line chart for at-a-glance understanding.

---

## Breaking Changes

### `full_details` page removed

The intermediate page (`current_page == 'full_details'`) no longer exists. Any stale `session_state` pointing there will fall through to the mode selection screen, which is the correct recovery path.

---

## New Features

### Unified results page layout

The results page now combines everything users need without requiring navigation:

- **Key metrics row** — 5 cards (Total FV, After-Tax Value, Tax Efficiency, Projected Annual Income) remain full-width at the top.
- **Narrative summary** — income/goal/tax sentence block, unchanged.
- **Two-column panel** — chat history + inline chat input on the left (`[3, 1]` ratio); "What you can do next" action buttons stacked vertically on the right.
- **Share & Feedback** — collapsed expander below the panel, preceded by a separator.
- **Footer** — version/copyright/contact block now appears on the results page (previously suppressed to avoid overlap with the sticky chat input).

### Inline chat input (no more sticky-to-bottom)

`_render_results_chat_panel` now renders inside `st.columns([3, 1])`, which causes `st.chat_input` to render inline rather than sticky to the viewport bottom. This unlocks natural page flow: action buttons appear alongside the chat, and Share & Feedback and the footer appear below — without workarounds.

### "What you can do next" action column

Three action buttons are always visible to the right of the chat panel:

| Button | Action |
|---|---|
| 📥 PDF Report | Opens the PDF generation dialog |
| 📊 View Cash Flow | Opens the cash flow projection dialog |
| 📈 Detailed Analysis | Navigates to the detailed analysis page |

Monte Carlo is surfaced as a natural suggestion in the chat opening message rather than a dedicated button.

### Cash flow dialog — line chart added

The cash flow dialog (`cashflow_dialog`) now renders a `st.line_chart` above the detail table, showing **Portfolio Balance** and **Annual After-Tax Income** by retirement age. The bare table (previously the only output) remains below the chart as a detail view.

### Income & Gap tab in Detailed Analysis

A fourth tab "🎯 Income & Gap" is added to the Detailed Analysis page:

- **3 metric cards** — Projected Annual Income, Income Goal, Annual Shortfall/Surplus with delta percentage.
- **Color-coded status banner** — success (surplus), warning (small gap), or error (large gap).
- **Gap-closing table** — when a shortfall exists: Option 1 (retire later — breakeven age + income at that age) and Option 2 (save more — required annual contribution increase with per-account breakdown).
- Values are deterministic Python computations persisted from the results page via `st.session_state`; no LLM call.

---

## UI Polish

### Collapsed by default

| Section | Change |
|---|---|
| 💬 Data Extraction Feedback | Changed from always-visible to `st.expander(expanded=False)` |
| 💬 Share & Feedback | Moved below chat panel; remains collapsed by default |

### Removed

| Section | Reason |
|---|---|
| 🔍 Tax Bucket Breakdown | Redundant detail; information available in Detailed Analysis tabs |
| 📋 What's new (footer button) | Removed from all non-splash pages; remains as `🆕 What's new` expander on the splash screen only |

---

## Files Changed

| File | Change |
|---|---|
| `fin_advisor.py` | Results page restructured; `full_details` page deleted; cash flow dialog chart added; Income & Gap tab added; Data Extraction Feedback collapsed; Tax Bucket Breakdown removed; footer shown on all pages; What's new button removed from footer |
| `RELEASE_NOTES_v15.0.0.md` | This file |
| `CLAUDE.md` | Version updated to 15.0.0 |
