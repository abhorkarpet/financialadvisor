"""
Financial Advisor — Stage 2: Asset Classification & Advanced Tax Logic

Enhanced retirement planning tool with:
- Asset classification (pre_tax, post_tax, tax_deferred)
- Per-asset growth simulation
- Sophisticated tax logic with IRS projections
- Capital gains calculations for brokerage accounts

USAGE:
  # 1) Run tests
  python fin_advisor.py --run-tests

  # 2) CLI with flags (no UI)
  python fin_advisor.py \
    --age 30 --retirement-age 65 \
    --income 85000 --contribution-rate 15 \
    --current-balance 50000 --growth-rate 7 \
    --inflation-rate 3 --tax-rate 25

  # 3) Streamlit (if installed)
  streamlit run fin_advisor.py
"""

from __future__ import annotations
import argparse
import math
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

# Optional Streamlit import (do NOT hard fail if missing)
try:
    import streamlit as st  # type: ignore
    _STREAMLIT_AVAILABLE = True
except Exception:  # ModuleNotFoundError or others
    st = None  # type: ignore
    _STREAMLIT_AVAILABLE = False

import pandas as pd

# ---------------------------
# Domain Models & Computation
# ---------------------------

class AssetType(Enum):
    """Asset classification for tax treatment."""
    PRE_TAX = "pre_tax"           # 401(k), Traditional IRA
    POST_TAX = "post_tax"         # Roth IRA, Brokerage
    TAX_DEFERRED = "tax_deferred" # Annuities, HSA

@dataclass
class Asset:
    """Individual asset with specific tax treatment."""
    name: str
    asset_type: AssetType
    current_balance: float
    annual_contribution: float
    growth_rate_pct: float
    tax_rate_pct: float = 0.0  # For post_tax assets (capital gains)
    
    def __post_init__(self):
        """Validate asset configuration."""
        if self.asset_type == AssetType.POST_TAX and self.tax_rate_pct == 0.0:
            # Default capital gains rate for brokerage accounts
            self.tax_rate_pct = 15.0

@dataclass
class TaxBracket:
    """IRS tax bracket information."""
    min_income: float
    max_income: Optional[float]
    rate_pct: float

@dataclass
class UserInputs:
    age: int
    retirement_age: int
    annual_income: float
    contribution_rate_pct: float  # % of income contributed annually
    expected_growth_rate_pct: float  # nominal annual return %
    inflation_rate_pct: float
    current_marginal_tax_rate_pct: float  # Current tax bracket
    retirement_marginal_tax_rate_pct: float  # Projected retirement tax bracket
    assets: List[Asset] = field(default_factory=list)
    
    # Legacy support
    @property
    def current_balance(self) -> float:
        """Total current balance across all assets."""
        return sum(asset.current_balance for asset in self.assets)
    
    @property
    def asset_types(self) -> List[str]:
        """Legacy asset types for backward compatibility."""
        return [asset.name for asset in self.assets]


def years_to_retirement(age: int, retirement_age: int) -> int:
    if retirement_age < age:
        raise ValueError("retirement_age must be >= age")
    return retirement_age - age


def future_value_with_contrib(principal: float, annual_contribution: float, rate_pct: float, years: int) -> float:
    """Compute FV with annual compounding and end-of-year contributions.
    Handles zero-rate edge case explicitly.
    FV = P*(1+r)^t + C * [((1+r)^t - 1)/r]
    """
    if years < 0:
        raise ValueError("years must be >= 0")
    r = rate_pct / 100.0
    if r == 0:
        return principal + annual_contribution * years
    growth = (1.0 + r) ** years
    return principal * growth + annual_contribution * ((growth - 1.0) / r)


def get_irs_tax_brackets_2024() -> List[TaxBracket]:
    """Get 2024 IRS tax brackets for single filers."""
    return [
        TaxBracket(0, 11000, 10.0),
        TaxBracket(11000, 44725, 12.0),
        TaxBracket(44725, 95375, 22.0),
        TaxBracket(95375, 182050, 24.0),
        TaxBracket(182050, 231250, 32.0),
        TaxBracket(231250, 578125, 35.0),
        TaxBracket(578125, None, 37.0),
    ]


