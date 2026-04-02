# Smart Retire AI — Retirement Planning Tool

A Python/Streamlit web app for projecting retirement savings with multi-asset tax optimization, Monte Carlo simulation, AI-powered statement processing, and a GPT-4 chat advisor.

**Current version: 12.5.1**

---

## Features

### Retirement Projection Engine
- **Explicit Tax Modeling**: Pre-tax, tax-free Roth, brokerage capital gains, and tax-deferred/HSA-style account behaviors
- **Per-Asset Growth Simulation**: Individual balance tracking with IRS tax bracket logic
- **Tax Efficiency Analysis**: Capital gains, Roth tax-free withdrawals, HSA partial benefits
- **Monte Carlo Simulation**: 1,000+ probabilistic scenarios with confidence intervals and probability of success

### Planning Modes
- **Detailed Planning (US-only)**: Asset-by-asset configuration with tax-aware account analysis and asset-specific withdrawal treatment
- **Simple Planning**: Conversational GPT-4 advisor that collects your goals and returns a quick projection — supports US and India (USD/INR)

### AI-Powered Statement Processing
- Upload PDF financial statements; GPT-4.1 extracts and categorizes accounts automatically
- Automatic tax classification (pre_tax / post_tax)
- PII removal, multi-file batch processing, CSV/JSON export
- Powered by n8n workflow automation

### Reporting
- Real-time charts and visualizations
- PDF report generation
- Multi-scenario comparison

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
OPENAI_API_KEY=               # Required for chat advisor
N8N_WEBHOOK_URL=              # Required for statement processing
N8N_STATEMENT_UPLOADER_URL=   # Optional separate uploader webhook
N8N_WEBHOOK_TOKEN=            # Optional auth token
```

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

For statement uploader setup, see [SETUP_STATEMENT_UPLOADER.md](SETUP_STATEMENT_UPLOADER.md).

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
  chat_advisor.py               # GPT-4 conversational planning
  gpt_system_prompt.txt         # Chat advisor system prompt
workflows/                      # n8n workflow JSON definitions
tests/
  test_fin_advisor.py           # Unit test suite
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

See [DEPLOYMENT.md](DEPLOYMENT.md) for Streamlit Community Cloud deployment instructions.

---

## Disclaimer

This tool is for educational and planning purposes only. It does not constitute professional financial advice. Consult a qualified financial advisor for personalized guidance.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
