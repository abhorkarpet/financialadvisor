# Smart Retire AI v15.8.0 Release Notes

**Release Date:** May 2026
**Version:** 15.8.0
**Previous Version:** 15.6.0

---

## Release Overview

v15.8.0 is a clean-up and automation release. It reverts testing overrides left in `statement_uploader.py` that would have broken production deployments, condenses the verbose privacy expander into a concise summary, tightens a minor tax-label condition, and extends `update_version.sh` with automated AI-driven steps for updating version strings and generating release notes via the Claude CLI.

---

## Features / Changes

### `update_version.sh` extended with Claude CLI automation

The version-bump script now includes an **AI Steps** section that invokes the `claude` CLI (if available) to:

1. Update the version string in `README.md` and `CLAUDE.md` automatically
2. Generate a new `RELEASE_NOTES_v<version>.md` at the project root and archive any previous root-level release notes into `release-notes/`

The interactive git workflow step count has been updated from 4 to 3 to reflect the consolidated flow. If `claude` is not found on `PATH`, the script prints a warning and skips the AI steps gracefully.

---

## Bug Fixes

### Statement uploader restored to env-var-driven processor selection

`statement_uploader.py` had three constants hard-coded for manual testing and never reverted before the v15.6.0 release commit:

- `_USE_PYTHON_PROCESSOR = True` (forced Python processor regardless of env)
- `_N8N_URL = None` (n8n backend silently disabled)
- `_COMPARISON_AVAILABLE = False` (comparison mode always off)

All three are now restored to their correct env-var-driven values:

```python
_USE_PYTHON_PROCESSOR = os.getenv("PYTHON_STATEMENT_PROCESSOR", "").lower() in ("true", "1", "yes")
_N8N_URL = os.getenv("N8N_STATEMENT_UPLOADER_URL") or os.getenv("N8N_WEBHOOK_URL")
_COMPARISON_AVAILABLE = bool(_N8N_URL and _OPENAI_KEY)
```

Deployments relying on n8n would have silently routed all uploads through the Python processor, and comparison mode would have been permanently unavailable.

### `_asset_to_tax_treatment_label` condition consolidated

Two consecutive `if` checks for `AssetType.PRE_TAX` and `AssetType.TAX_DEFERRED` (which return the same label `"Tax-Deferred"`) were collapsed into a single membership test:

```python
if asset.asset_type in (AssetType.PRE_TAX, AssetType.TAX_DEFERRED):
    return "Tax-Deferred"
```

No behaviour change; eliminates dead-code risk if the two branches diverge in future.

---

## UI Changes

### Privacy expander condensed

The "🔒 How It Works & Your Privacy" expander in the portfolio upload dialog was ~65 lines of verbose marketing copy, Q&A, and technical detail. It has been replaced with a concise 10-line summary covering the three key points users need:

- What the AI extracts from PDFs
- What personal data is removed
- How to control and clear extracted data

The detailed technical and FAQ content has been removed entirely.

---

## Files Changed

| File | Change |
|---|---|
| `fin_advisor.py` | Tax label condition consolidated; privacy expander condensed; version bumped to 15.8.0 |
| `statement_uploader.py` | Restored env-var-driven `_USE_PYTHON_PROCESSOR`, `_N8N_URL`, `_COMPARISON_AVAILABLE` |
| `update_version.sh` | Added AI steps section (Claude CLI); updated step count 4 → 3 |
| `financialadvisor/__init__.py` | Version bumped to 15.8.0 |
| `setup.py` | Version bumped to 15.8.0 |
| `CLAUDE.md` | Version updated to 15.8.0 |
| `README.md` | Version updated to 15.8.0 |
| `RELEASE_NOTES_v15.8.0.md` | This file |
