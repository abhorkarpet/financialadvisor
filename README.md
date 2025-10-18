# Financial Advisor - Retirement Planning Tool

A comprehensive Python-based financial planning tool that helps users project their retirement savings and analyze post-tax retirement income scenarios.

## Features

- **Retirement Projection Calculator**: Calculate future value of retirement savings with annual contributions
- **Tax-Aware Planning**: Simplified post-tax retirement balance estimation
- **Multiple Interface Options**: 
  - Interactive Streamlit web interface
  - Command-line interface for automation
  - Programmatic API for integration
- **Flexible Asset Types**: Support for 401(k), Roth IRA, brokerage accounts, and savings accounts
- **Comprehensive Testing**: Built-in unit test suite

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Setup
1. Clone the repository:
```bash
git clone https://github.com/yourusername/financialadvisor.git
cd financialadvisor
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Web Interface (Recommended)
Launch the interactive Streamlit web application:
```bash
streamlit run fin_advisor.py
```

### Command Line Interface
Run calculations directly from the command line:
```bash
python fin_advisor.py \
  --age 30 \
  --retirement-age 65 \
  --income 85000 \
  --contribution-rate 15 \
  --current-balance 50000 \
  --growth-rate 7 \
  --inflation-rate 3 \
  --tax-rate 25
```

### Run Tests
Execute the built-in test suite:
```bash
python fin_advisor.py --run-tests
```

## Parameters

| Parameter | Description | Default | Range |
|-----------|-------------|---------|-------|
| `--age` | Current age | 30 | 18-90 |
| `--retirement-age` | Target retirement age | 65 | 40-80 |
| `--income` | Annual income ($) | 85,000 | 10,000+ |
| `--contribution-rate` | Annual savings rate (% of income) | 15 | 0-50 |
| `--current-balance` | Current total savings ($) | 50,000 | 0+ |
| `--growth-rate` | Expected annual growth rate (%) | 7 | 0-20 |
| `--inflation-rate` | Expected inflation rate (%) | 3 | 0-10 |
| `--tax-rate` | Estimated retirement tax rate (%) | 25 | 0-50 |

## Supported Asset Types

- 401(k) / Traditional IRA (Pre-Tax)
- Roth IRA (Post-Tax)
- Brokerage Account
- Savings Account

## Project Structure

```
financialadvisor/
├── fin_advisor.py          # Main application file
├── requirements.txt        # Python dependencies
├── setup.py               # Package installation script
├── README.md              # This file
├── LICENSE                # MIT License
├── .gitignore             # Git ignore rules
└── .github/
    └── workflows/
        └── ci.yml         # GitHub Actions CI/CD
```

## Development

### Running Tests
```bash
python fin_advisor.py --run-tests
```

### Code Style
The project follows PEP 8 style guidelines. Consider using:
- `black` for code formatting
- `flake8` for linting
- `mypy` for type checking

### Contributing
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Roadmap

### Stage 1 (Current)
- ✅ Basic retirement projection calculator
- ✅ Simplified tax calculations
- ✅ Streamlit web interface
- ✅ Command-line interface
- ✅ Unit test suite

### Stage 2 (Planned)
- [ ] Monte Carlo simulation for risk analysis
- [ ] Per-account tax optimization
- [ ] Advanced withdrawal strategies
- [ ] Historical market data integration

### Stage 3 (Future)
- [ ] AI-powered financial advice
- [ ] Goal-based planning
- [ ] Multi-currency support
- [ ] Integration with financial APIs

## Mathematical Model

The tool uses the standard future value formula with annual contributions:

```
FV = P × (1 + r)^t + C × [((1 + r)^t - 1) / r]
```

Where:
- `P` = Principal (current balance)
- `C` = Annual contribution
- `r` = Annual growth rate (as decimal)
- `t` = Years until retirement

Post-tax balance is calculated using a simplified blended tax rate:
```
After-Tax Balance = FV × (1 - tax_rate)
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This tool is for educational and planning purposes only. It provides simplified projections and should not be considered as professional financial advice. Always consult with a qualified financial advisor for personalized guidance.

## Support

For questions, issues, or contributions, please:
1. Check the [Issues](https://github.com/yourusername/financialadvisor/issues) page
2. Create a new issue if your question isn't already addressed
3. Follow the contributing guidelines for code contributions

## Acknowledgments

- Built with Python and Streamlit
- Financial calculations based on standard compound interest formulas
- Inspired by the need for accessible retirement planning tools
