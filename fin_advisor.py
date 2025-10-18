"""
Finance Forecaster Prototype — Stage 1 (Streamlit-optional)

This file avoids hard dependency on Streamlit so it runs in restricted/sandboxed
environments. If Streamlit is available, it launches a simple UI. Otherwise, it
falls back to a CLI/arg-based runner. It also includes a small unit-test suite.

USAGE:
  # 1) Run tests
  python finance_forecaster_prototype.py --run-tests

  # 2) CLI with flags (no UI)
  python finance_forecaster_prototype.py \
    --age 30 --retirement-age 65 \
    --income 85000 --contribution-rate 15 \
    --current-balance 50000 --growth-rate 7 \
    --inflation-rate 3 --tax-rate 25

  # 3) Streamlit (if installed)
  streamlit run finance_forecaster_prototype.py
"""

from __future__ import annotations
import argparse
import math
import sys
from dataclasses import dataclass
from typing import Dict, List

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

@dataclass
class UserInputs:
    age: int
    retirement_age: int
    annual_income: float
    contribution_rate_pct: float  # % of income contributed annually
    current_balance: float
    expected_growth_rate_pct: float  # nominal annual return %
    inflation_rate_pct: float  # not yet used in Stage 1 projection
    tax_rate_pct: float  # simplified single blended rate for withdrawals
    asset_types: List[str]


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


def simple_post_tax(balance: float, tax_rate_pct: float) -> float:
    """Stage-1 simplified after-tax calculation applying a single blended rate."""
    tax_rate = tax_rate_pct / 100.0
    tax_rate = min(max(tax_rate, 0.0), 1.0)
    return balance * (1.0 - tax_rate)


def project(inputs: UserInputs) -> Dict[str, float]:
    yrs = years_to_retirement(inputs.age, inputs.retirement_age)
    annual_contribution = inputs.annual_income * (inputs.contribution_rate_pct / 100.0)
    fv = future_value_with_contrib(
        principal=inputs.current_balance,
        annual_contribution=annual_contribution,
        rate_pct=inputs.expected_growth_rate_pct,
        years=yrs,
    )
    after_tax = simple_post_tax(fv, inputs.tax_rate_pct)
    return {
        "Years Until Retirement": float(yrs),
        "Future Value (Pre-Tax)": float(round(fv, 2)),
        "Estimated Post-Tax Balance": float(round(after_tax, 2)),
    }


# ---------------------------
# UI LAYERS
# ---------------------------

_DEF_ASSET_TYPES = [
    "401(k) / Traditional IRA (Pre-Tax)",
    "Roth IRA (Post-Tax)",
    "Brokerage Account",
    "Savings Account",
]


def run_streamlit_ui() -> None:
    assert _STREAMLIT_AVAILABLE and st is not None

    st.set_page_config(page_title="Post-Tax Retirement Forecast Prototype", layout="centered")
    st.title("💰 Post-Tax Retirement Forecast (Prototype - Stage 1)")

    st.markdown(
        """
        ### Step 1: Input Your Financial Details
        This prototype captures basic inputs and computes a simplified projection.
        Future stages will add per-account tax logic, Monte Carlo, and AI assistance.
        """
    )

    col1, col2 = st.columns(2)
    with col1:
        age = st.number_input("Current Age", min_value=18, max_value=90, value=30)
        retirement_age = st.number_input("Target Retirement Age", min_value=40, max_value=80, value=65)
        annual_income = st.number_input("Annual Income ($)", min_value=10000, value=85000, step=1000)
        contribution_rate = st.slider("Annual Savings Rate (% of income)", 0, 50, 15)
    with col2:
        current_balance = st.number_input("Current Total Savings ($)", min_value=0, value=50000, step=1000)
        expected_growth_rate = st.slider("Expected Annual Growth Rate (%)", 0, 20, 7)
        inflation_rate = st.slider("Expected Inflation Rate (%)", 0, 10, 3)
        tax_rate = st.slider("Estimated Retirement Tax Rate (%)", 0, 50, 25)

    asset_types = st.multiselect("Select Asset Types You Hold", _DEF_ASSET_TYPES, default=[_DEF_ASSET_TYPES[0]])

    try:
        inputs = UserInputs(
            age=int(age),
            retirement_age=int(retirement_age),
            annual_income=float(annual_income),
            contribution_rate_pct=float(contribution_rate),
            current_balance=float(current_balance),
            expected_growth_rate_pct=float(expected_growth_rate),
            inflation_rate_pct=float(inflation_rate),
            tax_rate_pct=float(tax_rate),
            asset_types=list(asset_types),
        )
        result = project(inputs)
        st.markdown("---")
        st.subheader("Projected Results (Simplified)")
        st.dataframe(pd.DataFrame(result, index=[0]))
        st.success("✅ Input stage completed. Future versions will add Monte Carlo, AI, and tax-optimized withdrawals.")
    except Exception as e:
        st.error(f"Error: {e}")


