# Smart Retire AI — Retirement Planning Tool

A Python/Streamlit web app for projecting retirement savings with multi-asset tax optimization, Monte Carlo simulation, AI-powered statement processing, and a GPT-4 chat advisor.

**Current version: 16.5.0**

---

## Features

### Retirement Projection Engine
- **Explicit Tax Modeling**: Pre-tax, tax-free Roth, brokerage capital gains, HSA-style, and savings/checking interest income behaviors
- **Per-Asset Growth Simulation**: Individual balance tracking with IRS tax bracket logic
- **Tax Efficiency Analysis**: Capital gains, Roth tax-free withdrawals, HSA partial benefits, ordinary income on savings interest
- **Monte Carlo Simulation**: 1,000+ probabilistic scenarios with confidence intervals and probability of success

### Planning Modes
- **Detailed Planning (US-only)**: Asset-by-asset configuration with tax-aware account analysis and asset-specific withdrawal treatment
- **Simple Planning**: Conversational GPT-4 advisor that collects your goals and returns a quick projection — supports US and India (USD/INR)

### AI-Powered Statement Processing
- Upload PDF financial statements; GPT-4.1 extracts and categorizes accounts automatically
- Automatic tax classification (pre_tax / post_tax / tax_free) with tax bucket decomposition for 401k/403b accounts
- Account-number-based deduplication — survives generic AI-assigned names across multi-file batches
- Balance-based duplicate detection — catches same account under different institution label names
- PII removal, multi-file batch processing, CSV/JSON export
- Two processor backends, switchable via env var: **Python processor** (no n8n required) or **n8n webhook**

### Portfolio Management
- **"Manage Your Portfolio" dialog**: upload additional statements and merge into existing portfolio, edit accounts inline, or reset
- Upload flow mirrors onboarding UX with Phase 1/2 progress bar and live per-file AI processing timing
- Edit existing accounts without re-uploading: account name, tax treatment, balance, contributions, growth rate, add/delete rows

### Reporting
- Real-time charts and visualizations
- PDF report generation
- Multi-scenario comparison
- Cash flow projection with year-by-year portfolio balance and after-tax income chart
- Income & Gap analysis: projected income vs goal, gap-closing options (retire later or save more)

---

## Installation

**Prerequisites:** Python 3.9+

```bash
git clone https://github.com/abhorkarpet/financialadvisor.git
cd financialadvisor
pip install -r requirements.txt
```

### Environment variables

Copy `.env.example` to `.env` and fill in:

```
OPENAI_API_KEY=                    # Required for chat advisor and Python statement processor
PYTHON_STATEMENT_PROCESSOR=true    # Use built-in Python processor (no n8n needed)
N8N_WEBHOOK_URL=                   # Required only when using n8n processor
N8N_STATEMENT_UPLOADER_URL=        # Optional separate uploader webhook (n8n mode)
N8N_WEBHOOK_TOKEN=                 # Optional auth token (n8n mode)
```

Set `PYTHON_STATEMENT_PROCESSOR=true` to process statements without n8n. Leave it unset to fall back to the n8n webhook.

---

## Usage

```bash
# Main planning app
streamlit run fin_advisor.py

# Standalone statement uploader
streamlit run statement_uploader.py

# Run unit tests
python3 fin_advisor.py --run-tests
```

The app opens at `http://localhost:8501`.

For statement uploader setup, see [docs/SETUP_STATEMENT_UPLOADER.md](docs/SETUP_STATEMENT_UPLOADER.md).

---

## Project Structure

```
fin_advisor.py                  # Main Streamlit app
statement_uploader.py           # Standalone statement uploader UI
financialadvisor/
  core/
    calculator.py               # Future value formula and basic math
    tax_engine.py               # IRS tax brackets and tax logic
    projector.py                # Retirement projection engine
    monte_carlo.py              # Monte Carlo simulation
    explainer.py                # Human-readable result explanations
  domain/
    models.py                   # Asset, UserInputs, TaxBracket dataclasses
  utils/
    analytics.py                # PostHog event tracking
integrations/
  n8n_client.py                 # n8n webhook HTTP client
  statement_processor.py        # Pure Python statement processor (no n8n)
  processor_factory.py          # Returns active processor based on env var
  chat_advisor.py               # GPT-4 conversational planning
  gpt_system_prompt.txt         # Chat advisor system prompt
  detailed_planning_system_prompt.txt  # System prompt for Detailed Planning advisor
  detailed_setup_system_prompt.txt     # System prompt for Detailed Planning setup chat
workflows/                      # n8n workflow JSON definitions
tests/
  test_fin_advisor.py           # Unit test suite (127 tests)
  test_statement_processor.py   # Statement processor unit tests
  e2e/                          # End-to-end test suite
docs/                           # Supplementary docs (deployment, setup guides, analysis)
release-notes/                  # Historical release notes (prior versions)
RELEASE_NOTES_v15.6.0.md        # Current release notes
```

---

## Mathematical Model

Standard future value formula with annual contributions:

```
FV = P × (1 + r)^t  +  C × [((1 + r)^t − 1) / r]
```

- `P` = Principal (current balance)
- `C` = Annual contribution
- `r` = Annual growth rate
- `t` = Years to retirement

Zero-rate edge case is handled separately. Results are rounded to 2 decimal places. Tax logic branches per asset type.

---

## Development

### Testing
```bash
python3 fin_advisor.py --run-tests
```

CI runs the test suite against Python 3.9–3.12 on every push via GitHub Actions.

### Code style
- `black` — formatting
- `flake8` — linting
- `mypy` — type checking
- `bandit` / `safety` — security scanning

### Contributing
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes and open a Pull Request against `main`

---

## Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for Streamlit Community Cloud deployment instructions.

---

## Disclaimer

This tool is for educational and planning purposes only. It does not constitute professional financial advice. Consult a qualified financial advisor for personalized guidance.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