def project_tax_rate(income: float, brackets: List[TaxBracket]) -> float:
    """Project marginal tax rate based on income and tax brackets."""
    for bracket in brackets:
        if bracket.min_income <= income and (bracket.max_income is None or income < bracket.max_income):
            return bracket.rate_pct
    return brackets[-1].rate_pct  # Top bracket


def calculate_asset_growth(asset: Asset, years: int) -> Tuple[float, float]:
    """Calculate future value and total contributions for an asset.
    
    Returns:
        Tuple of (future_value, total_contributions)
    """
    fv = future_value_with_contrib(
        asset.current_balance,
        asset.annual_contribution,
        asset.growth_rate_pct,
        years
    )
    total_contributions = asset.annual_contribution * years
    return fv, total_contributions


def apply_tax_logic(asset: Asset, future_value: float, total_contributions: float, 
                   retirement_tax_rate_pct: float) -> Tuple[float, float]:
    """Apply tax logic based on asset type.
    
    Returns:
        Tuple of (after_tax_value, tax_liability)
    """
    if asset.asset_type == AssetType.PRE_TAX:
        # Pre-tax accounts: taxed at withdrawal
        tax_liability = future_value * (retirement_tax_rate_pct / 100.0)
        after_tax_value = future_value - tax_liability
        
    elif asset.asset_type == AssetType.POST_TAX:
        if "Roth" in asset.name:
            # Roth IRA: no tax on withdrawal
            after_tax_value = future_value
            tax_liability = 0.0
        else:
            # Brokerage: only capital gains are taxed
            gains = future_value - total_contributions
            tax_liability = gains * (asset.tax_rate_pct / 100.0)
            after_tax_value = future_value - tax_liability
            
    elif asset.asset_type == AssetType.TAX_DEFERRED:
        # Annuities, HSA: complex rules, simplified for now
        if "HSA" in asset.name:
            # HSA: tax-free for medical expenses, taxed for other withdrawals
            # Simplified: assume 50% medical, 50% other
            medical_portion = future_value * 0.5
            other_portion = future_value * 0.5
            tax_liability = other_portion * (retirement_tax_rate_pct / 100.0)
            after_tax_value = future_value - tax_liability
        else:
            # Annuities: taxed as ordinary income
            tax_liability = future_value * (retirement_tax_rate_pct / 100.0)
            after_tax_value = future_value - tax_liability
    else:
        raise ValueError(f"Unknown asset type: {asset.asset_type}")
    
    return after_tax_value, tax_liability


def simple_post_tax(balance: float, tax_rate_pct: float) -> float:
    """Legacy function for backward compatibility."""
    tax_rate = tax_rate_pct / 100.0
    tax_rate = min(max(tax_rate, 0.0), 1.0)
    return balance * (1.0 - tax_rate)


def project(inputs: UserInputs) -> Dict[str, float]:
    """Enhanced projection with asset classification and sophisticated tax logic."""
    yrs = years_to_retirement(inputs.age, inputs.retirement_age)
    
    # If no assets defined, create a default one for backward compatibility
    if not inputs.assets:
        total_contribution = inputs.annual_income * (inputs.contribution_rate_pct / 100.0)
        default_asset = Asset(
            name="401(k) / Traditional IRA (Pre-Tax)",
            asset_type=AssetType.PRE_TAX,
            current_balance=inputs.current_balance,
            annual_contribution=total_contribution,
            growth_rate_pct=inputs.expected_growth_rate_pct
        )
        inputs.assets = [default_asset]
    
    # Calculate projections for each asset
    asset_results = []
    total_pre_tax_value = 0.0
    total_after_tax_value = 0.0
    total_tax_liability = 0.0
    
    for asset in inputs.assets:
        future_value, total_contributions = calculate_asset_growth(asset, yrs)
        after_tax_value, tax_liability = apply_tax_logic(
            asset, future_value, total_contributions, 
            inputs.retirement_marginal_tax_rate_pct
        )
        
        asset_results.append({
            "name": asset.name,
            "type": asset.asset_type.value,
            "pre_tax_value": future_value,
            "after_tax_value": after_tax_value,
            "tax_liability": tax_liability,
            "total_contributions": total_contributions
        })
        
        total_pre_tax_value += future_value
        total_after_tax_value += after_tax_value
        total_tax_liability += tax_liability
    
    # Calculate tax efficiency
    tax_efficiency = (total_after_tax_value / total_pre_tax_value * 100) if total_pre_tax_value > 0 else 0
    
    result = {
        "Years Until Retirement": float(yrs),
        "Total Future Value (Pre-Tax)": float(round(total_pre_tax_value, 2)),
        "Total After-Tax Balance": float(round(total_after_tax_value, 2)),
        "Total Tax Liability": float(round(total_tax_liability, 2)),
        "Tax Efficiency (%)": float(round(tax_efficiency, 2)),
        "Number of Assets": len(inputs.assets),
    }
    
    # Add per-asset breakdown
    for i, asset_result in enumerate(asset_results):
        result[f"Asset {i+1} - {asset_result['name']} (Pre-Tax)"] = round(asset_result['pre_tax_value'], 2)
        result[f"Asset {i+1} - {asset_result['name']} (After-Tax)"] = round(asset_result['after_tax_value'], 2)
    
    return result


