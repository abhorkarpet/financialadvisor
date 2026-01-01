"""Main retirement projection logic."""

from typing import Dict

from financialadvisor.domain.models import Asset, AssetType, UserInputs
from financialadvisor.core.calculator import years_to_retirement
from financialadvisor.core.tax_engine import calculate_asset_growth, apply_tax_logic


def project(inputs: UserInputs) -> Dict[str, float]:
    """Enhanced projection with asset classification and sophisticated tax logic.

    Calculates retirement projections considering:
    - Multiple assets with different tax treatments
    - Compound growth with annual contributions
    - Tax-advantaged account benefits
    - Detailed per-asset breakdown

    Args:
        inputs: UserInputs object with all retirement parameters

    Returns:
        Dictionary with projection results including:
        - Total Future Value (Pre-Tax)
        - Total After-Tax Balance
        - Total Tax Liability
        - Tax Efficiency (%)
        - Per-asset breakdown
        - Backward-compatible aliases
    """
    yrs = years_to_retirement(inputs.age, inputs.retirement_age)

    # If no assets defined, create a default one for backward compatibility
    if not inputs.assets:
        total_contribution = inputs.annual_income * (inputs.contribution_rate_pct / 100.0)
        # Treat the year's contribution as already invested for backward compatibility
        default_asset = Asset(
            name="401(k) / Traditional IRA (Pre-Tax)",
            asset_type=AssetType.PRE_TAX,
            current_balance=inputs.current_balance + total_contribution,
            annual_contribution=0.0,
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
        "asset_results": asset_results,  # Store detailed breakdown for display
        "assets_input": inputs.assets  # Store input assets for current balance
    }

    # Backwards-compatible aliases expected by older callers/tests
    result["Future Value (Pre-Tax)"] = result["Total Future Value (Pre-Tax)"]
    result["Estimated Post-Tax Balance"] = result["Total After-Tax Balance"]

    # Add per-asset breakdown
    for i, asset_result in enumerate(asset_results):
        result[f"Asset {i+1} - {asset_result['name']} (Pre-Tax)"] = round(asset_result['pre_tax_value'], 2)
        result[f"Asset {i+1} - {asset_result['name']} (After-Tax)"] = round(asset_result['after_tax_value'], 2)

    return result
