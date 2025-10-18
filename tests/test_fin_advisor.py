"""
Unit tests for the Financial Advisor application.
"""

import unittest
import sys
import os

# Add the parent directory to the path so we can import fin_advisor
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fin_advisor import (
    UserInputs,
    years_to_retirement,
    future_value_with_contrib,
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


if __name__ == '__main__':
    unittest.main()
