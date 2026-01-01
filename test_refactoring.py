#!/usr/bin/env python3
"""Test refactored architecture to ensure backward compatibility."""

from financialadvisor import (
    AssetType,
    Asset,
    TaxBracket,
    UserInputs,
    years_to_retirement,
    future_value_with_contrib,
    get_irs_tax_brackets_2024,
    project_tax_rate,
    calculate_asset_growth,
    apply_tax_logic,
    project,
    explain_projected_balance,
)


def test_basic_functions():
    """Test basic calculation functions."""
    print("Testing basic functions...")

    # Test years_to_retirement
    assert years_to_retirement(30, 65) == 35
    print("  ✓ years_to_retirement")

    # Test future_value_with_contrib
    fv = future_value_with_contrib(50000, 12750, 7.0, 35)
    assert 2200000 < fv < 2400000  # Should be around $2.3M
    print("  ✓ future_value_with_contrib")

    # Test zero growth rate edge case
    fv_zero = future_value_with_contrib(50000, 10000, 0.0, 10)
    assert fv_zero == 150000  # 50000 + 10*10000
    print("  ✓ future_value_with_contrib (zero rate)")


def test_tax_functions():
    """Test tax-related functions."""
    print("\nTesting tax functions...")

    # Test get_irs_tax_brackets_2024
    brackets = get_irs_tax_brackets_2024()
    assert len(brackets) == 7
    assert brackets[0].rate_pct == 10.0
    print("  ✓ get_irs_tax_brackets_2024")

    # Test project_tax_rate
    rate = project_tax_rate(50000, brackets)
    assert rate == 22.0  # Falls in 22% bracket
    print("  ✓ project_tax_rate")

    # Test calculate_asset_growth
    asset = Asset(
        name="Test 401k",
        asset_type=AssetType.PRE_TAX,
        current_balance=50000,
        annual_contribution=10000,
        growth_rate_pct=7.0
    )
    fv, total_contrib = calculate_asset_growth(asset, 10)
    assert fv > 50000  # Should grow
    assert total_contrib == 100000  # 10 * 10000
    print("  ✓ calculate_asset_growth")

    # Test apply_tax_logic for pre-tax
    after_tax, tax_liability = apply_tax_logic(asset, 200000, 100000, 25.0)
    assert after_tax == 150000  # 200000 * 0.75
    assert tax_liability == 50000  # 200000 * 0.25
    print("  ✓ apply_tax_logic (pre-tax)")

    # Test apply_tax_logic for Roth (post-tax, tax-free)
    roth = Asset(
        name="Roth IRA",
        asset_type=AssetType.POST_TAX,
        current_balance=30000,
        annual_contribution=6000,
        growth_rate_pct=7.0
    )
    after_tax_roth, tax_roth = apply_tax_logic(roth, 100000, 60000, 25.0)
    assert after_tax_roth == 100000  # No tax
    assert tax_roth == 0.0
    print("  ✓ apply_tax_logic (Roth)")


def test_domain_models():
    """Test domain models."""
    print("\nTesting domain models...")

    # Test AssetType enum
    assert AssetType.PRE_TAX.value == "pre_tax"
    assert AssetType.POST_TAX.value == "post_tax"
    assert AssetType.TAX_DEFERRED.value == "tax_deferred"
    print("  ✓ AssetType enum")

    # Test Asset with default tax_rate_pct
    asset = Asset(
        name="Brokerage",
        asset_type=AssetType.POST_TAX,
        current_balance=10000,
        annual_contribution=5000,
        growth_rate_pct=6.0
    )
    assert asset.tax_rate_pct == 15.0  # Default capital gains rate
    print("  ✓ Asset default tax_rate_pct")

    # Test TaxBracket
    bracket = TaxBracket(0, 11000, 10.0)
    assert bracket.min_income == 0
    assert bracket.max_income == 11000
    assert bracket.rate_pct == 10.0
    print("  ✓ TaxBracket")

    # Test UserInputs backward compatibility
    inputs = UserInputs(
        age=30,
        retirement_age=65,
        annual_income=85000,
        contribution_rate_pct=15.0,
        current_balance=50000,
        expected_growth_rate_pct=7.0,
        tax_rate_pct=25.0  # Legacy parameter
    )
    assert inputs.current_marginal_tax_rate_pct == 25.0
    assert inputs.retirement_marginal_tax_rate_pct == 25.0
    assert inputs.tax_rate_pct == 25.0  # Legacy alias
    print("  ✓ UserInputs backward compatibility")


