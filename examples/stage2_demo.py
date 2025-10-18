#!/usr/bin/env python3
"""
Stage 2 Demo: Advanced Asset Classification & Tax Logic
Demonstrates the new features of the Financial Advisor Stage 2.
"""

import sys
import os

# Add the parent directory to the path so we can import fin_advisor
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fin_advisor import (
    Asset, AssetType, UserInputs, project,
    get_irs_tax_brackets_2024, project_tax_rate
)


def demo_asset_classification():
    """Demonstrate the new asset classification system."""
    print("=" * 70)
    print("STAGE 2 DEMO: Asset Classification & Tax Logic")
    print("=" * 70)
    
    print("\n1. ASSET CLASSIFICATION SYSTEM")
    print("-" * 40)
    
    # Create different types of assets
    assets = [
        Asset(
            name="401(k) - Company Match",
            asset_type=AssetType.PRE_TAX,
            current_balance=75000,
            annual_contribution=19500,  # 2024 limit
            growth_rate_pct=7.0
        ),
        Asset(
            name="Roth IRA",
            asset_type=AssetType.POST_TAX,
            current_balance=25000,
            annual_contribution=7000,  # 2024 limit
            growth_rate_pct=7.0
        ),
        Asset(
            name="Brokerage Account",
            asset_type=AssetType.POST_TAX,
            current_balance=30000,
            annual_contribution=5000,
            growth_rate_pct=7.0,
            tax_rate_pct=15.0  # Capital gains rate
        ),
        Asset(
            name="HSA (Health Savings Account)",
            asset_type=AssetType.TAX_DEFERRED,
            current_balance=15000,
            annual_contribution=4300,  # 2024 limit
            growth_rate_pct=6.0
        )
    ]
    
    print("Asset Portfolio:")
    for i, asset in enumerate(assets, 1):
        print(f"  {i}. {asset.name}")
        print(f"     Type: {asset.asset_type.value}")
        print(f"     Current Balance: ${asset.current_balance:,.0f}")
        print(f"     Annual Contribution: ${asset.annual_contribution:,.0f}")
        print(f"     Growth Rate: {asset.growth_rate_pct}%")
        if asset.tax_rate_pct > 0:
            print(f"     Tax Rate: {asset.tax_rate_pct}%")
        print()
    
    return assets


def demo_tax_brackets():
    """Demonstrate IRS tax bracket projections."""
    print("\n2. IRS TAX BRACKET PROJECTIONS")
    print("-" * 40)
    
    brackets = get_irs_tax_brackets_2024()
    print("2024 IRS Tax Brackets (Single Filer):")
    for bracket in brackets:
        max_income = f"${bracket.max_income:,.0f}" if bracket.max_income else "∞"
        print(f"  ${bracket.min_income:,.0f} - {max_income}: {bracket.rate_pct}%")
    
    # Test different income levels
    test_incomes = [30000, 60000, 100000, 200000, 500000]
    print(f"\nTax Rate Projections:")
    for income in test_incomes:
        rate = project_tax_rate(income, brackets)
        print(f"  Income ${income:,.0f} → Marginal Tax Rate: {rate}%")


def demo_retirement_projection(assets):
    """Demonstrate the enhanced retirement projection."""
    print("\n3. ENHANCED RETIREMENT PROJECTION")
    print("-" * 40)
    
    inputs = UserInputs(
        age=30,
        retirement_age=65,
        annual_income=120000,
        contribution_rate_pct=20,  # Not used in new system
        expected_growth_rate_pct=7.0,  # Not used in new system
        inflation_rate_pct=3.0,
        current_marginal_tax_rate_pct=24.0,  # Current bracket
        retirement_marginal_tax_rate_pct=22.0,  # Lower in retirement
        assets=assets
    )
    
    result = project(inputs)
    
    print(f"Scenario: Age {inputs.age} → {inputs.retirement_age} ({result['Years Until Retirement']:.0f} years)")
    print(f"Current Income: ${inputs.annual_income:,.0f}")
    print(f"Current Tax Rate: {inputs.current_marginal_tax_rate_pct}%")
    print(f"Retirement Tax Rate: {inputs.retirement_marginal_tax_rate_pct}%")
    print()
    
    print("PROJECTION RESULTS:")
    print(f"  Total Pre-Tax Value: ${result['Total Future Value (Pre-Tax)']:,.0f}")
    print(f"  Total After-Tax Value: ${result['Total After-Tax Balance']:,.0f}")
    print(f"  Total Tax Liability: ${result['Total Tax Liability']:,.0f}")
    print(f"  Tax Efficiency: {result['Tax Efficiency (%)']:.1f}%")
    print()
    
    print("PER-ASSET BREAKDOWN:")
    for i in range(1, len(assets) + 1):
        asset_key = f"Asset {i} - {assets[i-1].name} (After-Tax)"
        if asset_key in result:
            print(f"  {assets[i-1].name}: ${result[asset_key]:,.0f}")
    
    # Tax analysis
    tax_percentage = (result['Total Tax Liability'] / result['Total Future Value (Pre-Tax)'] * 100)
    print(f"\nTAX ANALYSIS:")
    print(f"  Effective Tax Rate: {tax_percentage:.1f}% of pre-tax value")
    
    if result['Tax Efficiency (%)'] > 85:
        print("  🎉 Excellent tax efficiency! Portfolio is well-optimized.")
    elif result['Tax Efficiency (%)'] > 75:
        print("  ⚠️ Good tax efficiency, but there's room for improvement.")
    else:
        print("  🚨 Consider tax optimization strategies.")


def demo_tax_optimization():
    """Demonstrate tax optimization insights."""
    print("\n4. TAX OPTIMIZATION INSIGHTS")
    print("-" * 40)
    
    print("Key Tax Strategies Demonstrated:")
    print("  1. Pre-tax contributions reduce current taxable income")
    print("  2. Roth contributions provide tax-free growth")
    print("  3. Brokerage accounts only tax capital gains")
    print("  4. HSA offers triple tax advantage")
    print("  5. Asset location optimization maximizes after-tax returns")
    print()
    
    print("Optimization Recommendations:")
    print("  • Maximize employer 401(k) match (free money)")
    print("  • Contribute to Roth IRA for tax-free growth")
    print("  • Use HSA for medical expenses and retirement")
    print("  • Consider tax-loss harvesting in brokerage accounts")
    print("  • Plan withdrawal sequence to minimize lifetime taxes")


def main():
    """Run the complete Stage 2 demonstration."""
    try:
        # Run all demos
        assets = demo_asset_classification()
        demo_tax_brackets()
        demo_retirement_projection(assets)
        demo_tax_optimization()
        
        print("\n" + "=" * 70)
        print("STAGE 2 DEMO COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print("\nNext Steps:")
        print("  • Try the Streamlit UI: streamlit run fin_advisor.py")
        print("  • Run CLI examples: python fin_advisor.py --no-ui --help")
        print("  • Explore the test suite: python fin_advisor.py --run-tests")
        print("  • Stage 3: Monte Carlo simulation and risk analysis")
        
    except Exception as e:
        print(f"\nError running demo: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
