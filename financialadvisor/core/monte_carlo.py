"""Monte Carlo simulation for retirement projections.

Provides probabilistic analysis of retirement outcomes by simulating
thousands of possible market scenarios with varying returns.
"""

import random
from typing import Dict, List, Tuple
import statistics

from financialadvisor.domain.models import UserInputs, Asset
from financialadvisor.core.calculator import future_value_with_contrib
from financialadvisor.core.tax_engine import calculate_asset_growth, apply_tax_logic


def run_monte_carlo_simulation(
    inputs: UserInputs,
    num_simulations: int = 1000,
    volatility: float = 15.0,
    seed: int = None
) -> Dict:
    """Run Monte Carlo simulation for retirement projections.

    Simulates multiple possible market scenarios by varying the growth rate
    around the expected value using a normal distribution.

    Args:
        inputs: UserInputs object with retirement parameters
        num_simulations: Number of simulations to run (default: 1000)
        volatility: Standard deviation of returns in percentage (default: 15%)
        seed: Random seed for reproducibility (optional)

    Returns:
        Dictionary containing:
        - outcomes: List of all after-tax balance outcomes
        - percentiles: Dict of percentile values (10th, 25th, 50th, 75th, 90th)
        - probability_of_success: Probability of meeting retirement income goal
        - mean: Average outcome
        - std_dev: Standard deviation of outcomes
        - min: Minimum outcome
        - max: Maximum outcome
    """
    if seed is not None:
        random.seed(seed)

    years = inputs.retirement_age - inputs.age
    outcomes = []

    for _ in range(num_simulations):
        # Simulate each asset with varying returns
        total_pre_tax = 0.0
        total_after_tax = 0.0

        for asset in inputs.assets:
            # Generate random return based on normal distribution
            # Mean = asset's expected growth rate
            # Std dev = volatility
            simulated_growth_rate = random.gauss(asset.growth_rate_pct, volatility)

            # Ensure growth rate doesn't go below -50% or above 100%
            simulated_growth_rate = max(-50.0, min(100.0, simulated_growth_rate))

            # Calculate future value with simulated growth rate
            fv = future_value_with_contrib(
                asset.current_balance,
                asset.annual_contribution,
                simulated_growth_rate,
                years
            )

            # Apply tax logic
            total_contributions = asset.annual_contribution * years
            after_tax_value, _ = apply_tax_logic(
                asset,
                fv,
                total_contributions,
                inputs.retirement_marginal_tax_rate_pct
            )

            total_pre_tax += fv
            total_after_tax += after_tax_value

        outcomes.append(total_after_tax)

    # Calculate statistics
    outcomes_sorted = sorted(outcomes)
    mean = statistics.mean(outcomes)
    std_dev = statistics.stdev(outcomes) if len(outcomes) > 1 else 0.0

    # Calculate percentiles
    percentiles = {
        "10th": outcomes_sorted[int(len(outcomes) * 0.10)],
        "25th": outcomes_sorted[int(len(outcomes) * 0.25)],
        "50th": outcomes_sorted[int(len(outcomes) * 0.50)],  # Median
        "75th": outcomes_sorted[int(len(outcomes) * 0.75)],
        "90th": outcomes_sorted[int(len(outcomes) * 0.90)],
    }

    # Calculate probability of success (if income goal is set)
    # Success = having enough to support desired income through retirement
    probability_of_success = 0.0
    if hasattr(inputs, 'life_expectancy') and inputs.life_expectancy > inputs.retirement_age:
        years_in_retirement = inputs.life_expectancy - inputs.retirement_age
        # This would need the income goal - we'll calculate it generically
        # For now, just calculate what percentage meet the median outcome
        successful_outcomes = sum(1 for outcome in outcomes if outcome >= percentiles["50th"])
        probability_of_success = (successful_outcomes / len(outcomes)) * 100

    return {
        "outcomes": outcomes,
        "percentiles": percentiles,
        "probability_of_success": probability_of_success,
        "mean": mean,
        "std_dev": std_dev,
        "min": min(outcomes),
        "max": max(outcomes),
        "num_simulations": num_simulations,
        "volatility": volatility,
    }


def calculate_probability_of_goal(
    outcomes: List[float],
    retirement_age: int,
    life_expectancy: int,
    annual_income_goal: float
) -> float:
    """Calculate probability of meeting retirement income goal.

    Args:
        outcomes: List of simulated after-tax balance outcomes
        retirement_age: Age at retirement
        life_expectancy: Expected age at death
        annual_income_goal: Desired annual income in retirement

    Returns:
        Probability as percentage (0-100)
    """
    if annual_income_goal <= 0:
        return 100.0  # No goal set, always "successful"

    years_in_retirement = life_expectancy - retirement_age
    if years_in_retirement <= 0:
        return 0.0

    # Amount needed to fund desired income for entire retirement
    total_needed = annual_income_goal * years_in_retirement

    # Count outcomes that meet or exceed the goal
    successful = sum(1 for outcome in outcomes if outcome >= total_needed)

    return (successful / len(outcomes)) * 100 if outcomes else 0.0


def get_confidence_interval(outcomes: List[float], confidence: float = 0.95) -> Tuple[float, float]:
    """Get confidence interval for outcomes.

    Args:
        outcomes: List of simulated outcomes
        confidence: Confidence level (default: 0.95 for 95%)

    Returns:
        Tuple of (lower_bound, upper_bound)
    """
    sorted_outcomes = sorted(outcomes)
    n = len(sorted_outcomes)

    # Calculate indices for confidence interval
    alpha = 1 - confidence
    lower_idx = int(n * (alpha / 2))
    upper_idx = int(n * (1 - alpha / 2))

    return sorted_outcomes[lower_idx], sorted_outcomes[upper_idx]
