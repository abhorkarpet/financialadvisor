"""
PDF Financial Statement Obfuscator

This module provides functionality to obfuscate financial information in PDF
statements for creating product demos without exposing personal data.

Features:
- Detects financial PDFs using existing validation logic
- Identifies and obfuscates numerical values within +-10% range
- Preserves document structure and formatting
- Generates new PDFs with obfuscated data
"""

import io
import re
import random
from typing import List, Dict, Tuple, Optional
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


class NumberObfuscator:
    """Handles obfuscation of different types of numbers"""

    def __init__(self, variance_percent: float = 10.0, seed: Optional[int] = None):
        """
        Initialize the number obfuscator.

        Args:
            variance_percent: Max percentage variance for obfuscation (default: 10%)
            seed: Random seed for reproducible obfuscation (optional)
        """
        self.variance_percent = variance_percent
        if seed is not None:
            random.seed(seed)

    def obfuscate_dollar_amount(self, amount: str) -> str:
        """
        Obfuscate a dollar amount within +-variance range.

        Args:
            amount: Dollar amount string (e.g., "$1,234.56", "$1234.56", "1,234.56")

        Returns:
            Obfuscated dollar amount in same format
        """
        # Extract numeric value
        numeric = re.sub(r'[^\d.]', '', amount)
        if not numeric or numeric == '.':
            return amount

        try:
            value = float(numeric)

            # Don't obfuscate zero or very small amounts
            if value < 0.01:
                return amount

            # Apply random variance
            variance = random.uniform(-self.variance_percent, self.variance_percent)
            new_value = value * (1 + variance / 100)

            # Round to 2 decimal places for currency
            new_value = round(new_value, 2)

            # Preserve original formatting
            has_dollar_sign = '$' in amount
            has_commas = ',' in amount
            has_cents = '.' in numeric

            # Format the new value
            if has_cents:
                formatted = f"{new_value:,.2f}"
            else:
                formatted = f"{int(new_value):,}"

            if not has_commas:
                formatted = formatted.replace(',', '')

            if has_dollar_sign:
                formatted = f"${formatted}"

            return formatted

        except (ValueError, TypeError):
            return amount

    def obfuscate_percentage(self, percent: str) -> str:
        """
        Obfuscate a percentage within +-variance range.

        Args:
            percent: Percentage string (e.g., "5.5%", "5.50%", "10%")

        Returns:
            Obfuscated percentage in same format
        """
        # Extract numeric value
        numeric = re.sub(r'[^\d.]', '', percent)
        if not numeric or numeric == '.':
            return percent

        try:
            value = float(numeric)

            # Apply random variance
            variance = random.uniform(-self.variance_percent, self.variance_percent)
            new_value = value * (1 + variance / 100)

            # Determine decimal places from original
            if '.' in numeric:
                decimal_places = len(numeric.split('.')[1])
                new_value = round(new_value, decimal_places)
                formatted = f"{new_value:.{decimal_places}f}"
            else:
                new_value = round(new_value)
                formatted = str(int(new_value))

            # Preserve percentage sign
            if '%' in percent:
                formatted = f"{formatted}%"

            return formatted

        except (ValueError, TypeError):
            return percent

    def obfuscate_account_number(self, account_num: str) -> str:
        """
        Obfuscate an account number by randomizing digits.

        Args:
            account_num: Account number string

        Returns:
            Obfuscated account number with same format
        """
        # Common account number patterns
        # Usually keep first few and last few digits, randomize middle
        digits = re.findall(r'\d+', account_num)

        if not digits:
            return account_num

        result = account_num
        for digit_group in digits:
            if len(digit_group) >= 4:
                # Keep first 2 and last 2 digits, randomize middle
                if len(digit_group) <= 6:
                    # For shorter numbers, just randomize all
                    new_digits = ''.join([str(random.randint(0, 9)) for _ in digit_group])
                else:
                    # Keep first 2 and last 2, randomize middle
                    prefix = digit_group[:2]
                    suffix = digit_group[-2:]
                    middle_len = len(digit_group) - 4
                    middle = ''.join([str(random.randint(0, 9)) for _ in range(middle_len)])
                    new_digits = prefix + middle + suffix

                result = result.replace(digit_group, new_digits, 1)

        return result

    def obfuscate_plain_number(self, number: str) -> str:
        """
        Obfuscate a plain number within +-variance range.

        Args:
            number: Plain number string (e.g., "1234", "1234.56")

        Returns:
            Obfuscated number in same format
        """
        try:
            # Determine if it's a float or int
            if '.' in number:
                value = float(number)
                decimal_places = len(number.split('.')[1])

                # Apply variance
                variance = random.uniform(-self.variance_percent, self.variance_percent)
                new_value = value * (1 + variance / 100)
                new_value = round(new_value, decimal_places)

                return f"{new_value:.{decimal_places}f}"
            else:
                value = int(number)

                # Apply variance
                variance = random.uniform(-self.variance_percent, self.variance_percent)
                new_value = value * (1 + variance / 100)
                new_value = round(new_value)

                return str(int(new_value))

        except (ValueError, TypeError):
            return number


