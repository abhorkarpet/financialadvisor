# Smart Retire AI v12.5.0 Release Notes

**Release Date:** April 2026
**Version:** 12.5.0
**Previous Version:** 12.4.1

---

## Release Overview

This release simplifies planning-mode navigation. Detailed Planning now focuses only on account-based setup, while Simple Planning remains the quick income-goal path. Users can switch directly between the two modes without going back through a hidden sub-mode flow.

---

## UX Changes

### Two-mode planning flow
- Removed the embedded Income Goal Calculator flow from Detailed Planning.
- Detailed Planning now always follows the asset-based onboarding path.
- Added a direct `Switch to Simple Planning` action from onboarding.
- Added a direct `Switch to Detailed Planning` action from Simple Planning.

### Detailed Planning is now US-only
- Removed the country selector from Detailed Planning onboarding.
- Added clear messaging at the top of onboarding that Detailed Planning currently supports US households only.
- Kept Simple Planning as the path for India planning and quick estimates.

---

## Files Changed

- `fin_advisor.py` — simplified planning flow, direct mode switches, US-only detailed onboarding
- `README.md`, `CLAUDE.md`, `TESTING.md` — version bumped to `12.5.0`
- `setup.py`, `financialadvisor/__init__.py` — version bumped to `12.5.0`
- `RELEASE_NOTES_v12.5.0.md` — this file
