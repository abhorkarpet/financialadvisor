"""Detailed explanation generation for retirement projections."""

from financialadvisor.domain.models import UserInputs
from financialadvisor.core.calculator import years_to_retirement
from financialadvisor.core.tax_engine import apply_tax_logic


def explain_projected_balance(inputs: UserInputs) -> str:
    """Generate a detailed explanation of how projected balance is calculated.

    Returns a formatted string explaining:
    - The core formula for future value with contributions
    - How annual contributions are incorporated
    - Step-by-step calculation breakdown
    - Tax treatment by asset type

    Args:
        inputs: UserInputs object with retirement planning parameters

    Returns:
        Multi-line formatted explanation string
    """
    yrs = years_to_retirement(inputs.age, inputs.retirement_age)

    explanation = []
    explanation.append("=" * 80)
    explanation.append("PROJECTED BALANCE CALCULATION EXPLAINED")
    explanation.append("=" * 80)
    explanation.append("")

    # Core Formula Section
    explanation.append("📊 CORE FORMULA: Future Value with Annual Contributions")
    explanation.append("-" * 80)
    explanation.append("")
    explanation.append("FV = P × (1 + r)^t + C × [((1 + r)^t - 1) / r]")
    explanation.append("")
    explanation.append("Where:")
    explanation.append("  P = Current Balance (Principal)")
    explanation.append("  r = Annual Growth Rate (as decimal)")
    explanation.append("  t = Years Until Retirement")
    explanation.append("  C = Annual Contribution (made at end of each year)")
    explanation.append("  FV = Future Value (Projected Balance)")
    explanation.append("")

    # Explanation of Each Term
    explanation.append("📈 HOW IT WORKS:")
    explanation.append("-" * 80)
    explanation.append("")
    explanation.append("The formula has TWO components:")
    explanation.append("")
    explanation.append("1. PRINCIPAL GROWTH: P × (1 + r)^t")
    explanation.append("   - Takes your current balance")
    explanation.append("   - Grows it with compound interest over t years")
    explanation.append("   - Example: $50,000 growing at 7% for 35 years")
    explanation.append("             = $50,000 × (1.07)^35")
    explanation.append("             = $50,000 × 10.677")
    explanation.append("             = $533,850")
    explanation.append("")
    explanation.append("2. CONTRIBUTION GROWTH: C × [((1 + r)^t - 1) / r]")
    explanation.append("   - Takes your annual contribution amount")
    explanation.append("   - Multiplies by the 'future value of annuity' factor")
    explanation.append("   - This accounts for each year's contribution growing")
    explanation.append("   - Example: $12,750/year at 7% for 35 years")
    explanation.append("             = $12,750 × [((1.07)^35 - 1) / 0.07]")
    explanation.append("             = $12,750 × 138.237")
    explanation.append("             = $1,762,523")
    explanation.append("")
    explanation.append("3. TOTAL PRE-TAX VALUE:")
    explanation.append("   = Principal Growth + Contribution Growth")
    explanation.append("   = $533,850 + $1,762,523")
    explanation.append("   = $2,296,373")
    explanation.append("")

    # Your Specific Calculation
    explanation.append("💼 YOUR CALCULATION:")
    explanation.append("-" * 80)
    explanation.append("")
    explanation.append(f"Age: {inputs.age} → Retirement Age: {inputs.retirement_age}")
    explanation.append(f"Years to Retirement: {yrs}")
    explanation.append("")

    # Calculate for each asset
    if not inputs.assets:
        # Use default asset logic
        total_contribution = inputs.annual_income * (inputs.contribution_rate_pct / 100.0)
        explanation.append(f"Current Balance (P): ${inputs.current_balance:,.2f}")
        explanation.append(f"Annual Contribution (C): ${total_contribution:,.2f}")
        explanation.append(f"Growth Rate (r): {inputs.expected_growth_rate_pct}% = {inputs.expected_growth_rate_pct/100.0:.4f}")
        explanation.append("")

        r = inputs.expected_growth_rate_pct / 100.0
        if r == 0:
            fv = inputs.current_balance + total_contribution * yrs
            explanation.append(f"Since growth rate is 0%, calculation simplifies to:")
            explanation.append(f"FV = {inputs.current_balance:,.2f} + {total_contribution:,.2f} × {yrs}")
            explanation.append(f"FV = ${fv:,.2f}")
        else:
            growth_factor = (1.0 + r) ** yrs
            principal_growth = inputs.current_balance * growth_factor
            annuity_factor = (growth_factor - 1.0) / r
            contribution_growth = total_contribution * annuity_factor
            fv = principal_growth + contribution_growth

            explanation.append(f"Step 1: Principal Growth")
            explanation.append(f"  P × (1 + r)^t = ${inputs.current_balance:,.2f} × (1 + {r:.4f})^{yrs}")
            explanation.append(f"                = ${inputs.current_balance:,.2f} × {growth_factor:.6f}")
            explanation.append(f"                = ${principal_growth:,.2f}")
            explanation.append("")
            explanation.append(f"Step 2: Contribution Growth")
            explanation.append(f"  C × [((1 + r)^t - 1) / r] = ${total_contribution:,.2f} × [({growth_factor:.6f} - 1) / {r:.4f}]")
            explanation.append(f"                            = ${total_contribution:,.2f} × {annuity_factor:.6f}")
            explanation.append(f"                            = ${contribution_growth:,.2f}")
            explanation.append("")
            explanation.append(f"Step 3: Total Pre-Tax Future Value")
            explanation.append(f"  FV = ${principal_growth:,.2f} + ${contribution_growth:,.2f}")
            explanation.append(f"     = ${fv:,.2f}")
            explanation.append("")

        # Tax calculation
        tax_liability = fv * (inputs.retirement_marginal_tax_rate_pct / 100.0)
        after_tax = fv - tax_liability
        explanation.append(f"Step 4: After-Tax Value")
        explanation.append(f"  Tax Rate: {inputs.retirement_marginal_tax_rate_pct}%")
        explanation.append(f"  Tax Liability = ${fv:,.2f} × {inputs.retirement_marginal_tax_rate_pct/100.0:.2f}")
        explanation.append(f"                = ${tax_liability:,.2f}")
        explanation.append(f"  After-Tax Value = ${fv:,.2f} - ${tax_liability:,.2f}")
        explanation.append(f"                  = ${after_tax:,.2f}")
    else:
        explanation.append("Assets Breakdown:")
        explanation.append("")

        for i, asset in enumerate(inputs.assets, 1):
            explanation.append(f"Asset {i}: {asset.name}")
            explanation.append(f"  Type: {asset.asset_type.value if hasattr(asset.asset_type, 'value') else asset.asset_type}")
            explanation.append(f"  Current Balance (P): ${asset.current_balance:,.2f}")
            explanation.append(f"  Annual Contribution (C): ${asset.annual_contribution:,.2f}")
            explanation.append(f"  Growth Rate (r): {asset.growth_rate_pct}%")
            explanation.append("")

            r = asset.growth_rate_pct / 100.0
            if r == 0:
                fv = asset.current_balance + asset.annual_contribution * yrs
                explanation.append(f"  FV = ${asset.current_balance:,.2f} + ${asset.annual_contribution:,.2f} × {yrs} = ${fv:,.2f}")
            else:
                growth_factor = (1.0 + r) ** yrs
                principal_growth = asset.current_balance * growth_factor
                annuity_factor = (growth_factor - 1.0) / r
                contribution_growth = asset.annual_contribution * annuity_factor
                fv = principal_growth + contribution_growth

                explanation.append(f"  Principal Growth: ${asset.current_balance:,.2f} × {growth_factor:.4f} = ${principal_growth:,.2f}")
                explanation.append(f"  Contribution Growth: ${asset.annual_contribution:,.2f} × {annuity_factor:.4f} = ${contribution_growth:,.2f}")
                explanation.append(f"  Pre-Tax FV: ${fv:,.2f}")

            # Tax calculation
            total_contributions = asset.annual_contribution * yrs
            after_tax_value, tax_liability = apply_tax_logic(
                asset, fv, total_contributions,
                inputs.retirement_marginal_tax_rate_pct
            )

            explanation.append(f"  Tax Liability: ${tax_liability:,.2f}")
            explanation.append(f"  After-Tax Value: ${after_tax_value:,.2f}")
            explanation.append("")

    # Tax Treatment Section
    explanation.append("")
    explanation.append("🏦 TAX TREATMENT BY ASSET TYPE:")
    explanation.append("-" * 80)
    explanation.append("")
    explanation.append("Pre-Tax (401k, Traditional IRA):")
    explanation.append("  • Full balance is taxed at retirement tax rate")
    explanation.append("  • Tax = FV × retirement_tax_rate")
    explanation.append("")
    explanation.append("Post-Tax (Roth IRA):")
    explanation.append("  • Tax-free on withdrawal")
    explanation.append("  • Tax = $0")
    explanation.append("")
    explanation.append("Post-Tax (Brokerage):")
    explanation.append("  • Only capital gains are taxed")
    explanation.append("  • Gains = FV - Total Contributions")
    explanation.append("  • Tax = Gains × capital_gains_rate")
    explanation.append("")
    explanation.append("Tax-Deferred (HSA):")
    explanation.append("  • 50% assumed for medical expenses (tax-free)")
    explanation.append("  • 50% for other withdrawals (taxed)")
    explanation.append("  • Tax = 50% × FV × retirement_tax_rate")
    explanation.append("")
    explanation.append("Tax-Deferred (Annuities):")
    explanation.append("  • Taxed as ordinary income")
    explanation.append("  • Tax = FV × retirement_tax_rate")
    explanation.append("")

    # Key Insights
    explanation.append("💡 KEY INSIGHTS:")
    explanation.append("-" * 80)
    explanation.append("")
    explanation.append("1. Annual contributions are assumed to be made at the END of each year")
    explanation.append("2. Each contribution grows with compound interest for the remaining years")
    explanation.append("3. The longer the time horizon, the more powerful the contribution growth")
    explanation.append("4. Asset type significantly affects after-tax value")
    explanation.append("5. Tax-advantaged accounts (Roth, HSA) provide substantial benefits")
    explanation.append("")
    explanation.append("=" * 80)

    return "\n".join(explanation)
