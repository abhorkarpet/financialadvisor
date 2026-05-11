# CLAUDE.md — Smart Retire AI

## Project Overview

**Smart Retire AI** is a Streamlit-based retirement planning web app. It projects retirement savings across multiple asset types with IRS tax logic, Monte Carlo simulation, AI-powered financial statement processing, and a GPT-4 chat advisor.

Current version: **16.6.0**

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit 1.28+ |
| Language | Python 3.9–3.12 |
| Data | Pandas, NumPy |
| AI/Chat | OpenAI (GPT-4) via `integrations/chat_advisor.py` |
| Statement processing | n8n webhooks + GPT-4.1 |
| PDF generation | ReportLab |
| Analytics | PostHog |
| Tests | unittest (built-in) |
| CI | GitHub Actions (`.github/workflows/`) |

---

## Running the App

```bash
# Install dependencies
pip install -r requirements.txt

# Start the main app
streamlit run fin_advisor.py

# Start the standalone statement uploader
streamlit run statement_uploader.py

# Run tests
python3 fin_advisor.py --run-tests
```

The main app runs on `http://localhost:8501`.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```
OPENAI_API_KEY=          # Required for chat advisor mode
N8N_WEBHOOK_URL=         # Required for statement processing
N8N_STATEMENT_UPLOADER_URL=   # Optional separate uploader webhook
N8N_WEBHOOK_TOKEN=       # Optional auth token for n8n
```

---

## Project Structure

```
fin_advisor.py                  # Main Streamlit app (~6500 lines)
statement_uploader.py           # Standalone uploader UI
financialadvisor/
  core/
    calculator.py               # FV formula, basic math
    tax_engine.py               # IRS brackets and tax logic
    projector.py                # Main retirement projection
    monte_carlo.py              # Monte Carlo simulation
    explainer.py                # Human-readable explanations
  domain/
    models.py                   # Asset, UserInputs, TaxBracket dataclasses
  utils/
    analytics.py                # PostHog event tracking
integrations/
  n8n_client.py                 # n8n webhook HTTP client
  chat_advisor.py               # GPT-4 conversation loop
  gpt_system_prompt.txt         # System prompt for chat advisor
tests/
  test_fin_advisor.py           # 19+ unit tests covering math, tax behavior, and planning handoff helpers
workflows/                      # n8n workflow JSON definitions
docs/                           # Supplementary documentation (deployment, analytics, setup guides)
release-notes/                  # Historical release notes (all versions prior to current)
RELEASE_NOTES_v13.0.0.md        # Current release notes
```

---

## Architecture

- **Layered**: domain → core → integrations → UI (fin_advisor.py)
- **Feature flags**: optional imports with no-op fallbacks (`_N8N_AVAILABLE`, `_CHAT_AVAILABLE`, `ANALYTICS_AVAILABLE`, `_REPORTLAB_AVAILABLE`)
- **Backward compat**: `UserInputs` supports both modern asset-based and legacy single-balance inputs via property aliases
- **State management**: Streamlit `st.session_state` for multi-page navigation, chat progress, and onboarding tracking

### Planning Modes

| Mode | Description |
|---|---|
| Detailed Planning | US-only asset-by-asset planning |
| Simple Planning | Chat-based planning (GPT-4) with US and India support |

Navigation between modes uses `st.session_state.current_page`.

---

## Core Math

Future value formula used throughout:

```
FV = P × (1+r)^t  +  C × [((1+r)^t − 1) / r]
```

- Special-cased when `r == 0` to avoid division by zero
- Results rounded to 2 decimal places
- Tax logic now uses explicit `tax_behavior` with backward-compatible `asset_type` support

---

## Testing

Tests live in `tests/test_fin_advisor.py` and cover:
- FV calculations (zero rate, positive rate, principal-only)
- Explicit tax behaviors (pre-tax, Roth/tax-free, brokerage gains, HSA split, cash-style post-tax)
- Backward compatibility with legacy inputs

Run with:
```bash
python3 fin_advisor.py --run-tests
```

CI runs the full suite against Python 3.9–3.12 on every push.

---

## Key Conventions

- The main `fin_advisor.py` is intentionally large — it's a monolithic Streamlit app; do not split it without a clear architectural reason
- New features added to core logic should go in `financialadvisor/core/`, not inline in `fin_advisor.py`
- Optional integrations (n8n, OpenAI, ReportLab, PostHog) must degrade gracefully — wrap imports in try/except and set a flag like `_FEATURE_AVAILABLE`
- Type hints are expected; the CI runs mypy
- Security: bandit scans run in CI; avoid shell injection and do not log PII from financial statements
