"""Domain models for retirement planning."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


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


# Default asset type mappings
_DEF_ASSET_TYPES = [
    ("401(k) / Traditional IRA", AssetType.PRE_TAX),
    ("Roth IRA", AssetType.POST_TAX),
    ("Brokerage Account", AssetType.POST_TAX),
    ("HSA (Health Savings Account)", AssetType.TAX_DEFERRED),
    ("Annuity", AssetType.TAX_DEFERRED),
    ("Savings Account", AssetType.POST_TAX),
]


@dataclass(init=False)
class UserInputs:
    """User inputs for retirement planning with backward compatibility.

    Supports both modern asset-based inputs and legacy single-balance inputs.
    """
    age: int
    retirement_age: int
    life_expectancy: int = 90  # Expected age at death
    annual_income: float = 0.0
    contribution_rate_pct: float = 0.0  # % of income contributed annually
    expected_growth_rate_pct: float = 7.0  # nominal annual return %
    inflation_rate_pct: float = 3.0
    current_marginal_tax_rate_pct: float = 0.0  # Current tax bracket
    retirement_marginal_tax_rate_pct: float = 0.0  # Projected retirement tax bracket
    assets: List[Asset] = field(default_factory=list)

    def __init__(
        self,
        age: int,
        retirement_age: int,
        annual_income: float = 0.0,
        contribution_rate_pct: float = 0.0,
        current_balance: Optional[float] = None,
        expected_growth_rate_pct: float = 7.0,
        inflation_rate_pct: float = 3.0,
        tax_rate_pct: Optional[float] = None,
        asset_types: Optional[List[str]] = None,
        life_expectancy: int = 90,
        current_marginal_tax_rate_pct: Optional[float] = None,
        retirement_marginal_tax_rate_pct: Optional[float] = None,
        assets: Optional[List[Asset]] = None,
    ):
        # Core fields
        self.age = age
        self.retirement_age = retirement_age
        self.life_expectancy = life_expectancy
        self.annual_income = annual_income
        self.contribution_rate_pct = contribution_rate_pct
        self.expected_growth_rate_pct = expected_growth_rate_pct
        self.inflation_rate_pct = inflation_rate_pct

        # Tax rates: prefer explicit modern names, fall back to legacy `tax_rate_pct` if provided
        if current_marginal_tax_rate_pct is not None:
            self.current_marginal_tax_rate_pct = current_marginal_tax_rate_pct
        elif tax_rate_pct is not None:
            self.current_marginal_tax_rate_pct = tax_rate_pct
        else:
            self.current_marginal_tax_rate_pct = 0.0

        if retirement_marginal_tax_rate_pct is not None:
            self.retirement_marginal_tax_rate_pct = retirement_marginal_tax_rate_pct
        else:
            # default to current tax rate if retirement not provided
            self.retirement_marginal_tax_rate_pct = self.current_marginal_tax_rate_pct

        # Legacy alias for tests / older callers
        self.tax_rate_pct = self.current_marginal_tax_rate_pct

        # Assets: accept modern `assets` list or legacy `asset_types` + `current_balance`
        self.assets = assets or []

        # Store legacy current balance if provided (used when no assets passed)
        self._legacy_current_balance = current_balance

        # If legacy asset_types provided and no explicit assets, create simple assets
        if asset_types and not self.assets:
            # Map known names to AssetType where possible
            name_to_type = {name: at for (name, at) in _DEF_ASSET_TYPES}
            for name in asset_types:
                asset_type = name_to_type.get(name, AssetType.POST_TAX)
                self.assets.append(
                    Asset(
                        name=name,
                        asset_type=asset_type,
                        current_balance=(self._legacy_current_balance or 0.0) if len(asset_types) == 1 else 0.0,
                        annual_contribution=self.annual_income * (self.contribution_rate_pct / 100.0),
                        growth_rate_pct=self.expected_growth_rate_pct,
                    )
                )

    @property
    def current_balance(self) -> float:
        """Total current balance across all assets or legacy value if no assets."""
        total = sum(asset.current_balance for asset in self.assets)
        if total == 0 and (self._legacy_current_balance is not None):
            return float(self._legacy_current_balance)
        return float(total)

    @property
    def asset_types(self) -> List[str]:
        """Legacy asset types for backward compatibility."""
        if self.assets:
            return [asset.name for asset in self.assets]
        return []