# ---------------------------
# UI LAYERS
# ---------------------------

_DEF_ASSET_TYPES = [
    ("401(k) / Traditional IRA", AssetType.PRE_TAX),
    ("Roth IRA", AssetType.POST_TAX),
    ("Brokerage Account", AssetType.POST_TAX),
    ("HSA (Health Savings Account)", AssetType.TAX_DEFERRED),
    ("Annuity", AssetType.TAX_DEFERRED),
    ("Savings Account", AssetType.POST_TAX),
]

def create_default_assets() -> List[Asset]:
    """Create default asset configuration."""
    return [
        Asset(
            name="401(k) / Traditional IRA",
            asset_type=AssetType.PRE_TAX,
            current_balance=50000,
            annual_contribution=12000,
            growth_rate_pct=7.0
        ),
        Asset(
            name="Roth IRA",
            asset_type=AssetType.POST_TAX,
            current_balance=10000,
            annual_contribution=6000,
            growth_rate_pct=7.0
        ),
        Asset(
            name="Brokerage Account",
            asset_type=AssetType.POST_TAX,
            current_balance=15000,
            annual_contribution=3000,
            growth_rate_pct=7.0,
            tax_rate_pct=15.0  # Capital gains rate
        )
    ]


def run_streamlit_ui() -> None:
    assert _STREAMLIT_AVAILABLE and st is not None

    st.set_page_config(page_title="Financial Advisor - Stage 2", layout="wide")
    st.title("💰 Financial Advisor - Advanced Retirement Planning")

    st.markdown(
        """
        ### Stage 2: Asset Classification & Advanced Tax Logic
        This enhanced version includes:
        - **Asset Classification**: Pre-tax, Post-tax, and Tax-deferred accounts
        - **Per-Asset Growth Simulation**: Individual tracking of each account
        - **Sophisticated Tax Logic**: IRS tax brackets and capital gains calculations
        - **Tax Efficiency Analysis**: Optimize your retirement strategy
        """
    )

    # Basic inputs
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Personal Information")
        age = st.number_input("Current Age", min_value=18, max_value=90, value=30)
        retirement_age = st.number_input("Target Retirement Age", min_value=40, max_value=80, value=65)
        annual_income = st.number_input("Annual Income ($)", min_value=10000, value=85000, step=1000)
        
    with col2:
        st.subheader("Tax Information")
        current_tax_rate = st.slider("Current Marginal Tax Rate (%)", 0, 50, 22)
        retirement_tax_rate = st.slider("Projected Retirement Tax Rate (%)", 0, 50, 25)
        inflation_rate = st.slider("Expected Inflation Rate (%)", 0, 10, 3)

    # Asset configuration
    st.subheader("Asset Configuration")
    
    # Quick setup options
    setup_option = st.radio(
        "Choose setup method:",
        ["Use Default Portfolio", "Configure Individual Assets", "Legacy Mode (Simple)"]
    )
    
    assets = []
    
    if setup_option == "Use Default Portfolio":
        assets = create_default_assets()
        st.info("Using default portfolio with 401(k), Roth IRA, and Brokerage account")
        
    elif setup_option == "Configure Individual Assets":
        num_assets = st.number_input("Number of Assets", min_value=1, max_value=10, value=3)
        
        for i in range(num_assets):
            with st.expander(f"Asset {i+1}"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    asset_name = st.text_input(f"Asset Name {i+1}", value=f"Asset {i+1}")
                    asset_type = st.selectbox(
                        f"Asset Type {i+1}",
                        options=[(name, atype) for name, atype in _DEF_ASSET_TYPES],
                        format_func=lambda x: f"{x[0]} ({x[1].value})"
                    )
                with col2:
                    current_balance = st.number_input(f"Current Balance {i+1} ($)", min_value=0, value=10000, step=1000)
                    annual_contribution = st.number_input(f"Annual Contribution {i+1} ($)", min_value=0, value=5000, step=500)
                with col3:
                    growth_rate = st.slider(f"Growth Rate {i+1} (%)", 0, 20, 7)
                    if asset_type[1] == AssetType.POST_TAX and "Brokerage" in asset_name:
                        tax_rate = st.slider(f"Capital Gains Rate {i+1} (%)", 0, 30, 15)
                    else:
                        tax_rate = 0
                
                assets.append(Asset(
                    name=asset_name,
                    asset_type=asset_type[1],
                    current_balance=current_balance,
                    annual_contribution=annual_contribution,
                    growth_rate_pct=growth_rate,
                    tax_rate_pct=tax_rate
                ))
    
    else:  # Legacy mode
        st.info("Legacy mode: Single blended calculation")
        contribution_rate = st.slider("Annual Savings Rate (% of income)", 0, 50, 15)
        current_balance = st.number_input("Current Total Savings ($)", min_value=0, value=50000, step=1000)
        expected_growth_rate = st.slider("Expected Annual Growth Rate (%)", 0, 20, 7)
        
        # Create legacy asset
        total_contribution = annual_income * (contribution_rate / 100.0)
        assets = [Asset(
            name="401(k) / Traditional IRA (Pre-Tax)",
            asset_type=AssetType.PRE_TAX,
            current_balance=current_balance,
            annual_contribution=total_contribution,
            growth_rate_pct=expected_growth_rate
        )]

    try:
        inputs = UserInputs(
            age=int(age),
            retirement_age=int(retirement_age),
            annual_income=float(annual_income),
            contribution_rate_pct=15.0,  # Not used in new system
            expected_growth_rate_pct=7.0,  # Not used in new system
            inflation_rate_pct=float(inflation_rate),
            current_marginal_tax_rate_pct=float(current_tax_rate),
            retirement_marginal_tax_rate_pct=float(retirement_tax_rate),
            assets=assets
        )
        
        result = project(inputs)
        
        st.markdown("---")
        st.subheader("📊 Retirement Projection Results")
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Years to Retirement", f"{result['Years Until Retirement']:.0f}")
        with col2:
            st.metric("Total Pre-Tax Value", f"${result['Total Future Value (Pre-Tax)']:,.0f}")
        with col3:
            st.metric("Total After-Tax Value", f"${result['Total After-Tax Balance']:,.0f}")
        with col4:
            st.metric("Tax Efficiency", f"{result['Tax Efficiency (%)']:.1f}%")
        
        # Detailed results
        st.subheader("📈 Detailed Breakdown")
        
        # Create a cleaner dataframe for display
        display_data = {}
        for key, value in result.items():
            if "Asset" in key and "Pre-Tax" in key:
                continue  # Skip individual asset pre-tax values
            elif "Asset" in key and "After-Tax" in key:
                asset_name = key.split(" - ")[1].replace(" (After-Tax)", "")
                if asset_name not in display_data:
                    display_data[asset_name] = {}
                display_data[asset_name]["After-Tax Value"] = f"${value:,.0f}"
            elif key not in ["Years Until Retirement", "Number of Assets"]:
                display_data[key] = {"Value": f"${value:,.0f}" if "Value" in key or "Balance" in key or "Liability" in key else f"{value:.1f}%" if "Efficiency" in key else value}
        
        if display_data:
            st.dataframe(pd.DataFrame(display_data).T, use_container_width=True)
        
        # Tax analysis
        st.subheader("💡 Tax Analysis")
        tax_liability = result.get("Total Tax Liability", 0)
        total_pre_tax = result.get("Total Future Value (Pre-Tax)", 1)
        tax_percentage = (tax_liability / total_pre_tax * 100) if total_pre_tax > 0 else 0
        
        st.info(f"**Total Tax Liability**: ${tax_liability:,.0f} ({tax_percentage:.1f}% of pre-tax value)")
        
        if result["Tax Efficiency (%)"] > 85:
            st.success("🎉 Excellent tax efficiency! Your portfolio is well-optimized.")
        elif result["Tax Efficiency (%)"] > 75:
            st.warning("⚠️ Good tax efficiency, but there may be room for improvement.")
        else:
            st.error("🚨 Consider tax optimization strategies to improve efficiency.")
            
        st.success("✅ Stage 2 analysis completed! Next: Monte Carlo simulation and AI optimization.")
        
    except Exception as e:
        st.error(f"Error: {e}")
        st.exception(e)


def run_cli(args: argparse.Namespace) -> None:
    """Run CLI with enhanced asset classification support."""
    def _coalesce(v, default):
        return v if v is not None else default

    age = _coalesce(args.age, 30)
    retirement_age = _coalesce(args.retirement_age, 65)
    annual_income = _coalesce(args.income, 85000.0)
    contribution_rate = _coalesce(args.contribution_rate, 15.0)
    current_balance = _coalesce(args.current_balance, 50000.0)
    growth_rate = _coalesce(args.growth_rate, 7.0)
    inflation_rate = _coalesce(args.inflation_rate, 3.0)
    current_tax_rate = _coalesce(args.current_tax_rate, 22.0)
    retirement_tax_rate = _coalesce(args.retirement_tax_rate, 25.0)
    
    # Create default assets for CLI
    total_contribution = annual_income * (contribution_rate / 100.0)
    assets = [
        Asset(
            name="401(k) / Traditional IRA",
            asset_type=AssetType.PRE_TAX,
            current_balance=current_balance * 0.7,  # 70% in pre-tax
            annual_contribution=total_contribution * 0.6,  # 60% to pre-tax
            growth_rate_pct=growth_rate
        ),
        Asset(
            name="Roth IRA",
            asset_type=AssetType.POST_TAX,
            current_balance=current_balance * 0.2,  # 20% in Roth
            annual_contribution=total_contribution * 0.3,  # 30% to Roth
            growth_rate_pct=growth_rate
        ),
        Asset(
            name="Brokerage Account",
            asset_type=AssetType.POST_TAX,
            current_balance=current_balance * 0.1,  # 10% in brokerage
            annual_contribution=total_contribution * 0.1,  # 10% to brokerage
            growth_rate_pct=growth_rate,
            tax_rate_pct=15.0  # Capital gains rate
        )
    ]

    inputs = UserInputs(
        age=int(age),
        retirement_age=int(retirement_age),
        annual_income=float(annual_income),
        contribution_rate_pct=float(contribution_rate),
        expected_growth_rate_pct=float(growth_rate),
        inflation_rate_pct=float(inflation_rate),
        current_marginal_tax_rate_pct=float(current_tax_rate),
        retirement_marginal_tax_rate_pct=float(retirement_tax_rate),
        assets=assets
    )

    result = project(inputs)

    print("\nFinancial Advisor - Stage 2: Advanced Retirement Planning")
    print("=" * 60)
    print(f"Age: {age} → Retirement: {retirement_age} ({result['Years Until Retirement']:.0f} years)")
    print(f"Annual Income: ${annual_income:,.0f}")
    print(f"Total Contribution: ${total_contribution:,.0f} ({contribution_rate:.0f}% of income)")
    print()
    
    print("Asset Breakdown:")
    for i, asset in enumerate(assets, 1):
        asset_key = f"Asset {i} - {asset.name} (After-Tax)"
        if asset_key in result:
            print(f"  {asset.name}: ${result[asset_key]:,.0f}")
    print()
    
    print("Summary:")
    print(f"  Total Pre-Tax Value: ${result['Total Future Value (Pre-Tax)']:,.0f}")
    print(f"  Total After-Tax Value: ${result['Total After-Tax Balance']:,.0f}")
    print(f"  Total Tax Liability: ${result['Total Tax Liability']:,.0f}")
    print(f"  Tax Efficiency: {result['Tax Efficiency (%)']:.1f}%")
    
    # Tax analysis
    tax_percentage = (result['Total Tax Liability'] / result['Total Future Value (Pre-Tax)'] * 100)
    print(f"  Tax Rate: {tax_percentage:.1f}% of pre-tax value")
    
    if result['Tax Efficiency (%)'] > 85:
        print("\n🎉 Excellent tax efficiency!")
    elif result['Tax Efficiency (%)'] > 75:
        print("\n⚠️ Good tax efficiency, room for improvement.")
    else:
        print("\n🚨 Consider tax optimization strategies.")


# ---------------------------
# Tests (unittest)
# ---------------------------

import unittest


class TestComputation(unittest.TestCase):
    def test_years_to_retirement_basic(self):
        self.assertEqual(years_to_retirement(30, 65), 35)

    def test_years_to_retirement_invalid(self):
        with self.assertRaises(ValueError):
            years_to_retirement(65, 60)

    def test_future_value_zero_rate(self):
        fv = future_value_with_contrib(10000, 1000, 0.0, 5)
        # 10k principal + 5*1k contributions
        self.assertAlmostEqual(fv, 15000.0, places=6)

    def test_future_value_positive_rate(self):
        # P=0, C=1000, r=10%, t=2  => 1000*((1.1^2 - 1)/0.1) = 1000*(0.21/0.1)=2100
        fv = future_value_with_contrib(0.0, 1000.0, 10.0, 2)
        self.assertAlmostEqual(fv, 2100.0, places=6)

    def test_post_tax_bounds(self):
        self.assertAlmostEqual(simple_post_tax(1000, 0), 1000.0)
        self.assertAlmostEqual(simple_post_tax(1000, 100), 0.0)
        self.assertAlmostEqual(simple_post_tax(1000, 25), 750.0)

    def test_asset_creation(self):
        asset = Asset(
            name="Test 401(k)",
            asset_type=AssetType.PRE_TAX,
            current_balance=10000,
            annual_contribution=5000,
            growth_rate_pct=7.0
        )
        self.assertEqual(asset.name, "Test 401(k)")
        self.assertEqual(asset.asset_type, AssetType.PRE_TAX)
        self.assertEqual(asset.current_balance, 10000)
        self.assertEqual(asset.annual_contribution, 5000)
        self.assertEqual(asset.growth_rate_pct, 7.0)

    def test_asset_growth_calculation(self):
        asset = Asset(
            name="Test Asset",
            asset_type=AssetType.PRE_TAX,
            current_balance=10000,
            annual_contribution=1000,
            growth_rate_pct=10.0
        )
        future_value, total_contributions = calculate_asset_growth(asset, 2)
        # Manual calculation: 10000 * 1.1^2 + 1000 * ((1.1^2 - 1)/0.1)
        # = 12100 + 1000 * (0.21/0.1) = 12100 + 2100 = 14200
        self.assertAlmostEqual(future_value, 14200.0, places=2)
        self.assertEqual(total_contributions, 2000.0)

    def test_tax_logic_pre_tax(self):
        asset = Asset(
            name="401(k)",
            asset_type=AssetType.PRE_TAX,
            current_balance=0,
            annual_contribution=0,
            growth_rate_pct=0
        )
        after_tax, tax_liability = apply_tax_logic(asset, 100000, 0, 25.0)
        self.assertEqual(after_tax, 75000.0)
        self.assertEqual(tax_liability, 25000.0)

    def test_tax_logic_roth_ira(self):
        asset = Asset(
            name="Roth IRA",
            asset_type=AssetType.POST_TAX,
            current_balance=0,
            annual_contribution=0,
            growth_rate_pct=0
        )
        after_tax, tax_liability = apply_tax_logic(asset, 100000, 0, 25.0)
        self.assertEqual(after_tax, 100000.0)
        self.assertEqual(tax_liability, 0.0)

    def test_tax_logic_brokerage(self):
        asset = Asset(
            name="Brokerage Account",
            asset_type=AssetType.POST_TAX,
            current_balance=0,
            annual_contribution=0,
            growth_rate_pct=0,
            tax_rate_pct=15.0
        )
        # 100k future value, 50k contributions = 50k gains
        after_tax, tax_liability = apply_tax_logic(asset, 100000, 50000, 25.0)
        expected_tax = 50000 * 0.15  # 15% on gains
        self.assertEqual(after_tax, 100000 - expected_tax)
        self.assertEqual(tax_liability, expected_tax)

    def test_project_enhanced(self):
        assets = [
            Asset(
                name="401(k)",
                asset_type=AssetType.PRE_TAX,
                current_balance=0,
                annual_contribution=10000,
                growth_rate_pct=10.0
            )
        ]
        inputs = UserInputs(
            age=30,
            retirement_age=31,
            annual_income=100000,
            contribution_rate_pct=10,
            expected_growth_rate_pct=10,
            inflation_rate_pct=0,
            current_marginal_tax_rate_pct=22,
            retirement_marginal_tax_rate_pct=25,
            assets=assets
        )
        res = project(inputs)
        self.assertIn("Total Future Value (Pre-Tax)", res)
        self.assertIn("Total After-Tax Balance", res)
        self.assertIn("Tax Efficiency (%)", res)
        # FV should be ~ 10000 contribution grown 1 year at 10% = 11000
        # But with 0 principal, it's just the contribution: 10000
        self.assertAlmostEqual(res["Total Future Value (Pre-Tax)"], 10000.0, places=2)
        # After tax @25% = 7500
        self.assertAlmostEqual(res["Total After-Tax Balance"], 7500.0, places=2)

    def test_irs_tax_brackets(self):
        brackets = get_irs_tax_brackets_2024()
        self.assertEqual(len(brackets), 7)
        self.assertEqual(brackets[0].rate_pct, 10.0)
        self.assertEqual(brackets[-1].rate_pct, 37.0)

    def test_tax_rate_projection(self):
        brackets = get_irs_tax_brackets_2024()
        # Test various income levels
        self.assertEqual(project_tax_rate(5000, brackets), 10.0)   # First bracket
        self.assertEqual(project_tax_rate(30000, brackets), 12.0)  # Second bracket
        self.assertEqual(project_tax_rate(100000, brackets), 24.0) # Fourth bracket


# ---------------------------
# Entrypoint
# ---------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Financial Advisor - Stage 2: Advanced Retirement Planning")
    p.add_argument("--run-tests", action="store_true", help="Run unit tests and exit")
    p.add_argument("--age", type=int, help="Current age")
    p.add_argument("--retirement-age", type=int, help="Target retirement age")
    p.add_argument("--income", type=float, help="Annual income")
    p.add_argument("--contribution-rate", type=float, help="Annual savings rate (percent of income)")
    p.add_argument("--current-balance", type=float, help="Current total savings")
    p.add_argument("--growth-rate", type=float, help="Expected annual growth rate (percent)")
    p.add_argument("--inflation-rate", type=float, help="Expected inflation rate (percent)")
    p.add_argument("--current-tax-rate", type=float, help="Current marginal tax rate (percent)")
    p.add_argument("--retirement-tax-rate", type=float, help="Projected retirement tax rate (percent)")
    p.add_argument("--asset-types", nargs="*", default=[], help="Asset types (legacy)")
    p.add_argument("--no-ui", action="store_true", help="Force non-UI CLI mode")
    return p


def main(argv: List[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.run_tests:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestComputation)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1

    # Always default to CLI mode when running the script directly
    # Streamlit UI should only be accessed via 'streamlit run fin_advisor.py'
    run_cli(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# Streamlit will automatically call this when running with 'streamlit run fin_advisor.py'
# This is the proper way to handle Streamlit execution
