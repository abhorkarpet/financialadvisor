# Smart Retire AI v15.6.0 Release Notes

**Release Date:** May 2026
**Version:** 15.6.0
**Previous Version:** 15.5.0

---

## Release Overview

v15.6 is a stabilisation release. All changes are bug fixes and CI improvements — no new user-facing features beyond removing the AI timing clock from the upload completion message.

---

## Bug Fixes

### NameError on statement upload when processor initialisation fails

If `get_processor()` raised an exception (e.g. missing env vars) before `_processor_type` was assigned, all three `except` blocks in the upload handler referenced an unbound name and crashed with `NameError`. Fixed by initialising `_processor_type = "unknown"` before the `try` block.

### Processor configuration validated before upload begins

A new `check_processor_configured()` helper in `integrations/processor_factory.py` verifies that a processor is fully configured before any files are processed. It checks:

- `PYTHON_STATEMENT_PROCESSOR=true` → requires `OPENAI_API_KEY`
- Neither flag set → requires `N8N_WEBHOOK_URL`

Both the "Manage Your Portfolio" dialog and the onboarding upload button now call this check up-front and show a specific, actionable error message instead of failing mid-upload.

### `try/except/pass` replaced with debug log (bandit B110)

A bare `except Exception: pass` in the Monte Carlo context block was flagged by bandit (CWE-703). Replaced with `logging.debug()` so the exception is visible in diagnostics without surfacing to the user. CI security scan now passes.

### e2e tests excluded from unit test discovery

`unittest.discover("tests")` was recursing into `tests/e2e/`, which imports `playwright` at module load time — causing `ModuleNotFoundError` on any CI runner without Playwright installed. Fixed by switching to an explicit `glob("tests/test_*.py")` loop that never touches `tests/e2e/`.

---

## UI Changes

### Timing clock removed from upload completion

The "(AI processing: 2.2s | Total: 2.2s)" suffix has been removed from the "✅ Extraction Complete!" message in both the "Manage Your Portfolio" dialog and the onboarding upload flow. The underlying timing calculations have also been removed.

---

## Files Changed

| File | Change |
|---|---|
| `fin_advisor.py` | NameError fix; processor config check; timing removed; e2e test discovery fix; bandit B110 fix |
| `integrations/processor_factory.py` | `check_processor_configured()` added |
| `financialadvisor/__init__.py` | Version bumped to 15.6.0 |
| `setup.py` | Version bumped to 15.6.0 |
| `CLAUDE.md` | Version updated to 15.6.0 |
| `README.md` | Version updated to 15.6.0 |
| `RELEASE_NOTES_v15.6.0.md` | This file |
