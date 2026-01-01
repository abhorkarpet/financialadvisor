"""Core business logic for retirement planning."""

from financialadvisor.core.calculator import (
    years_to_retirement,
    future_value_with_contrib,
)

from financialadvisor.core.tax_engine import (
    get_irs_tax_brackets_2024,
    project_tax_rate,
    calculate_asset_growth,
    apply_tax_logic,
)

from financialadvisor.core.projector import project

from financialadvisor.core.explainer import explain_projected_balance

__all__ = [
    "years_to_retirement",
    "future_value_with_contrib",
    "get_irs_tax_brackets_2024",
    "project_tax_rate",
    "calculate_asset_growth",
    "apply_tax_logic",
    "project",
    "explain_projected_balance",
]
