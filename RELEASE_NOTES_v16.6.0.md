# Smart Retire AI v16.6.0 Release Notes

**Release Date:** May 2026
**Version:** 16.6.0
**Previous Version:** 16.5.0

---

## Release Overview

v16.6.0 is a tooling and session-state correctness release. It extends `update_version.sh` with an automated PR-creation step using the GitHub CLI, and fixes a bug where returning to Detailed Planning after a "Start Over" would retain stale DP-specific session state (goals, chat messages, calculation cache, and asset hash) from the previous session.

---

## Features / Changes

### `update_version.sh` — automated PR creation (Step 4/4)

A new "Step 4/4" section is appended to the version-bump script. When `gh` (GitHub CLI) is available and the current branch is not `main`/`master`, the script prompts to create a pull request targeting `main`. Answering `Y` calls:

```bash
gh pr create \
  --title "release: v${NEW_VERSION}" \
  --base main \
  --body "..."
```

The PR body includes a standard checklist (version bumps, docs, release notes) and a Claude Code attribution footer. If `gh` is not on `PATH`, or if the user answers `N`, the step is skipped gracefully with a manual fallback command printed to the terminal. The existing interactive step count updated from 3 to 4.

---

## Bug Fixes

### Detailed Planning "Start Over" now fully clears DP session state

The "Start Over" handler in `fin_advisor.py` clears `setup_messages`, `setup_fields`, and `setup_fields_locked` unconditionally. However, when triggered from within Detailed Planning (`current_page == 'detailed_planning'`), four additional DP-specific keys were left populated:

| Key | Effect when stale |
|---|---|
| `dp_goals_done` | "Add / Manage Accounts" button already enabled on re-entry |
| `dp_calculated` | Results panel shown before any accounts are added |
| `dp_chat_messages` | Previous session's advisor messages visible in fresh session |
| `dp_assets_hash` | Auto-calculation skipped for new inputs that hash-match old state |

The handler now detects `current_page == 'detailed_planning'` and additionally calls `clear_detailed_planning_asset_state(st.session_state)` and resets all four keys to their initial values before triggering `st.rerun()`.

---

## UI Changes

No UI-visible changes in this release.

---

## Files Changed

| File | Change |
|---|---|
| `fin_advisor.py` | "Start Over" handler: clear DP session state when triggered from Detailed Planning; version bumped to 16.6.0 |
| `update_version.sh` | Step 4/4 added: automated PR creation via `gh pr create` |
| `financialadvisor/__init__.py` | Version bumped to 16.6.0 |
| `setup.py` | Version bumped to 16.6.0 |
| `CLAUDE.md` | Version updated to 16.6.0 |
| `README.md` | Version updated to 16.6.0 |
| `RELEASE_NOTES_v16.6.0.md` | This file |
