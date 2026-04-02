"""
Smart Retire AI — Advanced Retirement Planning Tool

Enhanced retirement planning tool with:
- Asset classification (pre_tax, post_tax, tax_deferred)
- Per-asset growth simulation with tax-efficient projections
- Portfolio growth during retirement with inflation-adjusted withdrawals
- One-time life expenses at retirement support
- Comprehensive income gap recommendations

Usage:
    Run the Streamlit web application:
        $ streamlit run fin_advisor.py

    Run unit tests:
        $ python3 fin_advisor.py --run-tests

Author: AI Assistant
Version: 12.4.0
"""

from __future__ import annotations
import argparse
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

# Version Management
VERSION = "12.4.0"

# Streamlit import
import streamlit as st
import streamlit.components.v1 as components
import io
import os
import csv
import time
import urllib.parse
from datetime import datetime

import pandas as pd

# Analytics module
try:
    from financialadvisor.utils.analytics import (
        initialize_analytics,
        set_analytics_consent,
        track_event,
        track_page_view,
        track_onboarding_step_started,
        track_onboarding_step_completed,
        track_feature_usage,
        track_pdf_generation,
        track_monte_carlo_run,
        track_statement_upload,
        track_error,
        is_analytics_enabled,
        opt_out,
        opt_in,
        get_age_range,
        get_goal_range,
        get_session_replay_script,
        reset_analytics_session,
    )
    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False
    # Define no-op functions if analytics not available with matching signatures
    def initialize_analytics() -> None: pass
    def set_analytics_consent(consented: bool) -> None: pass
    def track_event(event_name: str, properties: Optional[Dict[str, any]] = None, user_properties: Optional[Dict[str, any]] = None) -> None: pass
    def track_page_view(page_name: str) -> None: pass
    def track_onboarding_step_started(step: int, **kwargs: any) -> None: pass
    def track_onboarding_step_completed(step: int, **kwargs: any) -> None: pass
    def track_feature_usage(feature: str, **kwargs: any) -> None: pass
    def track_pdf_generation(success: bool) -> None: pass
    def track_monte_carlo_run(num_simulations: int, **kwargs: any) -> None: pass
    def track_statement_upload(success: bool, num_statements: int, num_accounts: int) -> None: pass
    def track_error(error_type: str, error_message: str, context: Optional[Dict[str, any]] = None) -> None: pass
    def is_analytics_enabled() -> bool: return False
    def opt_out() -> None: pass
    def opt_in() -> None: pass
    def get_age_range(age: float) -> str: return "unknown"
    def get_goal_range(goal: float) -> str: return "unknown"
    def get_session_replay_script() -> str: return ""
    def reset_analytics_session() -> None: pass

# n8n integration for financial statement upload
try:
    from integrations.n8n_client import N8NClient, N8NError
    from pypdf import PdfReader
    from dotenv import load_dotenv
    load_dotenv()  # Load environment variables from .env file
    _N8N_AVAILABLE = True
except ImportError:
    _N8N_AVAILABLE = False

# Chat advisor (Mode 2 conversational planning)
try:
    from integrations.chat_advisor import chat_with_advisor, fields_are_complete
    _CHAT_AVAILABLE = True
except ImportError:
    _CHAT_AVAILABLE = False

# PDF generation
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    _REPORTLAB_AVAILABLE = True
except ImportError:
    _REPORTLAB_AVAILABLE = False


def _fmt_inr(n: float) -> str:
    """Format a number using the Indian numbering system (last 3 digits, then groups of 2).

    Examples: 600000 → '6,00,000'  |  8589300 → '85,89,300'  |  10000000 → '1,00,00,000'
    """
    neg = n < 0
    s = str(int(round(abs(n))))
    if len(s) <= 3:
        return ('-' if neg else '') + s
    result = s[-3:]
    s = s[:-3]
    while s:
        result = s[-2:] + ',' + result
        s = s[:-2]
    return ('-' if neg else '') + result


def _fmt_currency(val: float, is_india: bool) -> str:
    """Return currency string: ₹Indian-format for India, $US-format for US."""
    if is_india:
        return f"₹{_fmt_inr(val)}"
    return f"${val:,.0f}"


