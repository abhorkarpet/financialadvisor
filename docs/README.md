# Financial Advisor Documentation

This directory contains comprehensive documentation for the Financial Advisor project.

## Contents

- **API Reference**: Detailed documentation of all functions and classes
- **User Guide**: Step-by-step instructions for using the application
- **Developer Guide**: Information for contributors and developers
- **Examples**: Sample usage scenarios and code examples

## Quick Start

1. **Installation**: See the main README.md for installation instructions
2. **Basic Usage**: Run `streamlit run fin_advisor.py` for the web interface
3. **CLI Usage**: Use `python fin_advisor.py --help` for command-line options

## Mathematical Models

The Financial Advisor uses standard financial formulas for retirement planning:

### Future Value with Annual Contributions
```
FV = P × (1 + r)^t + C × [((1 + r)^t - 1) / r]
```

Where:
- P = Principal (current balance)
- C = Annual contribution
- r = Annual growth rate (as decimal)
- t = Years until retirement

### Post-Tax Balance
```
After-Tax Balance = FV × (1 - tax_rate)
```

## API Reference

### Core Functions

#### `years_to_retirement(age: int, retirement_age: int) -> int`
Calculates the number of years until retirement.

**Parameters:**
- `age`: Current age
- `retirement_age`: Target retirement age

**Returns:**
- Number of years until retirement

**Raises:**
- `ValueError`: If retirement_age < age

#### `future_value_with_contrib(principal: float, annual_contribution: float, rate_pct: float, years: int) -> float`
Calculates future value with annual contributions and compound interest.

**Parameters:**
- `principal`: Initial balance
- `annual_contribution`: Annual contribution amount
- `rate_pct`: Annual growth rate as percentage
- `years`: Number of years

**Returns:**
- Future value after specified years

#### `simple_post_tax(balance: float, tax_rate_pct: float) -> float`
Calculates post-tax balance using a simplified tax rate.

**Parameters:**
- `balance`: Pre-tax balance
- `tax_rate_pct`: Tax rate as percentage

**Returns:**
- Post-tax balance

#### `project(inputs: UserInputs) -> Dict[str, float]`
Main projection function that calculates retirement projections.

**Parameters:**
- `inputs`: UserInputs object containing all financial parameters

**Returns:**
- Dictionary with projection results

### Data Classes

#### `UserInputs`
Dataclass containing all user input parameters for retirement planning.

**Fields:**
- `age`: Current age
- `retirement_age`: Target retirement age
- `annual_income`: Annual income
- `contribution_rate_pct`: Annual savings rate as percentage of income
- `current_balance`: Current total savings
- `expected_growth_rate_pct`: Expected annual growth rate
- `inflation_rate_pct`: Expected inflation rate
- `tax_rate_pct`: Estimated retirement tax rate
- `asset_types`: List of asset types held

## Examples

### Basic CLI Usage
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

### Programmatic Usage
```python
from fin_advisor import UserInputs, project

inputs = UserInputs(
    age=30,
    retirement_age=65,
    annual_income=85000,
    contribution_rate_pct=15,
    current_balance=50000,
    expected_growth_rate_pct=7,
    inflation_rate_pct=3,
    tax_rate_pct=25,
    asset_types=["401(k) / Traditional IRA (Pre-Tax)"]
)

result = project(inputs)
print(f"Future Value: ${result['Future Value (Pre-Tax)']:,.2f}")
```

## Testing

Run the test suite:
```bash
python fin_advisor.py --run-tests
```

Or run tests directly:
```bash
python -m pytest tests/
```

## Contributing

See the main README.md for contribution guidelines and development setup.
