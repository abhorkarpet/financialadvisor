# Smart Retire AI v13.0.0 Release Notes

**Release Date:** April 2026
**Version:** 13.0.0
**Previous Version:** 12.5.1

---

## Release Overview

v13.0 is a major feature release that introduces an AI-powered conversational layer for the Detailed Planning results page. Users can now ask the advisor to explain their exact numbers, explore what-if scenarios with a confirmation-before-apply flow, and get precise answers about breakeven retirement age, required contributions, and Monte Carlo outcomes — all grounded in pre-computed Python values, never hallucinated estimates.

---

## New Features

### Detailed Planning — Post-Results Chat Advisor
A full conversational advisor is now embedded on the Detailed Planning results page.

- **Calculation explanations** — the advisor explains exactly how projected income was calculated, including the three-pot withdrawal sequencing (brokerage → pre-tax → Roth), IRS RMDs starting at age 73, and the different tax treatments for each account type.
- **Correct tax treatment** — brokerage withdrawals use the 15% capital gains rate on the gains fraction only (not the flat retirement tax rate). Pre-tax/RMD withdrawals use the configurable flat rate. Roth withdrawals are tax-free. The advisor is explicitly instructed never to mix these up.
- **Two-step what-if flow** — when the user asks a what-if question (e.g. "what if I retire at 60?"), the advisor explains the impact first, then asks "Want me to apply this scenario and update your numbers?" Key Metrics only update after the user explicitly confirms.
- **Instant message display** — user messages appear immediately on submit (before the API responds), eliminating the blank-screen wait.
- **Download transcript** — a "Download chat transcript" button appears once the conversation has more than the opening message, saving as Markdown.

### Exact Breakeven Retirement Age
- Python binary search finds the exact first retirement age (up to 80) where projected income meets the user's goal.
- The result is injected into the chat context with a "use this exact number, do NOT estimate" directive — the advisor never approximates with heuristics like "5% per year."

### Exact Additional Contribution Needed
- Python binary search calculates the exact additional annual contribution required to close an income gap.
- Respects IRS 401k/403b limits (2024: \$23,000 under-50, \$30,500 catch-up 50+).
- Full breakdown injected into context: how much goes to pre-tax/401k (with IRS capacity), how much overflows to taxable brokerage.

### Monte Carlo Integration in Chat
- A 500-simulation Monte Carlo run (seed=42, reproducible) executes on every results page load.
- Income p10/p50/p90 percentiles, portfolio percentiles, and probability of meeting the income goal are injected into the chat context.
- The advisor explains what each percentile means, interprets the probability of success, and directs users to the full Monte Carlo page for the complete distribution chart.

---

## UX Improvements

### Projected Annual Income delta indicator
- The Key Metrics "Projected Annual Income" tile now shows ↓ red when income is below the goal and ↑ green when above — previously the negative delta displayed incorrectly as ↑ green due to a `$` prefix in the delta string.

### Chat input bar always visible
- Fixed: the app footer was overlapping the `st.chat_input` bar on the results page. The footer is now suppressed on the results page so the input is always reachable.

### Dollar sign formatting
- All chat advisor prompts and context strings now escape `$` as `\$` to prevent Streamlit's LaTeX parser from consuming currency values.

---

## Infrastructure

### `financialadvisor/core/chat_context.py` (new module)
- `build_detailed_chat_context()` — assembles a compact (~1,100 token) portfolio context string injected as a system message each turn.
- Includes: account breakdown, year-by-year simulation snapshot (key years), breakeven age, contribution analysis, and Monte Carlo summary.

### New helpers in `fin_advisor.py`
- `find_breakeven_retirement_age()` — iterates retirement ages, runs full projection + withdrawal simulation at each, returns exact breakeven.
- `find_breakeven_contribution()` — binary search over additional annual contribution; distributes to pre-tax up to IRS limit, remainder to brokerage.
- `_render_results_chat_panel()` — two-pass Streamlit pattern for instant user-message display + async API response.
- `_build_chat_transcript_md()` — formats conversation history as a downloadable Markdown file.
- IRS contribution limit constants: `_IRS_401K_LIMIT`, `_IRS_IRA_LIMIT`.

### System prompt improvements (`integrations/detailed_planning_system_prompt.txt`)
- Full knowledge base: RMDs, Social Security, tax efficiency, withdrawal sequencing, Monte Carlo interpretation, what-if scenarios.
- Explicit tax treatment rules with CRITICAL warnings against mixing rates.
- Two-step what-if protocol replacing the previous single-step auto-apply.
- BOUNDARIES section: dollar-sign escaping, exact-value directives, no estimation rules.

### Setup advisor improvements (`integrations/chat_advisor.py`)
- Three-pass birth year extraction before injecting pre-computed facts into the system prompt: (1) `__data__` blocks, (2) regex scan for 4-digit year, (3) regex scan for "retire at N" pattern.
- Prevents GPT arithmetic errors on years-to-retirement calculation.

---

## Files Changed

- `fin_advisor.py` — results chat panel, two-pass render, breakeven functions, IRS constants, delta indicator fix, footer suppression on results page, version bump to 13.0.0
- `financialadvisor/core/chat_context.py` — new: portfolio context builder for post-results advisor
- `integrations/chat_advisor.py` — `chat_with_results_advisor()`, `chat_with_setup_advisor()` birth-year extraction, `_parse_whatif_block()`
- `integrations/detailed_planning_system_prompt.txt` — full knowledge base, two-step what-if flow, tax treatment rules
- `integrations/detailed_setup_system_prompt.txt` — confirmation word list, years-to-retirement injection rule, dollar-sign escaping
- `RELEASE_NOTES_v13.0.0.md` — this file
- `CLAUDE.md` — version updated to 13.0.0