def load_release_notes() -> Optional[str]:
    """Load release notes for the current version from file."""
    notes_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"RELEASE_NOTES_v{VERSION}.md"
    )
    try:
        with open(notes_path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


# ---------------------------
# Import refactored modules
# ---------------------------
from financialadvisor.domain.models import (
    AssetType,
    TaxBehavior,
    Asset,
    TaxBracket,
    UserInputs,
    _DEF_ASSET_TYPES,
    infer_tax_behavior,
)

from financialadvisor.core.calculator import (
    years_to_retirement,
    future_value_with_contrib,
)

from financialadvisor.core.tax_engine import (
    get_irs_tax_brackets_2024,
    project_tax_rate,
    calculate_asset_growth,
    apply_tax_logic,
    simple_post_tax,
)

from financialadvisor.core.projector import project

from financialadvisor.core.explainer import explain_projected_balance

# ---------------------------
# Domain Models & Computation (now imported from financialadvisor package)
# ---------------------------

TAX_TREATMENT_OPTIONS = ["Tax-Deferred", "Tax-Free", "Post-Tax"]


def _resolve_tax_settings(
    tax_treatment: str,
    account_name: str,
    tax_rate_pct: float = 0.0,
) -> Tuple[AssetType, TaxBehavior, float]:
    """Convert UI tax labels into explicit internal tax settings."""
    normalized = str(tax_treatment).strip().lower().replace("_", "-")
    account_name = str(account_name).strip()
    rate = float(tax_rate_pct or 0.0)

    if normalized in {"pre-tax", "pre tax", "pre_tax"}:
        return AssetType.PRE_TAX, TaxBehavior.PRE_TAX, 0.0

    if normalized in {"tax-deferred", "tax deferred", "tax_deferred"}:
        lowered_name = account_name.lower()
        if "hsa" in lowered_name or "health savings" in lowered_name:
            return AssetType.TAX_DEFERRED, TaxBehavior.HSA_SPLIT, 0.0
        if "annuity" in lowered_name:
            return AssetType.TAX_DEFERRED, TaxBehavior.ORDINARY_INCOME, 0.0
        return AssetType.PRE_TAX, TaxBehavior.PRE_TAX, 0.0

    if normalized in {"tax-free", "tax free", "tax_free", "roth"}:
        return AssetType.POST_TAX, TaxBehavior.TAX_FREE, 0.0

    if normalized in {"post-tax", "post tax", "post_tax"}:
        tax_behavior = infer_tax_behavior(AssetType.POST_TAX, account_name, rate)
        normalized_rate = rate if tax_behavior == TaxBehavior.CAPITAL_GAINS else 0.0
        return AssetType.POST_TAX, tax_behavior, normalized_rate

    raise ValueError(
        f"Invalid tax treatment: '{tax_treatment}'. Must be 'Tax-Deferred', "
        f"'Tax-Free', or 'Post-Tax' (or legacy: 'pre_tax', 'post_tax', 'tax_deferred')"
    )


def _asset_to_tax_treatment_label(asset: Asset) -> str:
    """Return the stable editor label for an asset's tax treatment."""
    if asset.tax_behavior == TaxBehavior.TAX_FREE:
        return "Tax-Free"
    if asset.tax_behavior in (TaxBehavior.CAPITAL_GAINS, TaxBehavior.NO_ADDITIONAL_TAX):
        return "Post-Tax"
    return "Tax-Deferred"


def _asset_from_editor_row(row: Dict[str, object]) -> Asset:
    """Create an Asset from a row used in AI-upload and CSV editors."""
    account_name = str(row["Account Name"])
    raw_tax_rate = float(row.get("Tax Rate on Gains (%)", 0.0) or 0.0)
    asset_type, tax_behavior, normalized_tax_rate = _resolve_tax_settings(
        str(row["Tax Treatment"]),
        account_name,
        raw_tax_rate,
    )
    return Asset(
        name=account_name,
        asset_type=asset_type,
        current_balance=float(row["Current Balance"]),
        annual_contribution=float(row["Annual Contribution"]),
        growth_rate_pct=float(row["Growth Rate (%)"]),
        tax_behavior=tax_behavior,
        tax_rate_pct=normalized_tax_rate,
    )


def create_default_assets() -> List[Asset]:
    """Create default asset configuration."""
    return [
        Asset(
            name="401(k) / Traditional IRA",
            asset_type=AssetType.PRE_TAX,
            current_balance=50000,
            annual_contribution=12000,
            growth_rate_pct=7.0,
            tax_behavior=TaxBehavior.PRE_TAX,
        ),
        Asset(
            name="Roth IRA",
            asset_type=AssetType.POST_TAX,
            current_balance=10000,
            annual_contribution=6000,
            growth_rate_pct=7.0,
            tax_behavior=TaxBehavior.TAX_FREE,
        ),
        Asset(
            name="Brokerage Account",
            asset_type=AssetType.POST_TAX,
            current_balance=15000,
            annual_contribution=3000,
            growth_rate_pct=7.0,
            tax_behavior=TaxBehavior.CAPITAL_GAINS,
            tax_rate_pct=15.0  # Capital gains rate
        ),
        Asset(
            name="High-Yield Savings Account",
            asset_type=AssetType.POST_TAX,
            current_balance=25000,
            annual_contribution=2000,
            growth_rate_pct=4.5,
            tax_behavior=TaxBehavior.NO_ADDITIONAL_TAX,
            tax_rate_pct=0.0  # Interest taxed as ordinary income, but no capital gains
        )
    ]


def create_asset_template_csv() -> str:
    """Create a CSV template for asset configuration."""
    template_data = [
        {
            "Account Name": "401(k) / Traditional IRA",
            "Tax Treatment": "Tax-Deferred",
            "Current Balance": 50000,
            "Annual Contribution": 12000,
            "Growth Rate (%)": 7.0,
        },
        {
            "Account Name": "Roth IRA",
            "Tax Treatment": "Tax-Free",
            "Current Balance": 10000,
            "Annual Contribution": 6000,
            "Growth Rate (%)": 7.0,
        },
        {
            "Account Name": "Brokerage Account",
            "Tax Treatment": "Post-Tax",
            "Current Balance": 15000,
            "Annual Contribution": 3000,
            "Growth Rate (%)": 7.0,
        },
        {
            "Account Name": "High-Yield Savings Account",
            "Tax Treatment": "Post-Tax",
            "Current Balance": 25000,
            "Annual Contribution": 2000,
            "Growth Rate (%)": 4.5,
        }
    ]

    # Create CSV string
    output = io.StringIO()
    fieldnames = ["Account Name", "Tax Treatment", "Current Balance", "Annual Contribution", "Growth Rate (%)"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(template_data)

    return output.getvalue()


def parse_uploaded_csv(csv_content: str) -> tuple:
    """Parse uploaded CSV content into Asset objects. Returns (assets, warnings)."""
    assets = []
    warnings = []

    try:
        # Read CSV content
        csv_reader = csv.DictReader(io.StringIO(csv_content))

        # Determine which column name is used for tax treatment
        # Support both "Tax Treatment" (new) and "Asset Type" (legacy) for backward compatibility
        fieldnames = csv_reader.fieldnames or []
        has_tax_treatment = "Tax Treatment" in fieldnames
        has_asset_type = "Asset Type" in fieldnames

        if not has_tax_treatment and not has_asset_type:
            raise ValueError("CSV must contain either 'Tax Treatment' or 'Asset Type' column")

        tax_column = "Tax Treatment" if has_tax_treatment else "Asset Type"

        for row in csv_reader:
            # Validate required fields
            required_fields = ["Account Name", tax_column, "Current Balance", "Annual Contribution", "Growth Rate (%)"]
            for field in required_fields:
                if field not in row or not row[field].strip():
                    raise ValueError(f"Missing or empty required field: {field}")

            asset_type_str = row[tax_column].strip()
            
            # Parse numeric values (handle commas in numbers)
            try:
                def parse_number(value_str):
                    """Parse a number string, removing commas and handling empty values."""
                    if not value_str or str(value_str).strip() == '':
                        return 0.0
                    # Remove commas, dollar signs, and whitespace; strip % suffix
                    cleaned = str(value_str).replace(',', '').replace('$', '').strip()
                    is_percent = cleaned.endswith('%')
                    cleaned = cleaned.rstrip('%').strip()
                    return float(cleaned), is_percent

                def parse_rate(value_str, field_name):
                    """Parse a percentage field accepting 0.25, 25%, or 25 — always returns a value in 0-100 range."""
                    val, is_percent = parse_number(value_str)
                    # Decimal fraction (e.g. 0.25) → multiply to get percentage
                    if not is_percent and 0.0 < val < 1.0:
                        val *= 100
                    # Exactly 0 stays 0; integers >= 1 are already percentages (e.g. 25 → 25%)
                    # Edge case: bare "1" is ambiguous but almost certainly means 1%, not 100%
                    if not is_percent and val == 1.0:
                        warnings.append(
                            f'"{value_str}" entered for {field_name} — assumed **1%** (not 100%). '
                            f'Use "1%" to be explicit.'
                        )
                    return val

                def parse_plain(value_str):
                    val, _ = parse_number(value_str)
                    return val

                current_balance = parse_plain(row["Current Balance"])
                annual_contribution = parse_plain(row["Annual Contribution"])
                growth_rate = parse_rate(row["Growth Rate (%)"], "Growth Rate")
            except ValueError as e:
                raise ValueError(f"Invalid numeric value in row: {e}")

            # Validate ranges
            if current_balance < 0:
                raise ValueError("Current Balance cannot be negative")
            if annual_contribution < 0:
                raise ValueError("Annual Contribution cannot be negative")
            if growth_rate < 0 or growth_rate > 50:
                raise ValueError("Growth Rate must be between 0% and 50%")
            
            # Create asset
            asset = _asset_from_editor_row({
                "Account Name": row["Account Name"].strip(),
                "Tax Treatment": asset_type_str,
                "Current Balance": current_balance,
                "Annual Contribution": annual_contribution,
                "Growth Rate (%)": growth_rate,
                "Tax Rate on Gains (%)": 0.0,
            })
            
            assets.append(asset)
        
        if not assets:
            raise ValueError("No valid assets found in CSV")

        return assets, warnings
        
    except Exception as e:
        raise ValueError(f"Error parsing CSV: {str(e)}")


# ---------------------------------------------------------------------------
# Retirement simulation — sequencing + RMD model
# ---------------------------------------------------------------------------

# IRS Uniform Lifetime Table (2024) — distribution periods for RMD calculation.
# Source: IRS Publication 590-B.
_IRS_UNIFORM_LIFETIME_TABLE: Dict[int, float] = {
    73: 26.5, 74: 25.5, 75: 24.6, 76: 23.7, 77: 22.9, 78: 22.0, 79: 21.1,
    80: 20.2, 81: 19.4, 82: 18.5, 83: 17.7, 84: 16.8, 85: 16.0, 86: 15.2,
    87: 14.4, 88: 13.7, 89: 12.9, 90: 12.2, 91: 11.5, 92: 10.8, 93: 10.1,
    94: 9.5,  95: 8.9,  96: 8.4,  97: 7.8,  98: 7.3,  99: 6.8, 100: 6.4,
}


def _rmd_distribution_period(age: int) -> float:
    """Return IRS Uniform Lifetime Table distribution period for a given age.

    Returns float('inf') for ages below 73 (no RMD required).
    Uses a linear approximation beyond age 100.
    """
    if age < 73:
        return float('inf')
    if age in _IRS_UNIFORM_LIFETIME_TABLE:
        return _IRS_UNIFORM_LIFETIME_TABLE[age]
    # Linear extrapolation beyond age 100 (approx. -0.4 per year)
    return max(1.9, 6.4 - (age - 100) * 0.4)


def simulate_retirement(
    pretax_bal: float,
    roth_bal: float,
    brokerage_bal: float,
    brokerage_cost_basis: float,
    first_year_aftertax_target: float,
    retirement_age: int,
    life_expectancy: int,
    growth_rate: float,
    inflation_rate: float,
    retirement_tax_rate_pct: float,
    capital_gains_rate_pct: float = 15.0,
) -> list:
    """Year-by-year retirement simulation with withdrawal sequencing and RMDs.

    Withdrawal order each year (annuity due — withdrawals at START of year):
      1. RMD from pre-tax (forced at age >= 73; IRS Uniform Lifetime Table)
      2. Brokerage (capital gains tax on gains portion only)
      3. Roth IRA (tax-free)
      4. Additional pre-tax if still short (ordinary income tax)
      Portfolio grows on the remaining balance after withdrawals.

    Excess RMD beyond spending need is reinvested into brokerage after tax.

    Args:
        pretax_bal: Pre-tax (401k / Trad IRA / TAX_DEFERRED) balance at retirement
        roth_bal: Roth balance at retirement (tax-free)
        brokerage_bal: Taxable brokerage balance at retirement
        brokerage_cost_basis: Cost basis for brokerage account (contributions + original balance)
        first_year_aftertax_target: Desired after-tax income in year 1
        retirement_age: Age at retirement
        life_expectancy: Age at end of retirement
        growth_rate: Annual portfolio growth rate (decimal, e.g. 0.04)
        inflation_rate: Annual inflation rate (decimal, e.g. 0.03)
        retirement_tax_rate_pct: Ordinary income tax rate in retirement (percentage, e.g. 25.0)
        capital_gains_rate_pct: Long-term capital gains rate for brokerage (percentage, e.g. 15.0)

    Returns:
        List of dicts, one per year, with detailed withdrawal and balance data.
    """
    n = life_expectancy - retirement_age
    t_ord = retirement_tax_rate_pct / 100.0
    t_cg = capital_gains_rate_pct / 100.0
    year_data = []

    for year in range(1, n + 1):
        age = retirement_age + year - 1
        annual_target = first_year_aftertax_target * ((1.0 + inflation_rate) ** (year - 1))

        # --- 1. RMD from pre-tax (on start-of-year balance, before growth) ---
        rmd = 0.0
        rmd_tax = 0.0
        rmd_aftertax = 0.0
        if age >= 73 and pretax_bal > 0:
            dist_period = _rmd_distribution_period(age)
            rmd = min(pretax_bal, pretax_bal / dist_period)
            rmd_tax = rmd * t_ord
            rmd_aftertax = rmd - rmd_tax
            pretax_bal -= rmd

        # --- 2. Determine remaining after-tax needed ---
        brokerage_withdrawal = 0.0
        brokerage_tax = 0.0
        roth_withdrawal = 0.0
        extra_pretax_withdrawal = 0.0
        extra_pretax_tax = 0.0
        reinvested_excess = 0.0

        if rmd_aftertax >= annual_target:
            # RMD covers spending; reinvest excess after-tax into brokerage
            reinvested_excess = rmd_aftertax - annual_target
            brokerage_bal += reinvested_excess
            brokerage_cost_basis += reinvested_excess  # after-tax dollars = full cost basis
            actual_spend = annual_target
        else:
            actual_spend = rmd_aftertax
            remaining = annual_target - actual_spend

            # Draw from brokerage (capital gains on gains fraction only)
            if remaining > 0 and brokerage_bal > 0:
                gains_fraction = max(0.0, (brokerage_bal - brokerage_cost_basis) / brokerage_bal)
                effective_cg = gains_fraction * t_cg
                # Solve: withdrawal * (1 - effective_cg) = remaining
                needed_gross = remaining / (1.0 - effective_cg) if effective_cg < 1.0 else remaining
                brokerage_withdrawal = min(brokerage_bal, needed_gross)
                brokerage_tax = brokerage_withdrawal * effective_cg
                brokerage_aftertax = brokerage_withdrawal - brokerage_tax
                # Update cost basis proportionally
                basis_fraction = brokerage_withdrawal / brokerage_bal if brokerage_bal > 0 else 0
                brokerage_cost_basis = max(0.0, brokerage_cost_basis * (1.0 - basis_fraction))
                brokerage_bal -= brokerage_withdrawal
                actual_spend += brokerage_aftertax
                remaining -= brokerage_aftertax

            # Draw from Roth (tax-free)
            if remaining > 0 and roth_bal > 0:
                roth_withdrawal = min(roth_bal, remaining)
                roth_bal -= roth_withdrawal
                actual_spend += roth_withdrawal
                remaining -= roth_withdrawal

            # Draw additional from pre-tax if still short
            if remaining > 0 and pretax_bal > 0:
                needed_gross = remaining / (1.0 - t_ord) if t_ord < 1.0 else remaining
                extra_pretax_withdrawal = min(pretax_bal, needed_gross)
                extra_pretax_tax = extra_pretax_withdrawal * t_ord
                pretax_bal -= extra_pretax_withdrawal
                actual_spend += (extra_pretax_withdrawal - extra_pretax_tax)

        # --- 3. Grow remaining balances (after withdrawals — annuity due) ---
        pretax_bal    *= (1.0 + growth_rate)
        roth_bal      *= (1.0 + growth_rate)
        brokerage_bal *= (1.0 + growth_rate)
        # Cost basis does not grow (only the market value does)

        # --- 4. Clamp balances ---
        pretax_bal    = max(0.0, pretax_bal)
        roth_bal      = max(0.0, roth_bal)
        brokerage_bal = max(0.0, brokerage_bal)

        total_tax = rmd_tax + brokerage_tax + extra_pretax_tax
        total_portfolio_end = pretax_bal + roth_bal + brokerage_bal

        year_data.append({
            "year": year,
            "age": age,
            "rmd": rmd,
            "brokerage_withdrawal": brokerage_withdrawal,
            "roth_withdrawal": roth_withdrawal,
            "extra_pretax_withdrawal": extra_pretax_withdrawal,
            "reinvested_excess": reinvested_excess,
            "total_tax": total_tax,
            "actual_aftertax": actual_spend,
            "pretax_bal_end": pretax_bal,
            "roth_bal_end": roth_bal,
            "brokerage_bal_end": brokerage_bal,
            "total_portfolio_end": total_portfolio_end,
        })

    return year_data


def find_sustainable_withdrawal(
    pretax_bal: float,
    roth_bal: float,
    brokerage_bal: float,
    brokerage_cost_basis: float,
    retirement_age: int,
    life_expectancy: int,
    growth_rate: float,
    inflation_rate: float,
    retirement_tax_rate_pct: float,
    capital_gains_rate_pct: float = 15.0,
    legacy_goal: float = 0.0,
) -> tuple:
    """Binary search for the maximum first-year after-tax withdrawal that leaves
    `legacy_goal` in the portfolio at life_expectancy (default ≈ $0).

    Returns:
        (sustainable_withdrawal, year_data) where year_data is the full simulation
        for the found withdrawal amount.
    """
    total = pretax_bal + roth_bal + brokerage_bal
    if total <= 0:
        return 0.0, []

    low = 0.0
    high = total  # theoretical upper bound

    for _ in range(50):  # 50 iterations → sub-cent precision
        mid = (low + high) / 2.0
        data = simulate_retirement(
            pretax_bal, roth_bal, brokerage_bal, brokerage_cost_basis,
            mid, retirement_age, life_expectancy,
            growth_rate, inflation_rate,
            retirement_tax_rate_pct, capital_gains_rate_pct,
        )
        final_balance = data[-1]["total_portfolio_end"] if data else 0.0
        if final_balance > legacy_goal + 1.0:
            # Portfolio has money left above target — can afford a higher withdrawal
            low = mid
        else:
            # Portfolio fell below legacy target — withdrawal too high
            high = mid

    # Run one final simulation with the converged value to get clean year_data
    final_data = simulate_retirement(
        pretax_bal, roth_bal, brokerage_bal, brokerage_cost_basis,
        low, retirement_age, life_expectancy,
        growth_rate, inflation_rate,
        retirement_tax_rate_pct, capital_gains_rate_pct,
    )
    return low, final_data


def find_required_portfolio(
    target_after_tax_income: float,
    retirement_age: int,
    life_expectancy: int,
    retirement_tax_rate_pct: float,
    growth_rate: float = 0.04,
    inflation_rate: float = 0.03,
    legacy_goal: float = 0.0,
    life_expenses: float = 0.0,
) -> dict:
    """Binary search for the minimum pre-tax portfolio that sustains `target_after_tax_income`/year.
    Assumes all assets are pre-tax (uniform treatment). Reuses find_sustainable_withdrawal so the
    reverse calculation stays consistent with the forward simulator.
    life_expenses is a lump sum deducted from the portfolio at retirement before simulation.
    """
    years = max(0, life_expectancy - retirement_age)
    if target_after_tax_income <= 0:
        # No income needed — but must still fund legacy_goal if set.
        # With 0 withdrawals the portfolio grows at growth_rate; solve for the
        # present-value of legacy_goal then add one-time expenses on top.
        if legacy_goal > 0 and years > 0:
            min_for_legacy = legacy_goal / ((1.0 + growth_rate) ** years)
        else:
            min_for_legacy = legacy_goal  # years==0: need full amount today
        required = min_for_legacy + life_expenses
        return {
            "required_pretax_portfolio": required,
            "confirmed_income": 0.0,
            "years_in_retirement": years,
            "growth_rate": growth_rate,
            "inflation_rate": inflation_rate,
            "tax_rate": retirement_tax_rate_pct,
            "legacy_goal": legacy_goal,
            "life_expenses": life_expenses,
        }

    low = 0.0
    # Upper bound: generous enough for high income goals + legacy targets + one-time expenses
    high = (target_after_tax_income + legacy_goal) * 200.0 + life_expenses

    for _ in range(60):
        mid = (low + high) / 2.0
        # Deduct life_expenses before simulating sustainable income
        effective_bal = max(0.0, mid - life_expenses)
        income, _ = find_sustainable_withdrawal(
            pretax_bal=effective_bal, roth_bal=0.0, brokerage_bal=0.0,
            brokerage_cost_basis=0.0,
            retirement_age=retirement_age,
            life_expectancy=life_expectancy,
            growth_rate=growth_rate,
            inflation_rate=inflation_rate,
            retirement_tax_rate_pct=retirement_tax_rate_pct,
            legacy_goal=legacy_goal,
        )
        if income < target_after_tax_income:
            low = mid
        else:
            high = mid

    required = high
    effective_bal = max(0.0, required - life_expenses)
    confirmed_income, _ = find_sustainable_withdrawal(
        pretax_bal=effective_bal, roth_bal=0.0, brokerage_bal=0.0,
        brokerage_cost_basis=0.0,
        retirement_age=retirement_age,
        life_expectancy=life_expectancy,
        growth_rate=growth_rate,
        inflation_rate=inflation_rate,
        retirement_tax_rate_pct=retirement_tax_rate_pct,
        legacy_goal=legacy_goal,
    )
    return {
        "required_pretax_portfolio": required,
        "confirmed_income": confirmed_income,
        "years_in_retirement": years,
        "growth_rate": growth_rate,
        "inflation_rate": inflation_rate,
        "tax_rate": retirement_tax_rate_pct,
        "legacy_goal": legacy_goal,
        "life_expenses": life_expenses,
    }


def generate_pdf_report(result: Dict[str, float], assets: List[Asset], user_inputs: Dict) -> bytes:
    """Generate a comprehensive PDF report of the retirement analysis."""
    if not _REPORTLAB_AVAILABLE:
        raise ImportError("reportlab is required for PDF generation. Install with: pip install reportlab")
    
    # Create PDF in memory
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        textColor=colors.darkblue
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=14,
        spaceAfter=8,
        textColor=colors.darkgreen
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        wordWrap='CJK',
    )
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        alignment=TA_LEFT,
        wordWrap='CJK',
    )
    table_cell_right_style = ParagraphStyle(
        'TableCellRight',
        parent=table_cell_style,
        alignment=TA_RIGHT,
    )
    
    # Build PDF content
    story = []
    
    # Title
    client_name = user_inputs.get('client_name', 'Client')
    story.append(Paragraph(f"Retirement Planning Analysis Report", title_style))
    story.append(Paragraph(f"Prepared for: {client_name}", 
                          ParagraphStyle('ClientName', parent=styles['Heading2'], fontSize=16, alignment=TA_CENTER, textColor=colors.darkgreen)))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Legal Disclaimer
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.red,
        alignment=TA_LEFT,
        spaceAfter=12,
        borderWidth=1,
        borderColor=colors.red,
        borderPadding=6
    )
    
    story.append(Paragraph("IMPORTANT LEGAL DISCLAIMER", 
                          ParagraphStyle('DisclaimerTitle', parent=styles['Heading3'], fontSize=12, textColor=colors.red, alignment=TA_CENTER)))
    story.append(Paragraph(
        "This report provides educational and informational content only. It is NOT financial, tax, legal, or investment advice. "
        "Results are based on general assumptions and may not be suitable for your specific situation. "
        "Past performance does not guarantee future results; all projections are estimates. "
        "Always consult with qualified financial advisors, tax professionals, and legal counsel before making financial decisions. "
        "You are solely responsible for your financial decisions and their consequences. "
        "The creators and operators of this application disclaim all liability for any losses, damages, or consequences arising from the use of this information. "
        "By using this report, you acknowledge and agree to these terms.",
        disclaimer_style
    ))
    story.append(Spacer(1, 20))
    
    # Executive Summary
    story.append(Paragraph("Executive Summary", heading_style))
    
    summary_data = [
        ["Metric", "Value"],
        ["Years Until Retirement", f"{result.get('Years Until Retirement', 0):.0f} years"],
        ["Total Future Value (Pre-Tax)", f"${result.get('Total Future Value (Pre-Tax)', 0):,.0f}"],
        ["Total After-Tax Balance", f"${result.get('Total After-Tax Balance', 0):,.0f}"],
        ["Total Tax Liability", f"${result.get('Total Tax Liability', 0):,.0f}"],
        ["Tax Efficiency", f"{result.get('Tax Efficiency (%)', 0):.1f}%"]
    ]
    
    summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(summary_table)
    story.append(Spacer(1, 20))

    # Asset Breakdown
    story.append(Paragraph("Asset Breakdown", heading_style))

    # Asset details table with proper formatting
    asset_data = [[
        Paragraph("Account", table_header_style),
        Paragraph("Tax Treatment", table_header_style),
        Paragraph("Current Balance", table_header_style),
        Paragraph("Annual Contribution", table_header_style),
        Paragraph("Growth Rate", table_header_style),
    ]]
    for asset in assets:
        asset_data.append([
            Paragraph(asset.name, table_cell_style),
            Paragraph(asset.asset_type.value.replace('_', ' ').title(), table_cell_style),
            Paragraph(f"${asset.current_balance:,.0f}", table_cell_right_style),
            Paragraph(f"${asset.annual_contribution:,.0f}", table_cell_right_style),
            Paragraph(f"{asset.growth_rate_pct}%", table_cell_right_style),
        ])

    # Wider account/tax columns and wrapped paragraphs prevent clipped text.
    asset_table = Table(asset_data, colWidths=[2.2*inch, 1.15*inch, 0.95*inch, 1.05*inch, 0.65*inch], repeatRows=1)
    asset_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9)
    ]))
    
    story.append(asset_table)
    story.append(Spacer(1, 12))

    story.append(Spacer(1, 20))

    # Individual Asset Results
    story.append(Paragraph("Individual Asset Projections", heading_style))
    
    # Find individual asset results
    asset_results = []
    for key, value in result.items():
        if "Asset" in key and "After-Tax" in key:
            asset_name = key.split(" - ")[1].replace(" (After-Tax)", "")
            asset_results.append([asset_name, f"${value:,.0f}"])
    
    if asset_results:
        asset_results_data = [["Account", "After-Tax Value at Retirement"]]
        asset_results_data.extend(asset_results)
        
        results_table = Table(asset_results_data, colWidths=[3*inch, 2*inch])
        results_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(results_table)
        story.append(Spacer(1, 20))
    
    # Retirement Income Analysis
    story.append(Paragraph("Retirement Income Analysis", heading_style))

    life_expectancy = user_inputs.get('life_expectancy', 85)
    retirement_age = user_inputs.get('retirement_age', 65)
    years_in_retirement = life_expectancy - retirement_age

    # Validate years in retirement
    if years_in_retirement <= 0:
        raise ValueError(f"Life expectancy ({life_expectancy}) must be greater than retirement age ({retirement_age})")

    # Use the same sequencing + RMD simulation as the What-If section.
    retirement_growth_rate = user_inputs.get('retirement_growth_rate', 4.0)
    inflation_rate = user_inputs.get('inflation_rate', 3)

    pdf_pretax_fv = sum(
        ar['pre_tax_value']
        for ar, ai in zip(result.get('asset_results', []), result.get('assets_input', []))
        if ai.asset_type in (AssetType.PRE_TAX, AssetType.TAX_DEFERRED)
    )
    pdf_roth_fv = sum(
        ar['pre_tax_value']
        for ar, ai in zip(result.get('asset_results', []), result.get('assets_input', []))
        if ai.asset_type == AssetType.POST_TAX and 'roth' in ai.name.lower()
    )
    pdf_brok_fv = sum(
        ar['pre_tax_value']
        for ar, ai in zip(result.get('asset_results', []), result.get('assets_input', []))
        if ai.asset_type == AssetType.POST_TAX and 'roth' not in ai.name.lower()
    )
    pdf_brok_basis = sum(
        ar['total_contributions'] + ai.current_balance
        for ar, ai in zip(result.get('asset_results', []), result.get('assets_input', []))
        if ai.asset_type == AssetType.POST_TAX and 'roth' not in ai.name.lower()
    )

    annual_retirement_income, cashflow_data = find_sustainable_withdrawal(
        pdf_pretax_fv, pdf_roth_fv, pdf_brok_fv, pdf_brok_basis,
        int(retirement_age), int(life_expectancy),
        retirement_growth_rate / 100.0, inflation_rate / 100.0,
        float(user_inputs.get('retirement_marginal_tax_rate_pct', 25.0)),
    )

    retirement_income_goal = user_inputs.get('retirement_income_goal', 0)
    income_shortfall = retirement_income_goal - annual_retirement_income
    income_ratio = (annual_retirement_income / retirement_income_goal * 100) if retirement_income_goal > 0 else 0
    
    income_data = [
        ["Metric", "Value"],
        ["Projected Annual Retirement Income", f"${annual_retirement_income:,.0f}"],
        ["Desired Annual Retirement Income", f"${retirement_income_goal:,.0f}"],
        ["Annual Shortfall/Surplus", f"${income_shortfall:,.0f}"],
        ["Income Goal Achievement", f"{income_ratio:.1f}%"]
    ]
    
    income_table = Table(income_data, colWidths=[3*inch, 2*inch])
    income_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(income_table)
    story.append(Spacer(1, 20))

    # Model limitation note for retirement income projection
    income_note_style = ParagraphStyle(
        'IncomeNote',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.orangered,
        borderWidth=1,
        borderColor=colors.orangered,
        borderPadding=6,
        spaceAfter=20
    )
    story.append(Paragraph(
        "<b>Important Modeling Note:</b> Retirement income is estimated from a one-time after-tax portfolio adjustment at retirement. "
        "This model does not yet simulate year-by-year withdrawal taxation, tax bracket changes, or dynamic withdrawal sequencing.",
        income_note_style
    ))
    story.append(Spacer(1, 12))
    
    # Tax Analysis
    story.append(Paragraph("Tax Analysis", heading_style))
    
    tax_liability = result.get("Total Tax Liability", 0)
    total_pre_tax = result.get("Total Future Value (Pre-Tax)", 1)
    tax_percentage = (tax_liability / total_pre_tax * 100) if total_pre_tax > 0 else 0
    tax_efficiency = result.get("Tax Efficiency (%)", 0)
    
    tax_analysis = f"""
    <b>Tax Efficiency Rating:</b> {tax_efficiency:.1f}%<br/>
    <b>Total Tax Liability:</b> ${tax_liability:,.0f}<br/>
    <b>Tax as % of Pre-Tax Value:</b> {tax_percentage:.1f}%<br/>
    <b>Current Marginal Tax Rate:</b> {user_inputs.get('current_marginal_tax_rate_pct', 0)}%<br/>
    <b>Projected Retirement Tax Rate:</b> {user_inputs.get('retirement_marginal_tax_rate_pct', 0)}%
    """
    
    story.append(Paragraph(tax_analysis, styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Recommendations
    story.append(Paragraph("Recommendations", heading_style))
    
    recommendations = []
    tax_percentage = (result.get("Total Tax Liability", 0) / result.get("Total Future Value (Pre-Tax)", 1) * 100) if result.get("Total Future Value (Pre-Tax)", 0) > 0 else 0
    if tax_efficiency > 85:
        recommendations.append("🎉 <b>Excellent tax efficiency!</b> Your portfolio is well-optimized with minimal tax liability.")
    elif tax_efficiency > 75:
        recommendations.append(f"⚠️ <b>Good tax efficiency</b> ({tax_percentage:.1f}% tax burden), but there may be room for improvement. <i>Goal: Lower this percentage by shifting assets to tax-advantaged accounts.</i>")
        recommendations.append("💡 <b>Tax Optimization Tips:</b>")
        recommendations.append("• Optimize asset location (taxable vs tax-advantaged accounts)")
        recommendations.append("• Consider Roth vs Traditional contributions based on tax rates")
        recommendations.append("• Maximize employer 401(k) match and HSA contributions")
        recommendations.append("• Use tax-loss harvesting and strategic withdrawal order")
    else:
        recommendations.append("🚨 <b>Consider tax optimization</b> strategies to improve efficiency.")
        recommendations.append("⚠️ <b>Priority Actions:</b>")
        recommendations.append("• Review asset allocation across account types")
        recommendations.append("• Maximize tax-advantaged contributions (401k, IRA, HSA)")
        recommendations.append("• Consider Roth conversions during low-income years")
        recommendations.append("• Switch to tax-efficient index funds")
    
    if len(assets) < 3:
        recommendations.append("💡 Consider diversifying across more account types for better tax optimization.")
    
    # Check for high-growth assets
    high_growth_assets = [a for a in assets if a.growth_rate_pct > 8]
    if high_growth_assets:
        recommendations.append("📈 You have high-growth assets - ensure proper risk management.")
    
    # Check for low-growth assets
    low_growth_assets = [a for a in assets if a.growth_rate_pct < 5]
    if low_growth_assets:
        recommendations.append("💰 Consider if low-growth assets align with your retirement timeline.")
    
    for rec in recommendations:
        story.append(Paragraph(rec, styles['Normal']))
        story.append(Spacer(1, 6))
    
    story.append(Spacer(1, 20))

    # Cash Flow Table (year-by-year) at bottom of report.
    story.append(PageBreak())
    story.append(Paragraph("Cash Flow Projection (Year-by-Year)", heading_style))

    cashflow_header = [
        Paragraph("Year", table_header_style),
        Paragraph("Age", table_header_style),
        Paragraph("RMD", table_header_style),
        Paragraph("Brokerage W/D", table_header_style),
        Paragraph("Roth W/D", table_header_style),
        Paragraph("Extra Pre-Tax", table_header_style),
        Paragraph("Tax Paid", table_header_style),
        Paragraph("After-Tax Income", table_header_style),
        Paragraph("Total Portfolio", table_header_style),
    ]
    cashflow_rows = [cashflow_header]

    for row in cashflow_data:
        cashflow_rows.append([
            Paragraph(str(int(row["year"])), table_cell_right_style),
            Paragraph(str(int(row["age"])), table_cell_right_style),
            Paragraph(f"${row['rmd']:,.0f}" if row["rmd"] > 0 else "-", table_cell_right_style),
            Paragraph(f"${row['brokerage_withdrawal']:,.0f}" if row["brokerage_withdrawal"] > 0 else "-", table_cell_right_style),
            Paragraph(f"${row['roth_withdrawal']:,.0f}" if row["roth_withdrawal"] > 0 else "-", table_cell_right_style),
            Paragraph(f"${row['extra_pretax_withdrawal']:,.0f}" if row["extra_pretax_withdrawal"] > 0 else "-", table_cell_right_style),
            Paragraph(f"${row['total_tax']:,.0f}", table_cell_right_style),
            Paragraph(f"${row['actual_aftertax']:,.0f}", table_cell_right_style),
            Paragraph(f"${row['total_portfolio_end']:,.0f}", table_cell_right_style),
        ])

    cashflow_table = Table(
        cashflow_rows,
        colWidths=[0.35*inch, 0.35*inch, 0.55*inch, 0.7*inch, 0.55*inch, 0.7*inch, 0.55*inch, 0.85*inch, 0.85*inch],
        repeatRows=1,
    )
    cashflow_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(cashflow_table)
    story.append(Spacer(1, 12))

    # Footer Disclaimer
    story.append(Paragraph("DISCLAIMER: This report is for educational purposes only and does not constitute professional financial advice. Consult qualified professionals before making financial decisions.",
                          ParagraphStyle('FooterDisclaimer', parent=styles['Normal'], fontSize=7, alignment=TA_CENTER, textColor=colors.red)))
    story.append(Spacer(1, 12))

    # Contact Information
    contact_style = ParagraphStyle('ContactInfo', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER, textColor=colors.darkblue)
    story.append(Paragraph(f"<b>Smart Retire AI v{VERSION}</b>", contact_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Questions or feedback? Contact us at <b>smartretireai@gmail.com</b>", contact_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"Report generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
                          ParagraphStyle('ReportDate', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, textColor=colors.grey)))

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ==========================================
# DIALOG FUNCTIONS FOR NEXT STEPS
# ==========================================

@st.dialog("📄 Generate PDF Report")
def generate_report_dialog():
    """Dialog for generating and downloading PDF report."""
    st.markdown("""
    Create a comprehensive PDF report with:
    - Executive summary of your retirement plan
    - Detailed portfolio breakdown
    - Individual asset projections
    - Tax analysis and optimization strategies
    - Personalized recommendations
    """)

    st.markdown("---")

    # Name input
    report_name = st.text_input(
        "Your Name (Optional)",
        value=st.session_state.get('client_name', ''),
        placeholder="Enter your name for the report",
        help="This will appear on the PDF report"
    )

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("❌ Cancel", use_container_width=True):
            st.rerun()

    with col2:
        if st.button("📥 Generate PDF", type="primary", use_container_width=True):
            if not _REPORTLAB_AVAILABLE:
                st.error("⚠️ **PDF generation not available.** Install reportlab to enable PDF downloads:")
                st.code("pip install reportlab", language="bash")
                return

            try:
                # Get the result and assets from session state
                if 'last_result' not in st.session_state or 'assets' not in st.session_state:
                    st.error("❌ No analysis results found. Please run the analysis first.")
                    return

                result = st.session_state.last_result
                assets = st.session_state.assets

                # Prepare user inputs for PDF
                user_inputs = {
                    'client_name': report_name if report_name else 'Client',
                    'current_marginal_tax_rate_pct': st.session_state.get('whatif_current_tax_rate', 22),
                    'retirement_marginal_tax_rate_pct': st.session_state.get('whatif_retirement_tax_rate', 25),
                    'inflation_rate_pct': st.session_state.get('whatif_inflation_rate', 3),
                    'age': datetime.now().year - st.session_state.birth_year,
                    'retirement_age': int(st.session_state.get('whatif_retirement_age', 65)),
                    'life_expectancy': int(st.session_state.get('whatif_life_expectancy', 85)),
                    'birth_year': st.session_state.birth_year,
                    'retirement_income_goal': st.session_state.get('whatif_retirement_income_goal', 0),
                    'retirement_growth_rate': st.session_state.get('whatif_retirement_growth_rate', 4.0),
                    'inflation_rate': st.session_state.get('whatif_inflation_rate', 3)
                }

                # Generate PDF
                with st.spinner("Generating PDF report..."):
                    pdf_bytes = generate_pdf_report(result, assets, user_inputs)

                # Create filename
                client_name_clean = report_name.replace(" ", "_").replace(",", "").replace(".", "") if report_name else "Client"
                filename = f"retirement_analysis_{client_name_clean}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

                # Track successful PDF generation
                track_pdf_generation(success=True)

                # Show download button
                st.success("✅ PDF report generated successfully!")
                st.download_button(
                    label="📥 Download PDF Report",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    use_container_width=True
                )

            except Exception as e:
                # Track failed PDF generation
                track_pdf_generation(success=False)
                track_error('pdf_generation_error', str(e), {'report_name': report_name})

                st.error(f"❌ Error generating PDF: {str(e)}")
                st.info("💡 Try refreshing the page and running the analysis again.")


@st.dialog("🎲 Run Scenario Analysis")
def monte_carlo_dialog():
    """Dialog for configuring and running Monte Carlo simulation."""
    st.markdown("""
    Explore thousands of possible retirement scenarios to understand:
    - Range of potential retirement income
    - Best-case and worst-case outcomes
    - Probability of meeting your goals
    - Impact of market volatility
    """)

    st.markdown("---")

    # Configuration options
    col1, col2 = st.columns(2)

    with col1:
        num_simulations = st.select_slider(
            "Number of Scenarios",
            options=[100, 500, 1000, 5000, 10000],
            value=1000,
            help="More scenarios = more accurate results but slower processing"
        )

    with col2:
        volatility = st.slider(
            "Market Volatility (%)",
            min_value=5.0,
            max_value=30.0,
            value=15.0,
            step=1.0,
            help="Historical stock market volatility is ~15-20%. Higher = more uncertainty."
        )

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("❌ Cancel", use_container_width=True):
            st.rerun()

    with col2:
        if st.button("🚀 Run Analysis", type="primary", use_container_width=True):
            # Store configuration in session state and navigate to Monte Carlo page
            st.session_state.monte_carlo_config = {
                'num_simulations': num_simulations,
                'volatility': volatility
            }
            st.session_state.current_page = 'monte_carlo'
            st.rerun()


@st.dialog("📊 Cash Flow Projection", width="large")
def cashflow_dialog():
    """Dialog showing the year-by-year retirement cash flow table."""
    sim_data = st.session_state.get("cashflow_sim_data")

    if not sim_data:
        st.info("Run a retirement analysis first to see the cash flow projection.")
        return

    import pandas as pd

    _col_cfg = {
        "Year":          st.column_config.NumberColumn("Year",          format="%d"),
        "Age":           st.column_config.NumberColumn("Age",           format="%d"),
        "RMD":           st.column_config.TextColumn("RMD"),
        "Brokerage W/D": st.column_config.TextColumn("Brokerage W/D"),
        "Roth W/D":      st.column_config.TextColumn("Roth W/D"),
        "Extra Pre-Tax": st.column_config.TextColumn("Extra Pre-Tax"),
        "Tax Paid":      st.column_config.TextColumn("Tax Paid"),
        "After-Tax Income (adjusted for inflation)": st.column_config.TextColumn(
            "After-Tax Income (adjusted for inflation)",
            help="Each year the model grows all account pots, pays any forced RMD, then draws from brokerage → pre-tax → Roth until the target income is met. The target is the maximum first-year withdrawal that fully depletes the portfolio by your life expectancy.",
        ),
        "Total Portfolio": st.column_config.TextColumn("Total Portfolio"),
    }

    withdrawal_data = []
    for row in sim_data:
        withdrawal_data.append({
            "Year":          row["year"],
            "Age":           row["age"],
            "RMD":           f"${row['rmd']:,.0f}"                     if row["rmd"] > 0                     else None,
            "Brokerage W/D": f"${row['brokerage_withdrawal']:,.0f}"    if row["brokerage_withdrawal"] > 0    else None,
            "Roth W/D":      f"${row['roth_withdrawal']:,.0f}"         if row["roth_withdrawal"] > 0         else None,
            "Extra Pre-Tax": f"${row['extra_pretax_withdrawal']:,.0f}" if row["extra_pretax_withdrawal"] > 0 else None,
            "Tax Paid":      f"${row['total_tax']:,.0f}",
            "After-Tax Income (adjusted for inflation)": f"${row['actual_aftertax']:,.0f}",
            "Total Portfolio": f"${row['total_portfolio_end']:,.0f}",
        })

    df_withdrawals = pd.DataFrame(withdrawal_data)
    st.dataframe(df_withdrawals, use_container_width=True, hide_index=True, column_config=_col_cfg)

    if st.button("Close", use_container_width=True):
        st.rerun()


@st.dialog("💡 Reminder: Adjust Annual Contributions")
def contribution_reminder_dialog():
    """Dialog to remind users to adjust contributions before finishing onboarding."""
    st.markdown("""
    ### 📊 For More Accurate Projections

    We noticed you haven't set any annual contributions yet. Adding your expected annual
    contributions will significantly improve the accuracy of your retirement projections.

    **Why contributions matter:**
    - 🎯 More realistic projections of your future retirement balance
    - 📈 Better understanding of your retirement income potential
    - 💰 More accurate income gap recommendations

    **You can adjust contributions in the asset table above:**
    - Click the "Annual Contribution" cells to edit them
    - Set to $0 if you're no longer contributing to an account
    - Use your actual planned contribution amounts for the most accurate results
    """)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("← Go Back and Adjust", use_container_width=True, type="primary"):
            # Clear the flag and close dialog
            if 'show_contribution_reminder' in st.session_state:
                del st.session_state.show_contribution_reminder
            st.rerun()

    with col2:
        if st.button("Continue Anyway →", use_container_width=True):
            # User chose to proceed without adjusting contributions
            st.session_state.contribution_reminder_dismissed = True
            if 'show_contribution_reminder' in st.session_state:
                del st.session_state.show_contribution_reminder
            # Advance to results page
            st.session_state.current_page = 'results'
            st.session_state.results_source = 'onboarding'
            st.rerun()



def show_mode_selection_page():
    """Full-page mode selection: Simple (chat) vs Detailed (form). Shown after splash."""
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        "<h2 style='text-align:center;'>How would you like to plan your retirement?</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center; color:#666;'>Choose the experience that works best for you.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    col_simple, col_detailed = st.columns(2, gap="large")

    with col_simple:
        st.markdown(
            """
            <div style='border:2px solid #1f77b4; border-radius:12px; padding:28px 24px; min-height:220px;'>
                <div style='font-size:2.2em; text-align:center;'>💬</div>
                <h3 style='text-align:center; color:#1f77b4;'>Simple Planning</h3>
                <p style='text-align:center; color:#444;'>
                    Tell me your <strong>income goal</strong> and I'll calculate
                    how much you need to retire. Guided chat — no forms.
                </p>
                <p style='text-align:center; font-size:0.85em; color:#888;'>
                    Best for: quick estimates &amp; what-if exploration
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Start Chat →", type="primary", use_container_width=True, key="mode_select_simple"):
            st.session_state.planning_mode_choice = "I have an income goal — show how much I need"
            st.session_state.current_page = "chat_mode"
            st.session_state.chat_messages = []
            st.session_state.chat_fields = {}
            st.session_state.chat_complete = False
            st.rerun()

    with col_detailed:
        st.markdown(
            """
            <div style='border:2px solid #2ca02c; border-radius:12px; padding:28px 24px; min-height:220px;'>
                <div style='font-size:2.2em; text-align:center;'>📊</div>
                <h3 style='text-align:center; color:#2ca02c;'>Detailed Planning</h3>
                <p style='text-align:center; color:#444;'>
                    Enter your <strong>actual retirement accounts</strong> and see
                    detailed projections, tax analysis, and withdrawal strategy.
                </p>
                <p style='text-align:center; font-size:0.85em; color:#888;'>
                    Best for: precise planning with known asset balances
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Enter Details →", use_container_width=True, key="mode_select_detailed"):
            st.session_state.planning_mode_choice = "I know my assets — show my income"
            st.session_state.current_page = "onboarding"
            st.session_state.onboarding_step = 1
            st.rerun()


def show_chat_mode_page():
    """Chat + live results split-pane for Mode 2 (Income Goal → Portfolio)."""
    _CHAT_DEFAULTS_US = {"retirement_age": 65, "life_expectancy": 90, "tax_rate": 22, "growth_rate": 4.0, "inflation_rate": 3.0}
    _CHAT_DEFAULTS_IN = {"retirement_age": 60, "life_expectancy": 85, "tax_rate": 10, "growth_rate": 10.0, "inflation_rate": 7.0}

    # Initialize chat session state on first visit
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "chat_fields" not in st.session_state:
        st.session_state.chat_fields = {}
    if "chat_complete" not in st.session_state:
        st.session_state.chat_complete = False

    fields = st.session_state.chat_fields
    country = fields.get("country", "US")
    is_india = country == "India"
    _sym = "₹" if is_india else "$"
    _corpus_label = "Corpus" if is_india else "Portfolio"
    _defaults = _CHAT_DEFAULTS_IN if is_india else _CHAT_DEFAULTS_US

    # Header
    st.markdown("### 💬 Simple Retirement Planner")
    if st.button("← Change planning mode", key="chat_back_to_mode_select"):
        st.session_state.current_page = "mode_selection"
        st.rerun()

    st.markdown("---")

    chat_col, results_col = st.columns([1, 1], gap="large")

    # ── LEFT: Chat ──────────────────────────────────────────────────────────
    with chat_col:
        st.markdown("#### Chat")

        # Fixed-height scrollable message history — keeps input always visible below
        _msgs_box = st.container(height=460)
        with _msgs_box:
            # Initial greeting if conversation is empty — append first, then let the loop render
            if not st.session_state.chat_messages and _CHAT_AVAILABLE:
                opening = (
                    "Hi! Three quick questions to get started:\n\n"
                    "1. **Country** — are you planning for 🇺🇸 US or 🇮🇳 India?\n"
                    "2. **Birth year** — so I can calculate your age.\n"
                    "3. **Target income** — how much annual after-tax income would you like in retirement?"
                )
                st.session_state.chat_messages.append({"role": "assistant", "content": opening})

            # Render conversation history (single render path for all messages)
            for msg in st.session_state.chat_messages:
                avatar = "🧑‍💼" if msg["role"] == "assistant" else "🧑"
                with st.chat_message(msg["role"], avatar=avatar):
                    st.markdown(msg["content"])

        if not _CHAT_AVAILABLE:
            st.warning("Chat requires the `openai` package and an `OPENAI_API_KEY`. Run `pip install openai` and set the key in your `.env` file.")
        elif not os.getenv("OPENAI_API_KEY"):
            st.warning("Set `OPENAI_API_KEY` in your `.env` file to enable the chat advisor.")
        else:
            # Chat input sits below the fixed-height box, always visible
            user_input = st.chat_input("Type your answer or ask a what-if question…")
            if user_input:
                st.session_state.chat_messages.append({"role": "user", "content": user_input})

                # Detect country from current message so system prompt uses the right currency
                # before chat_fields has been populated (first-message timing issue)
                _msg_lower = user_input.lower()
                if "india" in _msg_lower:
                    _call_country = "India"
                elif any(w in _msg_lower for w in ("us", "usa", "united states", "america")):
                    _call_country = "US"
                else:
                    _call_country = country  # already confirmed in a prior turn

                with st.spinner(""):
                    try:
                        display_msg, new_fields = chat_with_advisor(
                            st.session_state.chat_messages,
                            country=_call_country,
                        )
                    except Exception as e:
                        display_msg = f"Sorry, I ran into an error: {e}"
                        new_fields = {}

                # Merge confirmed fields
                for k, v in new_fields.items():
                    if k != "done" and v is not None:
                        st.session_state.chat_fields[k] = v

                if new_fields.get("done"):
                    st.session_state.chat_complete = True

                st.session_state.chat_messages.append({"role": "assistant", "content": display_msg})
                st.rerun()

        # Download transcript button — visible once there are messages
        if st.session_state.chat_messages:
            def _build_chat_transcript(messages, fields, _is_india):
                sym = "₹" if _is_india else "$"
                lines = [
                    "# Smart Retire AI — Chat Transcript",
                    f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    "",
                    "---",
                    "",
                ]
                for msg in messages:
                    speaker = "**You:**" if msg["role"] == "user" else "**Advisor:**"
                    lines.append(f"{speaker} {msg['content']}")
                    lines.append("")
                if fields:
                    lines += ["---", "", "## Your Retirement Plan Summary", ""]
                    label_map = {
                        "country": "Country",
                        "birth_year": "Birth Year",
                        "retirement_age": "Retirement Age",
                        "life_expectancy": "Life Expectancy (age)",
                        "target_income": f"Target Income ({sym}/yr)",
                        "tax_rate": "Tax Rate (%)",
                        "growth_rate": "Growth Rate (%)",
                        "inflation_rate": "Inflation Rate (%)",
                        "legacy_goal": f"Legacy Goal ({sym})",
                        "life_expenses": f"One-Time Expenses ({sym})",
                    }
                    for key, label in label_map.items():
                        val = fields.get(key)
                        if val is not None:
                            lines.append(f"- **{label}:** {val}")
                return "\n".join(lines)

            _transcript = _build_chat_transcript(
                st.session_state.chat_messages,
                st.session_state.chat_fields,
                is_india,
            )
            _fname = f"retirement_chat_{datetime.now().strftime('%Y%m%d')}.md"
            st.download_button(
                "⬇ Download transcript",
                data=_transcript,
                file_name=_fname,
                mime="text/markdown",
                use_container_width=True,
                key="chat_download_btn",
            )

    # ── RIGHT: Live Results ──────────────────────────────────────────────────
    with results_col:
        st.markdown(f"#### Your {_corpus_label} Estimate")

        # Fixed-height container mirrors the chat box height so the panel floats alongside the chat
        _results_box = st.container(height=460)

        # Check if we have enough to calculate
        _f = st.session_state.chat_fields
        _ret_age = _f.get("retirement_age")
        _life_exp = _f.get("life_expectancy")
        _target = _f.get("target_income")
        _birth_year = _f.get("birth_year")

        _has_required = all(v is not None for v in [_ret_age, _life_exp, _target])

        def _to_float(val, fallback=None):
            """Strip commas/currency symbols and convert to float; return fallback on failure."""
            try:
                return float(str(val).replace(",", "").replace("₹", "").replace("$", "").strip())
            except (ValueError, TypeError):
                return fallback

        def _to_int(val, fallback=None):
            f = _to_float(val)
            return int(f) if f is not None else fallback

        with _results_box:
            if not _has_required:
                st.markdown(
                    """
                    <div style='border:1px dashed #ccc; border-radius:8px; padding:32px; text-align:center; color:#999; margin-top:16px;'>
                        <div style='font-size:2em;'>📋</div>
                        <p>Your plan will appear here as you answer the questions on the left.</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                _ret_age_i  = _to_int(_ret_age)
                _life_exp_i = _to_int(_life_exp)
                _target_f   = _to_float(_target)

                # Validate
                _errors = []
                if _ret_age_i is None or _life_exp_i is None:
                    _errors.append("Could not parse retirement age or life expectancy — please re-enter as plain numbers.")
                elif _life_exp_i <= _ret_age_i:
                    _errors.append("Life expectancy must be greater than retirement age.")
                if _target_f is None:
                    _errors.append("Could not parse target income — please re-enter as a plain number.")
                elif _target_f < 0:
                    _errors.append("Target income cannot be negative.")

                if _errors:
                    for e in _errors:
                        st.error(e)
                else:
                    _tax = _to_float(_f.get("tax_rate", _defaults["tax_rate"]), _defaults["tax_rate"])
                    _growth = _to_float(_f.get("growth_rate", _defaults["growth_rate"]), _defaults["growth_rate"]) / 100.0
                    _inflation = _to_float(_f.get("inflation_rate", _defaults["inflation_rate"]), _defaults["inflation_rate"]) / 100.0
                    _legacy = _to_float(_f.get("legacy_goal", 0), 0)
                    _expenses = _to_float(_f.get("life_expenses", 0), 0)

                    try:
                        _r = find_required_portfolio(
                            target_after_tax_income=_target_f,
                            retirement_age=_ret_age_i,
                            life_expectancy=_life_exp_i,
                            retirement_tax_rate_pct=_tax,
                            growth_rate=_growth,
                            inflation_rate=_inflation,
                            legacy_goal=_legacy,
                            life_expenses=_expenses,
                        )

                        st.metric(
                            f"Required {_corpus_label} at Retirement",
                            _fmt_currency(_r["required_pretax_portfolio"], is_india),
                        )
                        st.metric(
                            "Modeled First-Year After-Tax Income",
                            _fmt_currency(_r["confirmed_income"], is_india),
                        )

                        # Assumptions
                        if _birth_year:
                            _current_age = datetime.now().year - int(_birth_year)
                            _years_to_retire = max(0, int(_ret_age) - _current_age)
                            st.caption(f"Age {_current_age} today · {_years_to_retire} years to retirement")

                        st.caption(
                            f"Retiring at {_ret_age} · Planning to age {_life_exp} · "
                            f"{_r['years_in_retirement']} years in retirement"
                        )
                        st.caption(
                            f"{_tax:.0f}% tax rate · {_growth*100:.1f}% growth · {_inflation*100:.1f}% inflation"
                        )
                        if _legacy > 0:
                            st.caption(f"Legacy goal: {_fmt_currency(_legacy, is_india)}")
                        if _expenses > 0:
                            st.caption(f"One-time expenses at retirement: {_fmt_currency(_expenses, is_india)}")

                    except Exception as e:
                        st.error(f"Calculation error: {e}")

        # PDF export button — visible once we have enough to calculate
        if _has_required:
            st.markdown("---")

            def _build_results_pdf(fields, calc_result, _is_india, corpus_label):
                """Generate a PDF of the retirement plan estimate (results + assumptions only)."""
                buf = io.BytesIO()
                doc = SimpleDocTemplate(
                    buf,
                    pagesize=A4,
                    rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72,
                )
                styles = getSampleStyleSheet()
                title_style = ParagraphStyle(
                    "ChatTitle",
                    parent=styles["Title"],
                    fontSize=20,
                    spaceAfter=6,
                )
                heading_style = ParagraphStyle(
                    "ChatHeading",
                    parent=styles["Heading2"],
                    fontSize=13,
                    spaceBefore=16,
                    spaceAfter=6,
                    textColor=colors.HexColor("#1f77b4"),
                )

                story = []

                # Header
                story.append(Paragraph("Smart Retire AI", title_style))
                story.append(Paragraph(
                    f"Simple Retirement Plan · {datetime.now().strftime('%B %d, %Y')}",
                    styles["Normal"],
                ))
                story.append(Spacer(1, 20))

                # Key results table
                story.append(Paragraph(f"Required {corpus_label} at Retirement", heading_style))
                req = calc_result["required_pretax_portfolio"]
                inc = calc_result["confirmed_income"]
                result_data = [
                    ["Required Portfolio", _fmt_currency(req, _is_india)],
                    ["Modeled First-Year After-Tax Income", _fmt_currency(inc, _is_india)],
                ]
                tbl = Table(result_data, colWidths=[260, 160])
                tbl.setStyle(TableStyle([
                    ("FONTSIZE", (0, 0), (-1, -1), 12),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#e8f4fd"), colors.HexColor("#f0faf0")]),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ]))
                story.append(tbl)

                # Assumptions table
                story.append(Paragraph("Assumptions", heading_style))
                _birth = fields.get("birth_year")
                rows = []
                if _birth:
                    _age_now = datetime.now().year - int(_birth)
                    rows.append(["Current Age", str(_age_now)])
                    rows.append(["Years to Retirement", str(max(0, int(fields["retirement_age"]) - _age_now))])
                rows += [
                    ["Country", fields.get("country", "US")],
                    ["Retirement Age", str(fields["retirement_age"])],
                    ["Life Expectancy", str(fields["life_expectancy"])],
                    ["Years in Retirement", str(calc_result["years_in_retirement"])],
                    ["Tax Rate on Withdrawals", f"{fields.get('tax_rate', calc_result['tax_rate']):.0f}%"],
                    ["Portfolio Growth Rate", f"{calc_result['growth_rate']*100:.1f}%"],
                    ["Inflation Rate", f"{calc_result['inflation_rate']*100:.1f}%"],
                ]
                if calc_result.get("legacy_goal", 0) > 0:
                    rows.append(["Legacy Goal", _fmt_currency(calc_result["legacy_goal"], _is_india)])
                if calc_result.get("life_expenses", 0) > 0:
                    rows.append(["One-Time Expenses at Retirement", _fmt_currency(calc_result["life_expenses"], _is_india)])

                asmp_tbl = Table(rows, colWidths=[260, 160])
                asmp_tbl.setStyle(TableStyle([
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f9f9f9")]),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ]))
                story.append(asmp_tbl)

                # Disclaimer
                story.append(Spacer(1, 24))
                story.append(Paragraph(
                    "This report is for educational purposes only and does not constitute financial advice. "
                    "Projections are estimates based on the assumptions above.",
                    ParagraphStyle("Disclaimer", parent=styles["Normal"], fontSize=9,
                                   textColor=colors.grey, leading=13),
                ))

                doc.build(story)
                buf.seek(0)
                return buf.getvalue()

            _can_pdf = _REPORTLAB_AVAILABLE and int(_life_exp) > int(_ret_age) and float(_target) >= 0
            if _can_pdf:
                try:
                    _pdf_tax = float(_f.get("tax_rate", _defaults["tax_rate"]))
                    _pdf_growth = float(_f.get("growth_rate", _defaults["growth_rate"])) / 100.0
                    _pdf_inflation = float(_f.get("inflation_rate", _defaults["inflation_rate"])) / 100.0
                    _pdf_r = find_required_portfolio(
                        target_after_tax_income=float(_target),
                        retirement_age=int(_ret_age),
                        life_expectancy=int(_life_exp),
                        retirement_tax_rate_pct=_pdf_tax,
                        growth_rate=_pdf_growth,
                        inflation_rate=_pdf_inflation,
                        legacy_goal=float(_f.get("legacy_goal", 0)),
                        life_expenses=float(_f.get("life_expenses", 0)),
                    )
                    _pdf_bytes = _build_results_pdf(_f, _pdf_r, is_india, _corpus_label)
                    _pdf_fname = f"retirement_plan_{datetime.now().strftime('%Y%m%d')}.pdf"
                    st.download_button(
                        "📥 Download PDF Report",
                        data=_pdf_bytes,
                        file_name=_pdf_fname,
                        mime="application/pdf",
                        use_container_width=True,
                        key="chat_pdf_download",
                    )
                except Exception as _pdf_err:
                    st.caption(f"PDF generation failed: {_pdf_err}")
            else:
                st.caption("Install `reportlab` to enable PDF export.")


@st.dialog("How do you want to plan?")
def planning_mode_dialog():
    """Popup shown automatically at Step 2 entry — lets user choose forward or reverse planning mode."""
    st.markdown("Choose how you'd like to approach your retirement plan:")
    st.markdown("")

    mode = st.radio(
        "Planning approach",
        ["I know my assets — show my income", "I have an income goal — show how much I need"],
        index=0,
        label_visibility="collapsed",
        key="planning_mode_dialog_radio",
    )

    st.markdown("")
    if mode == "I know my assets — show my income":
        st.info("Enter your retirement accounts and we'll calculate your sustainable annual income.")
    else:
        st.info(
            "Tell us your target after-tax income and we'll calculate the pre-tax portfolio you need. "
            "Assumes 100% pre-tax accounts (e.g. 401k / Traditional IRA)."
        )

    st.markdown("---")
    if st.button("Continue →", type="primary", use_container_width=True, key="planning_mode_dialog_confirm"):
        st.session_state.planning_mode_choice = mode
        st.rerun()


@st.dialog("⚠️ Legal Disclaimer", width="large")
def legal_disclaimer_dialog():
    """Full legal disclaimer shown as a popup on non-onboarding pages."""
    st.markdown("""
    ### 🚨 DISCLAIMER - READ CAREFULLY

    **This application provides educational and informational content only. It is NOT financial, tax, legal, or investment advice.**

    **Important Limitations:**
    - **Not Professional Advice**: This tool is for educational purposes only and does not constitute professional financial, tax, legal, or investment advice
    - **No Personal Recommendations**: Results are based on general assumptions and may not be suitable for your specific situation
    - **No Guarantees**: Past performance does not guarantee future results; all projections are estimates
    - **Consult Professionals**: Always consult with qualified financial advisors, tax professionals, and legal counsel before making financial decisions
    - **Your Responsibility**: You are solely responsible for your financial decisions and their consequences

    **No Liability**: The creators and operators of this application disclaim all liability for any losses, damages, or consequences arising from the use of this information.

    **By using this application, you acknowledge and agree to these terms.**
    """)
    if st.button("Close", use_container_width=True, type="primary", key="close_legal_disclaimer"):
        st.rerun()


@st.dialog(f"🆕 What's New in v{VERSION}", width="large")
def whats_new_dialog():
    """Display the Release Overview section of the current version's release notes."""
    content = load_release_notes()
    if content:
        marker = "## 🎯 Release Overview"
        start = content.find(marker)
        end = content.find("\n---", start) if start != -1 else -1
        overview = content[start:end] if start != -1 and end != -1 else content
        st.markdown(overview)
    else:
        st.info(f"Release notes for v{VERSION} are not yet available.")
    st.markdown("---")
    if st.button("Close", use_container_width=True, type="primary", key="close_whats_new"):
        st.rerun()


# Streamlit UI - this runs when using 'streamlit run fin_advisor.py'
# Skip UI code if running tests
import sys
_RUNNING_TESTS = "--run-tests" in sys.argv

if not _RUNNING_TESTS:
    st.set_page_config(
        page_title="Smart Retire AI",
        page_icon="💰",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # Initialize analytics
    initialize_analytics()

    # Scroll to top on page changes
    # This ensures focus starts at top when navigating between pages
    components.html(
        """
        <script>
            window.parent.document.querySelector('section.main').scrollTo(0, 0);
        </script>
        """,
        height=0,
    )

    # Fix tooltip font consistency
    st.markdown("""
        <style>
        /* Ensure tooltips use consistent sans-serif font */
        [role="tooltip"],
        [data-baseweb="tooltip"],
        div[data-baseweb="popover"] {
            font-family: "Source Sans Pro", sans-serif !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # Note: PostHog session replay requires browser JavaScript which doesn't work
    # reliably in Streamlit's server-side architecture. Session analytics (based on
    # events) will still work and show session duration, events per session, etc.
    
    @st.dialog("📊 Help Us Improve Smart Retire AI")
    def analytics_consent_dialog():
        """Display analytics consent dialog for user opt-in."""
        st.markdown("""
        ### We'd like to collect anonymous usage data to improve your experience
    
        **What we collect (if you opt-in):**
        - ✅ Anonymous usage patterns (e.g., which features you use)
        - ✅ Error logs (to fix bugs faster)
        - ✅ Browser/device info (for compatibility)
    
        **What we NEVER collect:**
        - ❌ Your financial data (account balances, numbers)
        - ❌ Personal information (name, email, address)
        - ❌ PDF file contents
        - ❌ Exact ages or retirement goals
    
        **Your data:**
        - Anonymous ID only (not tied to you)
        - Encrypted and stored securely
        - Automatically deleted after 90 days
        - You can opt-out anytime in Advanced Settings
    
        ---
        """)
    
        # Privacy policy link
        if st.button("📄 Read Full Privacy Policy", use_container_width=True, key="analytics_privacy_link"):
            show_privacy_policy()
    
        st.markdown("---")
    
        # Consent buttons
        col1, col2 = st.columns(2)
    
        with col1:
            if st.button("✅ I Accept", type="primary", use_container_width=True, key="analytics_accept"):
                set_analytics_consent(True)
                track_event('analytics_consent_shown')
                st.success("✅ Thank you! Analytics enabled.")
                time.sleep(0.5)  # Brief pause to show success message
                st.rerun()
    
        with col2:
            if st.button("❌ No Thanks", use_container_width=True, key="analytics_decline"):
                set_analytics_consent(False)
                st.info("ℹ️ You can enable analytics later in Advanced Settings.")
                time.sleep(0.5)  # Brief pause to show info message
                st.rerun()
    
        st.caption("**Your choice is saved for this session.** You can change it anytime in Advanced Settings.")
    
    
    @st.dialog("Privacy Policy")
    def show_privacy_policy():
        """Display comprehensive privacy policy in a dialog."""
        st.markdown("""
        ## Smart Retire AI Privacy Policy
    
        **Effective Date:** January 2026
        **Last Updated:** January 3, 2026
    
        ---
    
        ### 📋 Introduction
    
        Smart Retire AI ("we", "our", or "the app") is committed to protecting your privacy. This policy explains what data we collect, how we use it, and your rights.
    
        ---
    
        ### 🔐 Data We NEVER Collect
    
        We want to be crystal clear about what we **DO NOT** collect:
    
        ❌ **Financial Account Information**
        - Account balances, numbers, or statements
        - Investment holdings or transaction details
        - Banking or credit card information
    
        ❌ **Personally Identifiable Information (PII)**
        - Names, email addresses, or phone numbers
        - Social Security Numbers or tax IDs
        - Home addresses or zip codes
        - Birth dates (we use age ranges only)
    
        ❌ **Sensitive Personal Data**
        - Uploaded PDF file contents
        - Exact retirement goals (we use ranges)
        - Specific financial advice or recommendations
    
        ---
    
        ### ✅ Data We May Collect (With Your Consent)
    
        **If you opt-in to analytics**, we collect anonymous usage data:
    
        **1. Anonymous Usage Events**
        - Actions you take in the app (e.g., "user completed step 1")
        - Features you use (e.g., "PDF report generated")
        - Anonymous user ID (random UUID, not linked to you)
    
        **2. Technical Information**
        - Browser type and version (for compatibility)
        - Operating system (for compatibility)
        - Device type (desktop/mobile/tablet)
        - Screen resolution (for UI optimization)
    
        **3. Session Data**
        - Time spent in app
        - Pages/screens visited
        - Navigation patterns (to improve UX)
    
        **4. Error Logs**
        - Error types and frequency (for debugging)
        - Performance metrics (load times, crashes)
    
        **5. Aggregated Statistics**
        - Number of assets added (count only, not values)
        - Age ranges (e.g., 30-40, not exact age)
        - Retirement goal ranges (not exact amounts)
    
        ---
    
        ### 🎯 How We Use Data
    
        **Analytics data is used to:**
        - ✅ Understand how users navigate the app
        - ✅ Identify where users encounter problems
        - ✅ Fix bugs and improve performance
        - ✅ Improve user experience and interface
        - ✅ Measure feature adoption and usage
    
        **We NEVER:**
        - ❌ Sell your data to third parties
        - ❌ Use data for advertising or marketing
        - ❌ Share data with financial institutions
        - ❌ Track you across other websites
        - ❌ Build personal profiles or credit scores
    
        ---
    
        ### 🔒 Data Storage & Security
    
        **If you opt-in to analytics:**
        - Data stored with PostHog (analytics platform)
        - Servers located in US/EU (GDPR compliant)
        - Data encrypted in transit (HTTPS)
        - Data encrypted at rest (AES-256)
        - Data automatically deleted after 90 days
    
        **Financial calculations:**
        - All calculations happen in your browser
        - No financial data sent to our servers
        - No cloud storage of your account information
    
        ---
    
        ### 🌍 GDPR & Privacy Compliance
    
        **Your Rights:**
        - ✅ **Right to Opt-Out**: Decline analytics at any time
        - ✅ **Right to Access**: Request data we've collected
        - ✅ **Right to Delete**: Request deletion of your data
        - ✅ **Right to Export**: Request copy of your data
        - ✅ **Right to Correct**: Request corrections to data
    
        **GDPR Compliance:**
        - ✅ Opt-in consent required (not opt-out)
        - ✅ Clear explanation of data collection
        - ✅ Easy to withdraw consent
        - ✅ Data minimization (only what's needed)
        - ✅ Purpose limitation (analytics only)
    
        ---
    
        ### 🍪 Cookies & Tracking
    
        **Session Cookies (Required):**
        - Used to maintain your session state
        - Stored locally in your browser only
        - Deleted when you close browser
        - Not used for tracking across sites
    
        **Analytics Cookies (Optional):**
        - Only if you opt-in to analytics
        - Used to recognize returning users (anonymously)
        - Can be disabled by declining analytics
        - No third-party advertising cookies
    
        ---
    
        ### 📊 Session Recording (Optional)
    
        **If you opt-in to session recording:**
        - We may record your interactions with the app
        - Used to understand user experience and fix UI issues
        - **Financial data is automatically masked**
        - Recordings deleted after 30 days
        - You can opt-out at any time
    
        **What's Masked in Recordings:**
        - All number inputs (balances, ages, goals)
        - Text inputs (names, custom labels)
        - Uploaded file names and contents
    
        **What's Visible in Recordings:**
        - Mouse movements and clicks
        - Page navigation patterns
        - Button clicks and interactions
        - UI elements (labels, help text)
    
        ---
    
        ### 👤 Children's Privacy
    
        Smart Retire AI is not intended for users under 18 years of age. We do not knowingly collect data from children.
    
        ---
    
        ### 🔄 Third-Party Services
    
        **Analytics Provider:**
        - PostHog (https://posthog.com)
        - GDPR and SOC 2 compliant
        - Privacy policy: https://posthog.com/privacy
    
        **Hosting:**
        - Streamlit Cloud (https://streamlit.io)
        - Privacy policy: https://streamlit.io/privacy-policy
    
        **AI Statement Processing:**
        - n8n webhook (self-hosted)
        - No data retention beyond processing
    
        ---
    
        ### ⚖️ Legal Basis for Processing
    
        We process data based on:
        - **Consent**: You explicitly opt-in to analytics
        - **Legitimate Interest**: Error logging and app improvement
        - **Contract**: Providing the app service you requested
    
        ---
    
        ### 🔔 Changes to Privacy Policy
    
        We may update this policy to reflect:
        - Changes in data practices
        - New features or services
        - Legal or regulatory requirements
    
        **How you'll be notified:**
        - Updated "Last Updated" date above
        - In-app notification on next visit
        - Option to review changes before continuing
    
        ---
    
        ### 📧 Contact Us
    
        Questions about privacy or data practices?
    
        **Email:** smartretireai@gmail.com
        **Response Time:** 24-48 hours
        **Data Requests:** Include "Privacy Request" in subject
    
        ---
    
        ### 📝 Your Consent
    
        By clicking "I Accept" on the analytics consent screen:
        - You acknowledge reading this privacy policy
        - You consent to anonymous analytics collection
        - You understand you can opt-out at any time
        - You agree to the terms described above
    
        By clicking "No Thanks" on the analytics consent screen:
        - No analytics data will be collected
        - The app will function normally
        - You can opt-in later in Settings if desired
    
        ---
    
        **Thank you for trusting Smart Retire AI with your retirement planning!**
        """)
    
        if st.button("Close", use_container_width=True, type="primary"):
            st.rerun()


    @st.dialog("✏️ Edit AI-Extracted Accounts", width="large")
    def edit_ai_accounts_dialog():
        """Modal for editing AI-extracted accounts with isolated context."""
        # Custom CSS to maximize dialog width
        st.markdown("""
            <style>
            [data-testid="stDialog"] {
                width: 95vw !important;
                max-width: 95vw !important;
            }
            </style>
        """, unsafe_allow_html=True)

        st.info("💡 **Make any adjustments to your extracted accounts below.**")

        if st.session_state.ai_edited_table is not None:
            df_display = st.session_state.ai_edited_table.copy()

            # Define column configuration - same as reload view
            column_config = {
                "#": st.column_config.TextColumn("#", disabled=True, help="Row number", width="small"),
                "Institution": st.column_config.TextColumn(
                    "Institution",
                    disabled=True,
                    help="Financial institution (e.g., Fidelity, Morgan Stanley)",
                    width="small"
                ),
                "Account Name": st.column_config.TextColumn(
                    "Account Name",
                    help="Account name/description from statement",
                    width="small"
                ),
                "Last 4": st.column_config.TextColumn(
                    "Last 4",
                    disabled=True,
                    help="Last 4 digits of account number",
                    width="small"
                ),
                "Account Type": st.column_config.TextColumn(
                    "Account Type",
                    disabled=True,
                    help="Type of account (401k, IRA, Savings, etc.)",
                    width="small"
                ),
                "Tax Treatment": st.column_config.SelectboxColumn(
                    "Tax Treatment",
                    options=TAX_TREATMENT_OPTIONS,
                    help="Tax treatment: Tax-Deferred (401k/IRA), Tax-Free (Roth), Post-Tax (Brokerage)"
                ),
                "Current Balance": st.column_config.NumberColumn(
                    "Current Balance ($)",
                    min_value=0,
                    format="$%d",
                    help="Current account balance"
                ),
                "Annual Contribution": st.column_config.NumberColumn(
                    "Annual Contribution ($)",
                    min_value=0,
                    format="$%d",
                    help="How much you contribute annually"
                ),
                "Growth Rate (%)": st.column_config.NumberColumn(
                    "Growth Rate (%)",
                    min_value=0.0,
                    max_value=20.0,
                    format="%.1f%%",
                    help="Expected annual growth rate"
                ),
                "Tax Rate on Gains (%)": st.column_config.NumberColumn(
                    "Tax Rate on Gains (%)",
                    min_value=0.0,
                    max_value=50.0,
                    format="%.1f%%",
                    help="Tax rate on gains (capital gains or income tax)"
                )
            }

            # Add optional column configs if they exist
            if "Income Eligibility" in df_display.columns:
                column_config["Income Eligibility"] = st.column_config.TextColumn(
                    "Income Eligibility",
                    disabled=True,
                    help="Income restrictions for this account type",
                    width="small"
                )
            if "Purpose" in df_display.columns:
                column_config["Purpose"] = st.column_config.TextColumn(
                    "Purpose",
                    disabled=True,
                    help="Primary purpose of this account",
                    width="small"
                )

            # Display editable table in modal
            edited_df = st.data_editor(
                df_display,
                column_config=column_config,
                use_container_width=True,
                hide_index=True,
                num_rows="dynamic",
                key="ai_table_modal_editor"
            )

            st.markdown("---")

            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("✅ Save Changes", type="primary", use_container_width=True):
                    st.session_state.ai_edited_table = edited_df
                    st.session_state.dialog_open = False
                    st.rerun()
            with col2:
                if st.button("❌ Cancel", use_container_width=True):
                    st.session_state.dialog_open = False
                    st.rerun()
        else:
            st.warning("No extracted data available to edit.")
            if st.button("Close", use_container_width=True):
                st.session_state.dialog_open = False
                st.rerun()


    # Initialize What's New dialog state — auto-show once per session
    if 'whats_new_shown' not in st.session_state:
        st.session_state.whats_new_shown = True
        st.session_state.show_whats_new = True
    if 'show_whats_new' not in st.session_state:
        st.session_state.show_whats_new = False

    # Trigger What's New dialog if flagged
    if st.session_state.get('show_whats_new', False):
        st.session_state.show_whats_new = False
        whats_new_dialog()

    # Initialize session state for splash screen
    if 'splash_dismissed' not in st.session_state:
        st.session_state.splash_dismissed = False
    
    # Initialize session state for onboarding flow
    if 'onboarding_step' not in st.session_state:
        st.session_state.onboarding_step = 1
    if 'onboarding_complete' not in st.session_state:
        st.session_state.onboarding_complete = False
    
    # Initialize session state for page navigation
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'mode_selection'  # Can be 'mode_selection', 'chat_mode', 'onboarding', or 'results'

    # Initialize chat session state
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
    if 'chat_fields' not in st.session_state:
        st.session_state.chat_fields = {}
    if 'chat_complete' not in st.session_state:
        st.session_state.chat_complete = False
    
    # Initialize session state for baseline values (from onboarding)
    if 'birth_year' not in st.session_state:
        st.session_state.birth_year = datetime.now().year - 30
    if 'baseline_retirement_age' not in st.session_state:
        st.session_state.baseline_retirement_age = 65
    if 'baseline_life_expectancy' not in st.session_state:
        st.session_state.baseline_life_expectancy = 85
    if 'baseline_retirement_income_goal' not in st.session_state:
        st.session_state.baseline_retirement_income_goal = 0  # Optional field
    if 'baseline_life_expenses' not in st.session_state:
        st.session_state.baseline_life_expenses = 0
    if 'baseline_legacy_goal' not in st.session_state:
        st.session_state.baseline_legacy_goal = 0
    if 'client_name' not in st.session_state:
        st.session_state.client_name = ""
    if 'assets' not in st.session_state:
        st.session_state.assets = []
    if 'country' not in st.session_state:
        st.session_state.country = 'US'

    # ==========================================
    # SIDEBAR - Advanced Settings (Collapsed by Default)
    # ==========================================
    with st.sidebar:
        with st.expander("⚙️ Advanced Settings", expanded=False):
            _sb_india = st.session_state.get('country', 'US') == 'India'

            st.markdown("### Tax Settings")

            # Current tax rate with helpful guidance
            with st.expander("💡 How to find your current tax rate", expanded=False):
                if _sb_india:
                    st.markdown("""
                    **India Income Tax — New Regime (FY 2024-25):**
                    - 0%:  Up to ₹3,00,000
                    - 5%:  ₹3,00,001 – ₹7,00,000
                    - 10%: ₹7,00,001 – ₹10,00,000
                    - 15%: ₹10,00,001 – ₹12,00,000
                    - 20%: ₹12,00,001 – ₹15,00,000
                    - 30%: Above ₹15,00,000

                    Check your Form 16 or ITR for your effective rate.
                    """)
                else:
                    st.markdown("""
                    **To find your current marginal tax rate:**
                    1. **From your tax return**: Look at your most recent Form 1040, Line 15 (Taxable Income)
                    2. **Use IRS tax brackets**: Find which bracket your income falls into

                    **2024 Tax Brackets (Single):**
                    - 10%: $0 - $11,600
                    - 12%: $11,601 - $47,150
                    - 22%: $47,151 - $100,525
                    - 24%: $100,526 - $191,950
                    - 32%: $191,951 - $243,725
                    - 35%: $243,726 - $609,350
                    - 37%: $609,351+
                    """)

            current_tax_rate = st.slider(
                "Current Marginal Tax Rate (%)", 0, 50,
                key=f"sidebar_current_tax_rate_{st.session_state.get('country','US')}",
                value=10 if _sb_india else 22,
                help="Your current tax bracket based on your income",
            )

            with st.expander("💡 How to estimate retirement tax rate", expanded=False):
                if _sb_india:
                    st.markdown("""
                    **Consider these factors:**
                    1. **Lower income**: Most retirees have lower taxable income
                    2. **EPF / PPF withdrawals**: Fully tax-free at maturity
                    3. **NPS**: 60% lump sum is tax-free; annuity income is taxable
                    4. **Senior citizen benefit**: ₹50,000 standard deduction on pension income

                    **Common scenarios:**
                    - **Conservative**: Same as current rate
                    - **Optimistic**: 10% (EPF/PPF-heavy corpus)
                    - **Pessimistic**: 20–30% (large NPS annuity or rental income)
                    """)
                else:
                    st.markdown("""
                    **Consider these factors:**
                    1. **Lower income**: Most people have lower income in retirement
                    2. **Social Security**: Only 85% is taxable for most people
                    3. **Roth withdrawals**: Tax-free if qualified
                    4. **Required Minimum Distributions**: Start at age 73 (2024)

                    **Common scenarios:**
                    - **Conservative**: Same as current rate
                    - **Optimistic**: 10-15% lower than current
                    - **Pessimistic**: 5-10% higher (if tax rates increase)
                    """)

            retirement_tax_rate = st.slider(
                "Projected Retirement Tax Rate (%)", 0, 50,
                key=f"sidebar_retirement_tax_rate_{st.session_state.get('country','US')}",
                value=10 if _sb_india else 22,
                help="Expected tax rate in retirement",
            )

            st.markdown("---")
            st.markdown("### Growth Rate Assumptions")

            with st.expander("💡 Inflation guidance", expanded=False):
                if _sb_india:
                    st.markdown("""
                    **Historical context (India):**
                    - **Long-term CPI average**: 5–7% annually
                    - **Recent years**: 4–7% (2020–2024)
                    - **RBI target**: 4% annually

                    **Consider:**
                    - **Conservative**: 6–7% (safe for long-term planning)
                    - **Moderate**: 5–6%
                    - **Optimistic**: 4% (RBI target)
                    """)
                else:
                    st.markdown("""
                    **Historical context:**
                    - **Long-term average**: 3.0-3.5% annually
                    - **Recent years**: 2-4% (2020-2024)
                    - **Federal Reserve target**: 2% annually

                    **Consider:**
                    - **Conservative**: 2-3% (Fed target)
                    - **Moderate**: 3-4% (historical average)
                    - **Aggressive**: 4-5% (higher inflation)
                    """)

            inflation_rate = st.slider(
                "Expected Inflation Rate (%)", 0, 15 if _sb_india else 10,
                key=f"sidebar_inflation_rate_{st.session_state.get('country','US')}",
                value=7 if _sb_india else 3,
                help="Long-term inflation assumption (affects purchasing power)",
            )

            st.markdown("---")
            st.markdown("### Investment Growth Rate")

            with st.expander("💡 Growth rate guidance", expanded=False):
                if _sb_india:
                    st.markdown("""
                    **Typical annual growth rates (India):**
                    - **Equity MF (large-cap)**: 10–12%
                    - **Equity MF (flexi/mid-cap)**: 12–15%
                    - **Balanced / hybrid MF**: 8–10%
                    - **Debt MF / FD**: 6–7%
                    - **PPF / EPF**: 7–8%

                    **Note:** This is used as the default when adding investment accounts.
                    """)
                else:
                    st.markdown("""
                    **Typical annual growth rates:**
                    - **Stocks/Equity funds**: 7-10%
                    - **Bonds/Fixed income**: 4-5%
                    - **Savings accounts**: 2-4%
                    - **Conservative portfolio**: 5-6%
                    - **Aggressive portfolio**: 8-10%

                    **Note:** This is used as the default when adding investment accounts.
                    """)

            default_growth_rate = st.slider(
                "Default Growth Rate for Investments (%)",
                min_value=0.0,
                max_value=20.0,
                key=f"sidebar_default_growth_rate_{st.session_state.get('country','US')}",
                value=10.0 if _sb_india else 7.0,
                step=0.5,
                help="Default annual growth rate for investment accounts (stocks, bonds, etc.)",
            )
    
            st.markdown("---")
            st.markdown("### 📊 Analytics & Privacy")
    
            # Show current analytics status
            analytics_enabled = is_analytics_enabled()
            if analytics_enabled:
                st.success("✅ **Analytics Enabled** - Helping us improve Smart Retire AI")
            else:
                st.info("ℹ️ **Analytics Disabled** - No usage data is collected")
    
            # Privacy policy link
            if st.button("📄 View Privacy Policy", use_container_width=True, key="sidebar_privacy_policy"):
                show_privacy_policy()
    
            # Opt-out/Opt-in toggle
            col1, col2 = st.columns(2)
            with col1:
                if st.button("❌ Disable Analytics", use_container_width=True, disabled=not analytics_enabled):
                    opt_out()
                    st.success("✅ Analytics disabled")
                    st.rerun()
            with col2:
                if st.button("✅ Enable Analytics", use_container_width=True, disabled=analytics_enabled):
                    opt_in()
                    st.success("✅ Analytics enabled")
                    st.rerun()
    
            # Reset analytics session (for testing)
            with st.expander("🔧 Advanced: Reset Analytics Session"):
                st.caption("Clear all analytics session data and start fresh. Useful for testing or privacy reset.")
                if st.button("🔄 Reset Analytics Session", use_container_width=True, key="reset_analytics"):
                    reset_analytics_session()
                    st.success("✅ Analytics session reset")
                    st.info("ℹ️ Refresh the page to see the analytics consent screen again.")
                    st.rerun()
    
            st.markdown("---")
            st.markdown("**💡 Tip:** Adjust these settings anytime during the onboarding process.")
    
    # Home button — visible from sub-pages so users can always return to Results
    if st.session_state.get('current_page') in ('detailed_analysis', 'monte_carlo'):
        st.sidebar.markdown("---")
        if st.sidebar.button("🏠 Results Dashboard", use_container_width=True, type="primary"):
            st.session_state.current_page = 'results'
            st.rerun()

    # Reset button (only show if onboarding is complete)
    if st.session_state.onboarding_complete:
        st.sidebar.markdown("---")
        if st.sidebar.button("🔄 Reset Onboarding", use_container_width=True):
            st.session_state.onboarding_step = 1
            st.session_state.onboarding_complete = False
            st.rerun()
    
    # Initialize session state for what-if scenario values (used on results page)
    if 'whatif_retirement_age' not in st.session_state:
        st.session_state.whatif_retirement_age = st.session_state.baseline_retirement_age
    if 'whatif_life_expectancy' not in st.session_state:
        st.session_state.whatif_life_expectancy = st.session_state.baseline_life_expectancy
    if 'whatif_retirement_income_goal' not in st.session_state:
        st.session_state.whatif_retirement_income_goal = st.session_state.baseline_retirement_income_goal
    if 'whatif_current_tax_rate' not in st.session_state:
        st.session_state.whatif_current_tax_rate = 22
    if 'whatif_retirement_tax_rate' not in st.session_state:
        st.session_state.whatif_retirement_tax_rate = 22
    if 'whatif_inflation_rate' not in st.session_state:
        st.session_state.whatif_inflation_rate = 3
    if 'whatif_life_expenses' not in st.session_state:
        st.session_state.whatif_life_expenses = st.session_state.baseline_life_expenses
    if 'whatif_legacy_goal' not in st.session_state:
        st.session_state.whatif_legacy_goal = st.session_state.baseline_legacy_goal
    if 'whatif_retirement_growth_rate' not in st.session_state:
        st.session_state.whatif_retirement_growth_rate = 4.0
    
    # Legacy compatibility (keep retirement_age, life_expectancy for backward compatibility)
    if 'retirement_age' not in st.session_state:
        st.session_state.retirement_age = st.session_state.baseline_retirement_age
    if 'life_expectancy' not in st.session_state:
        st.session_state.life_expectancy = st.session_state.baseline_life_expectancy
    if 'retirement_income_goal' not in st.session_state:
        st.session_state.retirement_income_goal = st.session_state.baseline_retirement_income_goal
    
    # ==========================================
    # PRIVACY POLICY DIALOG
    # ==========================================
    
    
    
    # ==========================================
    # SPLASH SCREEN / WELCOME PAGE
    # ==========================================
    if not st.session_state.splash_dismissed:
        # Display splash screen
        # Compact splash header
        st.markdown(
            f"""
            <div style='background: linear-gradient(135deg, #1f77b4 0%, #2ca02c 100%);
                        padding: 28px 32px;
                        border-radius: 16px;
                        text-align: center;
                        color: white;
                        margin: 16px auto 20px auto;
                        max-width: 900px;
                        box-shadow: 0 4px 16px rgba(0,0,0,0.12);'>
                <div style='font-size: 2em; font-weight: bold; margin-bottom: 4px;'>💰 Smart Retire AI</div>
                <div style='font-size: 0.95em; opacity: 0.85; margin-bottom: 6px;'>Version {VERSION} &nbsp;·&nbsp; Best used on a desktop browser</div>
                <div style='font-size: 1.15em; font-weight: 500; opacity: 0.95;'>Your AI-Powered Retirement Planning Companion</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 4 key features in a 2-column grid
        st.markdown("#### ✨ What you can do")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**💬 Simple Planning**")
            st.caption("Answer 3 questions in a chat and get your required corpus/portfolio instantly — no forms.")
            st.markdown("")
            st.markdown("**📊 Detailed Portfolio Analysis**")
            st.caption("Upload PDF statements, enter account balances, and get tax-optimised year-by-year projections.")
        with col2:
            st.markdown("**🎯 What-If Scenarios**")
            st.caption("Adjust any assumption — retirement age, income, growth rate — and see results update instantly.")
            st.markdown("")
            st.markdown("**🇮🇳 US & India Support**")
            st.caption("Full $ and ₹ support with country-specific defaults for tax rate, inflation, and growth.")

        st.markdown("---")

        # Analytics notice (auto opt-in)
        st.caption(
            "📊 By continuing you agree to anonymous usage analytics to help us improve the app. "
            "No financial data or personal information is ever collected. "
            "You can opt out anytime in Advanced Settings."
        )

        # Continue button
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("✅ Get Started", type="primary", use_container_width=True):
                st.session_state.splash_dismissed = True
                set_analytics_consent(True)
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            """
            <div style='text-align: center; color: #999; font-size: 0.85em;'>
                Questions? <a href='mailto:smartretireai@gmail.com' style='color: #1f77b4;'>smartretireai@gmail.com</a>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
        # Stop rendering the rest of the page
        st.stop()
    
    # ==========================================
    # PAGE ROUTING
    # ==========================================
    # Route to appropriate page based on current_page state

    if st.session_state.current_page == 'mode_selection':
        show_mode_selection_page()

    elif st.session_state.current_page == 'chat_mode':
        show_chat_mode_page()

    elif st.session_state.current_page == 'onboarding':
        # ==========================================
        # ONBOARDING PAGE
        # ==========================================
        st.markdown("---")
    
        # Progress indicator
        total_steps = 2
        current_step = st.session_state.onboarding_step
        
        # Visual progress bar
        progress_text = f"**Step {current_step} of {total_steps}**"
        progress_percentage = (current_step - 1) / total_steps
        st.progress(progress_percentage, text=progress_text)
        
        # Step titles
        step_titles = {
            1: "👤 Personal Information",
            2: "🏦 Asset Configuration"
        }
        
        st.subheader(f"📝 {step_titles[current_step]}")
        st.markdown("---")
        
        # ==========================================
        # STEP 1: Personal Information
        # ==========================================
        if current_step == 1:
            # Track step 1 started
            track_onboarding_step_started(1, country=st.session_state.get('country', 'US'))

            # Country selector — determines currency, terminology, and available modes
            _country_options = ["🇺🇸 United States", "🇮🇳 India"]
            _country_sel = st.selectbox(
                "Country",
                _country_options,
                index=0 if st.session_state.get('country', 'US') == 'US' else 1,
                key="country_select",
                help="Select your country. India mode shows the Corpus Calculator with ₹ (INR) currency.",
            )
            st.session_state.country = "India" if "India" in _country_sel else "US"
            _is_india = st.session_state.country == "India"
            _sym = "₹" if _is_india else "$"
            _corpus_label = "Corpus" if _is_india else "Portfolio"

            # Reset defaults when country changes so the new country's values appear immediately
            _prev_country = st.session_state.get('_prev_country', st.session_state.country)
            if _prev_country != st.session_state.country:
                if _is_india:
                    st.session_state.retirement_age = 60
                    st.session_state.life_expectancy = 85
                    st.session_state.retirement_income_goal = 0
                    st.session_state.whatif_retirement_growth_rate = 10.0
                    st.session_state.whatif_inflation_rate = 7.0
                    st.session_state.whatif_retirement_tax_rate = 10
                else:
                    st.session_state.retirement_age = 65
                    st.session_state.life_expectancy = 90
                    st.session_state.retirement_income_goal = 0
                    st.session_state.whatif_retirement_growth_rate = 4.0
                    st.session_state.whatif_inflation_rate = 3.0
                    st.session_state.whatif_retirement_tax_rate = 22
                # Delete all widget keys that carry country-specific defaults so they
                # re-initialize from their country-aware value= parameters on the next run.
                # (Streamlit forbids writing to widget keys after instantiation in the same run.)
                for _k in (
                    'goal_tax_rate', 'goal_growth_rate', 'goal_inflation_rate',
                    'goal_retirement_age', 'goal_life_expectancy', 'goal_target_income',
                    'retirement_income_goal_input',
                ):
                    st.session_state.pop(_k, None)
                track_event(
                    'country_selected',
                    {'country': st.session_state.country, 'previous_country': _prev_country},
                    user_properties={'country': st.session_state.country},
                )
                st.session_state._prev_country = st.session_state.country
                st.rerun()
            st.session_state._prev_country = st.session_state.country

            col1, col2 = st.columns(2)
    
            with col1:
                # Birth year input instead of age
                current_year = datetime.now().year
                birth_year = st.number_input(
                    "Birth Year",
                    min_value=current_year-90,
                    max_value=current_year-18,
                    value=st.session_state.birth_year,
                    help="Your birth year (age will be calculated automatically)",
                    key="birth_year_input"
                )
                st.session_state.birth_year = birth_year
                age = current_year - birth_year
                st.info(f"📅 **Current Age**: {age} years old")
    
                retirement_age = st.number_input(
                    "Target Retirement Age",
                    min_value=40,
                    max_value=80,
                    value=st.session_state.retirement_age,
                    help="When you plan to retire",
                    key="retirement_age_input"
                )
                st.session_state.retirement_age = retirement_age
                st.info(f"⏰ **Years to Retirement**: {retirement_age - age} years")
                # Life expectancy input with tooltip help
                life_expectancy = st.number_input(
                    "Life Expectancy (Age)",
                    min_value=retirement_age+1,
                    max_value=120,
                    value=st.session_state.life_expectancy,
                    help=(
                        """Average Life Expectancy (India):
• At birth: ~72 years (India avg)
• At age 30: ~75 years
• At age 60: ~80 years

Factors to Consider:
• Family history & health status
• Lifestyle (exercise, diet)
• Access to healthcare

💡 Tip: Plan to age 85–90 for safety."""
                        if _is_india else
                        """Average Life Expectancy:
• At birth: ~79 years (US avg)
• At age 30: ~80 years
• At age 50: ~82 years
• At age 65: ~85 years

Factors to Consider:
• Family history & health status
• Lifestyle (exercise, diet, smoking)
• Gender (women live 3-5 yrs longer)

💡 Tip: Add 5-10 years for safety."""
                    ),
                    key="life_expectancy_input"
                )
                st.session_state.life_expectancy = life_expectancy
                years_in_retirement = life_expectancy - retirement_age
                st.info(f"⏳ **Years in Retirement**: {years_in_retirement} years")

            with col2:
    
                # Retirement income goal with tooltip help
                retirement_income_goal = st.number_input(
                    f"After Tax Annual Income Needed in Retirement ({_sym}) - Optional",
                    min_value=0,
                    max_value=50_000_000 if _is_india else 500000,
                    value=st.session_state.retirement_income_goal,
                    step=50000 if _is_india else 5000,
                    help=(
                        """Typical Annual Needs (India):
• ₹3L–₹5L/yr:  Modest lifestyle
• ₹5L–₹8L/yr:  Comfortable lifestyle
• ₹8L–₹12L/yr: Enhanced lifestyle
• ₹12L+/yr:    Premium lifestyle

Consider:
• Housing (rent/EMI, maintenance)
• Healthcare (insurance, out-of-pocket)
• Daily living (food, utilities)
• Lifestyle (travel, family)

💡 Rule of thumb: 70–80% of pre-retirement income"""
                        if _is_india else
                        """Typical Annual Needs:
• $40K-$60K: Modest lifestyle
• $60K-$80K: Comfortable lifestyle
• $80K-$100K: Enhanced lifestyle
• $100K+: Premium lifestyle

Consider:
• Housing costs (rent/mortgage, taxes)
• Healthcare (insurance, out-of-pocket)
• Daily living (food, utilities)
• Lifestyle (travel, hobbies)
• Social Security (~$20-40K/yr)

💡 Rule of thumb: 70-80% of pre-retirement income"""
                    ),
                    key="retirement_income_goal_input"
                )
                st.session_state.retirement_income_goal = retirement_income_goal

                if retirement_income_goal > 0:
                    st.info(f"💰 **Target**: {_fmt_currency(retirement_income_goal, _is_india)}/year in retirement")
                else:
                    st.info("💡 **No target set** - Analysis will show your projected value")

                life_expenses = st.number_input(
                    f"One-Time Expenses at Retirement ({_sym}) — Optional",
                    min_value=0,
                    max_value=100_000_000 if _is_india else 10_000_000,
                    value=st.session_state.get('life_expenses', 0),
                    step=100_000 if _is_india else 10_000,
                    help=(
                        """A lump-sum amount deducted from your corpus at the moment you retire.

Examples:
• Paying off a remaining home loan
• Large medical or long-term care costs
• Down payment on a retirement home

💡 Common range: ₹5L–₹50L
   (e.g., ₹15L to clear a remaining home loan)

This amount is subtracted from your corpus before calculating sustainable income."""
                        if _is_india else
                        """A lump-sum amount deducted from your portfolio at the moment you retire.

Examples:
• Paying off a remaining mortgage
• Large medical or long-term care costs
• Down payment on a retirement home

💡 Common range: $50,000–$300,000
   (e.g., $150,000 to clear a remaining mortgage)

This amount is subtracted from your portfolio before calculating sustainable income."""
                    ),
                    key="life_expenses_input"
                )
                st.session_state.life_expenses = life_expenses

                if life_expenses > 0:
                    st.info(f"💸 **One-Time Deduction**: {_fmt_currency(life_expenses, _is_india)} at retirement")
                else:
                    st.info("💡 **No one-time expenses set** - No deduction at retirement")

                legacy_goal = st.number_input(
                    f"Legacy Goal — Money to Leave Behind ({_sym}) — Optional",
                    min_value=0,
                    max_value=100_000_000 if _is_india else 10_000_000,
                    value=st.session_state.get('legacy_goal', 0),
                    step=100_000 if _is_india else 10_000,
                    help=(
                        f"""The amount you want remaining in your corpus at end of life — this is NOT deducted at retirement.

The withdrawal simulation will preserve this amount so it can be passed on.

💡 Common range: ₹20L–₹2Cr
   (e.g., ₹50L as an inheritance for your family)

Modeled as a future-value target: the corpus must end at life expectancy with at least this balance."""
                        if _is_india else
                        """The amount you want remaining in your portfolio at end of life — this is NOT deducted at retirement.

The withdrawal simulation will preserve this amount so it can be passed on.

💡 Common range: $50,000–$500,000
   (e.g., $200,000 as an inheritance for your family)

Modeled as a future-value target: the portfolio must end at life expectancy with at least this balance."""
                    ),
                    key="legacy_goal_input"
                )
                st.session_state.legacy_goal = legacy_goal

                if legacy_goal > 0:
                    st.info(f"🎯 **Legacy Goal**: {_fmt_currency(legacy_goal, _is_india)} remaining at end of life")
                else:
                    st.info(f"💡 **No legacy goal set** - {_corpus_label} can be fully depleted at end of life")

            # Navigation button for Step 1
            st.markdown("---")
            col1, col2, col3 = st.columns([1, 1, 1])
            with col3:
                if st.button("Next: Asset Configuration →", type="primary", use_container_width=True):
                    # Track step 1 completed
                    track_onboarding_step_completed(
                        1,
                        country=st.session_state.get('country', 'US'),
                        age_range=get_age_range(datetime.now().year - st.session_state.birth_year),
                        retirement_age=st.session_state.retirement_age,
                        years_to_retirement=st.session_state.retirement_age - (datetime.now().year - st.session_state.birth_year),
                        goal_range=get_goal_range(st.session_state.retirement_income_goal)
                    )
                    st.session_state.onboarding_step = 2
                    st.rerun()
        
        # ==========================================
        # STEP 2: Asset Configuration
        # ==========================================
        elif current_step == 2:
            # Track step 2 started
            track_onboarding_step_started(2, country=st.session_state.get('country', 'US'))
    
            # Show contribution reminder dialog if flagged
            if st.session_state.get('show_contribution_reminder', False):
                contribution_reminder_dialog()

            # ---- Planning mode: auto-show dialog on first visit to Step 2 ----
            if "planning_mode_choice" not in st.session_state:
                if st.session_state.get('country') == 'India':
                    # India only supports the Income Goal (Corpus) Calculator
                    st.session_state.planning_mode_choice = "I have an income goal — show how much I need"
                else:
                    planning_mode_dialog()
                    st.stop()

            planning_mode = st.session_state.planning_mode_choice

            # Show current mode + allow switching (US only; India is locked to Income Goal mode)
            if st.session_state.get('country') != 'India':
                _mode_label = "Assets → Income" if "assets" in planning_mode else "Income Goal → Portfolio"
                _col_mode_a, _col_mode_b = st.columns([5, 1])
                _col_mode_a.caption(f"Planning mode: **{_mode_label}**")
                if _col_mode_b.button("Change", key="change_planning_mode_btn"):
                    del st.session_state["planning_mode_choice"]
                    st.rerun()

            # Currency / terminology helpers (used in Income Goal Calculator below)
            _is_india = st.session_state.get('country') == 'India'
            _sym = "₹" if _is_india else "$"
            _corpus_label = "Corpus" if _is_india else "Portfolio"

            if planning_mode == "I have an income goal — show how much I need":
                st.subheader("Income Goal Calculator" if not _is_india else "Corpus Calculator")
                if _is_india:
                    st.info(
                        "Enter your desired retirement income and we'll calculate the **corpus** you need. "
                        "Assumes corpus invested in NPS / EPF / PPF / Equity Mutual Funds. "
                        "If you expect Pension or NPS annuity income, reduce your target accordingly."
                    )
                else:
                    st.info(
                        "Enter your desired retirement income and we'll calculate the pre-tax portfolio "
                        "you need. **v1 assumes the entire portfolio is pre-tax** (e.g. 401k / Traditional IRA). "
                        "If you expect Social Security or Roth income, reduce your target accordingly."
                    )

                # Results container declared here so it renders above the inputs
                _goal_results_container = st.container()
                st.markdown("---")

                col1, col2 = st.columns(2)
                with col1:
                    _income_label = (
                        "Desired after-tax annual income (₹) — Excluding Pension/NPS"
                        if _is_india else
                        "Desired after-tax annual income ($) — Excluding Social Security"
                    )
                    _income_help = (
                        """Typical Annual Needs (India):
• ₹3L–₹5L/yr:  Modest lifestyle
• ₹5L–₹8L/yr:  Comfortable lifestyle
• ₹8L–₹12L/yr: Enhanced lifestyle
• ₹12L+/yr:    Premium lifestyle

Consider:
• Housing (rent/EMI, maintenance)
• Healthcare (insurance, out-of-pocket)
• Daily living (food, utilities)
• Lifestyle (travel, family)

💡 Exclude Pension / NPS annuity — enter only the income you need from your corpus.
Use the Pension/NPS expander below to calculate your net target."""
                        if _is_india else
                        """Typical Annual Needs:
• $40K–$60K: Modest lifestyle
• $60K–$80K: Comfortable lifestyle
• $80K–$100K: Enhanced lifestyle
• $100K+: Premium lifestyle

Consider:
• Housing costs (rent/mortgage, taxes)
• Healthcare (insurance, out-of-pocket)
• Daily living (food, utilities)
• Lifestyle (travel, hobbies)

💡 Exclude Social Security — enter only the income you need from your portfolio.
Use the Social Security expander below to calculate your net target."""
                    )
                    goal_target_income = st.number_input(
                        _income_label,
                        min_value=0,
                        value=int(st.session_state.get("retirement_income_goal", 600000 if _is_india else 60000)),
                        step=10000 if _is_india else 1000,
                        key="goal_target_income",
                        help=_income_help,
                    )
                    if goal_target_income > 0:
                        st.info(f"💰 **Income Target**: {_fmt_currency(goal_target_income, _is_india)}/year from your {'corpus' if _is_india else 'portfolio'}")
                    else:
                        st.info("💡 **No target set** — enter a desired annual income above")

                    _tax_help = (
                        """Your effective tax rate on corpus withdrawals in retirement.

India New Tax Regime typical rates:
• 10–15%: Moderate income retiree
• 20–25%: Higher income retiree
• 30%+:   High income

💡 EPF / PPF withdrawals are tax-free. NPS: 60% lump sum is tax-free; annuity income is taxable.
Consult a tax professional for a personalized estimate."""
                        if _is_india else
                        """Your effective tax rate on withdrawals in retirement.

Typical ranges:
• 10–15%: Low income / heavy Roth
• 22–24%: Middle income (most retirees)
• 32%+: Higher income

💡 This applies uniformly to all withdrawals (v1 assumes 100% pre-tax assets).
Consult a tax professional for a personalized estimate."""
                    )
                    goal_tax_rate = st.slider(
                        "Retirement tax rate (%)",
                        min_value=0,
                        max_value=99,
                        value=int(st.session_state.get("whatif_retirement_tax_rate", 10 if _is_india else 22)),
                        key="goal_tax_rate",
                        help=_tax_help,
                    )
                    st.info(f"🧾 **Tax Rate**: {goal_tax_rate}% applied to all withdrawals")

                    goal_legacy = st.number_input(
                        f"Legacy / end-of-life {_corpus_label.lower()} goal ({_sym}) — Optional",
                        min_value=0,
                        value=int(st.session_state.get("legacy_goal", 0)),
                        step=100000 if _is_india else 10000,
                        key="goal_legacy",
                        help=(
                            f"""The amount you want remaining in your {_corpus_label.lower()} at end of life — this is NOT deducted at retirement.

The withdrawal simulation will preserve this amount so it can be passed on.

💡 Common range: ₹20L–₹2Cr
   (e.g., ₹50L as an inheritance for your family)

Modeled as a future-value target: the corpus must end at life expectancy with at least this balance."""
                            if _is_india else
                            f"""The amount you want remaining in your portfolio at end of life — this is NOT deducted at retirement.

The withdrawal simulation will preserve this amount so it can be passed on.

💡 Common range: $50,000–$500,000
   (e.g., $200,000 as an inheritance for your family)

Modeled as a future-value target: the portfolio must end at life expectancy with at least this balance."""
                        ),
                    )
                    if goal_legacy > 0:
                        st.info(f"🎯 **Legacy Goal**: {_fmt_currency(goal_legacy, _is_india)} remaining at end of plan")
                    else:
                        st.info(f"💡 **No legacy goal** — {_corpus_label.lower()} can be fully depleted at end of life")

                    goal_life_expenses = st.number_input(
                        f"One-Time Expenses at Retirement ({_sym}) — Optional",
                        min_value=0,
                        max_value=10_000_000,
                        value=int(st.session_state.get("life_expenses", 0)),
                        step=100_000 if _is_india else 10_000,
                        key="goal_life_expenses",
                        help=(
                            f"""A lump-sum amount deducted from your corpus at the moment you retire.

Examples:
• Paying off a remaining home loan
• Large medical or long-term care costs
• Down payment on a retirement home

💡 Common range: ₹5L–₹50L
   (e.g., ₹15L to clear a remaining home loan)

This amount is subtracted from your corpus before calculating sustainable income."""
                            if _is_india else
                            """A lump-sum amount deducted from your portfolio at the moment you retire.

Examples:
• Paying off a remaining mortgage
• Large medical or long-term care costs
• Down payment on a retirement home

💡 Common range: $50,000–$300,000
   (e.g., $150,000 to clear a remaining mortgage)

This amount is subtracted from your portfolio before calculating sustainable income."""
                        ),
                    )
                    if goal_life_expenses > 0:
                        st.info(f"💸 **One-Time Deduction**: {_fmt_currency(goal_life_expenses, _is_india)} at retirement")
                    else:
                        st.info("💡 **No one-time expenses set** — no deduction at retirement")

                with col2:
                    goal_retirement_age = st.number_input(
                        "Retirement age",
                        min_value=50,
                        max_value=80,
                        value=int(st.session_state.get("retirement_age", 60 if _is_india else 65)),
                        key="goal_retirement_age",
                        help=f"The age at which you plan to retire and begin drawing from your {'corpus' if _is_india else 'portfolio'}.",
                    )
                    st.info(f"⏰ **Retiring at**: age {goal_retirement_age}")

                    goal_life_expectancy = st.number_input(
                        "Life expectancy (age)",
                        min_value=60,
                        max_value=110,
                        value=int(st.session_state.get("life_expectancy", 85 if _is_india else 90)),
                        key="goal_life_expectancy",
                        help=(
                            """Average Life Expectancy (India):
• At birth: ~72 years (India avg)
• At age 30: ~75 years
• At age 60: ~80 years

Factors to Consider:
• Family history & health status
• Lifestyle (exercise, diet)
• Access to healthcare

💡 Tip: Plan to age 85–90 for safety."""
                            if _is_india else
                            """Average Life Expectancy:
• At birth: ~79 years (US avg)
• At age 30: ~80 years
• At age 50: ~82 years
• At age 65: ~85 years

Factors to Consider:
• Family history & health status
• Lifestyle (exercise, diet, smoking)
• Gender (women live 3–5 yrs longer)

💡 Tip: Add 5–10 years for safety."""
                        ),
                    )
                    _goal_years_in_ret = goal_life_expectancy - goal_retirement_age
                    st.info(f"⏳ **Years in Retirement**: {_goal_years_in_ret} years")

                    goal_growth_rate = st.slider(
                        f"{'Corpus' if _is_india else 'Portfolio'} growth rate in retirement (%)",
                        min_value=0,
                        max_value=15 if _is_india else 10,
                        value=int(round(st.session_state.get("whatif_retirement_growth_rate", 10.0 if _is_india else 4.0))),
                        key="goal_growth_rate",
                        help=(
                            """Expected annual corpus growth rate during retirement.

Typical assumptions (India):
• 6–7%:  Conservative (debt MF / FD-heavy)
• 8–10%: Moderate (balanced MF)
• 10–12%: Equity-heavy MF

💡 A SWP (Systematic Withdrawal Plan) from equity MFs at 8–10% growth is a common Indian retirement strategy."""
                            if _is_india else
                            """Expected annual portfolio growth rate during retirement.

Typical assumptions:
• 3–4%: Conservative (bonds-heavy)
• 5–6%: Moderate (balanced)
• 7–8%: Aggressive (stocks-heavy)

💡 Default 4% is a common conservative estimate for a balanced retirement portfolio."""
                        ),
                    )
                    st.info(f"📈 **Growth Rate**: {goal_growth_rate}%/year on {'corpus' if _is_india else 'portfolio'}")

                    goal_inflation_rate = st.slider(
                        "Inflation rate (%)",
                        min_value=0,
                        max_value=15 if _is_india else 10,
                        value=int(round(st.session_state.get("whatif_inflation_rate", 7.0 if _is_india else 3.0))),
                        key="goal_inflation_rate",
                        help=(
                            """Expected average annual inflation rate over your retirement.

Historical context (India):
• Long-run CPI average: ~5–7%
• Recent years: 4–7%
• RBI target: 4%

💡 Use 7% or above for conservative planning."""
                            if _is_india else
                            """Expected average annual inflation rate over your retirement.

Historical context:
• US long-run average: ~3%
• Recent (2021–2023): 4–8%
• Fed target: 2%

💡 Higher inflation erodes purchasing power — use 3% or above for safety."""
                        ),
                    )
                    st.info(f"💹 **Inflation Rate**: {goal_inflation_rate}%/year")

                # Sync Income Goal Calculator values back to the shared session state keys
                # so Personal Info, What-If analysis, and the forward calculator all stay in sync.
                st.session_state.retirement_income_goal = goal_target_income
                st.session_state.whatif_retirement_income_goal = goal_target_income
                st.session_state.whatif_retirement_tax_rate = goal_tax_rate
                st.session_state.legacy_goal = goal_legacy
                st.session_state.whatif_legacy_goal = goal_legacy
                st.session_state.life_expenses = goal_life_expenses
                st.session_state.whatif_life_expenses = goal_life_expenses
                st.session_state.retirement_age = goal_retirement_age
                st.session_state.whatif_retirement_age = goal_retirement_age
                st.session_state.life_expectancy = goal_life_expectancy
                st.session_state.whatif_life_expectancy = goal_life_expectancy
                st.session_state.whatif_retirement_growth_rate = goal_growth_rate
                st.session_state.whatif_inflation_rate = goal_inflation_rate

                # Validate before running
                _goal_errors = []
                if goal_life_expectancy <= goal_retirement_age:
                    _goal_errors.append("Life expectancy must be greater than retirement age.")
                if goal_target_income < 0:
                    _goal_errors.append("Target income cannot be negative.")
                if goal_legacy < 0:
                    _goal_errors.append("Legacy goal cannot be negative.")

                with _goal_results_container:
                    if _goal_errors:
                        for _err in _goal_errors:
                            st.error(_err)
                    else:
                        _r = find_required_portfolio(
                            target_after_tax_income=float(goal_target_income),
                            retirement_age=int(goal_retirement_age),
                            life_expectancy=int(goal_life_expectancy),
                            retirement_tax_rate_pct=float(goal_tax_rate),
                            growth_rate=float(goal_growth_rate) / 100.0,
                            inflation_rate=float(goal_inflation_rate) / 100.0,
                            legacy_goal=float(goal_legacy),
                            life_expenses=float(goal_life_expenses),
                        )
                        st.markdown("#### Results")
                        _rc1, _rc2 = st.columns(2)
                        _rc1.metric(f"Required {_corpus_label} at Retirement", _fmt_currency(_r['required_pretax_portfolio'], _is_india))
                        _rc2.metric("Modeled First-Year After-Tax Income", f"{_fmt_currency(_r['confirmed_income'], _is_india)}/yr")
                        if goal_legacy > 0:
                            st.caption(
                                f"Includes a **{_fmt_currency(goal_legacy, _is_india)} legacy goal** remaining at end of plan. "
                            )
                        if goal_life_expenses > 0:
                            st.caption(
                                f"Includes a **{_fmt_currency(goal_life_expenses, _is_india)} one-time deduction** at retirement."
                            )
                        _assets_assumption = "NPS / EPF / PPF / Equity MF corpus" if _is_india else "100% pre-tax assets"
                        st.caption(
                            f"Assumptions: {goal_growth_rate}% {'corpus' if _is_india else 'portfolio'} growth · {goal_inflation_rate}% inflation · "
                            f"{goal_tax_rate}% tax rate · {_r['years_in_retirement']} years in retirement · "
                            f"{_assets_assumption}"
                        )
                        if _is_india:
                            with st.expander("💡 How to account for Pension / NPS Annuity income"):
                                st.markdown("""
                                    Pension or NPS annuity income is **not included** in this calculation.
                                    If you expect regular income from these sources, reduce your income target accordingly.

                                    **Common sources of pension income in India:**
                                    - **NPS (National Pension System)**: At maturity, 60% is a tax-free lump sum; the remaining
                                      40% must be used to purchase an annuity (taxable income). Estimate your annuity income
                                      as roughly 5–6% of the 40% annuity portion per year.
                                    - **EPF Pension (EPS)**: If you contributed to EPS, you receive a monthly pension from age 58.
                                      Check your estimated pension on the **[EPFO Member Portal](https://unifiedportal-mem.epfindia.gov.in/)**.
                                    - **Government / Defence Pension**: If applicable, this is a fixed monthly pension.

                                    **Example:** If your goal is ₹8,00,000/yr after-tax and you expect ₹2,40,000/yr from
                                    NPS annuity + EPF pension, enter **₹5,60,000** as your income target here.
                                """)
                        else:
                            with st.expander("💡 How to account for Social Security income"):
                                st.markdown("""
                                    Social Security benefits are **not included** in this calculation. If you expect to receive
                                    Social Security, reduce your income target by your estimated annual benefit.

                                    **How to find your estimated benefit:**
                                    - Visit **[ssa.gov/myaccount](https://www.ssa.gov/myaccount)** and create a free account — it shows your personalized benefit estimates at different claiming ages (62, 67, 70, etc.)
                                    - Alternatively, use the **[SSA Quick Calculator](https://www.ssa.gov/OACT/quickcalc/)** for a rough estimate without logging in

                                    **Example:** If your goal is **US$80,000/yr** after-tax and you expect **US$24,000/yr**
                                    from Social Security, enter **US$56,000** as your income target here.
                                """)

                st.markdown("---")
                if st.button("← Previous: Personal Info", key="goal_mode_back_btn"):
                    st.session_state.pop("planning_mode_choice", None)
                    st.session_state.onboarding_step = 1
                    st.rerun()
                st.stop()

            # Simplified setup options (removed Default Portfolio and Legacy Mode)
            # Pre-select "Configure Individual Assets" if the user previously used it
            if 'setup_method_radio' not in st.session_state and 'num_assets_manual' in st.session_state:
                st.session_state.setup_method_radio = "Configure Individual Assets"

            setup_option = st.radio(
                "Choose how to configure your accounts:",
                ["**Upload Financial Statements (AI) - Recommended**", "Upload CSV File", "Configure Individual Assets"],
                key="setup_method_radio",
                help="Select how you want to add your retirement accounts"
            )
    
            # Track asset configuration method selected
            track_event('asset_config_method_selected', {'method': setup_option})

            # Initialize from session state to preserve user's work when switching modes
            assets: List[Asset] = list(st.session_state.get('assets', []))

            if setup_option == "**Upload Financial Statements (AI) - Recommended**":
                if not _N8N_AVAILABLE:
                    st.error("❌ **n8n integration not available**")
                    st.info("Please install required packages: `pip install pypdf python-dotenv requests`")
                else:
                    st.info("🤖 **AI-Powered Statement Upload**: Upload your financial PDFs and let AI extract your account data automatically.")
        
                    # Privacy and How It Works explanation
                    with st.expander("🔒 How It Works & Your Privacy", expanded=False):
                        st.markdown("""
                        ### 🤖 What Happens to Your Statements?
        
                        **Your privacy is our priority.** Here's exactly what happens when you upload:
        
                        #### 📋 The Process (Simple Version):
                        1. **Upload** → You select your PDF statements (401k, IRA, brokerage, etc.)
                        2. **Extract** → AI reads the PDFs to find account numbers, balances, and types
                        3. **Clean** → Personal information (SSN, address, full names) is automatically removed
                        4. **Organize** → Data is structured into a clean table for you to review
                        5. **You Control** → You can edit, delete, or clear any extracted data
        
                        ---
        
                        ### 🔐 Privacy & Security
        
                        **What we protect:**
                        - ✅ **Personal Identifiable Information (PII)** is automatically scrubbed
                        - ✅ **Social Security Numbers** are removed
                        - ✅ **Full names and addresses** are stripped out
                        - ✅ Only account types, balances, and institution names are kept
        
                        **What stays:**
                        - 📊 Account balances (needed for retirement planning)
                        - 🏦 Account types (401k, IRA, Roth, etc.)
                        - 🏢 Institution names (Fidelity, Vanguard, etc.)
                        - 🔢 Last 4 digits of account numbers (for your reference)
        
                        **Your data, your control:**
                        - 💾 Data is processed temporarily and not permanently stored
                        - ❌ No data is saved to our servers long-term
                        - 🔄 You can clear extracted data anytime with "Clear and Upload New"
                        - ✏️ You can edit any extracted information before using it
        
                        ---
        
                        ### 🛠️ Technical Details (For The Curious)
        
                        **AI Processing:**
                        - Uses GPT-4 to intelligently read and categorize your statements
                        - Identifies account types (401k, Roth IRA, Brokerage, etc.)
                        - Extracts current balances and tax treatment
                        - Handles complex statements with multiple account types
        
                        **Why it's better than manual:**
                        - ⏱️ **Faster**: Seconds instead of minutes per statement
                        - 🎯 **Accurate**: AI recognizes formats from 100+ financial institutions
                        - 🧠 **Smart**: Automatically categorizes tax treatments (pre-tax, post-tax, tax-free)
                        - 🔄 **Consistent**: Standardizes data across different statement formats
        
                        **Supported Documents:**
                        - 401(k) and 403(b) statements
                        - Traditional and Roth IRAs
                        - Brokerage account statements
                        - HSA statements
                        - Bank account statements
                        - Annuity statements
        
                        ---
        
                        ### ❓ Common Questions
        
                        **Q: Can I use scanned PDFs?**
                        A: Yes! The AI can read both digital PDFs and scanned documents.
        
                        **Q: What if extraction makes a mistake?**
                        A: You review and edit all extracted data before it's used. Plus, you can rate the accuracy to help us improve.
        
                        **Q: Is my data encrypted?**
                        A: Yes, all uploads use secure HTTPS encryption.
        
                        **Q: What happens to my PDFs after processing?**
                        A: PDFs are processed temporarily and deleted. Only the extracted data (balances, account types) is shown to you.
                        """)
        
                    # Initialize session state for extracted data
                    if 'ai_extracted_accounts' not in st.session_state:
                        st.session_state.ai_extracted_accounts = None
                    if 'ai_tax_buckets' not in st.session_state:
                        st.session_state.ai_tax_buckets = {}
                    if 'ai_warnings' not in st.session_state:
                        st.session_state.ai_warnings = []
                    if 'ai_edited_table' not in st.session_state:
                        st.session_state.ai_edited_table = None
        
                    # Initialize variables for this run
                    df_extracted = None
                    tax_buckets_by_account = {}
        
                    # Check if we already have extracted data
                    if st.session_state.ai_extracted_accounts is not None:
                        st.success(f"✅ Using previously extracted {len(st.session_state.ai_extracted_accounts)} accounts")
        
                        # Add button to clear and re-upload
                        if st.button("🔄 Clear and Upload New Statements", type="secondary"):
                            st.session_state.ai_extracted_accounts = None
                            st.session_state.ai_tax_buckets = {}
                            st.session_state.ai_warnings = []
                            st.session_state.ai_edited_table = None
                            # Clear widget states
                            if 'ai_table_data' in st.session_state:
                                del st.session_state.ai_table_data
                            # Clear initialization flag
                            if 'ai_table_initialized' in st.session_state:
                                del st.session_state.ai_table_initialized
                            st.rerun()

                        # Add button to edit accounts in modal
                        edit_accounts_clicked_existing = st.button("✏️ Edit Accounts", type="primary", key="edit_accounts_button")
                        if edit_accounts_clicked_existing:
                            edit_ai_accounts_dialog()

                        # Use existing data
                        df_extracted = st.session_state.ai_extracted_accounts

                        # Filter out internal/debug columns (those starting with underscore) and store clean version
                        if df_extracted is not None and hasattr(df_extracted, 'columns'):
                            # Filter columns
                            cols_to_keep = [col for col in df_extracted.columns if not col.startswith('_')]
                            df_extracted = df_extracted[cols_to_keep]
                            # Update session state with clean version to maintain same reference
                            st.session_state.ai_extracted_accounts = df_extracted

                        tax_buckets_by_account = st.session_state.ai_tax_buckets
                        warnings = st.session_state.ai_warnings

                        # Display warnings if any
                        if warnings and len(warnings) > 0:
                            with st.expander(f"⚠️ Processing Warnings ({len(warnings)})", expanded=False):
                                for warning in warnings:
                                    st.warning(warning)

                        # **NEW: Display the editable table for previously extracted data**
                        # This ensures the table persists when navigating between steps
                        if df_extracted is not None:
                            # Check if we have a properly formatted edited table in session state
                            # The edited table has the correct column structure for display
                            if 'ai_edited_table' in st.session_state and st.session_state.ai_edited_table is not None:
                                # Check if it has the expected display columns (not raw extraction columns)
                                # These are the key columns that indicate a properly formatted table
                                expected_cols = ["Account Name", "Current Balance", "Annual Contribution", "Growth Rate (%)", "Tax Treatment"]
                                if all(col in st.session_state.ai_edited_table.columns for col in expected_cols):
                                    # Use the formatted table with all user edits preserved
                                    df_display = st.session_state.ai_edited_table.copy()
                                else:
                                    # Fall back to raw extraction (user needs to clear and re-extract)
                                    df_display = None
                            else:
                                # No edited table yet (shouldn't happen in reload view)
                                df_display = None

                            if df_display is not None:
                                with st.expander("📋 Extracted Accounts", expanded=True):

                                    # Define column configuration - MUST MATCH the original extraction config
                                    # Note: Column widths adjusted to emphasize amounts over names
                                    column_config = {
                                        "#": st.column_config.TextColumn("#", disabled=True, help="Row number", width="small"),
                                        "Institution": st.column_config.TextColumn(
                                            "Institution",
                                            disabled=True,
                                            help="Financial institution (e.g., Fidelity, Morgan Stanley)",
                                            width="small"
                                        ),
                                        "Account Name": st.column_config.TextColumn(
                                            "Account Name",
                                            help="Account name/description from statement",
                                            width="small"
                                        ),
                                        "Last 4": st.column_config.TextColumn(
                                            "Last 4",
                                            disabled=True,
                                            help="Last 4 digits of account number",
                                            width="small"
                                        ),
                                        "Account Type": st.column_config.TextColumn(
                                            "Account Type",
                                            disabled=True,
                                            help="Type of account (401k, IRA, Savings, etc.)",
                                            width="small"
                                        ),
                                        "Tax Treatment": st.column_config.SelectboxColumn(
                                            "Tax Treatment",
                                            options=TAX_TREATMENT_OPTIONS,
                                            help="Tax treatment: Tax-Deferred (401k/IRA), Tax-Free (Roth), Post-Tax (Brokerage)"
                                        ),
                                        "Current Balance": st.column_config.NumberColumn(
                                            "Current Balance ($)",
                                            min_value=0,
                                            format="$%d",
                                            help="Current account balance"
                                        ),
                                        "Annual Contribution": st.column_config.NumberColumn(
                                            "Annual Contribution ($)",
                                            min_value=0,
                                            format="$%d",
                                            help="How much you contribute annually"
                                        ),
                                        "Growth Rate (%)": st.column_config.NumberColumn(
                                            "Growth Rate (%)",
                                            min_value=0.0,
                                            max_value=20.0,
                                            format="%.1f%%",
                                            help="Expected annual growth rate"
                                        ),
                                        "Tax Rate on Gains (%)": st.column_config.NumberColumn(
                                            "Tax Rate on Gains (%)",
                                            min_value=0.0,
                                            max_value=50.0,
                                            format="%.1f%%",
                                            help="Tax rate on gains (capital gains or income tax)"
                                        )
                                    }

                                    # Add optional column configs if they exist in the data
                                    if "Income Eligibility" in df_display.columns:
                                        column_config["Income Eligibility"] = st.column_config.TextColumn(
                                            "Income Eligibility",
                                            disabled=True,
                                            help="Income restrictions for this account type",
                                            width="small"
                                        )
                                    if "Purpose" in df_display.columns:
                                        column_config["Purpose"] = st.column_config.TextColumn(
                                            "Purpose",
                                            disabled=True,
                                            help="Primary purpose of this account",
                                            width="small"
                                        )

                                    # Display read-only table - use Edit button above to modify
                                    st.dataframe(
                                        df_display,
                                        column_config=column_config,
                                        use_container_width=True,
                                        hide_index=True
                                    )
                            else:
                                # No properly formatted table available - show message
                                st.warning("⚠️ Please click '🔄 Clear and Upload New Statements' above and re-extract your data.")
        
                        # CRITICAL: Convert edited table to assets on every rerun
                        # This ensures assets persist even when user changes personal info
                        if st.session_state.ai_edited_table is not None:
                            edited_df = st.session_state.ai_edited_table
                            try:
                                assets = [_asset_from_editor_row(row) for _, row in edited_df.iterrows()]
        
                                st.info(f"📊 Using {len(assets)} AI-extracted accounts for retirement analysis")
        
                            except Exception as e:
                                st.error(f"❌ Error loading AI-extracted accounts: {str(e)}")
                                st.info("💡 Try clicking '🔄 Clear and Upload New Statements' and re-uploading.")
        
                    else:
                        # Upload financial statement PDFs
                        uploaded_files = st.file_uploader(
                            "📤 Upload Financial Statement PDFs",
                            type=['pdf'],
                            accept_multiple_files=True,
                            help="Upload 401(k), IRA, brokerage, or bank statements"
                        )
        
                        if uploaded_files:
                            if st.button("🚀 Extract Account Data", type="primary", use_container_width=True):
                                import time
        
                                progress_bar = st.progress(0)
                                status_text = st.empty()
        
                                try:
                                    start_time = time.time()
        
                                    # Phase 1: Upload (0-30%)
                                    status_text.markdown("**📤 Phase 1/2: Uploading Files**")
                                    progress_bar.progress(10)
        
                                    # Initialize n8n client and prepare files
                                    client = N8NClient()
                                    files_to_upload = [(f.name, f.getvalue()) for f in uploaded_files]
        
                                    status_text.markdown(f"**📤 Phase 1/2: Uploading** {len(uploaded_files)} file(s) to AI processor...")
                                    progress_bar.progress(25)
        
                                    # Phase 2: Processing (30-90%)
                                    status_text.markdown("**🤖 Phase 2/2: AI Processing** - Analyzing statements with GPT-4...may take up to one-to-two minutes")
                                    progress_bar.progress(40)

                                    # Create placeholder for timer that we can clear later
                                    timer_placeholder = st.empty()

                                    # Add live timer using components.html for immediate rendering
                                    with timer_placeholder.container():
                                        components.html("""
                                            <div id="ai-timer" style="font-size: 1.2em; color: #0066CC; font-weight: 600; margin: 10px 0; font-family: 'Source Sans Pro', sans-serif;">
                                                ⏱️ Processing time: <span id="timer-value">0s</span>
                                            </div>
                                            <script>
                                                let startTime = Date.now();
                                                setInterval(function() {
                                                    let elapsed = Math.floor((Date.now() - startTime) / 1000);
                                                    let timerElement = document.getElementById('timer-value');
                                                    if (timerElement) {
                                                        timerElement.textContent = elapsed + 's';
                                                    }
                                                }, 1000);
                                            </script>
                                        """, height=50)

                                    # Make the actual API call (blocking)
                                    ai_start_time = time.time()
                                    result = client.upload_statements(files_to_upload)
                                    ai_elapsed = time.time() - ai_start_time

                                    # Hide the timer now that processing is complete
                                    timer_placeholder.empty()

                                    # Show completion with total time
                                    total_time = time.time() - start_time
                                    progress_bar.progress(90)
        
                                    if result['success']:
                                        progress_bar.progress(100)
                                        status_text.markdown(f"**✅ Extraction Complete!** (AI processing: {ai_elapsed:.1f}s | Total: {total_time:.1f}s)")
        
                                        # Parse response (handle both JSON and CSV formats)
                                        response_format = result.get('format', 'csv')
                                        tax_buckets_by_account = {}
        
                                        if response_format == 'json':
                                            # Split accounts with multiple tax sources BEFORE creating DataFrame
                                            split_accounts = []
                                            for account in result['data']:
                                                # Check if account has multiple non-zero tax sources
                                                raw_tax_sources = account.get('_raw_tax_sources', [])
                                                non_zero_sources = [s for s in raw_tax_sources if s.get('balance', 0) > 0]
        
                                                if len(non_zero_sources) > 1:
                                                    # Split into separate accounts
                                                    for source in non_zero_sources:
                                                        split_account = account.copy()
                                                        source_label = source['label']
                                                        source_balance = source['balance']
        
                                                        # Determine tax treatment from source label
                                                        if 'roth' in source_label.lower():
                                                            tax_treatment = 'tax_free'
                                                            suffix = '- Roth'
                                                        elif 'after tax' in source_label.lower() or 'after-tax' in source_label.lower():
                                                            tax_treatment = 'post_tax'
                                                            suffix = '- After-Tax'
                                                        else:  # Employee Deferral, Traditional, etc.
                                                            tax_treatment = 'tax_deferred'
                                                            suffix = '- Traditional'
        
                                                        # Update split account
                                                        split_account['account_name'] = f"{account.get('account_name', '401k')} {suffix}"
                                                        split_account['ending_balance'] = source_balance
                                                        split_account['tax_treatment'] = tax_treatment
                                                        split_account['_tax_source_label'] = source_label
                                                        # Remove _raw_tax_sources to avoid confusion
                                                        split_account.pop('_raw_tax_sources', None)
        
                                                        split_accounts.append(split_account)
                                                else:
                                                    # Keep account as-is
                                                    split_accounts.append(account)
        
                                            # Save tax_buckets or raw_tax_sources before converting to DataFrame
                                            for idx, account in enumerate(split_accounts):
                                                account_id = account.get('account_id') or account.get('account_name') or f"account_{idx}"
        
                                                # Check for processed tax_buckets first
                                                if 'tax_buckets' in account and account['tax_buckets']:
                                                    tax_buckets_by_account[account_id] = account['tax_buckets']
                                                # Fall back to raw_tax_sources if available
                                                elif '_raw_tax_sources' in account and account['_raw_tax_sources']:
                                                    # Convert raw_tax_sources to bucket format for display
                                                    raw_sources = account['_raw_tax_sources']
                                                    buckets = []
                                                    for source in raw_sources:
                                                        if source.get('balance', 0) > 0:  # Only show non-zero balances
                                                            # Map label to tax treatment
                                                            label = source['label'].lower()
                                                            if 'roth' in label:
                                                                tax_treatment_bucket = 'tax_free'
                                                            elif 'after tax' in label or 'after-tax' in label:
                                                                tax_treatment_bucket = 'post_tax'
                                                            else:  # Employee deferral, traditional, etc.
                                                                tax_treatment_bucket = 'tax_deferred'
        
                                                            buckets.append({
                                                                'bucket_type': source['label'],
                                                                'tax_treatment': tax_treatment_bucket,
                                                                'balance': source['balance']
                                                            })
                                                    if buckets:
                                                        tax_buckets_by_account[account_id] = buckets
        
                                            # JSON format - already a list of dicts
                                            df_extracted = pd.DataFrame(split_accounts)
                                            # Rename JSON fields if needed
                                            column_mapping = {
                                                'account_name': 'label',
                                                'ending_balance': 'value',
                                                'balance_as_of_date': 'period_end',
                                                'institution': 'document_type',
                                                'account_id': 'account_id'
                                            }
                                            df_extracted = df_extracted.rename(columns={k: v for k, v in column_mapping.items() if k in df_extracted.columns})

                                            # Filter out internal/debug columns (those starting with underscore)
                                            df_extracted = df_extracted[[col for col in df_extracted.columns if not col.startswith('_')]]
                                        else:
                                            # CSV format
                                            csv_content = result['data']
                                            df_extracted = pd.read_csv(io.StringIO(csv_content))

                                        # Convert to numeric
                                        if 'value' in df_extracted.columns:
                                            df_extracted['value'] = pd.to_numeric(df_extracted['value'], errors='coerce')
                                        elif 'ending_balance' in df_extracted.columns:
                                            df_extracted['value'] = pd.to_numeric(df_extracted['ending_balance'], errors='coerce')
        
                                        # Store in session state for persistence across reruns
                                        st.session_state.ai_extracted_accounts = df_extracted
                                        st.session_state.ai_tax_buckets = tax_buckets_by_account
                                        st.session_state.ai_warnings = result.get('warnings', [])
    
                                        # Track successful statement upload
                                        track_statement_upload(
                                            success=True,
                                            num_statements=len(uploaded_files),
                                            num_accounts=len(df_extracted)
                                        )
    
                                        st.success(f"✅ Extracted {len(df_extracted)} accounts from your statements!")
                                        st.info("💡 **Data saved!** You can now edit other fields without losing your extracted accounts.")
        
                                        # Edit button (outside expander for reliability)
                                        edit_accounts_clicked_fresh = st.button("✏️ Edit Accounts", type="primary", key="edit_accounts_button")
                                        if edit_accounts_clicked_fresh:
                                            edit_ai_accounts_dialog()

                                        # Display warnings if any
                                        warnings = st.session_state.ai_warnings
                                        if warnings and len(warnings) > 0:
                                            with st.expander(f"⚠️ Processing Warnings ({len(warnings)})", expanded=False):
                                                for warning in warnings:
                                                    st.warning(warning)
                                                                                     
                                        # Map extracted data to Asset objects

                                        with st.expander("📋 Extracted Accounts", expanded=True):
        
                                            # Helper function to humanize account type
                                            def humanize_account_type(account_type: str) -> str:
                                                """Convert account_type codes to human-readable format."""
                                                if not account_type:
                                                    return 'Unknown'
        
                                                mappings = {
                                                    '401k': '401(k)',
                                                    'ira': 'IRA',
                                                    'roth_ira': 'Roth IRA',
                                                    'traditional_ira': 'Traditional IRA',
                                                    'rollover_ira': 'Rollover IRA',
                                                    'savings': 'Savings Account',
                                                    'checking': 'Checking Account',
                                                    'brokerage': 'Brokerage Account',
                                                    'hsa': 'HSA (Health Savings Account)',
                                                    'high yield savings': 'High Yield Savings',
                                                    'stock_plan': 'Stock Plan',
                                                    'roth': 'Roth IRA',
                                                    '403b': '403(b)',
                                                    '457': '457 Plan'
                                                }
                                                account_type_lower = str(account_type).lower().strip()
        
                                                # Check exact match first
                                                if account_type_lower in mappings:
                                                    return mappings[account_type_lower]
        
                                                # Check if it contains key patterns
                                                for key, value in mappings.items():
                                                    if key in account_type_lower:
                                                        return value
        
                                                # Default: title case with underscores removed
                                                return account_type.replace('_', ' ').title()
        
                                            # Check if we already have edited table data in session state
                                            if st.session_state.ai_edited_table is not None:
                                                # Use previously edited table
                                                df_table = st.session_state.ai_edited_table
                                            else:
                                                # Create editable table from extracted data (first time)
                                                table_data = []
                                                for idx, row in df_extracted.iterrows():
                                                    # Get account type first (we'll need it for inference)
                                                    account_type_raw = row.get('account_type', '')
                                                    account_type = humanize_account_type(account_type_raw)
        
                                                    # Map tax_treatment to AssetType (human-readable)
                                                    # If tax_treatment is missing, infer from account_type
                                                    tax_treatment = str(row.get('tax_treatment', '')).lower()
            
                                                    if not tax_treatment or tax_treatment == 'nan':
                                                        # Infer from account_type
                                                        account_type_lower = str(account_type_raw).lower()
                                                        if account_type_lower in ['401k', '403b', '457', 'ira', 'traditional_ira']:
                                                            tax_treatment = 'tax_deferred'
                                                        elif account_type_lower in ['roth_401k', 'roth_ira', 'roth_403b']:
                                                            tax_treatment = 'tax_free'
                                                        elif account_type_lower == 'hsa':
                                                            tax_treatment = 'tax_deferred'  # HSA is tax-deferred
                                                        else:
                                                            tax_treatment = 'post_tax'  # brokerage, savings, checking
            
                                                    # Map to display value
                                                    if tax_treatment == 'pre_tax' or tax_treatment == 'tax_deferred':
                                                        asset_type_display = 'Tax-Deferred'
                                                    elif tax_treatment == 'post_tax':
                                                        asset_type_display = 'Post-Tax'
                                                    elif tax_treatment == 'tax_free':
                                                        asset_type_display = 'Tax-Free'
                                                    else:
                                                        asset_type_display = 'Post-Tax'  # default
            
                                                    # Get account name and humanize it
                                                    account_name_raw = str(row.get('label', f"Account {idx+1}"))
            
                                                    # Helper function to humanize account names
                                                    def humanize_account_name(name: str) -> str:
                                                        """Convert raw account names to human-readable format."""
                                                        # Handle common patterns
                                                        name_clean = name.strip()
            
                                                        # Stock plans - extract company and plan type
                                                        if 'STOCK PLAN' in name_clean.upper():
                                                            # "STOCK PLAN - MICROSOFT ESPP PLAN" → "Microsoft ESPP"
                                                            # "STOCK PLAN - ORACLE STOCK OPTIONS" → "Oracle Stock Options"
                                                            parts = name_clean.split('-')
                                                            if len(parts) >= 2:
                                                                plan_details = parts[1].strip()
                                                                # Extract company name (first word) and plan type
                                                                words = plan_details.split()
                                                                if len(words) >= 2:
                                                                    company = words[0].title()
                                                                    if 'ESPP' in plan_details.upper():
                                                                        return f"{company} ESPP"
                                                                    elif 'STOCK OPTION' in plan_details.upper():
                                                                        return f"{company} Stock Options"
                                                                    elif 'RSU' in plan_details.upper():
                                                                        return f"{company} RSUs"
                                                                    else:
                                                                        plan_type = ' '.join(words[1:]).title()
                                                                        return f"{company} {plan_type}"
            
                                                        # Brokerage accounts
                                                        if 'at Work Self-Directed' in name_clean:
                                                            # "Morgan Stanley at Work Self-Directed Account" → "Morgan Stanley Brokerage"
                                                            institution = name_clean.split(' at Work')[0]
                                                            return f"{institution} Brokerage"
            
                                                        # Generic brokerage account shortening
                                                        if name_clean.lower() == 'brokerage account':
                                                            return 'Brokerage'
            
                                                        # Fix common formatting issues
                                                        replacements = {
                                                            'rollover_ira': 'Rollover IRA',
                                                            'roth_ira': 'Roth IRA',
                                                            'traditional_ira': 'Traditional IRA',
                                                            'health_savings_account': 'HSA',
                                                            '401k': '401(k)',
                                                            '403b': '403(b)',
                                                            '457': '457(b)',
                                                        }
            
                                                        name_lower = name_clean.lower()
                                                        for key, value in replacements.items():
                                                            if key == name_lower:
                                                                return value
                                                            # Also handle patterns like "401k - Traditional"
                                                            if name_lower.startswith(key):
                                                                suffix = name_clean[len(key):].strip()
                                                                return f"{value}{suffix}"
            
                                                        # Title case for all-caps names
                                                        if name_clean.isupper():
                                                            return name_clean.title()
            
                                                        # Return as-is if no pattern matches
                                                        return name_clean
            
                                                    account_name = humanize_account_name(account_name_raw)
            
                                                    # Get institution and account number for display
                                                    institution = str(row.get('document_type', ''))  # Institution is stored in document_type
                                                    account_number_last4 = str(row.get('account_number_last4', '')) if pd.notna(row.get('account_number_last4')) else ''
            
                                                    # Get current balance
                                                    current_balance = float(row.get('value', 0))
            
                                                    # Helper function to humanize income eligibility
                                                    def humanize_eligibility(value: str) -> str:
                                                        mappings = {
                                                            'eligible': '✅ Eligible',
                                                            'conditionally_eligible': '⚠️ Conditionally Eligible',
                                                            'not_eligible': '❌ Not Eligible'
                                                        }
                                                        return mappings.get(str(value).lower(), value)
            
                                                    # Helper function to humanize purpose
                                                    def humanize_purpose(value: str) -> str:
                                                        mappings = {
                                                            'income': 'Retirement Income',
                                                            'general_income': 'General Income',
                                                            'healthcare_only': 'Healthcare Only (HSA)',
                                                            'education_only': 'Education Only (529)',
                                                            'employment_compensation': 'Employment Compensation',
                                                            'restricted_other': 'Restricted/Other'
                                                        }
                                                        return mappings.get(str(value).lower(), value)
            
                                                    # Get income eligibility and purpose if available
                                                    income_eligibility = row.get('income_eligibility', '')
                                                    purpose = row.get('purpose', '')
            
                                                    # Set default growth rate based on account type
                                                    account_type_lower = str(account_type_raw).lower()
                                                    if account_type_lower in ['savings', 'checking']:
                                                        account_growth_rate = 3.0  # HYSA/Savings: conservative rate
                                                    else:
                                                        # Use the user's default growth rate for all investment accounts
                                                        account_growth_rate = 7
            
                                                    _, inferred_behavior, default_tax_rate = _resolve_tax_settings(
                                                        asset_type_display,
                                                        account_name,
                                                        0.0,
                                                    )

                                                    table_row = {
                                                        "#": f"#{idx+1}",
                                                        "Institution": institution,
                                                        "Account Name": account_name,
                                                        "Last 4": account_number_last4,
                                                        "Account Type": account_type,
                                                        "Tax Treatment": "Post-Tax" if inferred_behavior == TaxBehavior.NO_ADDITIONAL_TAX else asset_type_display,
                                                        "Current Balance": current_balance,
                                                        "Annual Contribution": 0.0,  # User needs to fill
                                                        "Growth Rate (%)": account_growth_rate,
                                                        "Tax Rate on Gains (%)": default_tax_rate
                                                    }
            
                                                    # Add income eligibility if available
                                                    if income_eligibility:
                                                        table_row["Income Eligibility"] = humanize_eligibility(income_eligibility)
            
                                                    # Add purpose if available
                                                    if purpose:
                                                        table_row["Purpose"] = humanize_purpose(purpose)
            
                                                    table_data.append(table_row)
        
                                                # Create DataFrame from table_data
                                                df_table = pd.DataFrame(table_data)

                                                # Initialize ai_edited_table ONLY on first extraction
                                                # Use a flag to prevent overwriting user edits on reruns
                                                if 'ai_table_initialized' not in st.session_state:
                                                    st.session_state.ai_edited_table = df_table.copy()
                                                    st.session_state.ai_table_initialized = True

                                            #st.info("💡 **Edit your data in the table. Changes save automatically as you type.**")

                                            # Define column configuration
                                            # Note: Column widths adjusted to emphasize amounts over names
                                            column_config = {
                                                "#": st.column_config.TextColumn("#", disabled=True, help="Row number", width="small"),
                                                "Institution": st.column_config.TextColumn(
                                                    "Institution",
                                                    disabled=True,
                                                    help="Financial institution (e.g., Fidelity, Morgan Stanley)",
                                                    width="small"
                                                ),
                                                "Account Name": st.column_config.TextColumn(
                                                    "Account Name",
                                                    help="Account name/description from statement",
                                                    width="small"
                                                ),
                                                "Last 4": st.column_config.TextColumn(
                                                    "Last 4",
                                                    disabled=True,
                                                    help="Last 4 digits of account number",
                                                    width="small"
                                                ),
                                                "Account Type": st.column_config.TextColumn(
                                                    "Account Type",
                                                    disabled=True,
                                                    help="Type of account (401k, IRA, Savings, etc.) - extracted from statement",
                                                    width="small"
                                                ),
                                                "Tax Treatment": st.column_config.SelectboxColumn(
                                                    "Tax Treatment",
                                                    options=TAX_TREATMENT_OPTIONS,
                                                    help="Tax treatment: Tax-Deferred (401k/IRA), Tax-Free (Roth IRA/Roth 401k), Post-Tax (Brokerage/Savings)"
                                                ),
                                                "Current Balance": st.column_config.NumberColumn(
                                                    "Current Balance ($)",
                                                    min_value=0,
                                                    format="$%d",
                                                    help="Current account balance (extracted from statements)"
                                                ),
                                                "Annual Contribution": st.column_config.NumberColumn(
                                                    "Annual Contribution ($)",
                                                    min_value=0,
                                                    format="$%d",
                                                    help="How much you contribute annually to this account"
                                                ),
                                                "Growth Rate (%)": st.column_config.NumberColumn(
                                                    "Growth Rate (%)",
                                                    min_value=0,
                                                    max_value=50,
                                                    format="%.1f%%",
                                                    help=f"Expected annual growth rate (your default: {7}%)"
                                                ),
                                                "Tax Rate on Gains (%)": st.column_config.NumberColumn(
                                                    "Tax Rate on Gains (%)",
                                                    min_value=0,
                                                    max_value=50,
                                                    format="%.1f%%",
                                                    help="Tax rate on GAINS only: 0% for Roth/Tax-Deferred, 15% for brokerage capital gains"
                                                ),
                                                "Income Eligibility": st.column_config.TextColumn(
                                                    "Income Eligibility",
                                                    disabled=True,
                                                    help="Can this account be used for retirement income? ✅ Eligible, ⚠️ Conditionally Eligible, ❌ Not Eligible"
                                                ),
                                                "Purpose": st.column_config.TextColumn(
                                                    "Purpose",
                                                    disabled=True,
                                                    help="Primary purpose of this account (e.g., Retirement Income, Healthcare, Education)"
                                                )
                                            }

                                            # Display editable table - auto-saves on every change
                                            edited_df = st.data_editor(
                                                st.session_state.ai_edited_table if st.session_state.ai_edited_table is not None else df_table,
                                                column_config=column_config,
                                                use_container_width=True,
                                                hide_index=True,
                                                num_rows="dynamic",
                                                key="ai_table_data"
                                            )

                                            # Auto-save edited data to session state
                                            st.session_state.ai_edited_table = edited_df

                                            # Extraction Quality Feedback Module
                                            st.markdown("---")
                                            st.markdown("#### 💬 Data Extraction Feedback")
                                            st.info("📊 **How accurate is the extracted data?** Your feedback helps us improve AI extraction quality.")
        
                                            feedback_col1, feedback_col2, feedback_col3 = st.columns([1, 1, 3])
        
                                            with feedback_col1:
                                                if st.button("👍 Looks Good", key="extraction_feedback_good", use_container_width=True, type="secondary"):
                                                    # Positive feedback - send email
                                                    subject = "AI Extraction Feedback - Accurate Data"
                                                    body = f"""Hi Smart Retire AI team,
        
        The AI extraction worked great! Here are the details:
        
        Number of accounts extracted: {len(edited_df)}
        Institution(s): {', '.join(edited_df['Institution'].unique())}
        
        The extracted data was accurate and saved me time.
        
        Thank you!
        """
                                                    # URL encode the body
                                                    body_encoded = body.replace(' ', '%20').replace('\n', '%0D%0A')
                                                    email_url = f"mailto:smartretireai@gmail.com?subject={subject}&body={body_encoded}"
                                                    st.markdown(f"✅ **Thanks for the feedback!** [Click here to send details]({email_url}) (optional)")
        
                                            with feedback_col2:
                                                if st.button("👎 Needs Work", key="extraction_feedback_bad", use_container_width=True, type="secondary"):
                                                    # Negative feedback - show form
                                                    st.session_state.show_extraction_feedback_form = True
        
                                            # Show detailed feedback form if user clicked "Needs Work"
                                            if st.session_state.get('show_extraction_feedback_form', False):
                                                st.markdown("---")
                                                st.markdown("##### 📝 Tell us what went wrong")
        
                                                with st.form("extraction_feedback_form", clear_on_submit=True):
                                                    issue_type = st.multiselect(
                                                        "What issues did you encounter? (Select all that apply)",
                                                        [
                                                            "Wrong account balances",
                                                            "Incorrect account types",
                                                            "Wrong tax classification",
                                                            "Missing accounts",
                                                            "Duplicate accounts",
                                                            "Wrong institution name",
                                                            "Account numbers incorrect",
                                                            "Other"
                                                        ]
                                                    )
        
                                                    specific_issues = st.text_area(
                                                        "Specific details about the issue:",
                                                        placeholder="E.g., 'My 401k balance was extracted as $50,000 but should be $75,000' or 'Roth IRA was classified as Tax-Deferred instead of Tax-Free'",
                                                        height=100
                                                    )
        
                                                    statement_type = st.text_input(
                                                        "Statement type/institution (optional):",
                                                        placeholder="E.g., 'Fidelity 401k' or 'Vanguard Roth IRA'"
                                                    )
        
                                                    submit_feedback = st.form_submit_button("📧 Send Feedback", type="primary", use_container_width=True)
        
                                                    if submit_feedback:
                                                        if issue_type and specific_issues:
                                                            # Generate email
                                                            subject = "AI Extraction Issue Report"
                                                            issues_list = '\n'.join([f"- {issue}" for issue in issue_type])
                                                            body = f"""Hi Smart Retire AI team,
        
        I encountered issues with the AI extraction feature:
        
        ISSUES ENCOUNTERED:
        {issues_list}
        
        SPECIFIC DETAILS:
        {specific_issues}
        
        STATEMENT INFO:
        {statement_type if statement_type else 'Not provided'}
        
        NUMBER OF ACCOUNTS: {len(edited_df)}
        INSTITUTIONS: {', '.join(edited_df['Institution'].unique())}
        
        Please investigate and improve the extraction accuracy.
        
        Thank you!
        """
                                                            # URL encode the body
                                                            body_encoded = body.replace(' ', '%20').replace('\n', '%0D%0A')
                                                            email_url = f"mailto:smartretireai@gmail.com?subject={subject}&body={body_encoded}"
                                                            st.success("✅ Thank you for the detailed feedback!")
                                                            st.markdown(f"📧 [Click here to send your feedback via email]({email_url})")
                                                            st.session_state.show_extraction_feedback_form = False
                                                        else:
                                                            st.error("⚠️ Please select at least one issue type and provide specific details.")
        
                                            # Display tax bucket breakdowns if available
                                            if tax_buckets_by_account:
                                                st.markdown("---")
                                                st.markdown("#### 🔍 Tax Bucket Breakdown")
                                                st.info("**Detailed tax source breakdown for retirement accounts with multiple tax treatments**")
        
                                                for account_id, buckets in tax_buckets_by_account.items():
                                                    # Find account name in DataFrame
                                                    account_row = df_extracted[df_extracted.get('account_id') == account_id] if 'account_id' in df_extracted.columns else None
                                                    if account_row is not None and not account_row.empty:
                                                        account_name = account_row.iloc[0].get('label', account_id)
                                                    else:
                                                        account_name = account_id
        
                                                    with st.expander(f"📊 {account_name}"):
                                                        # Create DataFrame for buckets
                                                        bucket_df = pd.DataFrame(buckets)
        
                                                        # Humanize bucket_type and tax_treatment
                                                        def humanize_bucket(value: str) -> str:
                                                            mappings = {
                                                                'traditional_401k': 'Traditional 401(k)',
                                                                'roth_in_plan_conversion': 'Roth In-Plan Conversion',
                                                                'after_tax_401k': 'After-Tax 401(k)',
                                                                'tax_deferred': 'Tax-Deferred',
                                                                'tax_free': 'Tax-Free',
                                                                'post_tax': 'Post-Tax',
                                                                'pre_tax': 'Pre-Tax'
                                                            }
                                                            return mappings.get(str(value).lower(), value)
        
                                                        if 'bucket_type' in bucket_df.columns:
                                                            bucket_df['bucket_type'] = bucket_df['bucket_type'].apply(humanize_bucket)
                                                        if 'tax_treatment' in bucket_df.columns:
                                                            bucket_df['tax_treatment'] = bucket_df['tax_treatment'].apply(humanize_bucket)
        
                                                        # Format balance as currency
                                                        if 'balance' in bucket_df.columns:
                                                            total_bucket_balance = bucket_df['balance'].sum()
                                                            bucket_df['balance'] = bucket_df['balance'].apply(lambda x: f"${x:,.2f}")
        
                                                        # Rename columns
                                                        bucket_df = bucket_df.rename(columns={
                                                            'bucket_type': 'Tax Bucket',
                                                            'tax_treatment': 'Tax Treatment',
                                                            'balance': 'Balance'
                                                        })
        
                                                        st.dataframe(bucket_df, use_container_width=True, hide_index=True)
        
                                                        # Show total
                                                        st.metric("Total", f"${total_bucket_balance:,.2f}")
        
                                            # Convert edited dataframe to Asset objects
                                            if not edited_df.empty:
                                                try:
                                                    assets = [_asset_from_editor_row(row) for _, row in edited_df.iterrows()]
        
                                                    st.success(f"✅ {len(assets)} accounts ready for retirement analysis!")
        
                                                except Exception as e:
                                                    st.error(f"❌ Error processing extracted data: {str(e)}")
                                                    st.info("💡 Please check the values in the table.")
        
                                    else:
                                        # Track failed statement upload
                                        track_statement_upload(
                                            success=False,
                                            num_statements=len(uploaded_files),
                                            num_accounts=0
                                        )
                                        track_error('statement_upload_failed', result.get('error', 'Unknown error'), {
                                            'num_files': len(uploaded_files)
                                        })
    
                                        progress_bar.progress(100)
                                        status_text.text("✗ Extraction failed")
                                        st.error(f"Extraction Error: {result.get('error', 'Unknown error')}")
        
                                except N8NError as e:
                                    # Track N8N configuration error
                                    track_statement_upload(success=False, num_statements=len(uploaded_files), num_accounts=0)
                                    track_error('statement_upload_n8n_error', str(e), {'num_files': len(uploaded_files)})
    
                                    progress_bar.progress(100)
                                    status_text.text("✗ Configuration error")
                                    st.error(f"Configuration Error: {str(e)}")
                                    st.info("💡 Make sure your .env file has the N8N_WEBHOOK_URL configured.")
    
                                except Exception as e:
                                    # Track unexpected error
                                    track_statement_upload(success=False, num_statements=len(uploaded_files), num_accounts=0)
                                    track_error('statement_upload_error', str(e), {'num_files': len(uploaded_files)})
    
                                    progress_bar.progress(100)
                                    status_text.text("✗ Unexpected error")
                                    st.error(f"Error: {str(e)}")
        
            elif setup_option == "Upload CSV File":
                st.info("📁 **CSV Upload Method**: Download a template, modify it with your data, then upload it back.")
                
                # Download template button
                csv_template = create_asset_template_csv()
                st.download_button(
                    label="📥 Download CSV Template",
                    data=csv_template,
                    file_name="asset_template.csv",
                    mime="text/csv",
                    help="Download a pre-filled template with example data"
                )
                
                # Upload file
                uploaded_file = st.file_uploader(
                    "📤 Upload Your CSV File",
                    type=['csv'],
                    help="Upload your modified CSV file with your asset data"
                )

                if uploaded_file is not None:
                    try:
                        # Check if this is a new file upload or the same file on rerun
                        file_id = f"{uploaded_file.name}_{uploaded_file.size}"
                        is_new_upload = ('csv_uploaded_file_id' not in st.session_state or
                                        st.session_state.csv_uploaded_file_id != file_id)

                        if is_new_upload:
                            # This is a new file - parse it and reset everything
                            csv_content = uploaded_file.read().decode('utf-8')
                            assets, csv_warnings = parse_uploaded_csv(csv_content)
                            for w in csv_warnings:
                                st.info(f"ℹ️ {w}")

                            # Store file ID and assets in session state
                            st.session_state.csv_uploaded_file_id = file_id
                            st.session_state.csv_uploaded_assets = assets

                            # Clear previous edits when a new file is uploaded
                            if 'csv_uploaded_edited_table' in st.session_state:
                                del st.session_state.csv_uploaded_edited_table

                            st.success(f"✅ Successfully loaded {len(assets)} assets from CSV file!")
                        else:
                            # Same file on rerun - use assets from session state
                            if 'csv_uploaded_assets' in st.session_state:
                                assets = st.session_state.csv_uploaded_assets
                        
                        # Show uploaded assets in editable table format
                        with st.expander("📋 Uploaded Assets (Editable)", expanded=True):
                            # Helper function to convert asset type to human-readable format
                            # Create editable table data
                            table_data = []
                            for i, asset in enumerate(assets):
                                row = {
                                    "Index": i,
                                    "Account Name": asset.name,
                                    "Tax Treatment": _asset_to_tax_treatment_label(asset),
                                    "Current Balance": asset.current_balance,
                                    "Annual Contribution": asset.annual_contribution,
                                    "Growth Rate (%)": asset.growth_rate_pct,
                                    "Tax Rate on Gains (%)": asset.tax_rate_pct
                                }
                                table_data.append(row)
                            
                            # Create editable dataframe
                            df = pd.DataFrame(table_data)

                            # Define column configuration for editing
                            column_config = {
                                "Index": st.column_config.NumberColumn("Index", disabled=True, help="Asset index (read-only)"),
                                "Account Name": st.column_config.TextColumn("Account Name", help="Name of the account"),
                                "Tax Treatment": st.column_config.SelectboxColumn(
                                    "Tax Treatment",
                                    options=TAX_TREATMENT_OPTIONS,
                                    help="Tax treatment: Tax-Deferred (401k/Traditional IRA), Tax-Free (Roth IRA/Roth 401k), Post-Tax (Brokerage/Savings)"
                                ),
                                "Current Balance": st.column_config.NumberColumn(
                                    "Current Balance ($)",
                                    min_value=0,
                                    format="$%d",
                                    help="Current account balance"
                                ),
                                "Annual Contribution": st.column_config.NumberColumn(
                                    "Annual Contribution ($)",
                                    min_value=0,
                                    format="$%d",
                                    help="Annual contribution amount"
                                ),
                                "Growth Rate (%)": st.column_config.NumberColumn(
                                    "Growth Rate (%)",
                                    min_value=0,
                                    max_value=50,
                                    format="%.1f%%",
                                    help=f"Expected annual growth rate (your default: {7}%)"
                                ),
                                "Tax Rate on Gains (%)": st.column_config.NumberColumn(
                                    "Tax Rate on Gains (%)",
                                    min_value=0,
                                    max_value=50,
                                    format="%.1f%%",
                                    help="Tax rate on GAINS only: 0% for Roth/Tax-Deferred, 15% for brokerage capital gains"
                                )
                            }

                            # Use edited table from session state if it exists, otherwise use fresh data
                            # This prevents losing user edits on rerun
                            if 'csv_uploaded_edited_table' in st.session_state and st.session_state.csv_uploaded_edited_table is not None:
                                # Preserve user edits across reruns
                                initial_data = st.session_state.csv_uploaded_edited_table
                            else:
                                # First time showing the table
                                initial_data = df

                            # Display editable table
                            st.info("💡 **Edit your assets directly in the table below. Changes will be applied when you run the analysis.**")
                            edited_df = st.data_editor(
                                initial_data,
                                column_config=column_config,
                                use_container_width=True,
                                hide_index=True,
                                num_rows="dynamic",
                                key="csv_uploaded_assets_table"  # Unique key for this table
                            )

                            # Save edited table to session state for persistence across reruns
                            st.session_state.csv_uploaded_edited_table = edited_df
                            
                            # Convert edited dataframe back to Asset objects
                            if not edited_df.empty:
                                try:
                                    updated_assets = [_asset_from_editor_row(row) for _, row in edited_df.iterrows()]
                                    
                                    # Update the assets list in both local and session state
                                    assets = updated_assets
                                    st.session_state.csv_uploaded_assets = updated_assets
                                    st.success(f"✅ Assets updated! {len(assets)} assets ready for analysis.")
                                    
                                except Exception as e:
                                    st.error(f"❌ Error updating assets: {str(e)}")
                                    st.info("💡 Please check your input values and try again.")
                        
                    except Exception as e:
                        st.error(f"❌ Error processing CSV file: {str(e)}")
                        st.info("💡 **Tip**: Make sure your CSV has the correct format. Download the template and use it as a guide.")
                
            elif setup_option == "Configure Individual Assets":
                st.info("🔧 **Manual Configuration**: Add each asset one by one using the form below.")

                # Seed session state with asset count the first time (or when switching from another mode)
                if 'num_assets_manual' not in st.session_state:
                    st.session_state.num_assets_manual = max(len(assets), 1) if assets else 3
                num_assets = st.number_input("Number of Assets", min_value=1, max_value=10, key="num_assets_manual", help="How many different accounts do you have?")

                # Clear assets list to rebuild from form
                configured_assets: List[Asset] = []

                _ASSET_TYPE_LABELS = {
                    AssetType.PRE_TAX: "Pre-Tax",
                    AssetType.POST_TAX: "After-Tax",
                    AssetType.TAX_DEFERRED: "Tax-Deferred",
                }

                for i in range(num_assets):
                    # Get existing asset data if available
                    existing_asset = assets[i] if i < len(assets) else None

                    with st.expander(f"🏦 Asset {i+1}", expanded=(i==0)):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            asset_name = st.text_input(
                                f"Asset Name {i+1}",
                                value=existing_asset.name if existing_asset else f"Asset {i+1}",
                                help="Name of your account"
                            )

                            # Find the index of the existing asset type in the options list
                            default_type_index = 0
                            if existing_asset:
                                for idx, (name, atype) in enumerate(_DEF_ASSET_TYPES):
                                    template_behavior = infer_tax_behavior(
                                        atype,
                                        name,
                                        15.0 if name == "Brokerage Account" else 0.0,
                                    )
                                    if (
                                        atype == existing_asset.asset_type
                                        and template_behavior == existing_asset.tax_behavior
                                    ):
                                        default_type_index = idx
                                        break

                            asset_type_selection: Tuple[str, AssetType] = st.selectbox(
                                f"Asset Type {i+1}",
                                options=[(name, atype) for name, atype in _DEF_ASSET_TYPES],
                                index=default_type_index,
                                format_func=lambda x: f"{x[0]} — {_ASSET_TYPE_LABELS.get(x[1], x[1].value)}",
                                help="Type of account for tax treatment"
                            )
                        with col2:
                            current_balance = st.number_input(
                                f"Current Balance {i+1} ($)",
                                min_value=0,
                                value=int(existing_asset.current_balance) if existing_asset else 10000,
                                step=1000,
                                help="Current account balance"
                            )
                            annual_contribution = st.number_input(
                                f"Annual Contribution {i+1} ($)",
                                min_value=0,
                                value=int(existing_asset.annual_contribution) if existing_asset else 5000,
                                step=500,
                                help="How much you contribute annually"
                            )
                        with col3:
                            growth_rate = st.slider(
                                f"Growth Rate {i+1} (%)",
                                0, 20,
                                int(existing_asset.growth_rate_pct) if existing_asset else 7,
                                help=f"Expected annual return (default: 7%)"
                            )
                            inferred_behavior = infer_tax_behavior(
                                asset_type_selection[1],
                                asset_name,
                                existing_asset.tax_rate_pct if existing_asset else 0.0,
                            )
                            if inferred_behavior == TaxBehavior.CAPITAL_GAINS:
                                tax_rate = st.slider(
                                    f"Capital Gains Rate {i+1} (%)",
                                    0, 30,
                                    int(existing_asset.tax_rate_pct) if existing_asset and existing_asset.tax_rate_pct > 0 else 15,
                                    help="Capital gains tax rate"
                                )
                            else:
                                tax_rate = 0

                        configured_assets.append(Asset(
                            name=asset_name,
                            asset_type=asset_type_selection[1],
                            current_balance=current_balance,
                            annual_contribution=annual_contribution,
                            growth_rate_pct=growth_rate,
                            tax_behavior=inferred_behavior,
                            tax_rate_pct=tax_rate
                        ))

                # Replace assets with newly configured ones
                assets = configured_assets
    
            st.markdown("---")


            # Tax Rate Explanation - only show for CSV/AI upload methods when assets exist (not for manual configuration)
            if setup_option != "Configure Individual Assets" and len(assets) > 0:
                with st.expander("📚 Understanding Tax Rates in Asset Configuration", expanded=False):
                    st.markdown("""
                    ### 🎯 Tax Rate Column Explained

                    The **Tax Rate (%)** column specifies the tax rate that applies to **gains only** (not the full balance) for certain account types:

                    #### **Pre-Tax Accounts (401k, Traditional IRA)**
                    - **Tax Rate**: `0%` (not applicable here)
                    - **Why**: The entire balance is taxed as ordinary income at withdrawal
                    - **Example**: Withdraw $100,000 → pay tax on full amount at retirement tax rate

                    #### **Post-Tax Accounts**
                    **Roth IRA:**
                    - **Tax Rate**: `0%`
                    - **Why**: No tax on withdrawals (contributions already taxed)
                    - **Example**: Withdraw $100,000 tax-free

                    **Brokerage Account:**
                    - **Tax Rate**: `15%` (default capital gains rate)
                    - **Why**: Only the **gains** are taxed, not original contributions
                    - **Example**:
                      - Contributed $50,000, grew to $100,000
                      - Only $50,000 gain taxed at 15% = $7,500 tax
                      - You keep $92,500

                    #### **Tax-Deferred Accounts (HSA, Annuities)**
                    - **Tax Rate**: Varies by account type
                    - **HSA**: `0%` for medical expenses, retirement tax rate for other withdrawals
                    - **Annuities**: Retirement tax rate on full amount

                    💡 **Key Insight**: This helps calculate how much you'll actually have available for retirement spending after taxes.
                    """)

                # Reference to Advanced Settings for default growth rate
                st.info("💡 **Note:** To set a default growth rate for all accounts, use **Advanced Settings** in the sidebar. This rate will auto-populate when you add accounts below.")
        
        
            # Save assets to session state
            st.session_state.assets = assets
        
            # Navigation buttons for Step 2
            st.markdown("---")
    
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if st.button("← Previous: Personal Info", use_container_width=True):
                    st.session_state.pop("planning_mode_choice", None)
                    st.session_state.onboarding_step = 1
                    st.rerun()
            with col3:
                # Disable complete button if no assets configured
                has_assets = len(assets) > 0
                button_disabled = not has_assets
    
                if st.button(
                    "Complete Setup → View Results",
                    type="primary",
                    use_container_width=True,
                    disabled=button_disabled,
                    help="Configure at least one asset to complete onboarding" if button_disabled else "Save your data and view retirement projections"
                ):
                    # Check if user has set any meaningful contributions
                    total_contributions = sum(asset.annual_contribution for asset in assets)
                    has_contributions = total_contributions > 0
    
                    # Show reminder if no contributions and user hasn't dismissed it yet
                    if not has_contributions and not st.session_state.get('contribution_reminder_dismissed', False):
                        st.session_state.show_contribution_reminder = True
                        st.rerun()
                    else:
                        # Track step 2 completed
                        track_onboarding_step_completed(
                            2,
                            country=st.session_state.get('country', 'US'),
                            num_accounts=len(assets),
                            setup_method=setup_option,
                            total_balance=sum(asset.current_balance for asset in assets)
                        )
    
                        # Save baseline values from onboarding
                        st.session_state.baseline_retirement_age = st.session_state.retirement_age
                        st.session_state.baseline_life_expectancy = st.session_state.life_expectancy
                        st.session_state.baseline_retirement_income_goal = st.session_state.retirement_income_goal
                        st.session_state.baseline_life_expenses = st.session_state.get('life_expenses', 0)
                        st.session_state.baseline_legacy_goal = st.session_state.get('legacy_goal', 0)

                        # Initialize what-if values to match baseline
                        st.session_state.whatif_retirement_age = st.session_state.retirement_age
                        st.session_state.whatif_life_expectancy = st.session_state.life_expectancy
                        st.session_state.whatif_retirement_income_goal = st.session_state.retirement_income_goal
                        st.session_state.whatif_life_expenses = st.session_state.get('life_expenses', 0)
                        st.session_state.whatif_legacy_goal = st.session_state.get('legacy_goal', 0)
    
                        # Mark onboarding as complete and navigate to results page
                        st.session_state.onboarding_complete = True
                        st.session_state.current_page = 'results'
                        st.session_state.results_source = 'onboarding'
    
                        # Track onboarding completed
                        track_event('onboarding_completed', {
                            'country': st.session_state.get('country', 'US'),
                            'num_accounts': len(assets),
                            'setup_method': setup_option,
                            'has_retirement_goal': st.session_state.retirement_income_goal > 0
                        }, user_properties={'country': st.session_state.get('country', 'US')})
    
                        st.rerun()
        
            # Show warning if no assets configured
            if not has_assets:
                st.warning("⚠️ Please configure at least one asset before completing onboarding.")
    
    elif st.session_state.current_page == 'results':

        # ==========================================
        # RESULTS & ANALYSIS PAGE
        # ==========================================
    
        # Track page view
        track_page_view('results')
    
        # Add navigation button to go back to setup
        if st.button("← Back to Setup", use_container_width=False):
            track_event('navigation_back_to_setup')
            # Return to whichever page last navigated to results
            if st.session_state.get('results_source') == 'chat_mode':
                st.session_state.current_page = 'chat_mode'
            else:
                st.session_state.current_page = 'onboarding'
            st.rerun()
    
        st.markdown("---")
    
        # Header
        st.header("📊 Retirement Projection & Analysis")
        st.markdown("Explore your retirement projections and adjust scenarios with what-if analysis below.")
    
        st.markdown("---")
    
        # Fixed Facts Section (non-editable baseline data)
        with st.expander("📋 Your Baseline Information (from setup)", expanded=False):
            col1, col2, col3 = st.columns(3)
            current_year = datetime.now().year
            baseline_age = current_year - st.session_state.birth_year
    
            with col1:
                st.metric("Birth Year", st.session_state.birth_year)
                st.metric("Current Age", f"{baseline_age} years")
            with col2:
                st.metric("Retirement Age (Baseline)", st.session_state.baseline_retirement_age)
                st.metric("Life Expectancy (Baseline)", st.session_state.baseline_life_expectancy)
            with col3:
                st.metric("Accounts Configured", len(st.session_state.assets))
                if st.session_state.baseline_retirement_income_goal > 0:
                    st.metric("Income Goal (Baseline)", f"${st.session_state.baseline_retirement_income_goal:,.0f}/year")
                else:
                    st.metric("Income Goal (Baseline)", "Not set")
    
            st.info("💡 **To change these values, go back to Setup using the button above.**")
    
        st.markdown("---")
    
        # Calculate values from what-if session state for results
        current_year = datetime.now().year
        age = current_year - st.session_state.birth_year
        retirement_age = st.session_state.whatif_retirement_age
        life_expectancy = st.session_state.whatif_life_expectancy
        retirement_income_goal = st.session_state.whatif_retirement_income_goal
        current_tax_rate = st.session_state.whatif_current_tax_rate
        retirement_tax_rate = st.session_state.whatif_retirement_tax_rate
        inflation_rate = st.session_state.whatif_inflation_rate
        retirement_growth_rate = st.session_state.whatif_retirement_growth_rate
        life_expenses = st.session_state.whatif_life_expenses
        legacy_goal = st.session_state.get('whatif_legacy_goal', 0)
        assets = st.session_state.assets
        
        try:
            inputs = UserInputs(
                age=int(age),
                retirement_age=int(retirement_age),
                life_expectancy=int(life_expectancy),
                annual_income=0.0,  # Not used in calculations anymore
                contribution_rate_pct=15.0,  # Not used in new system
                expected_growth_rate_pct=7.0,  # Not used in new system
                inflation_rate_pct=float(inflation_rate),
                current_marginal_tax_rate_pct=float(current_tax_rate),
                retirement_marginal_tax_rate_pct=float(retirement_tax_rate),
                assets=assets
            )
        
            result = project(inputs)
    
            # Save result and inputs to session state for Next Steps dialogs
            st.session_state.last_result = result
            st.session_state.last_inputs = inputs
    
            # Adjust after-tax balance for life expenses
            total_after_tax_original = result['Total After-Tax Balance']
    
            # Validate life expenses don't exceed portfolio balance
            if life_expenses > total_after_tax_original:
                st.error(f"""
                ⚠️ **One-Time Expenses Exceed Portfolio Balance**

                Your one-time expenses at retirement (**${life_expenses:,.0f}**) exceed
                your projected after-tax portfolio balance (**${total_after_tax_original:,.0f}**).

                Please either:
                - Reduce one-time expenses, or
                - Adjust your portfolio contributions/retirement age to build a larger balance
                """)
                st.stop()
    
            total_after_tax = total_after_tax_original - life_expenses
    
            # Key metrics in a prominent container
            with st.container():
                st.subheader("🎯 Key Metrics")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Years to Retirement", f"{result['Years Until Retirement']:.0f}")
                with col2:
                    st.metric("Total Pre-Tax Value", f"${result['Total Future Value (Pre-Tax)']:,.0f}")
                with col3:
                    _atv_help = "Estimated using a year-by-year simulation: each year all account pots grow, forced RMDs are paid first, then withdrawals follow brokerage → pre-tax → Roth order. The annual withdrawal is the maximum that sustains the portfolio through your life expectancy."
                    if life_expenses > 0:
                        st.metric(
                            "Total After-Tax Value",
                            f"${total_after_tax:,.0f}",
                            delta=f"-${life_expenses:,.0f} one-time expense",
                            delta_color="normal",
                            help=_atv_help,
                        )
                    else:
                        st.metric("Total After-Tax Value", f"${total_after_tax:,.0f}", help=_atv_help)
                with col4:
                    st.metric("Tax Efficiency", f"{result['Tax Efficiency (%)']:.1f}%")

            if legacy_goal > 0:
                st.metric(
                    "Legacy Goal",
                    f"${legacy_goal:,.0f}",
                    help="Target portfolio balance at end of life — the withdrawal simulation ensures this amount remains for your heirs. Unlike a one-time expense, this is not deducted at retirement; it reduces the sustainable withdrawal rate instead.",
                )
    
            # Income Analysis Section
            st.markdown("---")
            st.subheader("💰 Retirement Income Analysis")
            st.caption(
                "Income is modeled with a year-by-year simulation using optimal withdrawal sequencing "
                "(taxable → pre-tax → Roth) and IRS Required Minimum Distributions (RMDs) starting at age 73. "
                "Social Security income and tax brackets are not modeled — see the note below."
            )

            # Calculate retirement income from portfolio (using adjusted balance)
            years_in_retirement = life_expectancy - retirement_age  # Use actual life expectancy

            # Validate years in retirement
            if years_in_retirement <= 0:
                st.error(f"""
                ⚠️ **Invalid Retirement Period**

                Your life expectancy (**{life_expectancy}**) must be greater than
                your retirement age (**{retirement_age}**).

                Please adjust these values in the sliders above.
                """)
                st.stop()

            # --- Retirement income: year-by-year simulation with sequencing + RMDs ---
            # Split projected FVs into three pots by account type.
            pretax_fv = sum(
                ar['pre_tax_value']
                for ar, ai in zip(result['asset_results'], result['assets_input'])
                if ai.asset_type in (AssetType.PRE_TAX, AssetType.TAX_DEFERRED)
            )
            roth_fv = sum(
                ar['pre_tax_value']
                for ar, ai in zip(result['asset_results'], result['assets_input'])
                if ai.asset_type == AssetType.POST_TAX and 'roth' in ai.name.lower()
            )
            brok_fv = sum(
                ar['pre_tax_value']
                for ar, ai in zip(result['asset_results'], result['assets_input'])
                if ai.asset_type == AssetType.POST_TAX and 'roth' not in ai.name.lower()
            )
            brok_cost_basis = sum(
                ar['total_contributions'] + ai.current_balance
                for ar, ai in zip(result['asset_results'], result['assets_input'])
                if ai.asset_type == AssetType.POST_TAX and 'roth' not in ai.name.lower()
            )

            # Deduct life expenses proportionally across all three pots
            total_fv_all = pretax_fv + roth_fv + brok_fv
            if life_expenses > 0 and total_fv_all > 0:
                frac = life_expenses / total_fv_all
                pretax_fv       = max(0.0, pretax_fv       * (1.0 - frac))
                roth_fv         = max(0.0, roth_fv         * (1.0 - frac))
                brok_fv         = max(0.0, brok_fv         * (1.0 - frac))
                brok_cost_basis = max(0.0, brok_cost_basis * (1.0 - frac))

            annual_retirement_income, sim_data = find_sustainable_withdrawal(
                pretax_fv, roth_fv, brok_fv, brok_cost_basis,
                int(retirement_age), int(life_expectancy),
                retirement_growth_rate / 100.0, inflation_rate / 100.0,
                float(retirement_tax_rate),
                legacy_goal=legacy_goal,
            )
            st.session_state.cashflow_sim_data = sim_data

            # r, i, n still needed by the recommendations section (inverse annuity formula)
            r = retirement_growth_rate / 100.0
            i = inflation_rate / 100.0
            n = years_in_retirement
        
            # Only show income goal comparison if user set a goal
            if retirement_income_goal > 0:
                # Calculate shortfall or surplus
                income_shortfall = retirement_income_goal - annual_retirement_income
                income_ratio = (annual_retirement_income / retirement_income_goal) * 100
        
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(
                        "Projected Annual Income",
                        f"${annual_retirement_income:,.0f}",
                        help=f"First-year after-tax income. Modeled with optimal withdrawal sequencing (taxable → pre-tax → Roth) and IRS RMDs starting at age 73. Based on {years_in_retirement}-year retirement (age {retirement_age} to {life_expectancy})."
                    )
                with col2:
                    st.metric(
                        "Income Goal",
                        f"${retirement_income_goal:,.0f}",
                        help="Your desired retirement income"
                    )
                with col3:
                    if income_shortfall > 0:
                        st.metric(
                            "Annual Shortfall",
                            f"${income_shortfall:,.0f}",
                            delta=f"-{income_ratio:.1f}%",
                            delta_color="inverse"
                        )
                    else:
                        surplus = -income_shortfall
                        st.metric(
                            "Annual Surplus",
                            f"${surplus:,.0f}",
                            delta=f"+{income_ratio:.1f}%",
                            delta_color="normal"
                        )
        
                # Income status analysis
                if income_ratio >= 100:
                    st.success(f"🎉 **Excellent!** You're projected to exceed your retirement income goal by {income_ratio-100:.1f}%!")
                elif income_ratio >= 80:
                    st.warning(f"⚠️ **Good progress!** You're on track for {income_ratio:.1f}% of your retirement income goal.")
                elif income_ratio >= 60:
                    st.warning(f"🚨 **Needs attention!** You're only projected to achieve {income_ratio:.1f}% of your retirement income goal.")
                else:
                    st.error(f"❌ **Significant shortfall!** You're only projected to achieve {income_ratio:.1f}% of your retirement income goal.")
            else:
                # No income goal set - just show projected income
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(
                        "Projected Annual Income",
                        f"${annual_retirement_income:,.0f}",
                        help=f"First-year after-tax income. Modeled with optimal withdrawal sequencing (taxable → pre-tax → Roth) and IRS RMDs starting at age 73. Based on {years_in_retirement}-year retirement (age {retirement_age} to {life_expectancy})."
                    )
                with col2:
                    st.info("💡 **No income goal set** - Set a retirement income goal in Step 1 to see how your portfolio measures up!")
    
            # Social Security notice
            st.info(
                "ℹ️ **Social Security income is not included in this projection.** "
                "Your estimated SS benefit can significantly reduce the amount your portfolio needs to cover. "
                "Expand the section below to find your projected benefit and learn how to factor it in."
            )
            with st.expander("💡 Social Security Income Not Included — How to Factor It In", expanded=False):
                st.markdown("""
                ### This Tool Models Portfolio Income Only

                The projected retirement income shown above comes entirely from your **investment accounts**
                (401k, IRA, Roth, brokerage). It does **not** include Social Security benefits, pensions,
                rental income, or any other income source.

                Most retirees are entitled to Social Security — and for many it's $20,000–$40,000+ per year.
                Leaving it out of your planning can make your situation look worse than it actually is.

                ---

                ### How to Factor It Into This Tool

                The simplest approach: **subtract your expected SS benefit from your income goal.**

                > **Example:** You need $70,000/year in retirement. You expect $24,000/year from Social Security.
                > Set your income goal here to **$46,000/year** — the amount your portfolio needs to cover.

                ---

                ### How to Find Your Projected Social Security Benefit

                **Option 1 — my Social Security account (most accurate):**
                1. Go to [ssa.gov/myaccount](https://www.ssa.gov/myaccount/) and create a free account
                2. View your **Social Security Statement** — it shows your projected monthly benefit
                   at ages 62, 67 (full retirement age), and 70
                3. Your statement also shows your full earnings history and disability/survivor benefits

                **Option 2 — SSA Retirement Estimator:**
                - Use the quick estimator at
                  [ssa.gov/benefits/retirement/estimator.html](https://www.ssa.gov/benefits/retirement/estimator.html)
                - No account needed; based on your reported earnings

                ---

                ### Typical Social Security Benefit Amounts (2025)

                | Scenario | Monthly | Annual |
                |---|---|---|
                | Average retired worker | ~$1,900 | ~$22,800 |
                | Maximum at full retirement age (67) | ~$4,018 | ~$48,216 |
                | Maximum at age 70 (delayed) | ~$4,873 | ~$58,476 |

                > 💡 **Tip:** Delaying Social Security to age 70 increases your benefit by ~8% per year
                > beyond full retirement age — often worth considering if your portfolio can bridge the gap.
                """)

            # Explanation of retirement income calculation
            with st.expander("📊 How Is Retirement Income Calculated?", expanded=False):
                rmd_start_year = max(0, 73 - int(retirement_age))
                st.markdown(f"""
                ### Retirement Simulation: Sequencing with Required Minimum Distributions (RMDs)

                Income is calculated using a **year-by-year simulation** across your {n}-year retirement
                (age {retirement_age}–{life_expectancy}), not a simple formula. Each year the model:

                1. **Grows** all three account pots at {retirement_growth_rate:.1f}% annually
                2. **Forces Required Minimum Distributions (RMDs)** from pre-tax accounts starting at age 73 (IRS Uniform Lifetime Table)
                3. **Sequences remaining withdrawals** optimally: taxable brokerage → Roth (last)
                4. **Taxes each withdrawal** at the appropriate rate (ordinary income for pre-tax, capital
                   gains on brokerage gains, tax-free for Roth)

                **Starting balances at retirement** (after life expenses):
                - Pre-Tax (401k / Trad IRA / Tax-Deferred): **${pretax_fv:,.0f}**
                - Roth IRA: **${roth_fv:,.0f}**
                - Taxable Brokerage: **${brok_fv:,.0f}**
                {f"- RMDs begin: **Year {rmd_start_year + 1} (age 73)**" if int(retirement_age) < 73 else "- **RMDs begin immediately (age 73+)**"}

                **Sustainable first-year after-tax income: ${annual_retirement_income:,.0f}**
                *(binary search result: maximum first-year withdrawal that depletes portfolio at age {life_expectancy})*
                """)

                with st.expander("ℹ️ What is a Required Minimum Distribution (RMD)?", expanded=False):
                    st.markdown("""
**Required Minimum Distribution (RMD)** is the minimum amount the IRS requires you to withdraw
each year from tax-deferred retirement accounts (such as 401(k)s and Traditional IRAs) once you
reach age 73.

**Key facts:**
- RMDs begin at **age 73** (under the SECURE 2.0 Act, effective 2023)
- The annual amount is calculated by dividing your prior year-end account balance by a life
  expectancy factor from the **IRS Uniform Lifetime Table**
- Missing an RMD triggers a **25% excise tax** on the amount not withdrawn
- **Roth IRAs** are not subject to RMDs during the original owner's lifetime
- Excess RMD beyond your spending need can be reinvested in a taxable brokerage account

📖 [Learn more at IRS.gov — Required Minimum Distributions](https://www.irs.gov/retirement-plans/plan-participant-employee/required-minimum-distributions)
                    """)

                # Build year-by-year table from sim_data
                import pandas as pd
                if sim_data:
                    _col_cfg = {
                        "Year":          st.column_config.NumberColumn("Year",          format="%d"),
                        "Age":           st.column_config.NumberColumn("Age",           format="%d"),
                        "RMD":           st.column_config.TextColumn("RMD"),
                        "Brokerage W/D": st.column_config.TextColumn("Brokerage W/D"),
                        "Roth W/D":      st.column_config.TextColumn("Roth W/D"),
                        "Extra Pre-Tax": st.column_config.TextColumn("Extra Pre-Tax"),
                        "Tax Paid":      st.column_config.TextColumn("Tax Paid"),
                        "After-Tax Income (adjusted for inflation)": st.column_config.TextColumn(
                            "After-Tax Income (adjusted for inflation)"),
                        "Total Portfolio": st.column_config.TextColumn("Total Portfolio"),
                    }

                    withdrawal_data = []
                    for row in sim_data:
                        withdrawal_data.append({
                            "Year":          row["year"],
                            "Age":           row["age"],
                            "RMD":           f"${row['rmd']:,.0f}"                     if row["rmd"] > 0                     else None,
                            "Brokerage W/D": f"${row['brokerage_withdrawal']:,.0f}"    if row["brokerage_withdrawal"] > 0    else None,
                            "Roth W/D":      f"${row['roth_withdrawal']:,.0f}"         if row["roth_withdrawal"] > 0         else None,
                            "Extra Pre-Tax": f"${row['extra_pretax_withdrawal']:,.0f}" if row["extra_pretax_withdrawal"] > 0 else None,
                            "Tax Paid":      f"${row['total_tax']:,.0f}",
                            "After-Tax Income (adjusted for inflation)": f"${row['actual_aftertax']:,.0f}",
                            "Total Portfolio": f"${row['total_portfolio_end']:,.0f}",
                        })

                    df_withdrawals = pd.DataFrame(withdrawal_data)
                    st.dataframe(df_withdrawals, use_container_width=True, hide_index=True, column_config=_col_cfg)

                    # Detect when each pot depletes
                    brok_depletion = next((r["year"] for r in sim_data if r["brokerage_bal_end"] < 1), None)
                    pretax_depletion = next((r["year"] for r in sim_data if r["pretax_bal_end"] < 1), None)
                    roth_depletion = next((r["year"] for r in sim_data if r["roth_bal_end"] < 1), None)

                    depletion_notes = []
                    if brok_depletion:
                        depletion_notes.append(f"Brokerage depletes at year {brok_depletion} (age {int(retirement_age) + brok_depletion - 1})")
                    if pretax_depletion:
                        depletion_notes.append(f"Pre-tax depletes at year {pretax_depletion} (age {int(retirement_age) + pretax_depletion - 1})")
                    if roth_depletion:
                        depletion_notes.append(f"Roth depletes at year {roth_depletion} (age {int(retirement_age) + roth_depletion - 1})")

                    year10_income = sim_data[9]["actual_aftertax"] if len(sim_data) >= 10 else annual_retirement_income
                    total_aftertax = sum(r["actual_aftertax"] for r in sim_data)
                    total_tax_paid = sum(r["total_tax"] for r in sim_data)

                    notes_md = "\n".join(f"- {note}" for note in depletion_notes) if depletion_notes else "- All accounts last the full retirement period"
                    key_points_lines = [
                        "**Key Points:**",
                        f"- Year 1 after-tax income: **${annual_retirement_income:,.0f}**",
                        f"- Year 10 after-tax income: **${year10_income:,.0f}** (inflation-adjusted)",
                        f"- Total lifetime after-tax income: **${total_aftertax:,.0f}**",
                        f"- Total taxes paid in retirement: **${total_tax_paid:,.0f}**",
                        "",
                        "**Account depletion order:**",
                        notes_md,
                        "",
                        "---",
                        "### Why Sequencing and RMDs Matter",
                        "",
                        "Withdrawing from taxable accounts first lets Roth funds compound tax-free longer,",
                        "reducing lifetime taxes. RMDs force pre-tax withdrawals regardless of your preference,",
                        "so large pre-tax balances can push you into higher brackets - a key reason Roth",
                        "conversions before age 73 are often beneficial.",
                        "",
                        "**Note:** Tax brackets, Social Security benefit taxation, and state taxes are not modeled.",
                    ]
                    st.markdown("\n".join(key_points_lines))
    
            # Recommendations based on income analysis (only if goal is set)
            if retirement_income_goal > 0:
                # Use actionable heading when there's a shortfall
                if income_shortfall > 0:
                    expander_title = f"🎯 Strategies to Close Your ${income_shortfall:,.0f} Income Gap"
                else:
                    expander_title = "💡 Income Optimization Recommendations"
    
                with st.expander(expander_title, expanded=False):
                    if income_shortfall > 0:
                        # Calculate required after-tax balance to meet income goal
                        # Use INVERSE annuity formula to account for growth during retirement
                        # PV = PMT × [(1 - ((1+i)/(1+r))^n) / (r - i)]
    
                        if abs(r - i) < 0.0001:  # If growth rate equals inflation rate
                            # Simple multiplication when growth = inflation
                            required_balance_for_income = retirement_income_goal * n
                        else:
                            # Inverse annuity formula
                            numerator = 1 - ((1 + i) / (1 + r)) ** n
                            denominator = r - i
                            required_balance_for_income = retirement_income_goal * (numerator / denominator)
    
                        # Add life expenses (one-time deduction at retirement) and legacy goal
                        # (present value of holding `legacy_goal` at end of retirement)
                        legacy_goal_pv = legacy_goal / ((1 + r) ** n) if n > 0 else legacy_goal
                        required_after_tax_balance = required_balance_for_income + life_expenses + legacy_goal_pv
    
                        additional_balance_needed = required_after_tax_balance - total_after_tax
    
                        # Helper function to calculate required contribution increase (NPV-based)
                        def calculate_contribution_increase(assets, years_to_retirement, additional_balance_needed_aftertax, tax_efficiency_pct):
                            """Calculate additional annual contribution needed using NPV formula.
    
                            Key insight: We need additional_balance_needed in AFTER-TAX dollars, but
                            contributions grow PRE-TAX and then get taxed. So we must:
                            1. Convert after-tax target to pre-tax target
                            2. Calculate contributions needed for pre-tax target
                            3. Return the contribution amount
    
                            For each asset, we need to solve for additional contribution C:
                            FV_needed_pretax = P*(1+r)^t + (C_current + C_additional) * [((1+r)^t - 1)/r]
    
                            Rearranging: C_additional = [FV_needed_pretax - P*(1+r)^t] / [((1+r)^t - 1)/r] - C_current
                            """
                            # Convert after-tax target to pre-tax target
                            # If tax efficiency is 85%, and we need $100k after-tax, we need $117.6k pre-tax
                            additional_balance_needed_pretax = additional_balance_needed_aftertax / (tax_efficiency_pct / 100.0)
    
                            # Calculate weighted average growth rate
                            weighted_avg_rate = 0
                            total_balance = sum(a.current_balance for a in assets)
                            if total_balance > 0:
                                for asset in assets:
                                    weight = asset.current_balance / total_balance
                                    weighted_avg_rate += weight * (asset.growth_rate_pct / 100.0)
                            else:
                                weighted_avg_rate = 0.07  # default 7%
    
                            # Solve for additional contribution using future value of annuity formula
                            # FV = C * [((1+r)^t - 1)/r]
                            # C = FV / [((1+r)^t - 1)/r]
                            if weighted_avg_rate > 0 and years_to_retirement > 0:
                                growth_factor = (1.0 + weighted_avg_rate) ** years_to_retirement
                                annuity_factor = (growth_factor - 1.0) / weighted_avg_rate
                                total_additional_contribution = additional_balance_needed_pretax / annuity_factor
                            else:
                                total_additional_contribution = additional_balance_needed_pretax / max(years_to_retirement, 1)
    
                            return total_additional_contribution, weighted_avg_rate * 100
    
                        # Helper function to calculate additional years needed
                        def calculate_additional_years(assets, current_age, retirement_age, life_expectancy, income_goal, tax_efficiency_pct, retirement_growth_rate, inflation_rate, life_expenses, legacy_goal=0.0):
                            """Calculate additional years needed to work.

                            Key insight: Working longer has TWO benefits:
                            1. Portfolio grows longer (more years of contributions + growth)
                            2. Retirement period is shorter (need less total balance)

                            Solve for t in: FV = P*(1+r)^t + C * [((1+r)^t - 1)/r]
                            where FV is calculated using INVERSE annuity formula to account for
                            portfolio growth and inflation-adjusted withdrawals during retirement.

                            Must account for:
                            - Taxes by converting pre-tax FV to after-tax FV
                            - One-time life expenses deducted at retirement
                            - Legacy goal (present value of terminal portfolio target)
                            """
                            # Calculate weighted average growth rate and total current contributions
                            weighted_avg_rate = 0
                            total_current_contribution = 0
                            total_balance = sum(a.current_balance for a in assets)
    
                            if total_balance > 0:
                                for asset in assets:
                                    weight = asset.current_balance / total_balance
                                    weighted_avg_rate += weight * (asset.growth_rate_pct / 100.0)
                                    total_current_contribution += asset.annual_contribution
                            else:
                                weighted_avg_rate = 0.07
                                total_current_contribution = sum(a.annual_contribution for a in assets)
    
                            # Current projection data
                            total_current_balance = total_balance
    
                            # Helper to calculate future value (pre-tax)
                            def calculate_fv(years, principal, contribution, rate):
                                if rate == 0:
                                    return principal + contribution * years
                                growth = (1.0 + rate) ** years
                                return principal * growth + contribution * ((growth - 1.0) / rate)
    
                            # Iteratively test additional years with 0.1 year increments for precision
                            # For each additional year, recalculate BOTH:
                            # 1. Higher FV (more growth time)
                            # 2. Lower required balance (fewer retirement years)
                            for additional_tenths in range(0, 500):  # 0 to 50 years in 0.1 year increments
                                additional_years = additional_tenths / 10.0
                                test_retirement_age = retirement_age + additional_years
                                test_years_to_retirement = test_retirement_age - current_age
                                test_years_in_retirement = life_expectancy - test_retirement_age
    
                                # Skip if retirement age exceeds life expectancy
                                if test_years_in_retirement <= 0:
                                    continue
    
                                # Calculate what we'd have at this retirement age (PRE-TAX)
                                test_fv_pretax = calculate_fv(test_years_to_retirement, total_current_balance,
                                                      total_current_contribution, weighted_avg_rate)
    
                                # Convert to AFTER-TAX using tax efficiency ratio
                                test_fv_aftertax = test_fv_pretax * (tax_efficiency_pct / 100.0)
    
                                # Subtract life expenses - this is the actual available balance for generating income
                                available_balance_aftertax = test_fv_aftertax - life_expenses
    
                                # Calculate what we'd need for this shorter retirement period (AFTER-TAX)
                                # This is just the amount needed to generate income via annuity
                                # Use INVERSE annuity formula to account for growth during retirement
                                r_ret = retirement_growth_rate / 100.0
                                i_ret = inflation_rate / 100.0
    
                                if abs(r_ret - i_ret) < 0.0001:
                                    # Simple multiplication when growth = inflation
                                    required_balance_for_income = income_goal * test_years_in_retirement
                                else:
                                    # Inverse annuity formula
                                    numerator = 1 - ((1 + i_ret) / (1 + r_ret)) ** test_years_in_retirement
                                    denominator = r_ret - i_ret
                                    required_balance_for_income = income_goal * (numerator / denominator)
    
                                # Total required = income-generating balance + life expenses + legacy PV
                                legacy_goal_pv_iter = legacy_goal / ((1 + r_ret) ** test_years_in_retirement) if test_years_in_retirement > 0 else legacy_goal
                                required_balance_aftertax = required_balance_for_income + life_expenses + legacy_goal_pv_iter

                                # Found solution? Compare available balance (after life expenses) to required balance for income
                                if available_balance_aftertax >= required_balance_for_income + legacy_goal_pv_iter:
                                    return additional_years, weighted_avg_rate * 100, test_retirement_age, required_balance_aftertax

                            # If no solution found in 50 years, return 50
                            # Calculate required balance using inverse annuity formula
                            final_years_in_retirement = max(0, life_expectancy - retirement_age - 50)
                            if final_years_in_retirement > 0:
                                if abs(r_ret - i_ret) < 0.0001:
                                    final_required_balance_for_income = income_goal * final_years_in_retirement
                                else:
                                    numerator = 1 - ((1 + i_ret) / (1 + r_ret)) ** final_years_in_retirement
                                    denominator = r_ret - i_ret
                                    final_required_balance_for_income = income_goal * (numerator / denominator)
                                legacy_goal_pv_final = legacy_goal / ((1 + r_ret) ** final_years_in_retirement) if final_years_in_retirement > 0 else legacy_goal
                                final_required_balance = final_required_balance_for_income + life_expenses + legacy_goal_pv_final
                            else:
                                final_required_balance = life_expenses + legacy_goal  # Still need both even with 0 years in retirement
    
                            return 50.0, weighted_avg_rate * 100, retirement_age + 50, final_required_balance
    
                        # Calculate recommendations
                        years_to_retirement = retirement_age - age
                        tax_efficiency = result['Tax Efficiency (%)']
    
                        additional_contribution, avg_growth_rate_1 = calculate_contribution_increase(
                            inputs.assets, years_to_retirement, additional_balance_needed, tax_efficiency
                        )
                        additional_years, avg_growth_rate_2, new_retirement_age, required_balance_for_option2 = calculate_additional_years(
                            inputs.assets, age, retirement_age, life_expectancy, retirement_income_goal, tax_efficiency, retirement_growth_rate, inflation_rate, life_expenses, legacy_goal
                        )
    
                        # Calculate new years in retirement for option 2
                        new_years_in_retirement = life_expectancy - new_retirement_age
    
                        st.markdown(f"""
                        **To close the ${income_shortfall:,.0f} annual shortfall:**
    
                        1. **Increase contributions**: Boost annual savings by **${additional_contribution:,.0f} per year**
                           - Assumes {avg_growth_rate_1:.1f}% average growth rate across your portfolio
                           - Required total after-tax balance: ${required_after_tax_balance:,.0f}
                        """)
    
                        # Add button to go back to setup to edit contributions
                        if st.button("📝 Edit Portfolio Contributions", type="secondary", use_container_width=True):
                            track_event('edit_contributions_from_recommendations')
                            st.session_state.current_page = 'onboarding'
                            st.rerun()
    
                        st.markdown(f"""
                        2. **Extend retirement age**: Work **{additional_years:.1f} additional years** (retire at age {new_retirement_age:.0f})
                           - Assumes {avg_growth_rate_2:.1f}% average growth rate with current contribution levels
                           - Reduces retirement period to {new_years_in_retirement:.0f} years
                           - Required total after-tax balance: ${required_balance_for_option2:,.0f}

                        3. **Optimize asset allocation**: Consider higher-growth investments

                        4. **Reduce retirement expenses**: Lower your income goal to ${retirement_income_goal - income_shortfall:,.0f}/year (reduce by ${income_shortfall:,.0f})

                        5. **Consider part-time work**: Supplement retirement income
                        """)
                        if legacy_goal > 0:
                            annuity_factor = (total_after_tax / annual_retirement_income) if annual_retirement_income > 0 else 1
                            legacy_reduction_needed = min(income_shortfall * annuity_factor, legacy_goal)
                            new_legacy = legacy_goal - legacy_reduction_needed
                            st.info(
                                f"💡 **Alternatively**, reducing your legacy goal from **${legacy_goal:,.0f}** to "
                                f"**${new_legacy:,.0f}** (−${legacy_reduction_needed:,.0f}) would free up enough "
                                f"portfolio to close the income gap."
                            )
                    else:
                        st.markdown("""
                        **You're on track! Consider these optimizations:**
        
                        1. **Tax optimization**: Maximize Roth contributions
                        2. **Asset allocation**: Balance growth vs. preservation
                        3. **Estate planning**: Consider legacy goals
                        4. **Lifestyle upgrades**: You may be able to increase retirement spending
                        """)
            
            # Navigate to Detailed Analysis page
            st.markdown("---")
            if st.button("📈 View Detailed Analysis", use_container_width=True, type="primary", key="go_detailed_analysis"):
                st.session_state.current_page = 'detailed_analysis'
                st.rerun()

            with st.expander("🎯 What-If Scenario Adjustments", expanded=False):
                st.markdown("Adjust the values below to explore different retirement scenarios. Changes update instantly.")

                col1, col2, col3 = st.columns(3)

                with col1:
                    whatif_retirement_age = st.number_input(
                        "Retirement Age",
                        min_value=40,
                        max_value=80,
                        key="whatif_retirement_age",
                        help="Adjust retirement age to see impact on projections"
                    )

                    whatif_life_expectancy = st.number_input(
                        "Life Expectancy",
                        min_value=whatif_retirement_age + 1,
                        max_value=120,
                        key="whatif_life_expectancy",
                        help="Adjust life expectancy to see impact on retirement duration"
                    )

                with col2:
                    whatif_retirement_income_goal = st.number_input(
                        "Annual Retirement Income Goal ($)",
                        min_value=0,
                        max_value=1000000,
                        key="whatif_retirement_income_goal",
                        step=5000,
                        help="Target annual income in retirement (0 = no goal set)"
                    )

                    whatif_life_expenses = st.number_input(
                        "One-Time Expenses at Retirement ($)",
                        min_value=0,
                        max_value=10000000,
                        key="whatif_life_expenses",
                        step=10000,
                        help="Lump-sum deducted at retirement (e.g., paying off mortgage, medical costs, down payment on retirement home)"
                    )

                    whatif_legacy_goal = st.number_input(
                        "Legacy Goal — Money to Leave Behind ($)",
                        min_value=0,
                        max_value=10000000,
                        key="whatif_legacy_goal",
                        step=10000,
                        help="Target portfolio balance to leave at end of life (future-value target, not deducted at retirement — reduces sustainable withdrawal rate)"
                    )

                with col3:
                    whatif_inflation_rate = 3

                    whatif_retirement_growth_rate = st.slider(
                        "Portfolio Growth in Retirement (%)",
                        min_value=0.0,
                        max_value=10.0,
                        value=st.session_state.whatif_retirement_growth_rate,
                        step=0.5,
                        help="Expected portfolio growth rate during retirement (typically 3-5% for conservative allocations)"
                    )

                    whatif_retirement_tax_rate = st.slider(
                        "Retirement Tax Rate (%)",
                        min_value=0,
                        max_value=50,
                        value=st.session_state.whatif_retirement_tax_rate,
                        help="Expected tax rate in retirement (used to calculate after-tax balance)"
                    )

                # Update session state for widgets without key= binding (sliders)
                st.session_state.whatif_retirement_tax_rate = whatif_retirement_tax_rate
                st.session_state.whatif_inflation_rate = whatif_inflation_rate
                st.session_state.whatif_retirement_growth_rate = whatif_retirement_growth_rate

                if st.button("🔄 Reset to Baseline Values"):
                    track_feature_usage('what_if_reset')
                    st.session_state.whatif_retirement_age = st.session_state.baseline_retirement_age
                    st.session_state.whatif_life_expectancy = st.session_state.baseline_life_expectancy
                    st.session_state.whatif_retirement_income_goal = st.session_state.baseline_retirement_income_goal
                    st.session_state.whatif_current_tax_rate = 22
                    st.session_state.whatif_retirement_tax_rate = 22
                    st.session_state.whatif_inflation_rate = 3
                    st.session_state.whatif_retirement_growth_rate = 4.0
                    st.session_state.whatif_life_expenses = st.session_state.baseline_life_expenses
                    st.session_state.whatif_legacy_goal = st.session_state.baseline_legacy_goal
                    st.rerun()

            # Next Steps Section
            st.markdown("---")
            st.subheader("🎯 Next Steps")
            st.markdown("Take your retirement planning to the next level:")
    
            # Create three columns for the Next Steps buttons
            col1, col2, col3 = st.columns(3)
    
            with col1:
                st.markdown("### 📄 Generate Report")
                st.markdown("Create a comprehensive PDF report with your complete retirement analysis.")
                if st.button("📥 Create PDF Report", use_container_width=True, type="primary", key="next_steps_report"):
                    generate_report_dialog()
    
            with col2:
                st.markdown("### 🎲 Scenario Analysis")
                st.markdown("Explore thousands of scenarios and see how market volatility affects your plan.")
                if st.button("🚀 Run Scenarios", use_container_width=True, type="primary", key="next_steps_monte_carlo"):
                    monte_carlo_dialog()
    
            with col3:
                st.markdown("### 📊 Cash Flow Projection")
                st.markdown("Visualize year-by-year income and expenses throughout retirement.")
                if st.button("📊 View Cash Flow", use_container_width=True, type="primary", key="next_steps_cashflow"):
                    cashflow_dialog()
    
            # Share & Feedback section - Simple and clean
            st.markdown("---")
            with st.expander("💬 Share & Feedback", expanded=False):
                # Create tabs for better organization
                feedback_tab1, feedback_tab2, feedback_tab3 = st.tabs(["📤 Share", "⭐ Feedback", "📧 Contact"])
    
                with feedback_tab1:
                    st.markdown("**Share Smart Retire AI with others:** (Tip: Turn the pop-up blocker off for best results)")
    
                    app_url = "https://smartretireai.streamlit.app"
    
                    # Social share buttons - simple button layout
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        # Enhanced Twitter message with key features and value prop
                        twitter_text = "Just planned my retirement with Smart Retire AI! 🎯 FREE tool featuring:\n✅ AI-powered analysis\n✅ Tax optimization\n✅ Monte Carlo simulations\n✅ Personalized insights\n\nPlan your financial future →"
                        twitter_encoded = urllib.parse.quote(twitter_text)
                        twitter_url = f"https://twitter.com/intent/tweet?text={twitter_encoded}&url={app_url}"
                        if st.button("🐦 Twitter", use_container_width=True, key="share_twitter"):
                            components.html(
                                f"""<script>window.open("{twitter_url}", "_blank");</script>""",
                                height=0
                            )
                            st.success("Opening Twitter in new tab...")

                    with col2:
                        # LinkedIn with professional messaging
                        linkedin_url = f"https://www.linkedin.com/sharing/share-offsite/?url={app_url}"
                        if st.button("💼 LinkedIn", use_container_width=True, key="share_linkedin"):
                            components.html(
                                f"""<script>window.open("{linkedin_url}", "_blank");</script>""",
                                height=0
                            )
                            st.success("Opening LinkedIn in new tab...")

                    with col3:
                        facebook_url = f"https://www.facebook.com/sharer/sharer.php?u={app_url}"
                        if st.button("📘 Facebook", use_container_width=True, key="share_facebook"):
                            components.html(
                                f"""<script>window.open("{facebook_url}", "_blank");</script>""",
                                height=0
                            )
                            st.success("Opening Facebook in new tab...")

                    with col4:
                        if st.button("📧 Email", use_container_width=True, key="share_email"):
                            # Enhanced email with detailed value proposition
                            email_subject = "Powerful FREE Retirement Planning Tool - Smart Retire AI"
                            email_body = (
                                "Hi!%0A%0A"
                                "I discovered Smart Retire AI and thought you might find it helpful for retirement planning.%0A%0A"
                                "✨ What makes it special:%0A"
                                "• AI-powered financial statement analysis%0A"
                                "• Tax-optimized retirement projections%0A"
                                "• Monte Carlo simulations for risk assessment%0A"
                                "• Personalized recommendations based on your goals%0A"
                                "• PDF reports with detailed breakdowns%0A"
                                "• Completely FREE to use%0A%0A"
                                "Check it out: " + app_url + "%0A%0A"
                                "Best regards"
                            )
                            email_url = f"mailto:?subject={email_subject}&body={email_body}"
                            components.html(
                                f"""<script>window.location.href="{email_url}";</script>""",
                                height=0
                            )
                            st.success("Opening email client...")
    
                    st.markdown("---")
                    st.markdown("**Or copy and share the link:**")
                    st.code(app_url, language=None)
    
                with feedback_tab2:
                    st.markdown("**We'd love to hear from you!**")
    
                    # Quick rating
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("👍 Love it!", use_container_width=True, key="feedback_love"):
                            st.success("Thank you! 💚")
                            st.markdown("[Tell us what you love →](mailto:smartretireai@gmail.com?subject=Positive%20Feedback)")
                    with col2:
                        if st.button("👎 Could improve", use_container_width=True, key="feedback_improve"):
                            st.info("Thanks for the feedback!")
                            st.markdown("[Share suggestions →](mailto:smartretireai@gmail.com?subject=Suggestions)")
    
                    st.markdown("---")
    
                    # Simple feedback form
                    with st.form("simple_feedback_nextsteps"):
                        feedback_msg = st.text_area("Your feedback:", placeholder="Share your thoughts, report bugs, or request features...", height=100)
                        if st.form_submit_button("📧 Send Feedback"):
                            if feedback_msg:
                                email_url = f"mailto:smartretireai@gmail.com?subject=Smart%20Retire%20AI%20Feedback&body={feedback_msg}"
                                st.success("Ready to send!")
                                st.markdown(f"[Click to open email →]({email_url})")
    
                with feedback_tab3:
                    st.markdown("""
                    **Get in touch:**
    
                    📧 **Email:** [smartretireai@gmail.com](mailto:smartretireai@gmail.com)
                    ⏱️ **Response time:** 24-48 hours
                    🐙 **GitHub:** [Report Issues](https://github.com/abhorkarpet/financialadvisor/issues)
    
                    We're here to help with questions, bugs, or feature requests!
                    """)
    
        except Exception as e:
            st.error(f"❌ **Error in calculation**: {e}")
            with st.expander("🔍 Error Details", expanded=False):
                st.exception(e)
    
    elif st.session_state.current_page == 'detailed_analysis':
        # ==========================================
        # DETAILED ANALYSIS PAGE
        # ==========================================

        track_page_view('detailed_analysis')

        if st.button("← Back to Results", use_container_width=False):
            st.session_state.current_page = 'results'
            st.rerun()

        st.markdown("---")
        st.header("📈 Detailed Analysis")

        result = st.session_state.get('last_result')
        inputs = st.session_state.get('last_inputs')

        if not result:
            st.warning("No analysis data found. Please run a retirement analysis first.")
            st.stop()

        detail_tab1, detail_tab2, detail_tab3 = st.tabs(["💰 Asset Breakdown", "📊 Tax Analysis", "📋 Summary"])

        with detail_tab1:
            st.write("**Individual Asset Values at Retirement**")

            def humanize_account_name(name: str) -> str:
                """Convert account names to human-readable format."""
                replacements = {
                    'roth_ira': 'Roth IRA',
                    'ira': 'IRA',
                    '401k': '401(k)',
                    'hsa': 'HSA (Health Savings Account)'
                }
                name_lower = name.lower()
                for key, value in replacements.items():
                    if name_lower == key:
                        return value
                return name

            if 'asset_results' in result and 'assets_input' in result:
                asset_data = []
                total_current = 0
                total_contributions = 0
                total_growth = 0
                total_pre_tax = 0
                total_taxes = 0
                total_after_tax = 0

                for i, (asset_result, asset_input) in enumerate(zip(result['asset_results'], result['assets_input'])):
                    current_balance = asset_input.current_balance
                    contributions = asset_result['total_contributions']
                    pre_tax_value = asset_result['pre_tax_value']
                    tax_liability = asset_result['tax_liability']
                    after_tax_value = asset_result['after_tax_value']
                    growth = pre_tax_value - current_balance - contributions

                    total_current += current_balance
                    total_contributions += contributions
                    total_growth += growth
                    total_pre_tax += pre_tax_value
                    total_taxes += tax_liability
                    total_after_tax += after_tax_value

                    asset_data.append({
                        "Account": humanize_account_name(asset_result['name']),
                        "Current Balance": f"${current_balance:,.0f}",
                        "Your Contributions": f"${contributions:,.0f}",
                        "Investment Growth": f"${growth:,.0f}",
                        "Pre-Tax Value": f"${pre_tax_value:,.0f}",
                        "Est. Taxes": f"${tax_liability:,.0f}",
                        "After-Tax Value": f"${after_tax_value:,.0f}"
                    })

                if asset_data:
                    asset_data.append({
                        "Account": "📊 TOTAL",
                        "Current Balance": f"${total_current:,.0f}",
                        "Your Contributions": f"${total_contributions:,.0f}",
                        "Investment Growth": f"${total_growth:,.0f}",
                        "Pre-Tax Value": f"${total_pre_tax:,.0f}",
                        "Est. Taxes": f"${total_taxes:,.0f}",
                        "After-Tax Value": f"${total_after_tax:,.0f}"
                    })
                    st.info("💡 **How to read this table**: Current Balance → Add Your Contributions → Add Investment Growth = Pre-Tax Value → Subtract Taxes = After-Tax Value")
                    st.dataframe(pd.DataFrame(asset_data), use_container_width=True, hide_index=True)
                else:
                    st.info("No individual asset breakdown available")
            else:
                asset_data = []
                for key, value in result.items():
                    if "Asset" in key and "After-Tax" in key:
                        asset_name = key.split(" - ")[1].replace(" (After-Tax)", "")
                        asset_data.append({
                            "Account": humanize_account_name(asset_name),
                            "After-Tax Value": f"${value:,.0f}"
                        })
                if asset_data:
                    st.dataframe(pd.DataFrame(asset_data), use_container_width=True, hide_index=True)
                else:
                    st.info("No individual asset breakdown available")

            st.markdown("---")
            with st.expander("📊 How Are These Numbers Calculated?", expanded=False):
                st.markdown("Click below to see a detailed breakdown of the calculation formula and methodology.")
                if st.button("🔍 Show Detailed Calculation Explanation", key="show_explanation_btn"):
                    explanation = explain_projected_balance(inputs)
                    st.text(explanation)
                    st.download_button(
                        label="📥 Download Explanation",
                        data=explanation,
                        file_name=f"retirement_calculation_explanation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain",
                        key="download_explanation_btn"
                    )

        with detail_tab2:
            tax_liability = result.get("Total Tax Liability", 0.0)
            total_pre_tax = result.get("Total Future Value (Pre-Tax)", 1.0)
            tax_percentage = (tax_liability / total_pre_tax * 100) if total_pre_tax > 0 else 0.0

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Tax Liability", f"${tax_liability:,.0f}")
                st.metric("Tax as % of Pre-Tax Value", f"{tax_percentage:.1f}%")
            with col2:
                if result["Tax Efficiency (%)"] > 85:
                    st.success("🎉 **Excellent tax efficiency!** Your portfolio is well-optimized with minimal tax liability.")
                elif result["Tax Efficiency (%)"] > 75:
                    st.warning(f"⚠️ **Good tax efficiency** ({tax_percentage:.1f}% tax burden), but there may be room for improvement. *Goal: Lower this percentage by shifting assets to tax-advantaged accounts.*")
                    with st.expander("💡 **Get Tax Optimization Advice**", expanded=False):
                        st.markdown("""
                        ### 🎯 **Tax Optimization Strategies**

                        **1. Asset Location Optimization:**
                        - **Taxable accounts**: Hold tax-efficient index funds, municipal bonds
                        - **401(k)/IRA**: Hold high-dividend stocks, REITs, bonds
                        - **Roth IRA**: Hold high-growth stocks, international funds

                        **2. Contribution Strategy:**
                        - **Maximize employer 401(k) match** (free money!)
                        - **Consider Roth vs Traditional** based on current vs future tax rates
                        - **Backdoor Roth IRA** if income exceeds limits

                        **3. Withdrawal Strategy:**
                        - **Tax-loss harvesting** in taxable accounts
                        - **Roth conversion** during low-income years
                        - **Strategic withdrawal order**: Taxable → Traditional → Roth

                        **4. Advanced Strategies:**
                        - **HSA triple tax advantage** for medical expenses
                        - **Municipal bonds** for high tax brackets
                        - **Tax-efficient fund selection** (low turnover, index funds)

                        💡 **Next Steps**: Consider consulting a tax professional for personalized advice based on your specific situation.
                        """)
                else:
                    st.error("🚨 **Consider tax optimization** strategies to improve efficiency.")
                    with st.expander("🚨 **Urgent Tax Optimization Needed**", expanded=True):
                        st.markdown("""
                        ### ⚠️ **Your Tax Efficiency Needs Immediate Attention**

                        **Priority Actions:**
                        1. **Review asset allocation** across account types
                        2. **Maximize tax-advantaged contributions** (401k, IRA, HSA)
                        3. **Consider Roth conversions** if in lower tax bracket
                        4. **Optimize fund selection** for tax efficiency

                        **Quick Wins:**
                        - Switch to index funds (lower turnover = less taxes)
                        - Use tax-loss harvesting strategies
                        - Consider municipal bonds for taxable accounts
                        - Maximize HSA contributions if eligible

                        📞 **Recommendation**: Consult a financial advisor for comprehensive tax optimization strategy.
                        """)

        with detail_tab3:
            summary_data = {
                "Metric": [
                    "Years Until Retirement",
                    "Total Future Value (Pre-Tax)",
                    "Total After-Tax Balance",
                    "Total Tax Liability",
                    "Tax Efficiency (%)"
                ],
                "Value": [
                    f"{result['Years Until Retirement']:.0f} years",
                    f"${result['Total Future Value (Pre-Tax)']:,.0f}",
                    f"${result['Total After-Tax Balance']:,.0f}",
                    f"${result['Total Tax Liability']:,.0f}",
                    f"{result['Tax Efficiency (%)']:.1f}%"
                ]
            }
            st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)

    elif st.session_state.current_page == 'monte_carlo':
        # Show analytics consent dialog on first load
        if st.session_state.get('analytics_consent') is None:
            analytics_consent_dialog()

        # ==========================================
        # MONTE CARLO SIMULATION PAGE
        # ==========================================

        # Track page view
        track_page_view('monte_carlo')
    
        # Add navigation buttons to go back
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("← Back to Results", use_container_width=True):
                track_event('navigation_back_to_results')
                st.session_state.current_page = 'results'
                st.rerun()
    
        st.markdown("---")
    
        # Header
        st.header("🎲 Monte Carlo Simulation")
        st.markdown("Explore thousands of possible retirement scenarios with probabilistic analysis")
    
        st.markdown("---")
    
        # Educational explanation
        with st.expander("📚 What is Monte Carlo Simulation?", expanded=False):
            st.markdown("""
            ### What is Monte Carlo Simulation?
    
            Monte Carlo simulation runs **thousands of possible market scenarios** to show you the range of
            potential retirement outcomes, not just a single projection.
    
            **Why use it?**
            - Markets don't deliver consistent returns every year
            - See probability ranges (best case, worst case, most likely)
            - Understand uncertainty in your retirement plan
            - Make more informed decisions with probabilistic analysis
    
            **How it works:**
            1. Runs 1,000+ simulations with varying market returns
            2. Returns vary randomly around your expected growth rate
            3. Shows distribution of possible outcomes
            4. Calculates probability of meeting your retirement goals
            5. **Shows projected annual income variation** (not just final balance)
            """)
    
        st.markdown("---")
    
        # Configuration Section
        st.subheader("⚙️ Simulation Settings")
    
        # Get default values from session state if coming from dialog
        default_num_sims = 1000
        default_volatility = 15.0
        if 'monte_carlo_config' in st.session_state:
            default_num_sims = st.session_state.monte_carlo_config.get('num_simulations', 1000)
            default_volatility = st.session_state.monte_carlo_config.get('volatility', 15.0)
            # Clear the config after using it
            del st.session_state.monte_carlo_config
    
        col1, col2 = st.columns(2)
    
        with col1:
            num_simulations = st.select_slider(
                "Number of Simulations",
                options=[100, 500, 1000, 5000, 10000],
                value=default_num_sims,
                help="More simulations = more accurate results (but slower)"
            )
    
        with col2:
            volatility = st.slider(
                "Market Volatility (Standard Deviation %)",
                min_value=5.0,
                max_value=30.0,
                value=default_volatility,
                step=1.0,
                help="Historical stock market volatility is ~15-20%. Higher = more uncertainty."
            )
    
        st.markdown("---")
    
        # Run Simulation Button
        if st.button("🎲 Run Monte Carlo Simulation", type="primary", use_container_width=True, key="run_monte_carlo_main"):
            try:
                from financialadvisor.core.monte_carlo import (
                    run_monte_carlo_simulation,
                    calculate_probability_of_goal,
                    get_confidence_interval
                )
    
                # Prepare inputs for simulation
                current_year_mc = datetime.now().year
    
                simulation_inputs = UserInputs(
                    age=current_year_mc - st.session_state.birth_year,
                    retirement_age=int(st.session_state.whatif_retirement_age),
                    life_expectancy=int(st.session_state.whatif_life_expectancy),
                    annual_income=0.0,
                    contribution_rate_pct=15.0,
                    expected_growth_rate_pct=7.0,
                    inflation_rate_pct=float(st.session_state.whatif_inflation_rate),
                    current_marginal_tax_rate_pct=float(st.session_state.whatif_current_tax_rate),
                    retirement_marginal_tax_rate_pct=float(st.session_state.whatif_retirement_tax_rate),
                    assets=st.session_state.assets
                )
    
                with st.spinner(f"Running {num_simulations:,} simulations..."):
                    results = run_monte_carlo_simulation(
                        simulation_inputs,
                        num_simulations=num_simulations,
                        volatility=volatility
                    )
    
                    # Calculate probability of meeting income goal
                    prob_success: Optional[float]
                    if st.session_state.whatif_retirement_income_goal > 0:
                        prob_success = calculate_probability_of_goal(
                            results["outcomes"],
                            int(st.session_state.whatif_retirement_age),
                            int(st.session_state.whatif_life_expectancy),
                            float(st.session_state.whatif_retirement_income_goal)
                        )
                    else:
                        prob_success = None
    
                    # Get confidence interval
                    ci_lower, ci_upper = get_confidence_interval(results["outcomes"], confidence=0.95)
                    ci_income_lower, ci_income_upper = get_confidence_interval(results["annual_income_outcomes"], confidence=0.95)

                # Escape currency for markdown so "$...$" is not parsed as LaTeX/math.
                def md_currency(v):
                    return f"\\${v:,.0f}"
    
                # Track successful Monte Carlo run
                track_monte_carlo_run(num_simulations=num_simulations, volatility=volatility)
    
                # Display Results
                st.success(f"✅ Completed {num_simulations:,} simulations!")
    
            except Exception as e:
                # Track Monte Carlo error
                track_error('monte_carlo_error', str(e), {
                    'num_simulations': num_simulations,
                    'volatility': volatility
                })
                st.error(f"❌ Error running Monte Carlo simulation: {str(e)}")
                st.info("💡 Try reducing the number of simulations or refreshing the page.")
                st.stop()
    
            st.markdown("---")
    
            # Key Metrics - Annual Income (Primary Focus)
            st.markdown("### 💰 Projected Annual Income Distribution")
            st.info("This shows how much annual income you could have in retirement across different market scenarios")
    
            metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    
            with metric_col1:
                st.metric(
                    "Median Annual Income",
                    f"${results['income_percentiles']['50th']:,.0f}",
                    help="50th percentile - half of outcomes above, half below"
                )
    
            with metric_col2:
                st.metric(
                    "Mean Annual Income",
                    f"${results['mean_annual_income']:,.0f}",
                    help="Average annual income across all simulations"
                )
    
            with metric_col3:
                st.metric(
                    "Best Case (90th %ile)",
                    f"${results['income_percentiles']['90th']:,.0f}",
                    help="90% of outcomes are below this annual income"
                )
    
            with metric_col4:
                st.metric(
                    "Worst Case (10th %ile)",
                    f"${results['income_percentiles']['10th']:,.0f}",
                    help="Only 10% of outcomes are below this annual income"
                )
    
            # Annual Income Percentile Breakdown
            st.markdown("#### Annual Income Range (Percentiles)")
    
            income_percentile_data = {
                "Percentile": ["10th", "25th", "50th (Median)", "75th", "90th"],
                "Annual Income": [
                    f"${results['income_percentiles']['10th']:,.0f}",
                    f"${results['income_percentiles']['25th']:,.0f}",
                    f"${results['income_percentiles']['50th']:,.0f}",
                    f"${results['income_percentiles']['75th']:,.0f}",
                    f"${results['income_percentiles']['90th']:,.0f}",
                ]
            }
    
            st.table(income_percentile_data)
    
            # 95% Confidence Interval for Income
            ci_lines = [
                f"**95% Confidence Interval for Annual Income:** {md_currency(ci_income_lower)} - {md_currency(ci_income_upper)}",
                "",
                "There's a 95% probability your annual retirement income will fall within this range.",
            ]
            st.markdown("\n".join(ci_lines))
    
            # Probability of success
            if prob_success is not None:
                st.markdown("")
                if prob_success >= 80:
                    st.success(f"🎯 **{prob_success:.1f}% probability** of meeting your ${st.session_state.whatif_retirement_income_goal:,.0f}/year income goal")
                elif prob_success >= 60:
                    st.warning(f"⚠️ **{prob_success:.1f}% probability** of meeting your ${st.session_state.whatif_retirement_income_goal:,.0f}/year income goal")
                else:
                    st.error(f"🚨 **{prob_success:.1f}% probability** of meeting your ${st.session_state.whatif_retirement_income_goal:,.0f}/year income goal")
    
            # Distribution visualization for Annual Income
            st.markdown("#### Distribution of Annual Income Outcomes")
    
            # Create histogram data for income
            import math
            num_bins = 30
            min_val = results['min_income']
            max_val = results['max_income']
            bin_width = (max_val - min_val) / num_bins
    
            # Store bins with numeric centers for proper sorting
            bins_data: Dict[float, int] = {}
            for outcome in results['annual_income_outcomes']:
                bin_idx = min(int((outcome - min_val) / bin_width), num_bins - 1)
                bin_center = min_val + (bin_idx + 0.5) * bin_width
                bins_data[bin_center] = bins_data.get(bin_center, 0) + 1
    
            # Sort by bin_center and create labels
            sorted_bins = sorted(bins_data.items())
            bins_df = pd.DataFrame([
                {"Income Range": f"${center/1000:.0f}K", "Count": count}
                for center, count in sorted_bins
            ])
    
            # Use categorical index to preserve sort order (prevent alphabetical re-sorting)
            bins_df["Income Range"] = pd.Categorical(
                bins_df["Income Range"],
                categories=bins_df["Income Range"].tolist(),
                ordered=True
            )
            bins_df = bins_df.set_index("Income Range")
    
            # Display as bar chart
            st.bar_chart(bins_df)
    
            st.info("""
            💡 **Interpretation Tips:**
            - The median (50th percentile) is your most likely annual income
            - The 10th-90th percentile range shows 80% of possible income outcomes
            - Higher volatility = wider range of annual income outcomes
            - Conservative planning often targets the 25th percentile or lower
            """)
    
            st.markdown("---")
    
            # Secondary Metrics - Total Balance
            st.markdown("### 📊 Total Retirement Balance Distribution")
    
            metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    
            with metric_col1:
                st.metric(
                    "Median Balance",
                    f"${results['percentiles']['50th']:,.0f}",
                    help="50th percentile - half of outcomes above, half below"
                )
    
            with metric_col2:
                st.metric(
                    "Mean Balance",
                    f"${results['mean']:,.0f}",
                    help="Average of all simulated outcomes"
                )
    
            with metric_col3:
                st.metric(
                    "Best Case (90th %ile)",
                    f"${results['percentiles']['90th']:,.0f}",
                    help="90% of outcomes are below this value"
                )
    
            with metric_col4:
                st.metric(
                    "Worst Case (10th %ile)",
                    f"${results['percentiles']['10th']:,.0f}",
                    help="Only 10% of outcomes are below this value"
                )
    
            # Percentile breakdown for balance
            st.markdown("#### Total Balance Range (Percentiles)")
    
            percentile_data = {
                "Percentile": ["10th", "25th", "50th (Median)", "75th", "90th"],
                "After-Tax Balance": [
                    f"${results['percentiles']['10th']:,.0f}",
                    f"${results['percentiles']['25th']:,.0f}",
                    f"${results['percentiles']['50th']:,.0f}",
                    f"${results['percentiles']['75th']:,.0f}",
                    f"${results['percentiles']['90th']:,.0f}",
                ]
            }
    
            st.table(percentile_data)
    
            # 95% Confidence Interval for Balance
            ci_balance_lines = [
                f"**95% Confidence Interval for Total Balance:** {md_currency(ci_lower)} - {md_currency(ci_upper)}",
                "",
                "There's a 95% probability your retirement balance will fall within this range.",
            ]
            st.markdown("\n".join(ci_balance_lines))
    
            # Distribution visualization for Balance
            st.markdown("#### Distribution of Balance Outcomes")
    
            # Create histogram data for balance
            min_val_balance = results['min']
            max_val_balance = results['max']
            bin_width_balance = (max_val_balance - min_val_balance) / num_bins
    
            # Store bins with numeric centers for proper sorting
            bins_balance_data: Dict[float, int] = {}
            for outcome in results['outcomes']:
                bin_idx = min(int((outcome - min_val_balance) / bin_width_balance), num_bins - 1)
                bin_center = min_val_balance + (bin_idx + 0.5) * bin_width_balance
                bins_balance_data[bin_center] = bins_balance_data.get(bin_center, 0) + 1
    
            # Sort by bin_center and create labels
            sorted_bins_balance = sorted(bins_balance_data.items())
            bins_balance_df = pd.DataFrame([
                {"Balance Range": f"${center/1000:.0f}K", "Count": count}
                for center, count in sorted_bins_balance
            ])
    
            # Use categorical index to preserve sort order (prevent alphabetical re-sorting)
            bins_balance_df["Balance Range"] = pd.Categorical(
                bins_balance_df["Balance Range"],
                categories=bins_balance_df["Balance Range"].tolist(),
                ordered=True
            )
            bins_balance_df = bins_balance_df.set_index("Balance Range")
    
            # Display as bar chart
            st.bar_chart(bins_balance_df)
    
    # Page footer with version, copyright, and contact information
    st.markdown("---")
    _, col_center, _ = st.columns([3, 2, 3])
    with col_center:
        if st.button(f"📋 What's new in v{VERSION}", use_container_width=True):
            st.session_state.show_whats_new = True
            st.rerun()
    st.markdown(
        f"""
        <div style='text-align: center; color: #666; font-size: 0.85em; padding: 20px 10px; background-color: #f8f9fa; border-radius: 8px; margin-top: 30px;'>
            <div style='margin-bottom: 8px;'>
                <strong style='color: #1f77b4;'>Smart Retire AI v{VERSION}</strong>
            </div>
            <div style='margin-bottom: 8px; color: #888;'>
                Advanced Retirement Planning with Asset Classification & Tax Optimization
            </div>
            <div style='margin-bottom: 8px;'>
                <span style='color: #555;'>© 2025-2026 Smart Retire AI. All rights reserved.</span>
            </div>
            <div>
                <span style='color: #555;'>Questions? Contact us: </span>
                <a href='mailto:smartretireai@gmail.com' style='color: #1f77b4; text-decoration: none; font-weight: 500;'>
                    smartretireai@gmail.com
                </a>
            </div>
            <div style='margin-top: 12px; font-size: 0.75em; color: #999;'>
                <em>Disclaimer: This tool provides estimates for educational purposes. Consult a financial advisor for personalized advice.</em>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    
# ---------------------------
# Tests (unittest)
# ---------------------------

import unittest


# ---------------------------
# Entrypoint
# ---------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Smart Retire AI - Advanced Retirement Planning")
    p.add_argument("--run-tests", action="store_true", help="Run unit tests and exit")
    return p


# Test runner - only runs when called with --run-tests
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and "--run-tests" in sys.argv:
        suite = unittest.defaultTestLoader.discover("tests")
        test_result = unittest.TextTestRunner(verbosity=2).run(suite)
        sys.exit(0 if test_result.wasSuccessful() else 1)
    else:
        print("🚀 Smart Retire AI - Advanced Retirement Planning")
        print("=" * 60)
        print("\nThis application requires the Streamlit web interface.")
        print("\nTo run the application:")
        print("  streamlit run fin_advisor.py")
        print("\nThis will open your web browser with the interactive interface.")
        print("\nFor testing, use:")
        print("  python3 fin_advisor.py --run-tests")
