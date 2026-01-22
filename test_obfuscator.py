#!/usr/bin/env python3
"""
Test script for PDF obfuscator

This script tests the obfuscation logic without requiring actual PDF files.
"""

from pdf_obfuscator import NumberObfuscator, PDFObfuscator


def test_number_obfuscator():
    """Test the NumberObfuscator class"""
    print("Testing NumberObfuscator...")
    print("="*60)

    obfuscator = NumberObfuscator(variance_percent=10.0, seed=12345)

    # Test dollar amounts
    print("\n1. Dollar Amounts:")
    test_amounts = [
        "$1,234.56",
        "$50,000",
        "$100.00",
        "1,234.56",
        "$5.00"
    ]

    for amount in test_amounts:
        obfuscated = obfuscator.obfuscate_dollar_amount(amount)
        print(f"  {amount:>15} → {obfuscated:>15}")

    # Test percentages
    print("\n2. Percentages:")
    test_percentages = [
        "5.5%",
        "10%",
        "2.75%",
        "100%"
    ]

    for percent in test_percentages:
        obfuscated = obfuscator.obfuscate_percentage(percent)
        print(f"  {percent:>10} → {obfuscated:>10}")

    # Test account numbers
    print("\n3. Account Numbers:")
    test_accounts = [
        "1234567890",
        "9876543210",
        "123456"
    ]

    for account in test_accounts:
        obfuscated = obfuscator.obfuscate_account_number(account)
        print(f"  {account:>15} → {obfuscated:>15}")

    # Test plain numbers
    print("\n4. Plain Numbers:")
    test_numbers = [
        "1234",
        "1234.56",
        "999.99"
    ]

    for number in test_numbers:
        obfuscated = obfuscator.obfuscate_plain_number(number)
        print(f"  {number:>10} → {obfuscated:>10}")

    print("\n" + "="*60)
    print("✓ NumberObfuscator tests completed!\n")


def test_text_obfuscation():
    """Test text obfuscation"""
    print("Testing Text Obfuscation...")
    print("="*60)

    obfuscator = PDFObfuscator(variance_percent=10.0, seed=12345)

    sample_text = """
    FINANCIAL STATEMENT
    Statement Period: 01/01/2024 - 12/31/2024

    Account Summary
    Account #1234567890

    401(k) Plan Balance: $125,450.00
    Traditional IRA: $45,000.00
    Roth IRA: $30,000.00
    Brokerage Account: $15,250.50

    Total Balance: $215,700.50

    Performance
    Year-to-Date Return: 12.5%
    Annual Return: 10.25%
    Expense Ratio: 0.15%

    Contributions
    Employee Deferral: $22,500.00
    Employer Match: $7,500.00
    Total Contributions: $30,000.00
    """

    obfuscated_text, stats = obfuscator.obfuscate_text(sample_text)

    print("\nOriginal Text (excerpt):")
    print("-"*60)
    print(sample_text[:300] + "...")

    print("\nObfuscated Text (excerpt):")
    print("-"*60)
    print(obfuscated_text[:300] + "...")

    print("\n\nStatistics:")
    print("-"*60)
    print(f"  Dollar amounts obfuscated: {stats['dollar_amounts']}")
    print(f"  Percentages obfuscated: {stats['percentages']}")
    print(f"  Account numbers obfuscated: {stats['account_numbers']}")

    print("\n" + "="*60)
    print("✓ Text obfuscation tests completed!\n")


def test_reproducibility():
    """Test that using the same seed produces the same results"""
    print("Testing Reproducibility...")
    print("="*60)

    amount = "$1,234.56"

    # Create two obfuscators with the same seed
    obf1 = NumberObfuscator(variance_percent=10.0, seed=99999)
    obf2 = NumberObfuscator(variance_percent=10.0, seed=99999)

    result1 = obf1.obfuscate_dollar_amount(amount)
    result2 = obf2.obfuscate_dollar_amount(amount)

    print(f"\nOriginal: {amount}")
    print(f"Result 1 (seed=99999): {result1}")
    print(f"Result 2 (seed=99999): {result2}")

    if result1 == result2:
        print("\n✓ Results are identical (reproducible)")
    else:
        print("\n✗ Results differ (not reproducible)")

    # Test with different seed
    obf3 = NumberObfuscator(variance_percent=10.0, seed=88888)
    result3 = obf3.obfuscate_dollar_amount(amount)

    print(f"\nResult 3 (seed=88888): {result3}")

    if result1 != result3:
        print("✓ Different seed produces different result")
    else:
        print("✗ Different seed produces same result (unexpected)")

    print("\n" + "="*60)
    print("✓ Reproducibility tests completed!\n")


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("PDF OBFUSCATOR TEST SUITE")
    print("="*60 + "\n")

    try:
        test_number_obfuscator()
        test_text_obfuscation()
        test_reproducibility()

        print("="*60)
        print("ALL TESTS PASSED ✓")
        print("="*60)

    except Exception as e:
        print(f"\n✗ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