def run_cli(args: argparse.Namespace) -> None:
    # If no CLI flags given, provide a tiny interactive prompt instead.
    def _coalesce(v, default):
        return v if v is not None else default

    age = _coalesce(args.age, 30)
    retirement_age = _coalesce(args.retirement_age, 65)
    annual_income = _coalesce(args.income, 85000.0)
    contribution_rate = _coalesce(args.contribution_rate, 15.0)
    current_balance = _coalesce(args.current_balance, 50000.0)
    growth_rate = _coalesce(args.growth_rate, 7.0)
    inflation_rate = _coalesce(args.inflation_rate, 3.0)
    tax_rate = _coalesce(args.tax_rate, 25.0)
    asset_types = args.asset_types or [_DEF_ASSET_TYPES[0]]

    inputs = UserInputs(
        age=int(age),
        retirement_age=int(retirement_age),
        annual_income=float(annual_income),
        contribution_rate_pct=float(contribution_rate),
        current_balance=float(current_balance),
        expected_growth_rate_pct=float(growth_rate),
        inflation_rate_pct=float(inflation_rate),
        tax_rate_pct=float(tax_rate),
        asset_types=asset_types,
    )

    result = project(inputs)

    print("\nPost-Tax Retirement Forecast (Stage 1)")
    print("-" * 44)
    for k, v in result.items():
        print(f"{k:28s}: {v}")


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

    def test_project_rounding(self):
        inputs = UserInputs(
            age=30,
            retirement_age=31,
            annual_income=100000,
            contribution_rate_pct=10,
            current_balance=0,
            expected_growth_rate_pct=10,
            inflation_rate_pct=0,
            tax_rate_pct=25,
            asset_types=[],
        )
        res = project(inputs)
        self.assertIn("Future Value (Pre-Tax)", res)
        self.assertIn("Estimated Post-Tax Balance", res)
        # FV should be ~ 10000 contribution grown 1 year at 10% = 11000
        self.assertAlmostEqual(res["Future Value (Pre-Tax)"], 11000.0, places=2)
        # After tax @25% = 8250
        self.assertAlmostEqual(res["Estimated Post-Tax Balance"], 8250.0, places=2)


# ---------------------------
# Entrypoint
# ---------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Post-Tax Retirement Forecast Prototype (Stage 1)")
    p.add_argument("--run-tests", action="store_true", help="Run unit tests and exit")
    p.add_argument("--age", type=int)
    p.add_argument("--retirement-age", type=int)
    p.add_argument("--income", type=float)
    p.add_argument("--contribution-rate", type=float)
    p.add_argument("--current-balance", type=float)
    p.add_argument("--growth-rate", type=float)
    p.add_argument("--inflation-rate", type=float)
    p.add_argument("--tax-rate", type=float)
    p.add_argument("--asset-types", nargs="*", default=[])
    p.add_argument("--no-ui", action="store_true", help="Force non-UI CLI mode")
    return p


def main(argv: List[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.run_tests:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestComputation)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1

    if (not args.no_ui) and _STREAMLIT_AVAILABLE:
        run_streamlit_ui()
        return 0

    run_cli(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
