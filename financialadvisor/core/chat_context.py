"""
Build a compact calculation context string for the post-results chat advisor.
Pure Python — no Streamlit imports. Injected as a system message per turn.
"""
from __future__ import annotations


def build_detailed_chat_context(
    result: dict,
    inputs: object,
    annual_retirement_income: float,
    sim_data: list[dict],
    whatif_values: dict,
    assets: list,
    birth_year: int | None = None,
    breakeven_retirement_age: int | None = None,
    income_at_breakeven: float = 0.0,
    breakeven_contribution: int | None = None,
    contrib_breakdown: dict | None = None,
    contrib_irs_maxed: bool = False,
    mc_summary: dict | None = None,
) -> str:
    """Format portfolio results into a compact context string (~1,100 tokens).

    Args:
        result:                   Output of project(inputs) — keys include
                                  'Total Future Value (Pre-Tax)',
                                  'Total After-Tax Balance', 'Tax Efficiency (%)',
                                  'Years Until Retirement', 'asset_results'.
        inputs:                   UserInputs instance (has .age, .retirement_age, etc.)
        annual_retirement_income: First-year after-tax income from find_sustainable_withdrawal.
        sim_data:                 Year-by-year simulation rows from find_sustainable_withdrawal.
        whatif_values:            Dict of current what-if parameter values.
        assets:                   List of Asset objects (current state, not at retirement).
        birth_year:               Optional; used to display the actual birth year.
    """
    age = getattr(inputs, "age", 0)
    retirement_age = int(whatif_values.get("retirement_age") or getattr(inputs, "retirement_age", 65))
    life_expectancy = int(whatif_values.get("life_expectancy") or getattr(inputs, "life_expectancy", 90))
    years_in_retirement = max(0, life_expectancy - retirement_age)
    retirement_income_goal = float(whatif_values.get("retirement_income_goal") or 0)
    inflation_rate = float(whatif_values.get("inflation_rate") or getattr(inputs, "inflation_rate_pct", 3.0))
    growth_rate = float(whatif_values.get("retirement_growth_rate") or 4.0)
    tax_rate = float(whatif_values.get("retirement_tax_rate") or getattr(inputs, "retirement_marginal_tax_rate_pct", 22.0))
    life_expenses = float(whatif_values.get("life_expenses") or 0)
    legacy_goal = float(whatif_values.get("legacy_goal") or 0)

    pretax_fv = float(result.get("Total Future Value (Pre-Tax)", 0))
    after_tax_raw = float(result.get("Total After-Tax Balance", 0))
    after_tax = max(0.0, after_tax_raw - life_expenses)
    tax_eff = float(result.get("Tax Efficiency (%)", 0))
    years_to_retire = float(result.get("Years Until Retirement", max(0, retirement_age - age)))

    income_shortfall = retirement_income_goal - annual_retirement_income

    lines: list[str] = ["[PORTFOLIO CONTEXT]"]

    # -- Section 1: Overview --
    by_str = f"{birth_year} | " if birth_year else ""
    lines.append(
        f"Birth year: {by_str}Current age: {age} | "
        f"Retirement age: {retirement_age} | Life expectancy: {life_expectancy}"
    )
    lines.append(
        f"Years to retirement: {int(years_to_retire)} | "
        f"Years in retirement: {years_in_retirement}"
    )
    lines.append(
        f"Growth rate (retirement): {growth_rate:.1f}% | "
        f"Inflation: {inflation_rate:.1f}%"
    )
    lines.append(
        f"Tax rates: ordinary income (pre-tax/RMD withdrawals) = {tax_rate:.0f}% flat (user-configurable) | "
        f"capital gains (brokerage gains only) = 15% | Roth = 0%"
    )
    lines.append("")
    lines.append(f"Total pre-tax portfolio value at retirement: ${pretax_fv:,.0f}")
    lines.append(f"Total after-tax portfolio value at retirement: ${after_tax:,.0f}")
    lines.append(f"Tax efficiency: {tax_eff:.1f}%")
    lines.append(f"Projected annual income Year 1 (after-tax): ${annual_retirement_income:,.0f}/year")

    if retirement_income_goal > 0:
        if income_shortfall > 0:
            gap_pct = (income_shortfall / retirement_income_goal) * 100
            lines.append(
                f"Income goal: ${retirement_income_goal:,.0f}/year | "
                f"Shortfall: ${income_shortfall:,.0f}/year ({gap_pct:.1f}% gap)"
            )
            # Pre-computed breakeven retirement age (Python-exact, not estimated)
            if breakeven_retirement_age is not None:
                lines.append(
                    f"EXACT breakeven retirement age: {breakeven_retirement_age} "
                    f"(first age where income >= goal; projected income at that age: "
                    f"${income_at_breakeven:,.0f}/year) — use this exact number, do NOT estimate"
                )
            else:
                lines.append(
                    "Breakeven retirement age: not achievable by age 80 under current assumptions"
                )

            # Pre-computed additional contribution needed (Python-exact, not estimated)
            bd = contrib_breakdown or {}
            if breakeven_contribution is not None:
                pretax_add  = bd.get("pretax", 0)
                brok_add    = bd.get("brokerage", 0)
                irs_limit   = bd.get("irs_401k_limit", 0)
                cur_pretax  = bd.get("pretax_current", 0)
                capacity    = bd.get("pretax_capacity", 0)
                detail = f"  → ${pretax_add:,}/yr to pre-tax/401k"
                if capacity > 0:
                    detail += f" (IRS limit: ${irs_limit:,}; currently contributing ${cur_pretax:,}; capacity: ${capacity:,})"
                else:
                    detail += f" (IRS 401k limit of ${irs_limit:,} is already reached)"
                if brok_add > 0:
                    detail += f"  + ${brok_add:,}/yr to taxable brokerage (pre-tax capacity exhausted)"
                lines.append(
                    f"EXACT additional annual contribution needed to close gap: ${breakeven_contribution:,}/year"
                    + (" — use this exact number, do NOT estimate" if not contrib_irs_maxed else
                       " — but pre-tax capacity is maxed; remainder goes to taxable brokerage")
                )
                lines.append(detail)
            else:
                lines.append(
                    "Additional contribution to close gap: not achievable by contributing "
                    f"up to ${bd.get('irs_401k_limit', 23000):,}/yr pre-tax + unlimited brokerage "
                    "(gap too large for contributions alone — consider delaying retirement)"
                )
        else:
            lines.append(
                f"Income goal: ${retirement_income_goal:,.0f}/year | "
                f"Surplus: ${-income_shortfall:,.0f}/year"
            )

    if life_expenses > 0:
        lines.append(f"One-time expenses deducted at retirement: ${life_expenses:,.0f}")
    if legacy_goal > 0:
        lines.append(f"Legacy/estate goal (preserved at death): ${legacy_goal:,.0f}")

    # -- Monte Carlo summary (pre-computed, 500 simulations, volatility=15%) --
    if mc_summary:
        lines.append("")
        lines.append(
            f"MONTE CARLO ANALYSIS ({mc_summary.get('num_sims', 500)} simulations, "
            f"volatility={mc_summary.get('volatility', 15.0):.0f}% std dev):"
        )
        lines.append(
            f"  Annual income — bad scenario (10th pct): ${mc_summary['income_p10']:,.0f}/yr | "
            f"median (50th): ${mc_summary['income_p50']:,.0f}/yr | "
            f"good scenario (90th): ${mc_summary['income_p90']:,.0f}/yr"
        )
        lines.append(
            f"  Portfolio balance — 10th: ${mc_summary['bal_p10']:,.0f} | "
            f"median: ${mc_summary['bal_p50']:,.0f} | "
            f"90th: ${mc_summary['bal_p90']:,.0f}"
        )
        if mc_summary.get("prob_success") is not None:
            lines.append(
                f"  Probability of meeting income goal: {mc_summary['prob_success']:.1f}%"
            )
        lines.append(
            "  Note: income estimates use a simplified model (portfolio / years in retirement). "
            "The full Monte Carlo page runs the complete withdrawal simulation per scenario."
        )

    # -- Section 2: Account breakdown --
    lines.append("")
    lines.append("ACCOUNTS (today's balances → projected value at retirement):")
    asset_results = result.get("asset_results", [])
    assets_input = result.get("assets_input", assets)
    for idx, asset in enumerate(assets_input[:15]):
        ar = asset_results[idx] if idx < len(asset_results) else {}
        fv = float(ar.get("pre_tax_value", 0))
        name = getattr(asset, "name", f"Account {idx + 1}")
        balance = float(getattr(asset, "current_balance", 0))
        contrib = float(getattr(asset, "annual_contribution", 0))
        growth = float(getattr(asset, "growth_rate_pct", 7.0))
        tax_label = _tax_label(getattr(asset, "asset_type", None), name)
        lines.append(
            f"  {idx + 1}. {name} [{tax_label}] — "
            f"Balance: ${balance:,.0f} | Contrib: ${contrib:,.0f}/yr | "
            f"Growth: {growth:.1f}% | At retirement: ${fv:,.0f}"
        )
    if len(assets_input) > 15:
        lines.append(f"  ... and {len(assets_input) - 15} more accounts")

    # -- Section 3: Year-by-year snapshot (key years only) --
    if sim_data:
        lines.append("")
        lines.append("YEAR-BY-YEAR SNAPSHOT (selected years):")
        indices: set[int] = {0}  # always year 1
        # RMD start year (age 73)
        for i, row in enumerate(sim_data):
            if row.get("age", 0) >= 73 and row.get("rmd", 0) > 0:
                indices.add(i)
                break
        for target in [4, 9]:  # years 5 and 10
            if target < len(sim_data):
                indices.add(target)
        indices.add(len(sim_data) - 1)  # final year

        for idx in sorted(indices):
            if idx >= len(sim_data):
                continue
            row = sim_data[idx]
            rmd_str = f" | RMD: ${row.get('rmd', 0):,.0f}" if row.get("rmd", 0) > 0 else ""
            portfolio = row.get("total_portfolio_end", 0)
            lines.append(
                f"  Year {row['year']} (age {row['age']}): "
                f"Income: ${row['actual_aftertax']:,.0f}{rmd_str} | "
                f"Portfolio: ${portfolio:,.0f}"
            )

    return "\n".join(lines)


def _tax_label(asset_type: object, name: str) -> str:
    """Short human-readable tax label for an asset."""
    if asset_type is None:
        return "unknown"
    s = str(asset_type).lower()
    if "pre_tax" in s or "tax_deferred" in s:
        return "pre-tax/401k"
    if "hsa" in s:
        return "HSA"
    if "post_tax" in s:
        return "Roth" if "roth" in name.lower() else "brokerage/post-tax"
    return s
