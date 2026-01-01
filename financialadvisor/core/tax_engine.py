"""Tax calculation and projection logic."""

from typing import List, Tuple

from financialadvisor.domain.models import Asset, AssetType, TaxBracket
from financialadvisor.core.calculator import future_value_with_contrib


def get_irs_tax_brackets_2024() -> List[TaxBracket]:
    """Get 2024 IRS tax brackets for single filers.

    Returns:
        List of TaxBracket objects for 2024 single filer brackets
    """
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
    """Project marginal tax rate based on income and tax brackets.

    Args:
        income: Annual income
        brackets: List of tax brackets

    Returns:
        Marginal tax rate percentage for the given income
    """
    for bracket in brackets:
        if bracket.min_income <= income and (bracket.max_income is None or income < bracket.max_income):
            return bracket.rate_pct
    return brackets[-1].rate_pct  # Top bracket


def calculate_asset_growth(asset: Asset, years: int) -> Tuple[float, float]:
    """Calculate future value and total contributions for an asset.

    Args:
        asset: Asset to calculate growth for
        years: Number of years to project

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


def apply_tax_logic(
    asset: Asset,
    future_value: float,
    total_contributions: float,
    retirement_tax_rate_pct: float
) -> Tuple[float, float]:
    """Apply tax logic based on asset type.

    Different asset types have different tax treatments:
    - PRE_TAX: Taxed at full retirement rate on withdrawal
    - POST_TAX (Roth): Tax-free on withdrawal
    - POST_TAX (Brokerage): Capital gains taxed
    - TAX_DEFERRED (HSA): 50% medical (tax-free), 50% other (taxed)
    - TAX_DEFERRED (Annuities): Taxed as ordinary income

    Args:
        asset: Asset to apply tax logic to
        future_value: Pre-tax future value
        total_contributions: Total amount contributed over time
        retirement_tax_rate_pct: Marginal tax rate at retirement

    Returns:
        Tuple of (after_tax_value, tax_liability)

    Raises:
        ValueError: If asset type is unknown
    """
    # Handle both enum and string asset types for robustness
    asset_type = asset.asset_type
    if hasattr(asset_type, 'value'):
        asset_type_value = asset_type.value
    else:
        asset_type_value = str(asset_type)

    if asset_type == AssetType.PRE_TAX or asset_type_value == "pre_tax":
        # Pre-tax accounts: taxed at withdrawal
        tax_liability = future_value * (retirement_tax_rate_pct / 100.0)
        after_tax_value = future_value - tax_liability

    elif asset_type == AssetType.POST_TAX or asset_type_value == "post_tax":
        if "Roth" in asset.name:
            # Roth IRA: no tax on withdrawal
            after_tax_value = future_value
            tax_liability = 0.0
        else:
            # Brokerage: only capital gains are taxed
            gains = future_value - total_contributions
            tax_liability = gains * (asset.tax_rate_pct / 100.0)
            after_tax_value = future_value - tax_liability

    elif asset_type == AssetType.TAX_DEFERRED or asset_type_value == "tax_deferred":
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
        raise ValueError(
            f"Unknown asset type: {asset.asset_type} "
            f"(type: {type(asset.asset_type)}, value: {asset_type_value})"
        )

    return after_tax_value, tax_liability


def simple_post_tax(balance: float, tax_rate_pct: float) -> float:
    """Legacy function for backward compatibility.

    Args:
        balance: Pre-tax balance
        tax_rate_pct: Tax rate as percentage

    Returns:
        After-tax balance
    """
    tax_rate = tax_rate_pct / 100.0
    tax_rate = min(max(tax_rate, 0.0), 1.0)
    return balance * (1.0 - tax_rate)
