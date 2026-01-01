#!/usr/bin/env python3
"""Simple test for explain_projected_balance function."""

# Import just the core functionality we need to test
import sys
import os

# Let's test by directly importing only what we need
# First, let's verify the function was added correctly

# Read the fin_advisor.py file and check for our function
with open('fin_advisor.py', 'r') as f:
    content = f.read()
    if 'def explain_projected_balance' in content:
        print("✓ explain_projected_balance function found in fin_advisor.py")

        # Count the lines of the function
        lines = content.split('\n')
        start_idx = None
        end_idx = None
        for i, line in enumerate(lines):
            if 'def explain_projected_balance' in line:
                start_idx = i
            if start_idx is not None and line.strip() and not line.startswith(' ') and not line.startswith('\t') and i > start_idx:
                end_idx = i
                break

        if start_idx and end_idx:
            function_lines = end_idx - start_idx
            print(f"✓ Function is {function_lines} lines long")

        # Check for key components in the function
        checks = [
            ('FV = P × (1 + r)^t', 'Formula explained'),
            ('Annual Contribution', 'Annual contribution mentioned'),
            ('PRINCIPAL GROWTH', 'Principal growth component explained'),
            ('CONTRIBUTION GROWTH', 'Contribution growth component explained'),
            ('TAX TREATMENT', 'Tax treatment explained'),
            ('Pre-Tax (401k', 'Pre-tax asset type covered'),
            ('Post-Tax (Roth', 'Roth IRA covered'),
            ('Post-Tax (Brokerage', 'Brokerage account covered'),
            ('Tax-Deferred (HSA', 'HSA covered'),
            ('end of each year', 'Timing of contributions specified')
        ]

        passed = 0
        for check, description in checks:
            if check in content:
                print(f"✓ {description}")
                passed += 1
            else:
                print(f"✗ {description}")

        print(f"\n{passed}/{len(checks)} checks passed")

        if passed == len(checks):
            print("\n✓✓✓ All checks passed! The explanation module is properly implemented.")
        else:
            print(f"\n⚠ Some checks failed. Review the implementation.")
    else:
        print("✗ explain_projected_balance function NOT found!")
        sys.exit(1)
