# Projected Balance Explanation Module

## Overview

The projected balance explanation module provides a detailed breakdown of how retirement balance projections are calculated, including the mathematical formulas and step-by-step calculations.

## How Annual Contributions Are Used

Annual contributions are incorporated into the projection using the **Future Value with Contributions formula**:

```
FV = P × (1 + r)^t + C × [((1 + r)^t - 1) / r]
```

Where:
- **P** = Current Balance (Principal)
- **r** = Annual Growth Rate (as decimal)
- **t** = Years Until Retirement
- **C** = Annual Contribution (made at end of each year)
- **FV** = Future Value (Projected Balance)

### Two Components:

1. **Principal Growth**: `P × (1 + r)^t`
   - Grows the current balance with compound interest

2. **Contribution Growth**: `C × [((1 + r)^t - 1) / r]`
   - Applies the "future value of annuity" formula
   - Each year's contribution grows with compound interest for the remaining years
   - Assumes contributions are made at the **end of each year**

## Usage

### Function: `explain_projected_balance(inputs: UserInputs) -> str`

Returns a comprehensive formatted explanation including:
- The core formula
- Step-by-step calculation breakdown
- Your specific numbers
- Tax treatment by asset type
- Key insights

### Example

```python
from fin_advisor import UserInputs, explain_projected_balance, project

# Create input parameters
inputs = UserInputs(
    age=30,
    retirement_age=65,
    annual_income=85000,
    contribution_rate_pct=15.0,
    current_balance=50000,
    expected_growth_rate_pct=7.0,
    expected_inflation_rate_pct=3.0,
    retirement_marginal_tax_rate_pct=25.0
)

# Get the detailed explanation
explanation = explain_projected_balance(inputs)
print(explanation)

# Also get the numerical results
results = project(inputs)
print(f"Projected Balance: ${results['projected_balance']:,.2f}")
```

### Example with Multiple Assets

```python
from fin_advisor import UserInputs, Asset, AssetType, explain_projected_balance

inputs = UserInputs(
    age=35,
    retirement_age=65,
    annual_income=120000,
    contribution_rate_pct=0,
    current_balance=0,
    expected_growth_rate_pct=7.0,
    expected_inflation_rate_pct=3.0,
    retirement_marginal_tax_rate_pct=28.0,
    assets=[
        Asset(
            name="401(k) Pre-Tax",
            asset_type=AssetType.PRE_TAX,
            current_balance=80000,
            annual_contribution=19500,
            growth_rate_pct=7.0
        ),
        Asset(
            name="Roth IRA",
            asset_type=AssetType.POST_TAX,
            current_balance=30000,
            annual_contribution=6500,
            growth_rate_pct=7.5
        )
    ]
)

explanation = explain_projected_balance(inputs)
print(explanation)
```

## Sample Output

The explanation includes:

1. **Core Formula Section**: Shows the mathematical formula with variable definitions
2. **How It Works**: Breaks down the two components (principal growth and contribution growth)
3. **Your Calculation**: Shows your specific numbers plugged into the formula
4. **Tax Treatment by Asset Type**: Explains how different account types are taxed
5. **Key Insights**: Important notes about the calculation

## Tax Treatment

The module explains how different asset types are treated:

- **Pre-Tax (401k, Traditional IRA)**: Full balance taxed at retirement tax rate
- **Post-Tax (Roth IRA)**: Tax-free on withdrawal
- **Post-Tax (Brokerage)**: Only capital gains are taxed
- **Tax-Deferred (HSA)**: 50% medical (tax-free), 50% other (taxed)
- **Tax-Deferred (Annuities)**: Taxed as ordinary income

## Running the Examples

A complete example script is provided:

```bash
python examples/explain_projection.py
```

This demonstrates:
- Simple single-asset projection
- Multiple assets with different tax treatments
- Young investor with long time horizon

## Location in Code

The `explain_projected_balance()` function is defined in `fin_advisor.py` at line 318.

## Key Features

✓ Shows complete mathematical formula
✓ Breaks down principal growth vs. contribution growth
✓ Uses your actual numbers for personalized calculation
✓ Explains tax treatment for each asset type
✓ Highlights that contributions are made at year-end
✓ Provides concrete numerical examples
