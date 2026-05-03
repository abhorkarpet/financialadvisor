"""
Unit tests for the Financial Advisor application.
"""

import unittest
import sys
import os

# Add the parent directory to the path so we can import fin_advisor
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fin_advisor import (
    Asset,
    AssetType,
    TaxBehavior,
    UserInputs,
    _asset_from_editor_row,
    _dedupe_ai_editor_rows,
    _dedupe_uploaded_file_payloads,
    _fmt_inr,
    _format_money_input,
    _humanize_ai_account_name,
    _humanize_ai_account_type,
    _parse_money_input,
    _rmd_distribution_period,
    _resolve_tax_settings,
    apply_tax_logic,
    clear_detailed_planning_asset_state,
    collect_detailed_planning_handoff_fields,
    extract_release_overview,
    find_required_portfolio,
    has_existing_detailed_asset_state,
    simulate_retirement,
    years_to_retirement,
    future_value_with_contrib,
    parse_uploaded_csv,
    simple_post_tax,
    project
)


class TestFinancialAdvisor(unittest.TestCase):
    """Test cases for the Financial Advisor application."""

    def test_years_to_retirement_basic(self):
        """Test basic years to retirement calculation."""
        self.assertEqual(years_to_retirement(30, 65), 35)
        self.assertEqual(years_to_retirement(25, 60), 35)
        self.assertEqual(years_to_retirement(40, 40), 0)

    def test_years_to_retirement_invalid(self):
        """Test invalid retirement age scenarios."""
        with self.assertRaises(ValueError):
            years_to_retirement(65, 60)
        with self.assertRaises(ValueError):
            years_to_retirement(50, 30)

    def test_future_value_zero_rate(self):
        """Test future value calculation with zero growth rate."""
        fv = future_value_with_contrib(10000, 1000, 0.0, 5)
        # 10k principal + 5*1k contributions = 15k
        self.assertAlmostEqual(fv, 15000.0, places=6)

    def test_future_value_positive_rate(self):
        """Test future value calculation with positive growth rate."""
        # P=0, C=1000, r=10%, t=2 => 1000*((1.1^2 - 1)/0.1) = 1000*(0.21/0.1)=2100
        fv = future_value_with_contrib(0.0, 1000.0, 10.0, 2)
        self.assertAlmostEqual(fv, 2100.0, places=6)

    def test_future_value_with_principal(self):
        """Test future value calculation with both principal and contributions."""
        # P=5000, C=1000, r=5%, t=3
        # Principal grows: 5000 * 1.05^3 = 5788.125
        # Contributions: 1000 * ((1.05^3 - 1)/0.05) = 1000 * (0.157625/0.05) = 3152.5
        # Total: 5788.125 + 3152.5 = 8940.625
        fv = future_value_with_contrib(5000.0, 1000.0, 5.0, 3)
        self.assertAlmostEqual(fv, 8940.625, places=2)

    def test_post_tax_bounds(self):
        """Test post-tax calculation boundary conditions."""
        self.assertAlmostEqual(simple_post_tax(1000, 0), 1000.0)
        self.assertAlmostEqual(simple_post_tax(1000, 100), 0.0)
        self.assertAlmostEqual(simple_post_tax(1000, 25), 750.0)

    def test_post_tax_edge_cases(self):
        """Test post-tax calculation edge cases."""
        # Test negative tax rate (should be clamped to 0)
        self.assertAlmostEqual(simple_post_tax(1000, -10), 1000.0)
        # Test tax rate > 100% (should be clamped to 100%)
        self.assertAlmostEqual(simple_post_tax(1000, 150), 0.0)

    def test_project_rounding(self):
        """Test project function with known values."""
        inputs = UserInputs(
            age=30,
            retirement_age=31,
            annual_income=100000,
            contribution_rate_pct=10,
            current_balance=0,
            expected_growth_rate_pct=10,
            inflation_rate_pct=0,
            tax_rate_pct=25,
            asset_types=[],
        )
        result = project(inputs)
        
        self.assertIn("Years Until Retirement", result)
        self.assertIn("Future Value (Pre-Tax)", result)
        self.assertIn("Estimated Post-Tax Balance", result)
        
        # FV should be ~ 10000 contribution grown 1 year at 10% = 11000
        self.assertAlmostEqual(result["Future Value (Pre-Tax)"], 11000.0, places=2)
        # After tax @25% = 8250
        self.assertAlmostEqual(result["Estimated Post-Tax Balance"], 8250.0, places=2)

    def test_project_comprehensive(self):
        """Test project function with comprehensive scenario."""
        inputs = UserInputs(
            age=25,
            retirement_age=65,
            annual_income=75000,
            contribution_rate_pct=15,
            current_balance=10000,
            expected_growth_rate_pct=7,
            inflation_rate_pct=3,
            tax_rate_pct=22,
            asset_types=["401(k) / Traditional IRA (Pre-Tax)"],
        )
        result = project(inputs)
        
        # Verify all expected keys are present
        expected_keys = [
            "Years Until Retirement",
            "Future Value (Pre-Tax)",
            "Estimated Post-Tax Balance"
        ]
        for key in expected_keys:
            self.assertIn(key, result)
            self.assertIsInstance(result[key], float)
            self.assertGreater(result[key], 0)

        # Verify years calculation
        self.assertEqual(result["Years Until Retirement"], 40.0)
        
        # Verify post-tax is less than pre-tax
        self.assertLess(result["Estimated Post-Tax Balance"], result["Future Value (Pre-Tax)"])

    def test_user_inputs_validation(self):
        """Test UserInputs dataclass creation."""
        inputs = UserInputs(
            age=30,
            retirement_age=65,
            annual_income=85000.0,
            contribution_rate_pct=15.0,
            current_balance=50000.0,
            expected_growth_rate_pct=7.0,
            inflation_rate_pct=3.0,
            tax_rate_pct=25.0,
            asset_types=["401(k) / Traditional IRA (Pre-Tax)"]
        )
        
        self.assertEqual(inputs.age, 30)
        self.assertEqual(inputs.retirement_age, 65)
        self.assertEqual(inputs.annual_income, 85000.0)
        self.assertEqual(inputs.contribution_rate_pct, 15.0)
        self.assertEqual(inputs.current_balance, 50000.0)
        self.assertEqual(inputs.expected_growth_rate_pct, 7.0)
        self.assertEqual(inputs.inflation_rate_pct, 3.0)
        self.assertEqual(inputs.tax_rate_pct, 25.0)
        self.assertEqual(len(inputs.asset_types), 1)

    def test_asset_from_editor_row_tax_free(self):
        """Tax-Free rows should produce explicit Roth-style tax behavior."""
        asset = _asset_from_editor_row({
            "Account Name": "Roth IRA",
            "Tax Treatment": "Tax-Free",
            "Current Balance": 10000,
            "Annual Contribution": 6000,
            "Growth Rate (%)": 7.0,
            "Tax Rate on Gains (%)": 0.0,
        })
        self.assertEqual(asset.asset_type, AssetType.POST_TAX)
        self.assertEqual(asset.tax_behavior, TaxBehavior.TAX_FREE)
        self.assertEqual(asset.tax_rate_pct, 0.0)

    def test_asset_from_editor_row_brokerage(self):
        """Post-tax brokerage rows should keep capital-gains behavior."""
        asset = _asset_from_editor_row({
            "Account Name": "Brokerage Account",
            "Tax Treatment": "Post-Tax",
            "Current Balance": 10000,
            "Annual Contribution": 1000,
            "Growth Rate (%)": 7.0,
            "Tax Rate on Gains (%)": 15.0,
        })
        self.assertEqual(asset.asset_type, AssetType.POST_TAX)
        self.assertEqual(asset.tax_behavior, TaxBehavior.CAPITAL_GAINS)
        self.assertEqual(asset.tax_rate_pct, 15.0)

    def test_asset_from_editor_row_savings(self):
        """Post-tax savings rows should use interest-income behavior (gains taxed at ordinary income rate)."""
        asset = _asset_from_editor_row({
            "Account Name": "High-Yield Savings Account",
            "Tax Treatment": "Post-Tax",
            "Current Balance": 10000,
            "Annual Contribution": 1000,
            "Growth Rate (%)": 4.0,
            "Tax Rate on Gains (%)": 0.0,
        })
        self.assertEqual(asset.asset_type, AssetType.POST_TAX)
        self.assertEqual(asset.tax_behavior, TaxBehavior.INTEREST_INCOME)
        self.assertEqual(asset.tax_rate_pct, 0.0)

    def test_parse_money_input_accepts_human_formats(self):
        """Natural money parsing should handle k/m/$/comma formats."""
        self.assertEqual(_parse_money_input("$200k", "Income Goal"), 200000.0)
        self.assertEqual(_parse_money_input("2.5m", "Income Goal"), 2500000.0)
        self.assertEqual(_parse_money_input("150,000", "Income Goal"), 150000.0)
        self.assertEqual(_parse_money_input("5000", "Income Goal"), 5000.0)

    def test_parse_money_input_rejects_bad_formats(self):
        """Malformed money input should raise a clear validation error."""
        with self.assertRaises(ValueError):
            _parse_money_input("abc", "Income Goal")
        with self.assertRaises(ValueError):
            _parse_money_input("-10k", "Income Goal")

    def test_format_money_input(self):
        """Formatted money text should be friendly for text inputs."""
        self.assertEqual(_format_money_input(0), "0")
        self.assertEqual(_format_money_input(200000), "200,000")
        self.assertEqual(_format_money_input(2500.5), "2,500.5")

    def test_dedupe_uploaded_file_payloads(self):
        """Byte-identical uploads should be skipped before sending to AI extraction."""
        files, skipped = _dedupe_uploaded_file_payloads(
            [
                ("stmt1.pdf", b"abc"),
                ("stmt2.pdf", b"abc"),
                ("stmt3.pdf", b"xyz"),
            ]
        )
        self.assertEqual([name for name, _ in files], ["stmt1.pdf", "stmt3.pdf"])
        self.assertEqual(len(skipped), 1)
        self.assertIn("stmt2.pdf", skipped[0])

    def test_dedupe_ai_editor_rows(self):
        """Likely duplicate extracted account rows should be removed with a warning."""
        import pandas as pd

        df = pd.DataFrame(
            [
                {"#": "#1", "Institution": "Fidelity", "Account Name": "IRA", "Last 4": "1234", "Current Balance": 1000.0},
                {"#": "#2", "Institution": "Fidelity", "Account Name": "IRA", "Last 4": "1234", "Current Balance": 1000.0},
                {"#": "#3", "Institution": "Vanguard", "Account Name": "Brokerage", "Last 4": "5678", "Current Balance": 2000.0},
            ]
        )
        deduped, warnings = _dedupe_ai_editor_rows(df)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(list(deduped["#"]), ["#1", "#2"])
        self.assertEqual(len(warnings), 1)
        self.assertIn("Potential duplicate removed", warnings[0])

    def test_humanize_ai_labels(self):
        """Extracted account labels should preserve IRA and 401(K) capitalization."""
        self.assertEqual(_humanize_ai_account_type("ira"), "IRA")
        self.assertEqual(_humanize_ai_account_type("401k"), "401(K)")
        self.assertEqual(_humanize_ai_account_name("IRA"), "IRA")
        self.assertEqual(_humanize_ai_account_name("401K"), "401(K)")

    def test_parse_uploaded_csv_preserves_tax_behaviors(self):
        """CSV parsing should resolve Roth, brokerage, and savings deterministically."""
        csv_content = (
            "Account Name,Tax Treatment,Current Balance,Annual Contribution,Growth Rate (%)\n"
            "Roth IRA,Tax-Free,10000,6000,7\n"
            "Brokerage Account,Post-Tax,15000,3000,7\n"
            "High-Yield Savings Account,Post-Tax,25000,2000,4.5\n"
        )
        assets, warnings = parse_uploaded_csv(csv_content)
        self.assertEqual(warnings, [])
        self.assertEqual(assets[0].tax_behavior, TaxBehavior.TAX_FREE)
        self.assertEqual(assets[1].tax_behavior, TaxBehavior.CAPITAL_GAINS)
        self.assertEqual(assets[1].tax_rate_pct, 15.0)
        self.assertEqual(assets[2].tax_behavior, TaxBehavior.INTEREST_INCOME)
        self.assertEqual(assets[2].tax_rate_pct, 0.0)

    def test_tax_logic_hsa_split(self):
        """HSA-like behavior should tax only the simplified non-medical half."""
        asset = Asset(
            name="HSA Account",
            asset_type=AssetType.TAX_DEFERRED,
            current_balance=0,
            annual_contribution=0,
            growth_rate_pct=0,
            tax_behavior=TaxBehavior.HSA_SPLIT,
        )
        after_tax, tax_liability = apply_tax_logic(asset, 100000, 0, 20.0)
        self.assertEqual(tax_liability, 10000.0)
        self.assertEqual(after_tax, 90000.0)

    def test_tax_logic_no_additional_tax(self):
        """Cash-style post-tax assets should not be forced through capital-gains math."""
        asset = Asset(
            name="High-Yield Savings Account",
            asset_type=AssetType.POST_TAX,
            current_balance=0,
            annual_contribution=0,
            growth_rate_pct=0,
            tax_behavior=TaxBehavior.NO_ADDITIONAL_TAX,
        )
        after_tax, tax_liability = apply_tax_logic(asset, 100000, 50000, 25.0)
        self.assertEqual(tax_liability, 0.0)
        self.assertEqual(after_tax, 100000.0)

    def test_collect_detailed_planning_handoff_fields(self):
        """Simple Planning fields should map cleanly into Detailed Planning state."""
        seeded = collect_detailed_planning_handoff_fields({
            "country": "India",
            "birth_year": 1990,
            "retirement_age": 62,
            "life_expectancy": 90,
            "target_income": 80000,
            "legacy_goal": 250000,
            "life_expenses": 100000,
            "tax_rate": 24,
            "growth_rate": 5.5,
            "inflation_rate": 2.8,
        })
        self.assertEqual(seeded["birth_year"], 1990)
        self.assertEqual(seeded["retirement_age"], 62)
        self.assertEqual(seeded["life_expectancy"], 90)
        self.assertEqual(seeded["retirement_income_goal"], 80000)
        self.assertEqual(seeded["legacy_goal"], 250000)
        self.assertEqual(seeded["life_expenses"], 100000)
        self.assertEqual(seeded["whatif_retirement_tax_rate"], 24)
        self.assertEqual(seeded["whatif_retirement_growth_rate"], 5.5)
        self.assertEqual(seeded["whatif_inflation_rate"], 2.8)
        self.assertEqual(seeded["country"], "US")
        self.assertEqual(seeded["_prev_country"], "US")

    def test_has_existing_detailed_asset_state(self):
        """Detailed asset detection should recognize saved assets and upload tables."""
        self.assertFalse(has_existing_detailed_asset_state({}))
        self.assertTrue(has_existing_detailed_asset_state({"assets": [object()]}))
        self.assertTrue(has_existing_detailed_asset_state({"csv_uploaded_assets": [object()]}))

    def test_clear_detailed_planning_asset_state(self):
        """Start-fresh reset should clear saved asset inputs and bump upload widget versions."""
        state = {
            "assets": [object()],
            "setup_method_radio": "Upload CSV File",
            "num_assets_manual": 4,
            "ai_extracted_accounts": [object()],
            "ai_tax_buckets": {"401k": "tax_deferred"},
            "ai_warnings": ["warn"],
            "ai_edited_table": [object()],
            "ai_table_data": "data",
            "ai_table_initialized": True,
            "csv_uploaded_file_id": "file.csv_100",
            "csv_uploaded_assets": [object()],
            "csv_uploaded_edited_table": [object()],
            "ai_upload_widget_version": 1,
            "csv_upload_widget_version": 2,
        }
        clear_detailed_planning_asset_state(state)
        self.assertEqual(state["assets"], [])
        self.assertEqual(state["ai_upload_widget_version"], 2)
        self.assertEqual(state["csv_upload_widget_version"], 3)
        self.assertNotIn("setup_method_radio", state)
        self.assertNotIn("num_assets_manual", state)
        self.assertNotIn("ai_extracted_accounts", state)
        self.assertNotIn("csv_uploaded_assets", state)


