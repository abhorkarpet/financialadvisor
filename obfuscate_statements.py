#!/usr/bin/env python3
"""
Financial Statement Obfuscator - Command Line Tool

Obfuscate financial information in PDF statements for creating product demos
without exposing personal data.

Usage:
    python obfuscate_statements.py statement1.pdf statement2.pdf
    python obfuscate_statements.py --variance 15 --output-dir ./demo *.pdf
    python obfuscate_statements.py --check-only statement.pdf

Features:
- Detects financial PDFs automatically
- Obfuscates dollar amounts within ±10% range (configurable)
- Obfuscates percentages, account numbers
- Preserves document structure
- Generates new PDFs with "_obfuscated" suffix
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List
from pdf_obfuscator import PDFObfuscator
from statement_uploader import extract_pdf_text, is_likely_financial_document


def check_financial_document(file_path: str, verbose: bool = False) -> bool:
    """
    Check if a PDF is a financial document.

    Args:
        file_path: Path to PDF file
        verbose: Print detailed detection information

    Returns:
        True if financial document, False otherwise
    """
    try:
        with open(file_path, 'rb') as f:
            content = f.read()

        text = extract_pdf_text(content)
        is_financial, confidence, keywords, debug_info = is_likely_financial_document(
            text, os.path.basename(file_path), debug=True
        )

        if verbose:
            print(f"\n{'='*60}")
            print(f"File: {os.path.basename(file_path)}")
            print(f"{'='*60}")
            print(f"Financial Document: {'✓ YES' if is_financial else '✗ NO'}")
            print(f"Confidence: {confidence*100:.1f}%")

            if debug_info:
                print(f"\nDetection Details:")
                print(f"  Score: {debug_info['total_score']:.1f} / {debug_info['max_possible']:.1f}")
                print(f"  Threshold: {debug_info['threshold']:.1f}")

                scores = debug_info['scores']
                matched = debug_info['matched_by_category']

                if scores.get('high_confidence', 0) > 0:
                    print(f"\n  High Confidence Keywords (+{scores['high_confidence']:.1f} pts):")
                    for kw in matched.get('high_confidence', [])[:5]:
                        print(f"    - {kw}")

                if scores.get('medium_confidence', 0) > 0:
                    print(f"\n  Medium Confidence Keywords (+{scores['medium_confidence']:.1f} pts):")
                    for kw in matched.get('medium_confidence', [])[:5]:
                        print(f"    - {kw}")

                if scores.get('account_types', 0) > 0:
                    print(f"\n  Account Types (+{scores['account_types']:.1f} pts):")
                    for kw in matched.get('account_types', []):
                        print(f"    - {kw}")

                if scores.get('filename', 0) > 0:
                    print(f"\n  Filename Hints (+{scores['filename']:.1f} pts):")
                    for kw in matched.get('filename', []):
                        print(f"    - {kw}")

                if scores.get('date_pattern', 0) > 0:
                    print(f"\n  Date Pattern: +{scores['date_pattern']:.1f} pts")

                if scores.get('dollar_amounts', 0) > 0:
                    print(f"  Dollar Amounts: +{scores['dollar_amounts']:.1f} pts")

                if debug_info.get('non_financial_indicator'):
                    print(f"\n  ✗ Rejected: Found '{debug_info['non_financial_indicator']}'")

        return is_financial

    except Exception as e:
        print(f"✗ Error checking {file_path}: {str(e)}", file=sys.stderr)
        return False


def obfuscate_file(
    input_path: str,
    output_dir: str = None,
    variance: float = 10.0,
    seed: int = None,
    force: bool = False,
    verbose: bool = False
) -> bool:
    """
    Obfuscate a single PDF file.

    Args:
        input_path: Path to input PDF
        output_dir: Output directory (default: same as input)
        variance: Variance percentage for obfuscation
        seed: Random seed for reproducibility
        force: Skip financial document check
        verbose: Print detailed information

    Returns:
        True if successful, False otherwise
    """
    input_file = Path(input_path)

    if not input_file.exists():
        print(f"✗ File not found: {input_path}", file=sys.stderr)
        return False

    if not input_file.suffix.lower() == '.pdf':
        print(f"✗ Not a PDF file: {input_path}", file=sys.stderr)
        return False

    # Check if it's a financial document (unless forced)
    if not force:
        with open(input_file, 'rb') as f:
            content = f.read()
        text = extract_pdf_text(content)
        is_financial, confidence, _, _ = is_likely_financial_document(
            text, input_file.name
        )

        if not is_financial:
            print(f"⚠ Skipping {input_file.name} (not detected as financial statement, confidence: {confidence*100:.0f}%)")
            print(f"  Use --force to obfuscate anyway")
            return False

        if verbose:
            print(f"✓ Detected as financial statement (confidence: {confidence*100:.0f}%)")

    # Read PDF content
    try:
        with open(input_file, 'rb') as f:
            pdf_content = f.read()
    except Exception as e:
        print(f"✗ Error reading {input_path}: {str(e)}", file=sys.stderr)
        return False

    # Obfuscate
    try:
        obfuscator = PDFObfuscator(variance_percent=variance, seed=seed)
        obfuscated_pdf, stats = obfuscator.obfuscate_pdf(pdf_content)

        # Determine output path
        if output_dir:
            output_path = Path(output_dir) / f"{input_file.stem}_obfuscated.pdf"
            output_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            output_path = input_file.parent / f"{input_file.stem}_obfuscated.pdf"

        # Write obfuscated PDF
        with open(output_path, 'wb') as f:
            f.write(obfuscated_pdf)

        print(f"✓ Obfuscated: {input_file.name} → {output_path.name}")

        if verbose or stats.get('error'):
            if stats.get('error'):
                print(f"  ✗ Error: {stats['error']}")
            else:
                print(f"  Statistics:")
                print(f"    - Dollar amounts: {stats.get('dollar_amounts', 0)}")
                print(f"    - Percentages: {stats.get('percentages', 0)}")
                print(f"    - Account numbers: {stats.get('account_numbers', 0)}")
                print(f"    - Variance: ±{variance}%")
                if seed:
                    print(f"    - Seed: {seed} (reproducible)")

        return True

    except Exception as e:
        print(f"✗ Error obfuscating {input_path}: {str(e)}", file=sys.stderr)
        if verbose:
            import traceback
            traceback.print_exc()
        return False


def main():
    """Main command-line interface"""
    parser = argparse.ArgumentParser(
        description="Obfuscate financial information in PDF statements for demos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Obfuscate single file
  python obfuscate_statements.py statement.pdf

  # Obfuscate multiple files
  python obfuscate_statements.py statement1.pdf statement2.pdf statement3.pdf

  # Use wildcards
  python obfuscate_statements.py statements/*.pdf

  # Custom variance and output directory
  python obfuscate_statements.py --variance 15 --output-dir ./demo *.pdf

  # Check if files are financial statements (no obfuscation)
  python obfuscate_statements.py --check-only statement.pdf

  # Force obfuscation even if not detected as financial
  python obfuscate_statements.py --force non_financial.pdf

  # Reproducible obfuscation with seed
  python obfuscate_statements.py --seed 12345 statement.pdf
        """
    )

    parser.add_argument(
        'files',
        nargs='+',
        help='PDF file(s) to obfuscate'
    )

    parser.add_argument(
        '-o', '--output-dir',
        help='Output directory for obfuscated files (default: same as input)'
    )

    parser.add_argument(
        '-v', '--variance',
        type=float,
        default=10.0,
        help='Variance percentage for number obfuscation (default: 10.0)'
    )

    parser.add_argument(
        '-s', '--seed',
        type=int,
        help='Random seed for reproducible obfuscation'
    )

    parser.add_argument(
        '-f', '--force',
        action='store_true',
        help='Force obfuscation even if not detected as financial statement'
    )

    parser.add_argument(
        '-c', '--check-only',
        action='store_true',
        help='Only check if files are financial statements, do not obfuscate'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print detailed information and statistics'
    )

    args = parser.parse_args()

    # Validate variance
    if args.variance < 0 or args.variance > 100:
        print("✗ Variance must be between 0 and 100", file=sys.stderr)
        sys.exit(1)

    # Check-only mode
    if args.check_only:
        print("Checking financial document detection...\n")
        for file_path in args.files:
            check_financial_document(file_path, verbose=True)
        sys.exit(0)

    # Process files
    print(f"Processing {len(args.files)} file(s)...")
    print(f"Variance: ±{args.variance}%")
    if args.seed:
        print(f"Seed: {args.seed} (reproducible)")
    if args.output_dir:
        print(f"Output directory: {args.output_dir}")
    print()

    success_count = 0
    skip_count = 0
    error_count = 0

    for file_path in args.files:
        result = obfuscate_file(
            file_path,
            output_dir=args.output_dir,
            variance=args.variance,
            seed=args.seed,
            force=args.force,
            verbose=args.verbose
        )

        if result:
            success_count += 1
        elif result is False:
            error_count += 1
        else:
            skip_count += 1

    # Summary
    print()
    print("="*60)
    print("Summary:")
    print(f"  ✓ Successfully obfuscated: {success_count}")
    if skip_count > 0:
        print(f"  ⚠ Skipped (not financial): {skip_count}")
    if error_count > 0:
        print(f"  ✗ Errors: {error_count}")
    print("="*60)

    # Exit code
    if error_count > 0:
        sys.exit(1)
    elif success_count == 0:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