def test_project_function():
    """Test main projection function."""
    print("\nTesting project function...")

    # Test simple projection
    inputs = UserInputs(
        age=30,
        retirement_age=65,
        annual_income=85000,
        contribution_rate_pct=15.0,
        current_balance=50000,
        expected_growth_rate_pct=7.0,
        retirement_marginal_tax_rate_pct=25.0
    )

    result = project(inputs)

    # Check required keys
    assert "Years Until Retirement" in result
    assert "Total Future Value (Pre-Tax)" in result
    assert "Total After-Tax Balance" in result
    assert "Total Tax Liability" in result
    assert "Tax Efficiency (%)" in result

    # Check backward-compatible aliases
    assert "Future Value (Pre-Tax)" in result
    assert "Estimated Post-Tax Balance" in result

    # Verify calculations
    assert result["Years Until Retirement"] == 35
    assert result["Total Future Value (Pre-Tax)"] > 0
    assert result["Total After-Tax Balance"] > 0
    assert result["Total After-Tax Balance"] < result["Total Future Value (Pre-Tax)"]

    print("  ✓ project (simple)")

    # Test multi-asset projection
    multi_inputs = UserInputs(
        age=35,
        retirement_age=65,
        annual_income=120000,
        contribution_rate_pct=0,
        current_balance=0,
        expected_growth_rate_pct=7.0,
        retirement_marginal_tax_rate_pct=28.0,
        assets=[
            Asset(
                name="401(k) Pre-Tax",
                asset_type=AssetType.PRE_TAX,
                current_balance=80000,
                annual_contribution=19500,
                growth_rate_pct=7.0
            ),
            Asset(
                name="Roth IRA",
                asset_type=AssetType.POST_TAX,
                current_balance=30000,
                annual_contribution=6500,
                growth_rate_pct=7.5
            )
        ]
    )

    multi_result = project(multi_inputs)
    assert multi_result["Number of Assets"] == 2
    assert "asset_results" in multi_result
    assert len(multi_result["asset_results"]) == 2

    print("  ✓ project (multi-asset)")


def test_explainer():
    """Test explanation generation."""
    print("\nTesting explainer...")

    inputs = UserInputs(
        age=30,
        retirement_age=65,
        annual_income=85000,
        contribution_rate_pct=15.0,
        current_balance=50000,
        expected_growth_rate_pct=7.0,
        retirement_marginal_tax_rate_pct=25.0
    )

    explanation = explain_projected_balance(inputs)

    # Check that explanation contains key sections
    assert "CORE FORMULA" in explanation
    assert "FV = P × (1 + r)^t + C × [((1 + r)^t - 1) / r]" in explanation
    assert "PRINCIPAL GROWTH" in explanation
    assert "CONTRIBUTION GROWTH" in explanation
    assert "TAX TREATMENT" in explanation
    assert "KEY INSIGHTS" in explanation

    # Should be a substantial explanation
    lines = explanation.split('\n')
    assert len(lines) > 80

    print("  ✓ explain_projected_balance")


def main():
    """Run all tests."""
    print("=" * 80)
    print("REFACTORING TEST SUITE")
    print("=" * 80)

    try:
        test_basic_functions()
        test_tax_functions()
        test_domain_models()
        test_project_function()
        test_explainer()

        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)
        print("\nRefactoring successful:")
        print("  • Domain models extracted to financialadvisor/domain/")
        print("  • Core logic extracted to financialadvisor/core/")
        print("  • Clean __init__.py with public API")
        print("  • Backward compatibility maintained")
        print("  • All functions working correctly")

        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
