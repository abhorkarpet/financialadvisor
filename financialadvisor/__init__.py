"""
Financial Advisor - Retirement Planning Library

A modular retirement planning tool with asset classification,
tax-advantaged projections, and detailed explanations.
"""

# Version
__version__ = "4.6.0"

# Domain models
from financialadvisor.domain.models import (
    AssetType,
    Asset,
    TaxBracket,
    UserInputs,
)

# Core functions
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

# Public API
__all__ = [
    # Version
    "__version__",

    # Domain models
    "AssetType",
    "Asset",
    "TaxBracket",
    "UserInputs",

    # Core calculation functions
    "years_to_retirement",
    "future_value_with_contrib",
    "calculate_asset_growth",

    # Tax functions
    "get_irs_tax_brackets_2024",
    "project_tax_rate",
    "apply_tax_logic",

    # Main functions
    "project",
    "explain_projected_balance",
]
