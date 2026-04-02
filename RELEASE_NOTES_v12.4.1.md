# Smart Retire AI v12.4.1 Release Notes

**Release Date:** April 2026
**Version:** 12.4.1
**Previous Version:** 12.4.0

---

## Release Overview

This patch release fixes the splash-screen release notes experience introduced in `12.4.0`. The "What's new" content now appears again on the splash screen as a non-intrusive expander, while the full release notes dialog still opens only when the footer button is clicked.

---

## Fixes

### Splash-screen "What's new" expander
- Fixed a mismatch between the splash-screen parser and the `12.4.0` release notes heading format.
- Added a shared release-overview extraction helper so the splash expander and footer dialog read the same section.
- Kept the release notes dialog hidden by default; it no longer auto-opens on load.

---

## Files Changed

- `fin_advisor.py` — shared release-overview parser and splash-screen expander fix
- `README.md`, `CLAUDE.md`, `TESTING.md` — version bumped to `12.4.1`
- `setup.py`, `financialadvisor/__init__.py` — version bumped to `12.4.1`
- `RELEASE_NOTES_v12.4.1.md` — this file
