"""Core financial calculation functions."""


def years_to_retirement(age: int, retirement_age: int) -> int:
    """Calculate years remaining until retirement.

    Args:
        age: Current age
        retirement_age: Target retirement age

    Returns:
        Number of years until retirement

    Raises:
        ValueError: If retirement_age is less than current age
    """
    if retirement_age < age:
        raise ValueError("retirement_age must be >= age")
    return retirement_age - age


def future_value_with_contrib(
    principal: float,
    annual_contribution: float,
    rate_pct: float,
    years: int
) -> float:
    """Compute future value with annual compounding and end-of-year contributions.

    Uses the formula:
    FV = P*(1+r)^t + C * [((1+r)^t - 1)/r]

    Where:
    - P = principal (current balance)
    - r = annual growth rate (as decimal)
    - t = time in years
    - C = annual contribution

    Handles zero-rate edge case explicitly.

    Args:
        principal: Current balance
        annual_contribution: Amount contributed at end of each year
        rate_pct: Annual growth rate as percentage (e.g., 7.0 for 7%)
        years: Number of years to project

    Returns:
        Future value after specified years

    Raises:
        ValueError: If years is negative
    """
    if years < 0:
        raise ValueError("years must be >= 0")

    r = rate_pct / 100.0

    # Special case: zero growth rate
    if r == 0:
        return principal + annual_contribution * years

    # Standard compound interest with contributions
    growth = (1.0 + r) ** years
    return principal * growth + annual_contribution * ((growth - 1.0) / r)
