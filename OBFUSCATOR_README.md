# Financial Statement Obfuscator

**Offline PDF Financial Statement Handler for Product Demos**

This tool allows you to create product demos using financial statements while protecting personal information. It automatically detects financial PDFs and obfuscates numerical data within a configurable range (±10% by default).

## Features

- ✅ **Offline Processing** - No external APIs or internet required
- 🔍 **Auto-Detection** - Automatically identifies financial statements
- 🔢 **Smart Obfuscation** - Obfuscates numbers within ±10% range (configurable)
- 📄 **Multiple Formats** - Handles dollar amounts, percentages, account numbers
- 🎯 **Batch Processing** - Process multiple PDFs at once
- 🔐 **Privacy-First** - All processing happens locally on your machine

## What Gets Obfuscated

The tool intelligently identifies and obfuscates:

1. **Dollar Amounts**: $1,234.56 → $1,189.23 (±10%)
2. **Percentages**: 5.5% → 5.8% (±10%)
3. **Account Numbers**: Account #1234567890 → Account #1267893450
4. **Plain Numbers**: Large numbers in financial context

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Install Dependencies

All required dependencies are already in `requirements.txt`:

```bash
pip install -r requirements.txt
```

Key dependencies:
- `pypdf>=3.17.0` - PDF reading
- `reportlab>=4.0.0` - PDF generation
- `pandas>=2.0.0` - Data processing

## Usage

### Basic Usage

Obfuscate a single PDF:

```bash
python obfuscate_statements.py statement.pdf
```

This will create `statement_obfuscated.pdf` in the same directory.

### Multiple Files

Process multiple PDFs at once:

```bash
python obfuscate_statements.py statement1.pdf statement2.pdf statement3.pdf
```

Use wildcards:

```bash
python obfuscate_statements.py statements/*.pdf
```

### Custom Variance

Change the obfuscation range (default is ±10%):

```bash
# Use ±15% variance
python obfuscate_statements.py --variance 15 statement.pdf

# Use ±5% variance for more subtle changes
python obfuscate_statements.py --variance 5 statement.pdf
```

### Custom Output Directory

Specify where obfuscated files should be saved:

```bash
python obfuscate_statements.py --output-dir ./demo_statements *.pdf
```

### Check Document Detection

Check if files are detected as financial statements without obfuscating:

```bash
python obfuscate_statements.py --check-only statement.pdf
```

This will show:
- Whether the file is detected as a financial statement
- Confidence score
- Keywords that were matched
- Detailed scoring breakdown

### Force Obfuscation

Force obfuscation even if not detected as a financial statement:

```bash
python obfuscate_statements.py --force non_financial.pdf
```

### Reproducible Obfuscation

Use a seed for consistent obfuscation across runs:

```bash
python obfuscate_statements.py --seed 12345 statement.pdf
```

Running this command multiple times will produce the same obfuscated values.

### Verbose Output

Get detailed statistics about what was obfuscated:

```bash
python obfuscate_statements.py --verbose statement.pdf
```

Output includes:
- Number of dollar amounts obfuscated
- Number of percentages obfuscated
- Number of account numbers obfuscated
- Variance used
- Seed (if specified)

## Command-Line Options

```
usage: obfuscate_statements.py [-h] [-o OUTPUT_DIR] [-v VARIANCE] [-s SEED]
                                [-f] [-c] [--verbose]
                                files [files ...]

Obfuscate financial information in PDF statements for demos

positional arguments:
  files                 PDF file(s) to obfuscate

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUT_DIR, --output-dir OUTPUT_DIR
                        Output directory for obfuscated files (default: same as input)
  -v VARIANCE, --variance VARIANCE
                        Variance percentage for number obfuscation (default: 10.0)
  -s SEED, --seed SEED  Random seed for reproducible obfuscation
  -f, --force           Force obfuscation even if not detected as financial statement
  -c, --check-only      Only check if files are financial statements, do not obfuscate
  --verbose             Print detailed information and statistics
```

## Examples

### Example 1: Basic Product Demo Setup

```bash
# Create demo directory
mkdir demo_statements

# Obfuscate all statements with ±15% variance
python obfuscate_statements.py --variance 15 --output-dir demo_statements *.pdf

# Output:
# Processing 3 file(s)...
# Variance: ±15.0%
# Output directory: demo_statements
#
# ✓ Obfuscated: 401k_statement.pdf → 401k_statement_obfuscated.pdf
# ✓ Obfuscated: ira_statement.pdf → ira_statement_obfuscated.pdf
# ✓ Obfuscated: brokerage_statement.pdf → brokerage_statement_obfuscated.pdf
#
# ============================================================
# Summary:
#   ✓ Successfully obfuscated: 3
# ============================================================
```

### Example 2: Check Detection Before Processing

```bash
# First, check what will be processed
python obfuscate_statements.py --check-only *.pdf

# Output shows detection details for each file:
# ============================================================
# File: 401k_statement.pdf
# ============================================================
# Financial Document: ✓ YES
# Confidence: 95.0%
#
# Detection Details:
#   Score: 19.0 / 20.0
#   Threshold: 6.0
#
#   High Confidence Keywords (+15.0 pts):
#     - 401k
#     - retirement
#     - employer match
#
# ... (more details)
```

### Example 3: Reproducible Demo Data

```bash
# Create consistent demo data that won't change between runs
python obfuscate_statements.py --seed 42 --output-dir demo *.pdf

# You can run this command multiple times and get identical output
```