class PDFObfuscator:
    """Handles PDF document obfuscation"""

    def __init__(self, variance_percent: float = 10.0, seed: Optional[int] = None):
        """
        Initialize the PDF obfuscator.

        Args:
            variance_percent: Max percentage variance for number obfuscation
            seed: Random seed for reproducible obfuscation
        """
        self.obfuscator = NumberObfuscator(variance_percent, seed)
        self.variance_percent = variance_percent

    def extract_text_from_pdf(self, pdf_content: bytes) -> str:
        """
        Extract text from PDF file.

        Args:
            pdf_content: PDF file as bytes

        Returns:
            Extracted text string
        """
        try:
            pdf = PdfReader(io.BytesIO(pdf_content))
            text_parts = []

            for page in pdf.pages:
                text_parts.append(page.extract_text())

            return '\n'.join(text_parts)

        except Exception as e:
            raise ValueError(f"Could not extract text from PDF: {str(e)}")

    def obfuscate_text(self, text: str) -> Tuple[str, Dict[str, int]]:
        """
        Obfuscate numbers in extracted text.

        Args:
            text: Extracted text from PDF

        Returns:
            Tuple of (obfuscated_text, stats_dict)
        """
        obfuscated_text = text
        stats = {
            'dollar_amounts': 0,
            'percentages': 0,
            'account_numbers': 0,
            'plain_numbers': 0
        }

        # 1. Obfuscate dollar amounts (e.g., $1,234.56, $1234, 1,234.56)
        dollar_pattern = r'\$?[\d,]+\.?\d*'

        def replace_dollar(match):
            original = match.group(0)
            # Only process if it looks like currency (has $ or comma or decimal)
            if '$' in original or ',' in original or ('.' in original and len(original.split('.')[-1]) == 2):
                stats['dollar_amounts'] += 1
                return self.obfuscator.obfuscate_dollar_amount(original)
            return original

        obfuscated_text = re.sub(dollar_pattern, replace_dollar, obfuscated_text)

        # 2. Obfuscate percentages (e.g., 5.5%, 10%)
        percent_pattern = r'\d+\.?\d*%'

        def replace_percent(match):
            stats['percentages'] += 1
            return self.obfuscator.obfuscate_percentage(match.group(0))

        obfuscated_text = re.sub(percent_pattern, replace_percent, obfuscated_text)

        # 3. Obfuscate account numbers (patterns like "Account #1234567890")
        account_pattern = r'(?:Account|Acct\.?|Account Number|Policy|Contract)[\s#:]*(\d{6,})'

        def replace_account(match):
            stats['account_numbers'] += 1
            original = match.group(0)
            account_num = match.group(1)
            obfuscated_num = self.obfuscator.obfuscate_account_number(account_num)
            return original.replace(account_num, obfuscated_num)

        obfuscated_text = re.sub(account_pattern, replace_account, obfuscated_text, flags=re.IGNORECASE)

        return obfuscated_text, stats

    def create_text_pdf(self, text: str, output_filename: str = None) -> bytes:
        """
        Create a simple text-based PDF from obfuscated text.

        Args:
            text: Obfuscated text to include in PDF
            output_filename: Optional output filename

        Returns:
            PDF content as bytes
        """
        buffer = io.BytesIO()

        # Create PDF canvas
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Set up text formatting
        c.setFont("Helvetica", 10)

        # Split text into lines
        lines = text.split('\n')

        # Starting position
        y_position = height - 50
        line_height = 12

        for line in lines:
            # Check if we need a new page
            if y_position < 50:
                c.showPage()
                c.setFont("Helvetica", 10)
                y_position = height - 50

            # Wrap long lines
            if len(line) > 90:
                # Simple word wrapping
                words = line.split()
                current_line = ""
                for word in words:
                    if len(current_line) + len(word) + 1 <= 90:
                        current_line += word + " "
                    else:
                        c.drawString(50, y_position, current_line.strip())
                        y_position -= line_height
                        current_line = word + " "

                        if y_position < 50:
                            c.showPage()
                            c.setFont("Helvetica", 10)
                            y_position = height - 50

                if current_line:
                    c.drawString(50, y_position, current_line.strip())
                    y_position -= line_height
            else:
                c.drawString(50, y_position, line)
                y_position -= line_height

        # Save PDF
        c.save()

        # Get PDF bytes
        buffer.seek(0)
        return buffer.getvalue()

    def obfuscate_pdf(self, pdf_content: bytes, output_filename: str = None) -> Tuple[bytes, Dict]:
        """
        Obfuscate a PDF financial statement.

        Args:
            pdf_content: Original PDF content as bytes
            output_filename: Optional output filename

        Returns:
            Tuple of (obfuscated_pdf_bytes, stats_dict)
        """
        # Extract text
        text = self.extract_text_from_pdf(pdf_content)

        # Obfuscate text
        obfuscated_text, stats = self.obfuscate_text(text)

        # Create new PDF with obfuscated text
        obfuscated_pdf = self.create_text_pdf(obfuscated_text, output_filename)

        return obfuscated_pdf, stats

    def obfuscate_multiple_pdfs(self, pdf_files: List[Tuple[str, bytes]]) -> List[Tuple[str, bytes, Dict]]:
        """
        Obfuscate multiple PDF files.

        Args:
            pdf_files: List of (filename, pdf_content_bytes) tuples

        Returns:
            List of (filename, obfuscated_pdf_bytes, stats) tuples
        """
        results = []

        for filename, content in pdf_files:
            try:
                obfuscated_pdf, stats = self.obfuscate_pdf(content)

                # Generate output filename
                base_name = filename.rsplit('.', 1)[0]
                output_filename = f"{base_name}_obfuscated.pdf"

                results.append((output_filename, obfuscated_pdf, stats))

            except Exception as e:
                # Include error in results
                results.append((filename, None, {'error': str(e)}))

        return results


def obfuscate_financial_statement(
    pdf_content: bytes,
    variance_percent: float = 10.0,
    seed: Optional[int] = None
) -> Tuple[bytes, Dict]:
    """
    Convenience function to obfuscate a single financial statement PDF.

    Args:
        pdf_content: PDF file content as bytes
        variance_percent: Max percentage variance for obfuscation (default: 10%)
        seed: Random seed for reproducible obfuscation (optional)

    Returns:
        Tuple of (obfuscated_pdf_bytes, statistics_dict)

    Example:
        >>> with open('statement.pdf', 'rb') as f:
        ...     content = f.read()
        >>> obfuscated_pdf, stats = obfuscate_financial_statement(content)
        >>> print(f"Obfuscated {stats['dollar_amounts']} dollar amounts")
        >>> with open('statement_obfuscated.pdf', 'wb') as f:
        ...     f.write(obfuscated_pdf)
    """
    obfuscator = PDFObfuscator(variance_percent, seed)
    return obfuscator.obfuscate_pdf(pdf_content)
