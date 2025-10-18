#!/usr/bin/env python3
"""
Basic usage examples for the Financial Advisor application.
"""

import sys
import os

# Add the parent directory to the path so we can import fin_advisor
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fin_advisor import UserInputs, project, years_to_retirement, future_value_with_contrib


def example_1_basic_projection():
    """Example 1: Basic retirement projection."""
    print("=" * 60)
    print("Example 1: Basic Retirement Projection")
    print("=" * 60)
    
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
    
    print(f"Current Age: {inputs.age}")
    print(f"Retirement Age: {inputs.retirement_age}")
    print(f"Annual Income: ${inputs.annual_income:,.2f}")
    print(f"Contribution Rate: {inputs.contribution_rate_pct}%")
    print(f"Current Balance: ${inputs.current_balance:,.2f}")
    print(f"Expected Growth Rate: {inputs.expected_growth_rate_pct}%")
    print(f"Tax Rate: {inputs.tax_rate_pct}%")
    print()
    print("Projection Results:")
    for key, value in result.items():
        if "Balance" in key or "Value" in key:
            print(f"{key}: ${value:,.2f}")
        else:
            print(f"{key}: {value}")


def example_2_early_retirement():
    """Example 2: Early retirement scenario."""
    print("\n" + "=" * 60)
    print("Example 2: Early Retirement Scenario")
    print("=" * 60)
    
    inputs = UserInputs(
        age=25,
        retirement_age=50,
        annual_income=100000,
        contribution_rate_pct=25,  # Aggressive savings
        current_balance=20000,
        expected_growth_rate_pct=8,
        inflation_rate_pct=2.5,
        tax_rate_pct=20,
        asset_types=["401(k) / Traditional IRA (Pre-Tax)", "Roth IRA (Post-Tax)"]
    )
    
    result = project(inputs)
    
    print(f"Current Age: {inputs.age}")
    print(f"Retirement Age: {inputs.retirement_age}")
    print(f"Annual Income: ${inputs.annual_income:,.2f}")
    print(f"Contribution Rate: {inputs.contribution_rate_pct}% (Aggressive)")
    print(f"Current Balance: ${inputs.current_balance:,.2f}")
    print(f"Expected Growth Rate: {inputs.expected_growth_rate_pct}%")
    print(f"Tax Rate: {inputs.tax_rate_pct}%")
    print()
    print("Projection Results:")
    for key, value in result.items():
        if "Balance" in key or "Value" in key:
            print(f"{key}: ${value:,.2f}")
        else:
            print(f"{key}: {value}")


def example_3_conservative_approach():
    """Example 3: Conservative investment approach."""
    print("\n" + "=" * 60)
    print("Example 3: Conservative Investment Approach")
    print("=" * 60)
    
    inputs = UserInputs(
        age=40,
        retirement_age=67,
        annual_income=120000,
        contribution_rate_pct=12,
        current_balance=150000,
        expected_growth_rate_pct=5,  # Conservative growth
        inflation_rate_pct=3.5,
        tax_rate_pct=28,
        asset_types=["401(k) / Traditional IRA (Pre-Tax)", "Savings Account"]
    )
    
    result = project(inputs)
    
    print(f"Current Age: {inputs.age}")
    print(f"Retirement Age: {inputs.retirement_age}")
    print(f"Annual Income: ${inputs.annual_income:,.2f}")
    print(f"Contribution Rate: {inputs.contribution_rate_pct}%")
    print(f"Current Balance: ${inputs.current_balance:,.2f}")
    print(f"Expected Growth Rate: {inputs.expected_growth_rate_pct}% (Conservative)")
    print(f"Tax Rate: {inputs.tax_rate_pct}%")
    print()
    print("Projection Results:")
    for key, value in result.items():
        if "Balance" in key or "Value" in key:
            print(f"{key}: ${value:,.2f}")
        else:
            print(f"{key}: {value}")


def example_4_comparison_scenarios():
    """Example 4: Compare different contribution rates."""
    print("\n" + "=" * 60)
    print("Example 4: Contribution Rate Comparison")
    print("=" * 60)
    
    base_inputs = {
        "age": 30,
        "retirement_age": 65,
        "annual_income": 75000,
        "current_balance": 30000,
        "expected_growth_rate_pct": 7,
        "inflation_rate_pct": 3,
        "tax_rate_pct": 22,
        "asset_types": ["401(k) / Traditional IRA (Pre-Tax)"]
    }
    
    contribution_rates = [10, 15, 20, 25]
    
    print("Comparing different contribution rates:")
    print(f"Base scenario: Age {base_inputs['age']}, Income ${base_inputs['annual_income']:,.0f}")
    print(f"Current Balance: ${base_inputs['current_balance']:,.0f}")
    print(f"Growth Rate: {base_inputs['expected_growth_rate_pct']}%")
    print()
    
    for rate in contribution_rates:
        inputs = UserInputs(
            contribution_rate_pct=rate,
            **base_inputs
        )
        result = project(inputs)
        
        print(f"Contribution Rate: {rate:2d}% → Future Value: ${result['Future Value (Pre-Tax)']:,.0f}")


def example_5_manual_calculations():
    """Example 5: Manual calculation verification."""
    print("\n" + "=" * 60)
    print("Example 5: Manual Calculation Verification")
    print("=" * 60)
    
    # Simple scenario for manual verification
    principal = 10000
    annual_contribution = 5000
    rate_pct = 10
    years = 3
    
    fv = future_value_with_contrib(principal, annual_contribution, rate_pct, years)
    
    print(f"Principal: ${principal:,.2f}")
    print(f"Annual Contribution: ${annual_contribution:,.2f}")
    print(f"Growth Rate: {rate_pct}%")
    print(f"Years: {years}")
    print()
    
    # Manual calculation
    r = rate_pct / 100
    principal_growth = principal * (1 + r) ** years
    contribution_growth = annual_contribution * (((1 + r) ** years - 1) / r)
    manual_fv = principal_growth + contribution_growth
    
    print("Manual Calculation:")
    print(f"Principal Growth: ${principal:,.2f} × (1.10)³ = ${principal_growth:,.2f}")
    print(f"Contribution Growth: ${annual_contribution:,.2f} × [((1.10)³ - 1) / 0.10] = ${contribution_growth:,.2f}")
    print(f"Total Future Value: ${manual_fv:,.2f}")
    print()
    print(f"Function Result: ${fv:,.2f}")
    print(f"Match: {'✓' if abs(fv - manual_fv) < 0.01 else '✗'}")


def main():
    """Run all examples."""
    print("Financial Advisor - Usage Examples")
    print("=" * 60)
    
    try:
        example_1_basic_projection()
        example_2_early_retirement()
        example_3_conservative_approach()
        example_4_comparison_scenarios()
        example_5_manual_calculations()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
