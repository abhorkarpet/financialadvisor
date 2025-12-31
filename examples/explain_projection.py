#!/usr/bin/env python3
"""
Example script demonstrating the projected balance explanation module.

This script shows how to use the explain_projected_balance() function
to get a detailed breakdown of how retirement projections are calculated.
"""

import sys
import os

# Add parent directory to path to import fin_advisor
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fin_advisor import UserInputs, Asset, AssetType, explain_projected_balance, project


def example_1_simple_projection():
    """Example 1: Simple projection with default single asset."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Simple Retirement Projection")
    print("=" * 80)

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

    # Get projection results
    results = project(inputs)

    print(f"\nProjection Results:")
    print(f"  Pre-Tax Balance: ${results['projected_balance_pre_tax']:,.2f}")
    print(f"  After-Tax Balance: ${results['projected_balance']:,.2f}")
    print(f"\n{'-' * 80}")
    print("DETAILED EXPLANATION:")
    print('-' * 80)

    # Get detailed explanation
    explanation = explain_projected_balance(inputs)
    print(explanation)


def example_2_multiple_assets():
    """Example 2: Multiple assets with different types."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Multiple Asset Types")
    print("=" * 80)

    inputs = UserInputs(
        age=35,
        retirement_age=65,
        annual_income=120000,
        contribution_rate_pct=0,  # Contributions specified per asset
        current_balance=0,         # Balance specified per asset
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
            ),
            Asset(
                name="Brokerage Account",
                asset_type=AssetType.POST_TAX,
                current_balance=25000,
                annual_contribution=5000,
                growth_rate_pct=6.5,
                tax_rate_pct=15.0  # Capital gains rate
            ),
            Asset(
                name="HSA",
                asset_type=AssetType.TAX_DEFERRED,
                current_balance=8000,
                annual_contribution=3850,
                growth_rate_pct=6.0
            )
        ]
    )

    # Get projection results
    results = project(inputs)

    print(f"\nProjection Results:")
    print(f"  Total Pre-Tax Balance: ${results['projected_balance_pre_tax']:,.2f}")
    print(f"  Total After-Tax Balance: ${results['projected_balance']:,.2f}")
    print(f"  Total Tax Liability: ${results['total_tax_liability']:,.2f}")
    print(f"  Tax Efficiency: {results['tax_efficiency_pct']:.2f}%")

    print(f"\n{'-' * 80}")
    print("DETAILED EXPLANATION:")
    print('-' * 80)

    # Get detailed explanation
    explanation = explain_projected_balance(inputs)
    print(explanation)


def example_3_young_investor():
    """Example 3: Young investor with long time horizon."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Young Investor (25 years old, 40 years to retirement)")
    print("=" * 80)

    inputs = UserInputs(
        age=25,
        retirement_age=65,
        annual_income=60000,
        contribution_rate_pct=10.0,
        current_balance=10000,
        expected_growth_rate_pct=8.0,  # Higher growth for longer horizon
        expected_inflation_rate_pct=3.0,
        retirement_marginal_tax_rate_pct=22.0
    )

    # Get projection results
    results = project(inputs)

    print(f"\nProjection Results:")
    print(f"  Pre-Tax Balance: ${results['projected_balance_pre_tax']:,.2f}")
    print(f"  After-Tax Balance: ${results['projected_balance']:,.2f}")
    print(f"\n{'-' * 80}")
    print("DETAILED EXPLANATION:")
    print('-' * 80)

    # Get detailed explanation
    explanation = explain_projected_balance(inputs)
    print(explanation)


if __name__ == "__main__":
    # Run all examples
    print("\n" * 2)
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "PROJECTED BALANCE EXPLANATION EXAMPLES" + " " * 24 + "║")
    print("╚" + "=" * 78 + "╝")

    # Example 1: Simple single-asset scenario
    example_1_simple_projection()

    input("\n\nPress Enter to continue to Example 2...")

    # Example 2: Multiple assets with different tax treatments
    example_2_multiple_assets()

    input("\n\nPress Enter to continue to Example 3...")

    # Example 3: Young investor with long time horizon
    example_3_young_investor()

    print("\n" * 2)
    print("=" * 80)
    print("All examples completed!")
    print("=" * 80)
