# Financial Advisor - Advanced Retirement Planning Tool

A comprehensive Python-based financial planning tool that helps users project their retirement savings with sophisticated asset classification and tax optimization.

## Features

### Stage 2: Advanced Asset Classification & Tax Logic
- **Asset Classification System**: Pre-tax, Post-tax, and Tax-deferred account types
- **Per-Asset Growth Simulation**: Individual tracking and projection for each account
- **Sophisticated Tax Logic**: 
  - IRS tax bracket projections for future tax rates
  - Capital gains calculations for brokerage accounts
  - Tax-free withdrawals for Roth IRAs
  - Complex rules for HSAs and annuities
- **Tax Efficiency Analysis**: Optimize your retirement strategy with detailed tax impact analysis
- **Multiple Interface Options**: 
  - Interactive Streamlit web interface with asset configuration
  - Command-line interface for automation
  - Programmatic API for integration
- **Comprehensive Testing**: Built-in unit test suite with 13 test cases

### NEW: Financial Statement Uploader (AI-Powered)
- **Automated Data Extraction**: Upload PDF statements and extract account data automatically
- **AI Processing**: Uses GPT-4.1 to intelligently categorize accounts
- **Tax Classification**: Automatically maps accounts to pre_tax/post_tax categories
- **Multi-File Support**: Process multiple statements at once
- **PII Removal**: Automatically removes personal information for privacy
- **Structured Output**: Returns clean CSV data ready for analysis
- **n8n Integration**: Leverages workflow automation for reliable processing

**Supported Statements:** 401(k), Traditional IRA, Roth IRA, Brokerage, HSA, Bank statements

📖 **Setup Guide:** See [SETUP_STATEMENT_UPLOADER.md](SETUP_STATEMENT_UPLOADER.md) for complete setup instructions.

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

### Web Interface (Primary)
Launch the interactive Streamlit web application:
```bash
streamlit run fin_advisor.py
```

This will open your web browser with the full-featured interface including:
- Asset configuration and management
- Real-time tax efficiency analysis
- Interactive charts and visualizations
- Multiple portfolio scenarios

### Statement Uploader (AI Data Extraction)
Launch the statement uploader application:
```bash
streamlit run statement_uploader.py
```

This opens a separate interface for:
- Uploading PDF financial statements
- AI-powered data extraction
- Automatic tax categorization
- CSV/JSON export

**Setup required:** See [SETUP_STATEMENT_UPLOADER.md](SETUP_STATEMENT_UPLOADER.md) for n8n workflow configuration.

### Testing
Execute the built-in test suite:
```bash
python fin_advisor.py --run-tests
```

### Direct Execution
If you run the script directly without Streamlit:
```bash
python fin_advisor.py
```

You'll get helpful instructions on how to properly launch the application.

**Note**: This application is designed for the Streamlit web interface. The complex asset configuration and tax optimization features require the interactive UI for the best experience.

## Interface Features

The Streamlit web interface provides intuitive controls for:

- **Personal Information**: Age, retirement age, annual income
- **Tax Settings**: Current and projected retirement tax rates
- **Asset Configuration**: Multiple account types with individual settings
- **Portfolio Setup**: Three modes - Default Portfolio, Individual Assets, Legacy
- **Real-time Analysis**: Instant tax efficiency calculations and recommendations

## Asset Classification System

### Pre-Tax Assets
- **401(k) / Traditional IRA**: Taxed at withdrawal using projected retirement tax rate
- **Tax Treatment**: Full future value subject to income tax

### Post-Tax Assets
- **Roth IRA**: Tax-free withdrawals (no tax on qualified distributions)
- **Brokerage Account**: Only capital gains are taxed (default 15% rate)
- **Tax Treatment**: Roth = no tax, Brokerage = capital gains tax only

### Tax-Deferred Assets
- **HSA (Health Savings Account)**: Tax-free for medical expenses, taxed for other withdrawals
- **Annuity**: Taxed as ordinary income at withdrawal
- **Tax Treatment**: Complex rules with partial tax benefits

## Project Structure

```
financialadvisor/
├── fin_advisor.py                    # Main retirement planning app
├── statement_uploader.py             # AI-powered statement uploader
├── requirements.txt                  # Python dependencies
├── setup.py                         # Package installation script
├── README.md                        # This file
├── SETUP_STATEMENT_UPLOADER.md      # Statement uploader setup guide
├── LICENSE                          # MIT License
├── .gitignore                       # Git ignore rules
├── .env.example                     # Environment config template
├── integrations/                    # External service integrations
│   ├── __init__.py
│   ├── n8n_client.py               # n8n webhook client
│   └── README.md                   # Integration docs
├── workflows/                       # n8n workflow definitions
│   ├── n8n-statement-categorizer.json
│   └── README.md                   # Workflow setup guide
└── .github/
    └── workflows/
        └── ci.yml                  # GitHub Actions CI/CD
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

### Stage 1 (Completed)
- ✅ Basic retirement projection calculator
- ✅ Simplified tax calculations
- ✅ Streamlit web interface
- ✅ Unit test suite

### Stage 2 (Current)
- ✅ Asset classification system (pre_tax, post_tax, tax_deferred)
- ✅ Per-asset growth simulation with individual tracking
- ✅ Sophisticated tax logic with IRS tax brackets
- ✅ Capital gains calculations for brokerage accounts
- ✅ Tax efficiency analysis and optimization insights
- ✅ Enhanced UI with asset configuration options
- ✅ Comprehensive test suite (13 test cases)

### Stage 3 (Planned)
- [ ] Monte Carlo simulation for risk analysis
- [ ] Advanced withdrawal strategies and sequencing
- [ ] Historical market data integration
- [ ] Scenario analysis and stress testing

### Stage 4 (Future)
- [ ] AI-powered financial advice and optimization
- [ ] Goal-based planning with multiple objectives
- [ ] Multi-currency support
- [ ] Integration with financial APIs and real-time data

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