### Example 4: Verbose Processing

```bash
# Get detailed statistics
python obfuscate_statements.py --verbose --variance 10 statement.pdf

# Output:
# ✓ Detected as financial statement (confidence: 95%)
# ✓ Obfuscated: statement.pdf → statement_obfuscated.pdf
#   Statistics:
#     - Dollar amounts: 47
#     - Percentages: 12
#     - Account numbers: 3
#     - Variance: ±10.0%
```

## How It Works

### 1. Document Detection

The tool uses the same detection logic as `statement_uploader.py`:

- Scans for financial keywords (401k, IRA, Roth, brokerage, etc.)
- Looks for account types (checking, savings, etc.)
- Detects date patterns and dollar amounts
- Scores confidence on a 0-100% scale
- Threshold: 30% confidence required

### 2. Number Obfuscation

For each detected number:

- **Dollar amounts**: Extracts numeric value, applies ±variance%, preserves formatting
  - `$1,234.56` → `$1,312.89` (within ±10%)
  - `$50,000` → `$47,500` (within ±10%)

- **Percentages**: Applies same variance to percentage values
  - `5.5%` → `5.2%` (within ±10%)
  - `10%` → `11%` (within ±10%)

- **Account Numbers**: Randomizes digits while preserving format
  - `Account #1234567890` → `Account #1267843290`
  - Keeps first 2 and last 2 digits for longer numbers

### 3. PDF Generation

- Extracts text from original PDF
- Applies obfuscation to all detected numbers
- Generates new PDF with same text content
- Maintains readability and basic formatting

## Limitations

1. **Layout Preservation**: The tool creates text-based PDFs. Complex layouts with images, tables, and precise formatting may not be perfectly preserved. For best results with complex layouts, consider using PDF editing software to manually adjust the output.

2. **OCR**: If your PDFs are scanned images (not text), you'll need to OCR them first. The tool only works with text-based PDFs.

3. **PII**: While the tool obfuscates numbers, it does NOT remove:
   - Names
   - Addresses
   - Social Security Numbers (unless in account number format)
   - Email addresses
   - Other personal text

   For complete anonymization, manually review the output or use additional tools.

## Supported Document Types

The auto-detection works with:

- ✅ 401(k) statements
- ✅ IRA statements (Traditional, Roth, Rollover)
- ✅ Brokerage account statements
- ✅ Bank statements (checking, savings)
- ✅ HSA (Health Savings Account) statements
- ✅ Investment account statements
- ✅ Retirement account summaries

## Troubleshooting

### "Not detected as financial statement"

If a legitimate financial statement isn't being detected:

1. Use `--check-only` to see the detection details:
   ```bash
   python obfuscate_statements.py --check-only statement.pdf
   ```

2. Check the confidence score and keywords matched

3. Use `--force` to obfuscate anyway:
   ```bash
   python obfuscate_statements.py --force statement.pdf
   ```

### "Error reading PDF"

- Ensure the PDF is not password-protected
- Try opening the PDF in a PDF reader to verify it's not corrupted
- If it's a scanned PDF, you may need OCR software first

### Numbers not obfuscated correctly

- Use `--verbose` to see statistics
- Check if numbers are in expected format ($, %, etc.)
- Adjust variance if needed

## Python API

You can also use the obfuscator in your own Python scripts:

```python
from pdf_obfuscator import obfuscate_financial_statement

# Read PDF
with open('statement.pdf', 'rb') as f:
    pdf_content = f.read()

# Obfuscate with custom variance
obfuscated_pdf, stats = obfuscate_financial_statement(
    pdf_content,
    variance_percent=15.0,
    seed=12345  # Optional: for reproducibility
)

# Save result
with open('statement_obfuscated.pdf', 'wb') as f:
    f.write(obfuscated_pdf)

# Check statistics
print(f"Obfuscated {stats['dollar_amounts']} dollar amounts")
print(f"Obfuscated {stats['percentages']} percentages")
print(f"Obfuscated {stats['account_numbers']} account numbers")
```

### Advanced Python Usage

```python
from pdf_obfuscator import PDFObfuscator

# Create obfuscator with custom settings
obfuscator = PDFObfuscator(variance_percent=12.5, seed=42)

# Process multiple files
pdf_files = [
    ('statement1.pdf', pdf1_bytes),
    ('statement2.pdf', pdf2_bytes),
]

results = obfuscator.obfuscate_multiple_pdfs(pdf_files)

for filename, obfuscated_pdf, stats in results:
    if obfuscated_pdf:
        with open(filename, 'wb') as f:
            f.write(obfuscated_pdf)
        print(f"✓ {filename}: {stats['dollar_amounts']} amounts obfuscated")
    else:
        print(f"✗ {filename}: {stats.get('error', 'Unknown error')}")
```

## Security & Privacy

- **Offline Only**: All processing happens on your local machine
- **No Network Calls**: No data is sent to external servers
- **Deterministic**: Using `--seed` produces consistent results
- **Open Source**: Full source code available for review

## Contributing

Found a bug or want to improve the obfuscator? Contributions welcome!

1. Test your changes with real financial statements
2. Ensure backward compatibility
3. Update documentation

## License

Same license as the parent Smart Retire AI project.

## Support

For issues or questions:
- GitHub Issues: https://github.com/abhorkarpet/financialadvisor/issues
- Main Documentation: See main README.md

---

**Smart Retire AI v8.4.0** - Financial Statement Obfuscator
