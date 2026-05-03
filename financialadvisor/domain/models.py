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


class TaxBehavior(Enum):
    """Explicit tax behavior used by projection logic."""
    PRE_TAX = "pre_tax"
    TAX_FREE = "tax_free"
    CAPITAL_GAINS = "capital_gains"
    HSA_SPLIT = "hsa_split"
    ORDINARY_INCOME = "ordinary_income"
    INTEREST_INCOME = "interest_income"  # gains-only taxed at ordinary income rate (savings/checking)
    NO_ADDITIONAL_TAX = "no_additional_tax"


def _normalize_asset_type(value):
    """Normalize string asset types for backward compatibility."""
    if isinstance(value, AssetType):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "pretax": AssetType.PRE_TAX,
            "posttax": AssetType.POST_TAX,
            "taxdeferred": AssetType.TAX_DEFERRED,
        }
        if normalized in aliases:
            return aliases[normalized]
        return AssetType(normalized)
    return value


def _normalize_tax_behavior(value):
    """Normalize string tax behaviors for backward compatibility."""
    if value is None or isinstance(value, TaxBehavior):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        return TaxBehavior(normalized)
    return value


def infer_tax_behavior(asset_type, name: str, tax_rate_pct: float = 0.0) -> TaxBehavior:
    """Infer tax behavior when legacy callers don't set it explicitly."""
    normalized_asset_type = _normalize_asset_type(asset_type)
    name_lower = (name or "").lower()

    if normalized_asset_type == AssetType.PRE_TAX:
        return TaxBehavior.PRE_TAX

    if normalized_asset_type == AssetType.TAX_DEFERRED:
        if "hsa" in name_lower or "health savings" in name_lower:
            return TaxBehavior.HSA_SPLIT
        return TaxBehavior.ORDINARY_INCOME

    if normalized_asset_type == AssetType.POST_TAX:
        if "roth" in name_lower:
            return TaxBehavior.TAX_FREE
        if any(keyword in name_lower for keyword in ("savings", "checking", "cash")):
            return TaxBehavior.INTEREST_INCOME
        if tax_rate_pct > 0 or any(
            keyword in name_lower
            for keyword in ("brokerage", "taxable", "stock", "espp", "rsu", "equity", "mutual fund")
        ):
            return TaxBehavior.CAPITAL_GAINS
        return TaxBehavior.NO_ADDITIONAL_TAX

    raise ValueError(f"Unknown asset type for tax behavior inference: {asset_type}")


def infer_asset_type_from_name(name: str) -> AssetType:
    """Infer asset type from a legacy account name when no exact mapping exists."""
    normalized = (name or "").strip().lower()

    if any(token in normalized for token in ("hsa", "health savings", "annuity")):
        return AssetType.TAX_DEFERRED

    if any(token in normalized for token in ("roth", "brokerage", "taxable", "savings", "checking", "cash")):
        return AssetType.POST_TAX

    if any(token in normalized for token in ("401", "403", "457", "traditional ira", "rollover ira", "pre-tax", "pretax")):
        return AssetType.PRE_TAX

    if "ira" in normalized:
        return AssetType.PRE_TAX

    return AssetType.POST_TAX


@dataclass
class Asset:
    """Individual asset with specific tax treatment."""
    name: str
    asset_type: AssetType
    current_balance: float
    annual_contribution: float
    growth_rate_pct: float
    tax_behavior: Optional[TaxBehavior] = None
    tax_rate_pct: float = 0.0  # For post_tax assets (capital gains)

    def __post_init__(self):
        """Validate asset configuration."""
        self.asset_type = _normalize_asset_type(self.asset_type)
        self.tax_behavior = _normalize_tax_behavior(self.tax_behavior)

        if self.tax_behavior is None:
            self.tax_behavior = infer_tax_behavior(self.asset_type, self.name, self.tax_rate_pct)

        if self.tax_behavior == TaxBehavior.CAPITAL_GAINS and self.tax_rate_pct == 0.0:
            # Default capital gains rate for brokerage-style accounts
            self.tax_rate_pct = 15.0
        elif self.tax_behavior != TaxBehavior.CAPITAL_GAINS:
            self.tax_rate_pct = 0.0


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
                asset_type = name_to_type.get(name, infer_asset_type_from_name(name))
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
