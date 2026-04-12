# Smart Retire AI v12.5.1 Release Notes

**Release Date:** April 2026
**Version:** 12.5.1
**Previous Version:** 12.5.0

---

## Release Overview

This patch release makes the Simple-to-Detailed Planning transition clearer and safer. It adds stronger guidance for US users when account-specific tax treatment matters, preserves more planning inputs during handoff, and protects existing detailed account data with an explicit reuse-or-reset choice.

---

## UX Changes

### Stronger Detailed Planning nudge for US users
- Simple Planning now shows a stronger warning above the PDF export action when the estimate uses a simplified tax model.
- The callout highlights that account-specific tax treatment can materially change the required portfolio.
- The upgrade path into Detailed Planning remains available directly from the results panel.

### Safer Simple → Detailed handoff
- Detailed Planning now preserves the key values already entered in Simple Planning.
- If saved detailed accounts already exist, the app now asks whether to reuse them or start fresh before opening onboarding.
- Starting fresh clears saved AI-upload, CSV-upload, and manual account setup state so Step 2 opens cleanly.

### Clearer product messaging
- Detailed Planning copy now consistently describes the feature as US-only account-based planning.
- Splash and mode-selection messaging better distinguishes Simple Planning (US and India) from Detailed Planning (US-only).

---

## Quality Improvements

- Added regression tests for Simple-to-Detailed field handoff, existing-asset detection, and detailed-state reset behavior.
- Updated docs and version markers across the app, package metadata, and contributor docs to `12.5.1`.

---

## Files Changed

- `fin_advisor.py` — Simple/Detailed handoff flow, stronger US-only results callout, detailed-state reuse/reset dialog, version bump
- `tests/test_fin_advisor.py` — regression coverage for handoff/reset helpers
- `README.md`, `CLAUDE.md`, `TESTING.md` — version and planning-mode documentation updated
- `setup.py`, `financialadvisor/__init__.py` — version bumped to `12.5.1`
- `RELEASE_NOTES_v12.5.1.md` — this file
