# Smart Retire AI v16.5.0 Release Notes

**Release Date:** May 2026
**Version:** 16.5.0
**Previous Version:** 16.0.0

---

## Release Overview

v16.5.0 is a UI polish and UX clarity release. It simplifies the verbose multi-phase upload status messages in the statement upload flow, upgrades the Detailed Planning right panel to use `st.markdown` for richer formatting, adds a Social Security / pension disclaimer, refines the "Add / Manage Accounts" button enablement logic to rely on the setup-chat completion flag rather than individual field checks, guards auto-calculation against zero-balance portfolios, and updates the setup advisor system prompt to reference the correct button label.

---

## Features / Changes

### Simplified upload progress messages

The multi-phase status labels shown during statement upload have been condensed. Labels previously read `Phase 1/2: Uploading` / `Phase 2/2: AI Processing — Reading PDF` / `Phase 2/2: AI Processing — Analyzing` / `Phase 2/2: AI Processing — Done`. They now use concise inline labels:

| Stage | Before | After |
|---|---|---|
| Upload | `📤 Phase 1/2: Uploading N file(s) to AI processor...` | `📤 Uploading N file(s)…` |
| Reading PDF | `📄 Phase 2/2: AI Processing (label) — Reading PDF: name ⏱️ Xs` | `📄 Reading name (label) ⏱️ Xs` |
| AI call | `🤖 Phase 2/2: AI Processing (label) — Analyzing name (part X/Y) with GPT-4 ⏱️ Xs` | `🤖 Analyzing name part X/Y (label) ⏱️ Xs` |
| File done | `✅ Phase 2/2: AI Processing (label) — Done: name ⏱️ Xs` | `✅ Done name (label) ⏱️ Xs` |
| Batch start | `🤖 Phase 2/2: AI Processing — Analyzing N statement(s) with GPT-4...` | `🤖 Analyzing N statement(s)…` |

### "Add / Manage Accounts" button enablement simplified

`_can_add` in `_render_dp_right_panel` previously derived its value by checking whether `birth_year` and `retirement_age` were present in `setup_fields` or `session_state`. It now reads `st.session_state.dp_goals_done` directly — the flag already set by the setup chat advisor when onboarding is complete. The associated help text was updated from `"Share your birth year and retirement age in the chat first."` to `"Complete the setup chat first."`.

### Setup advisor prompt references updated

`integrations/detailed_setup_system_prompt.txt` now instructs the advisor to tell users `"Hit **Add/Manage Account** on the right to add your accounts."` (previously `"Hit **Continue** below…"`), and the TURN 4+ closing message now references the **Add/Manager Accounts** button and **Key Results** panel to match the current UI layout.

---

## Bug Fixes

### Auto-calculation skipped for zero-balance portfolios

`_render_dp_right_panel` previously triggered the projection auto-calculation whenever `assets` was non-empty, regardless of whether any account had a balance. It now additionally checks `_total_balance > 0`, preventing spurious calculation runs (and the misleading results they produced) when all accounts are placeholder entries with a `$0` balance. A helper caption `"All accounts have a $0 balance — add balances to see your projection."` is shown in this state.

### Unused field variables removed from `_render_dp_right_panel`

`fields`, `by`, and `ra` were extracted from `session_state` at the top of the function but used only for the old `_can_add` check. Now that `_can_add` reads `dp_goals_done`, these three variables are no longer needed and have been removed, eliminating dead reads from session state.

---

## UI Changes

### Portfolio and tax efficiency lines promoted to `st.markdown`

`st.caption` calls rendering the portfolio total, income line, and tax efficiency were replaced with `st.markdown`. The text now renders at normal body weight rather than caption size, making key projection figures easier to read at a glance.

### Monte Carlo label expanded

The compact inline MC label was `MC **X%**`. It now reads `Monte Carlo Simulation success probability **X%**` for clarity — users no longer need to know what "MC" means.

### Social Security / pension disclaimer added

An `st.info` callout `"Does not account for Social Security, pensions, or other income sources."` is displayed directly below the projection summary lines whenever results are shown. This surfaces a material caveat that was previously absent from the results view.

---

## Files Changed

| File | Change |
|---|---|
| `fin_advisor.py` | Upload status messages condensed; `_render_dp_right_panel` refactored — `st.caption` → `st.markdown`, MC label expanded, SS/pension disclaimer added, `_can_add` simplified, zero-balance guard + caption added, dead variables removed; version bumped to 16.5.0 |
| `integrations/detailed_setup_system_prompt.txt` | Button label references updated to match current UI |
| `financialadvisor/__init__.py` | Version bumped to 16.5.0 |
| `setup.py` | Version bumped to 16.5.0 |
| `CLAUDE.md` | Version updated to 16.5.0 |
| `README.md` | Version updated to 16.5.0 |
| `RELEASE_NOTES_v16.5.0.md` | This file |