class TestFmtInr(unittest.TestCase):
    """Indian number formatting — 3-digit last group, 2-digit groups above."""

    def test_under_1000_unchanged(self):
        self.assertEqual(_fmt_inr(999), "999")

    def test_exactly_1000(self):
        self.assertEqual(_fmt_inr(1000), "1,000")

    def test_lakhs(self):
        self.assertEqual(_fmt_inr(600_000), "6,00,000")

    def test_crores(self):
        self.assertEqual(_fmt_inr(10_000_000), "1,00,00,000")

    def test_large_number(self):
        self.assertEqual(_fmt_inr(8_589_300), "85,89,300")

    def test_negative_number(self):
        result = _fmt_inr(-600_000)
        self.assertTrue(result.startswith("-"))
        self.assertIn("6,00,000", result)

    def test_zero(self):
        self.assertEqual(_fmt_inr(0), "0")


class TestExtractReleaseOverview(unittest.TestCase):
    """Release notes overview extraction."""

    _NOTES = """\
# Release Notes v1.0.0

## 🎯 Release Overview
This is the overview text.

---

## Other Section
More content.
"""

    def test_returns_overview_section(self):
        result = extract_release_overview(self._NOTES)
        self.assertIn("Release Overview", result)
        self.assertIn("overview text", result)

    def test_stops_before_next_section(self):
        result = extract_release_overview(self._NOTES)
        self.assertNotIn("Other Section", result)

    def test_include_heading_false_strips_header(self):
        result = extract_release_overview(self._NOTES, include_heading=False)
        self.assertNotIn("## 🎯 Release Overview", result)
        self.assertIn("overview text", result)

    def test_none_content_returns_none(self):
        self.assertIsNone(extract_release_overview(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(extract_release_overview(""))

    def test_no_overview_marker_returns_full_content(self):
        notes = "# Release Notes\n\nNo overview marker here."
        result = extract_release_overview(notes)
        self.assertIn("No overview marker", result)


class TestRmdDistributionPeriod(unittest.TestCase):
    """IRS Uniform Lifetime Table lookups and extrapolation."""

    def test_below_73_returns_infinity(self):
        self.assertEqual(_rmd_distribution_period(72), float("inf"))
        self.assertEqual(_rmd_distribution_period(0), float("inf"))

    def test_at_73_returns_table_value(self):
        result = _rmd_distribution_period(73)
        self.assertGreater(result, 0)
        self.assertNotEqual(result, float("inf"))

    def test_exact_table_age(self):
        # Age 80 should be in the IRS table (distribution period ~20.2)
        result = _rmd_distribution_period(80)
        self.assertAlmostEqual(result, 20.2, delta=1.0)

    def test_beyond_100_extrapolates(self):
        result = _rmd_distribution_period(105)
        self.assertGreater(result, 0)
        self.assertLess(result, 10)

    def test_distribution_period_decreases_with_age(self):
        self.assertGreater(_rmd_distribution_period(73), _rmd_distribution_period(85))


class TestSimulateRetirement(unittest.TestCase):
    """Year-by-year retirement simulation boundary checks."""

    def test_zero_balance_portfolio_stays_zero(self):
        result = simulate_retirement(
            pretax_bal=0, roth_bal=0, brokerage_bal=0, brokerage_cost_basis=0,
            first_year_aftertax_target=50_000,
            retirement_age=65, life_expectancy=85,
            growth_rate=0.06, inflation_rate=0.03,
            retirement_tax_rate_pct=22.0,
        )
        self.assertEqual(len(result), 20)
        for row in result:
            self.assertEqual(row["total_portfolio_end"], 0.0)

    def test_returns_correct_number_of_years(self):
        result = simulate_retirement(
            pretax_bal=500_000, roth_bal=0, brokerage_bal=0, brokerage_cost_basis=0,
            first_year_aftertax_target=30_000,
            retirement_age=65, life_expectancy=80,
            growth_rate=0.04, inflation_rate=0.02,
            retirement_tax_rate_pct=15.0,
        )
        self.assertEqual(len(result), 15)  # 80 - 65

    def test_roth_withdrawal_tax_free(self):
        """Roth withdrawals should incur zero income tax."""
        result = simulate_retirement(
            pretax_bal=0, roth_bal=500_000, brokerage_bal=0, brokerage_cost_basis=0,
            first_year_aftertax_target=20_000,
            retirement_age=65, life_expectancy=70,
            growth_rate=0.04, inflation_rate=0.0,
            retirement_tax_rate_pct=22.0,
        )
        # First year: roth withdrawal should be tax-free
        year1 = result[0]
        self.assertEqual(year1.get("extra_pretax_tax", 0), 0.0)
        self.assertIn("roth_withdrawal", year1)

    def test_year_data_keys_present(self):
        result = simulate_retirement(
            pretax_bal=200_000, roth_bal=0, brokerage_bal=0, brokerage_cost_basis=0,
            first_year_aftertax_target=10_000,
            retirement_age=65, life_expectancy=70,
            growth_rate=0.05, inflation_rate=0.02,
            retirement_tax_rate_pct=20.0,
        )
        expected_keys = {"age", "total_portfolio_end"}
        for key in expected_keys:
            self.assertIn(key, result[0])


class TestFindRequiredPortfolio(unittest.TestCase):
    """Binary search for minimum pre-tax portfolio — boundary and consistency checks."""

    def test_zero_income_goal_returns_zero_portfolio(self):
        result = find_required_portfolio(
            target_after_tax_income=0,
            retirement_age=65,
            life_expectancy=85,
            retirement_tax_rate_pct=22.0,
        )
        self.assertEqual(result["required_pretax_portfolio"], 0.0)
        self.assertEqual(result["confirmed_income"], 0.0)

    def test_positive_income_goal_returns_positive_portfolio(self):
        result = find_required_portfolio(
            target_after_tax_income=50_000,
            retirement_age=65,
            life_expectancy=85,
            retirement_tax_rate_pct=22.0,
            growth_rate=0.04,
            inflation_rate=0.03,
        )
        self.assertGreater(result["required_pretax_portfolio"], 0)

    def test_longer_retirement_requires_more(self):
        shorter = find_required_portfolio(
            target_after_tax_income=40_000,
            retirement_age=65,
            life_expectancy=75,
            retirement_tax_rate_pct=22.0,
            growth_rate=0.04,
            inflation_rate=0.02,
        )
        longer = find_required_portfolio(
            target_after_tax_income=40_000,
            retirement_age=65,
            life_expectancy=90,
            retirement_tax_rate_pct=22.0,
            growth_rate=0.04,
            inflation_rate=0.02,
        )
        self.assertGreater(
            longer["required_pretax_portfolio"],
            shorter["required_pretax_portfolio"],
        )

    def test_result_includes_expected_keys(self):
        result = find_required_portfolio(
            target_after_tax_income=30_000,
            retirement_age=65,
            life_expectancy=85,
            retirement_tax_rate_pct=15.0,
        )
        for key in ("required_pretax_portfolio", "confirmed_income", "years_in_retirement"):
            self.assertIn(key, result)

    def test_life_expenses_added_to_requirement(self):
        base = find_required_portfolio(
            target_after_tax_income=40_000,
            retirement_age=65,
            life_expectancy=85,
            retirement_tax_rate_pct=22.0,
            growth_rate=0.04,
            inflation_rate=0.02,
        )
        with_expenses = find_required_portfolio(
            target_after_tax_income=40_000,
            retirement_age=65,
            life_expectancy=85,
            retirement_tax_rate_pct=22.0,
            growth_rate=0.04,
            inflation_rate=0.02,
            life_expenses=50_000,
        )
        self.assertGreater(
            with_expenses["required_pretax_portfolio"],
            base["required_pretax_portfolio"],
        )


class TestResolveTaxSettings(unittest.TestCase):
    """UI tax label → internal AssetType + TaxBehavior conversion."""

    def test_pre_tax_variants(self):
        for label in ("pre-tax", "pre tax", "pre_tax"):
            asset_type, behavior, rate = _resolve_tax_settings(label, "401k")
            self.assertEqual(behavior, TaxBehavior.PRE_TAX)
            self.assertEqual(rate, 0.0)

    def test_tax_deferred_plain(self):
        asset_type, behavior, rate = _resolve_tax_settings("tax-deferred", "My 401k")
        self.assertEqual(behavior, TaxBehavior.PRE_TAX)

    def test_tax_deferred_hsa(self):
        asset_type, behavior, rate = _resolve_tax_settings("tax-deferred", "HSA Account")
        self.assertEqual(behavior, TaxBehavior.HSA_SPLIT)

    def test_tax_deferred_annuity(self):
        asset_type, behavior, rate = _resolve_tax_settings("tax-deferred", "Variable Annuity")
        self.assertEqual(behavior, TaxBehavior.ORDINARY_INCOME)

    def test_tax_free_variants(self):
        for label in ("tax-free", "tax free", "roth"):
            asset_type, behavior, rate = _resolve_tax_settings(label, "Roth IRA")
            self.assertEqual(behavior, TaxBehavior.TAX_FREE)
            self.assertEqual(rate, 0.0)

    def test_post_tax_brokerage_uses_capital_gains(self):
        _, behavior, _ = _resolve_tax_settings("post-tax", "Brokerage Account")
        self.assertEqual(behavior, TaxBehavior.CAPITAL_GAINS)

    def test_post_tax_savings_uses_interest_income(self):
        _, behavior, _ = _resolve_tax_settings("post-tax", "High-Yield Savings Account")
        self.assertEqual(behavior, TaxBehavior.INTEREST_INCOME)

    def test_invalid_label_raises(self):
        with self.assertRaises(ValueError):
            _resolve_tax_settings("banana", "Some Account")


if __name__ == '__main__':
    unittest.main()
