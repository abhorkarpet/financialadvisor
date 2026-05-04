"""
Financial Statement Uploader - Standalone Streamlit App

This app allows users to upload financial statement PDFs and extract
structured account data using an n8n workflow with AI processing.

Run with: streamlit run statement_uploader.py
"""

import os
import io
import re
import pandas as pd
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from pypdf import PdfReader
from integrations.n8n_client import N8NClient, N8NError
from integrations.statement_processor import StatementProcessor, StatementProcessorError
from integrations.processor_factory import get_processor

_USE_PYTHON_PROCESSOR = os.getenv("PYTHON_STATEMENT_PROCESSOR", "").lower() in ("true", "1", "yes")
_N8N_URL = os.getenv("N8N_STATEMENT_UPLOADER_URL") or os.getenv("N8N_WEBHOOK_URL")
_OPENAI_KEY = os.getenv("OPENAI_API_KEY")
# Comparison mode is possible only when both backends are configured
_COMPARISON_AVAILABLE = bool(_N8N_URL and _OPENAI_KEY)


# Page configuration
st.set_page_config(
    page_title="Financial Statement Uploader",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/abhorkarpet/financialadvisor',
        'Report a bug': 'https://github.com/abhorkarpet/financialadvisor/issues',
        'About': "Smart Retire AI - Financial Statement Uploader v2.0"
    }
)


# Financial document keywords for pre-filtering
FINANCIAL_KEYWORDS = {
    'high_confidence': [
        '401(k)', '401k', 'ira', 'roth', 'brokerage', 'investment',
        'retirement', 'account balance', 'portfolio', 'vanguard',
        'fidelity', 'schwab', 'statement period', 'account summary',
        'total balance', 'contributions', 'employer match', 'hsa',
        'health savings', 'annuity', 'dividend', 'capital gains',
        'tax-deferred', 'tax-exempt', 'rollover', 'beneficiary'
    ],
    'medium_confidence': [
        'account', 'balance', 'statement', 'quarterly', 'annual',
        'assets', 'securities', 'market value', 'shares', 'units',
        'funds', 'equity', 'bonds', 'stocks', 'mutual fund'
    ],
    'account_types': [
        'checking', 'savings', 'money market', 'cd', 'certificate of deposit'
    ]
}

NON_FINANCIAL_INDICATORS = [
    'recipe', 'resume', 'cv', 'curriculum vitae', 'cover letter',
    'menu', 'syllabus', 'lesson plan',
    'medical record', 'prescription', 'diagnosis'
]
# Note: Removed 'receipt' and 'invoice' as they appear in legitimate financial documents
# (e.g., "upon receipt of this statement", "invoice for services")


def extract_pdf_text(file_content: bytes, max_pages: int = 3) -> str:
    """
    Extract text from first few pages of PDF.

    Args:
        file_content: PDF file as bytes
        max_pages: Maximum number of pages to extract (default: 3)

    Returns:
        Extracted text string
    """
    try:
        pdf = PdfReader(io.BytesIO(file_content))
        text_parts = []

        # Extract text from first few pages
        for i in range(min(max_pages, len(pdf.pages))):
            page = pdf.pages[i]
            text_parts.append(page.extract_text())

        return ' '.join(text_parts).lower()

    except Exception as e:
        st.warning(f"Could not extract text from PDF: {str(e)}")
        return ""


def is_likely_financial_document(text: str, filename: str = "", debug: bool = False) -> Tuple[bool, float, List[str], Dict]:
    """
    Determine if a document is likely a financial statement.

    Args:
        text: Extracted text from document
        filename: Original filename (optional hint)
        debug: If True, return detailed scoring breakdown

    Returns:
        Tuple of (is_financial, confidence_score, matched_keywords, debug_info)
    """
    if not text:
        return False, 0.0, [], {}

    text_lower = text.lower()
    filename_lower = filename.lower()
    matched_keywords = []
    score = 0.0

    # Debug information
    debug_info = {
        'scores': {},
        'matched_by_category': {},
        'non_financial_indicator': None,
        'total_score': 0.0,
        'threshold': 6.0,
        'max_possible': 20.0
    }

    # Check for non-financial indicators first
    for indicator in NON_FINANCIAL_INDICATORS:
        if indicator in text_lower or indicator in filename_lower:
            debug_info['non_financial_indicator'] = indicator
            return False, 0.0, [f"non-financial: {indicator}"], debug_info

    # High confidence keywords (5 points each)
    high_conf_matches = []
    high_conf_score = 0.0
    for keyword in FINANCIAL_KEYWORDS['high_confidence']:
        if keyword.lower() in text_lower:
            high_conf_score += 5.0
            matched_keywords.append(keyword)
            high_conf_matches.append(keyword)
    score += high_conf_score
    debug_info['scores']['high_confidence'] = high_conf_score
    debug_info['matched_by_category']['high_confidence'] = high_conf_matches

    # Medium confidence keywords (2 points each)
    med_conf_matches = []
    med_conf_score = 0.0
    for keyword in FINANCIAL_KEYWORDS['medium_confidence']:
        if keyword.lower() in text_lower:
            med_conf_score += 2.0
            if keyword not in matched_keywords:
                matched_keywords.append(keyword)
                med_conf_matches.append(keyword)
    score += med_conf_score
    debug_info['scores']['medium_confidence'] = med_conf_score
    debug_info['matched_by_category']['medium_confidence'] = med_conf_matches

    # Account types (3 points each)
    account_matches = []
    account_score = 0.0
    for keyword in FINANCIAL_KEYWORDS['account_types']:
        if keyword.lower() in text_lower:
            account_score += 3.0
            if keyword not in matched_keywords:
                matched_keywords.append(keyword)
                account_matches.append(keyword)
    score += account_score
    debug_info['scores']['account_types'] = account_score
    debug_info['matched_by_category']['account_types'] = account_matches

    # Filename hints (bonus points)
    filename_matches = []
    filename_score = 0.0
    filename_keywords = ['statement', '401k', 'ira', 'roth', 'brokerage', 'invest']
    for keyword in filename_keywords:
        if keyword in filename_lower:
            filename_score += 2.0
            filename_matches.append(keyword)
    score += filename_score
    debug_info['scores']['filename'] = filename_score
    debug_info['matched_by_category']['filename'] = filename_matches

    # Look for date patterns (common in statements)
    date_score = 0.0
    date_patterns = [
        r'\d{1,2}/\d{1,2}/\d{2,4}',  # 12/31/2024
        r'\d{4}-\d{2}-\d{2}',         # 2024-12-31
        r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4}'
    ]
    for pattern in date_patterns:
        if re.search(pattern, text_lower):
            date_score = 1.0
            break
    score += date_score
    debug_info['scores']['date_pattern'] = date_score

    # Look for dollar amounts (common in statements)
    dollar_score = 0.0
    if re.search(r'\$[\d,]+\.\d{2}', text):
        dollar_score = 2.0
    score += dollar_score
    debug_info['scores']['dollar_amounts'] = dollar_score

    # Normalize score to 0-1 range
    confidence = min(score / 20.0, 1.0)  # 20 points = 100% confidence
    debug_info['total_score'] = score

    # Threshold: 0.3 confidence or higher
    is_financial = confidence >= 0.3

    return is_financial, confidence, matched_keywords, debug_info


def validate_uploaded_files(uploaded_files, debug: bool = False) -> Dict:
    """
    Validate and categorize uploaded files.

    Args:
        uploaded_files: List of Streamlit UploadedFile objects
        debug: If True, include detailed debug information

    Returns:
        Dict with 'valid', 'invalid', and 'stats' keys
    """
    valid_files = []
    invalid_files = []

    for file in uploaded_files:
        # Reset file pointer
        file.seek(0)
        content = file.read()
        file.seek(0)  # Reset again for later use

        # Extract text and check
        text = extract_pdf_text(content)
        is_financial, confidence, keywords, debug_info = is_likely_financial_document(text, file.name, debug=debug)

        file_info = {
            'file': file,
            'name': file.name,
            'size': len(content),
            'confidence': confidence,
            'keywords': keywords[:5],  # Top 5 keywords
            'debug_info': debug_info if debug else None
        }

        if is_financial:
            valid_files.append(file_info)
        else:
            invalid_files.append(file_info)

    return {
        'valid': valid_files,
        'invalid': invalid_files,
        'stats': {
            'total': len(uploaded_files),
            'valid_count': len(valid_files),
            'invalid_count': len(invalid_files)
        }
    }


def load_custom_css():
    """Apply custom CSS styling"""
    st.markdown("""
    <style>
        .main-header {
            font-size: 2.5rem;
            font-weight: bold;
            color: #1f77b4;
            margin-bottom: 1rem;
        }
        .upload-box {
            border: 2px dashed #1f77b4;
            border-radius: 10px;
            padding: 2rem;
            text-align: center;
            margin: 1rem 0;
        }
        .success-box {
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
            border-radius: 5px;
            padding: 1rem;
            margin: 1rem 0;
        }
        .error-box {
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            border-radius: 5px;
            padding: 1rem;
            margin: 1rem 0;
        }
        .info-box {
            background-color: #d1ecf1;
            border: 1px solid #bee5eb;
            border-radius: 5px;
            padding: 1rem;
            margin: 1rem 0;
        }
    </style>
    """, unsafe_allow_html=True)


def check_configuration():
    """
    Check if the statement processor is properly configured.

    Returns:
        tuple: (is_configured: bool, webhook_url_or_mode: str, error_message: str)
    """
    if _USE_PYTHON_PROCESSOR:
        if not os.getenv('OPENAI_API_KEY'):
            return False, None, "OPENAI_API_KEY not set (required for Python processor)"
        return True, 'python-processor', None

    # n8n mode — try statement-uploader-specific URL first, then fall back to general webhook URL
    webhook_url = _N8N_URL #os.getenv('N8N_STATEMENT_UPLOADER_URL') or os.getenv('N8N_WEBHOOK_URL')

    if not webhook_url:
        return False, None, "N8N_STATEMENT_UPLOADER_URL or N8N_WEBHOOK_URL environment variable not set"

    # Basic URL validation
    if not webhook_url.startswith(('http://', 'https://')):
        return False, webhook_url, "Invalid webhook URL format"

    return True, webhook_url, None


def display_configuration_help():
    """Display help for configuring the statement processor."""
    st.markdown('<div class="info-box">', unsafe_allow_html=True)
    st.markdown("### ⚙️ Configuration Required")

    if _USE_PYTHON_PROCESSOR:
        st.markdown("""
    The Python processor is enabled (`PYTHON_STATEMENT_PROCESSOR=true`) but `OPENAI_API_KEY` is missing.

    **Fix:** Add your OpenAI API key to your `.env` file:
    ```bash
    OPENAI_API_KEY=sk-...
    PYTHON_STATEMENT_PROCESSOR=true
    ```

    Then restart the app:
    ```bash
    streamlit run statement_uploader.py
    ```
    """)
    else:
        st.markdown("""
    To use this app, you need to set up the n8n workflow webhook:

    **Step 1: Deploy n8n Workflow**
    1. Follow instructions in `workflows/README.md`
    2. Import the workflow to your n8n instance
    3. Convert Form Trigger to Webhook Trigger
    4. Activate the workflow and copy the webhook URL

    **Step 2: Configure Environment**

    Create a `.env` file in the project root:
    ```bash
    # Dedicated URL for statement uploader (recommended)
    N8N_STATEMENT_UPLOADER_URL=https://your-n8n-instance.com/webhook/statement-uploader

    # OR use the general webhook URL (fallback)
    N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/financial-statement-upload

    # Optional authentication token
    N8N_WEBHOOK_TOKEN=your_optional_auth_token
    ```

    Alternatively, skip n8n entirely with the Python processor:
    ```bash
    PYTHON_STATEMENT_PROCESSOR=true
    OPENAI_API_KEY=sk-...
    ```

    **Step 3: Load Environment**
    ```bash
    streamlit run statement_uploader.py
    ```
    """)

    st.markdown('</div>', unsafe_allow_html=True)


def humanize_value(value: str) -> str:
    """Convert coded values to human-readable format."""
    if pd.isna(value):
        return value

    value_str = str(value).strip()

    # Tax treatment mappings
    tax_mappings = {
        'pre_tax': 'Pre-Tax',
        'post_tax': 'Post-Tax',
        'tax_free': 'Tax-Free',
        'tax_deferred': 'Tax-Deferred',
    }

    # Account type mappings
    account_mappings = {
        '401k': '401(k)',
        'ira': 'IRA',
        'roth_ira': 'Roth IRA',
        'traditional_ira': 'Traditional IRA',
        'rollover_ira': 'Rollover IRA',
        'savings': 'Savings',
        'checking': 'Checking',
        'brokerage': 'Brokerage',
        'hsa': 'HSA',
    }

    # Asset category mappings
    asset_category_mappings = {
        'retirement': 'Retirement Accounts',
        'cash': 'Cash & Savings',
        'brokerage': 'Brokerage Accounts',
        'real_estate': 'Real Estate',
        'investment': 'Investments',
        'equity': 'Equity',
        'fixed_income': 'Fixed Income',
    }

    # Investment type mappings
    investment_type_mappings = {
        'mixed': 'Mixed Assets',
        'stocks': 'Stocks',
        'bonds': 'Bonds',
        'mutual_funds': 'Mutual Funds',
        'etf': 'ETFs',
        'cash': 'Cash',
        'money_market': 'Money Market',
    }

    # Purpose mappings
    purpose_mappings = {
        'income': 'Retirement Income',
        'general_income': 'General Income',
        'healthcare_only': 'Healthcare Only (HSA)',
        'education_only': 'Education Only (529)',
        'employment_compensation': 'Employment Compensation',
        'restricted_other': 'Restricted/Other',
    }

    # Income eligibility mappings
    eligibility_mappings = {
        'eligible': '✅ Eligible',
        'conditionally_eligible': '⚠️ Conditionally Eligible',
        'not_eligible': '❌ Not Eligible',
    }

    # Tax bucket type mappings
    bucket_mappings = {
        'traditional_401k': 'Traditional 401(k)',
        'roth_in_plan_conversion': 'Roth In-Plan Conversion',
        'after_tax_401k': 'After-Tax 401(k)',
        'employee_deferral': 'Employee Deferral',
        'employer_match': 'Employer Match',
    }

    # Check mappings
    if value_str.lower() in tax_mappings:
        return tax_mappings[value_str.lower()]
    if value_str.lower() in account_mappings:
        return account_mappings[value_str.lower()]
    if value_str.lower() in asset_category_mappings:
        return asset_category_mappings[value_str.lower()]
    if value_str.lower() in investment_type_mappings:
        return investment_type_mappings[value_str.lower()]
    if value_str.lower() in purpose_mappings:
        return purpose_mappings[value_str.lower()]
    if value_str.lower() in eligibility_mappings:
        return eligibility_mappings[value_str.lower()]
    if value_str.lower() in bucket_mappings:
        return bucket_mappings[value_str.lower()]

    # Default: capitalize first letter of each word (replace _ with space)
    if '_' in value_str:
        return value_str.replace('_', ' ').title()

    return value_str


def display_results(data, format_type='csv', warnings=None, key_prefix=''):
    """
    Display extracted financial data in a formatted table.

    Args:
        data: Either CSV string or list of account dictionaries
        format_type: 'csv' or 'json'
        warnings: Optional list of warning messages from processing
    """
    try:
        # Store tax_buckets data before flattening to DataFrame
        tax_buckets_by_account = {}

        # Convert data to DataFrame
        if format_type == 'json':
            # Split accounts with multiple tax sources BEFORE creating DataFrame
            split_accounts = []
            for account in data:
                # Check if account has multiple non-zero tax sources
                raw_tax_sources = account.get('_raw_tax_sources', [])
                non_zero_sources = [s for s in raw_tax_sources if s.get('balance', 0) > 0]

                if len(non_zero_sources) > 1:
                    # Split into separate accounts
                    for source in non_zero_sources:
                        split_account = account.copy()
                        source_label = source['label']
                        source_balance = source['balance']

                        # Determine tax treatment from source label
                        if 'roth' in source_label.lower():
                            tax_treatment = 'tax_free'
                            suffix = '- Roth'
                        elif 'after tax' in source_label.lower() or 'after-tax' in source_label.lower():
                            tax_treatment = 'post_tax'
                            suffix = '- After-Tax'
                        else:  # Employee Deferral, Traditional, etc.
                            tax_treatment = 'tax_deferred'
                            suffix = '- Traditional'

                        # Update split account
                        split_account['account_name'] = f"{account.get('account_name', '401k')} {suffix}"
                        split_account['ending_balance'] = source_balance
                        split_account['tax_treatment'] = tax_treatment
                        split_account['_tax_source_label'] = source_label
                        # Remove _raw_tax_sources to avoid confusion
                        split_account.pop('_raw_tax_sources', None)

                        split_accounts.append(split_account)
                else:
                    # Keep account as-is
                    split_accounts.append(account)

            # Save tax_buckets or raw_tax_sources before converting to DataFrame
            for idx, account in enumerate(split_accounts):
                account_id = account.get('account_id') or account.get('account_name') or f"account_{idx}"

                # Check for processed tax_buckets first
                if 'tax_buckets' in account and account['tax_buckets']:
                    tax_buckets_by_account[account_id] = account['tax_buckets']
                # Fall back to raw_tax_sources if available
                elif '_raw_tax_sources' in account and account['_raw_tax_sources']:
                    # Convert raw_tax_sources to bucket format for display
                    raw_sources = account['_raw_tax_sources']
                    buckets = []
                    for source in raw_sources:
                        if source.get('balance', 0) > 0:  # Only show non-zero balances
                            # Map label to tax treatment
                            label = source['label'].lower()
                            if 'roth' in label:
                                tax_treatment_bucket = 'tax_free'
                            elif 'after tax' in label or 'after-tax' in label:
                                tax_treatment_bucket = 'post_tax'
                            else:  # Employee deferral, traditional, etc.
                                tax_treatment_bucket = 'tax_deferred'

                            buckets.append({
                                'bucket_type': source['label'],
                                'tax_treatment': tax_treatment_bucket,
                                'balance': source['balance']
                            })
                    if buckets:
                        tax_buckets_by_account[account_id] = buckets

            # Convert JSON array to DataFrame
            df = pd.DataFrame(split_accounts)
            # Rename JSON fields to match CSV column names
            column_mapping = {
                'account_name': 'label',
                'ending_balance': 'value',
                'account_type': 'account_type',
                'tax_treatment': 'tax_treatment',
                'currency': 'currency',
                'balance_as_of_date': 'period_end',
                'institution': 'document_type',
                'purpose': 'purpose',
                'income_eligibility': 'income_eligibility',
                'classification_confidence': 'classification_confidence',
                'account_id': 'account_id'
            }
            df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
        else:
            # Parse CSV
            df = pd.read_csv(io.StringIO(data))

        # Convert numeric columns
        if 'value' in df.columns:
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
        elif 'ending_balance' in df.columns:
            df['value'] = pd.to_numeric(df['ending_balance'], errors='coerce')

        if df.empty or len(df) == 0:
            st.warning("No financial data was extracted from the uploaded statements.")
            st.info("""
            **Possible reasons:**
            - The document may not contain recognizable financial statements
            - Account balances might be zero or empty
            - The document was classified as NON-FINANCIAL

            Please ensure you're uploading actual financial statements (401k, IRA, brokerage, etc.)
            """)
            return

        st.success(f"✓ Successfully extracted {len(df)} account(s)")

        # Display summary
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Accounts", len(df))

        with col2:
            if 'value' in df.columns:
                total_value = df['value'].sum()
                st.metric("Total Value", f"${total_value:,.2f}")

        with col3:
            if 'account_type' in df.columns:
                unique_types = df['account_type'].nunique()
                st.metric("Account Types", unique_types)

        # Display data table
        st.markdown("### Extracted Account Data")

        # Format display columns
        display_df = df.copy()

        # Humanize coded values in text columns
        text_columns = ['tax_treatment', 'account_type', 'asset_category', 'instrument_type', 'purpose', 'income_eligibility']
        for col in text_columns:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(humanize_value)

        # Format value column as currency
        if 'value' in display_df.columns:
            display_df['value'] = display_df['value'].apply(lambda x: f"${x:,.2f}")

        # Format confidence column as percentage
        if 'confidence' in display_df.columns:
            display_df['confidence'] = display_df['confidence'].apply(lambda x: f"{x*100:.0f}%")

        # Format classification_confidence column as percentage
        if 'classification_confidence' in display_df.columns:
            display_df['classification_confidence'] = display_df['classification_confidence'].apply(
                lambda x: f"{x*100:.0f}%" if pd.notna(x) else ""
            )

        # Rename columns to be more readable
        column_renames = {
            'document_type': 'Document Type',
            'period_start': 'Period Start',
            'period_end': 'Period End',
            'label': 'Account Label',
            'value': 'Balance',
            'currency': 'Currency',
            'account_type': 'Account Type',
            'asset_category': 'Asset Category',
            'tax_treatment': 'Tax Treatment',
            'instrument_type': 'Investment Type',
            'purpose': 'Account Purpose',
            'income_eligibility': 'Income Eligibility',
            'classification_confidence': 'Classification Confidence',
            'confidence': 'Confidence',
            'notes': 'Notes'
        }
        display_df = display_df.rename(columns=column_renames)

        st.dataframe(
            display_df,
            width='stretch',
            hide_index=True
        )

        # Display warnings if any
        if warnings and len(warnings) > 0:
            st.markdown("### ⚠️ Processing Warnings")
            for warning in warnings:
                st.warning(warning)

        # Display tax bucket breakdowns
        if tax_buckets_by_account:
            st.markdown("### 🔍 Tax Bucket Breakdown")
            st.info("**Detailed tax source breakdown for retirement accounts**")

            for account_id, buckets in tax_buckets_by_account.items():
                # Find account name in DataFrame
                account_row = df[df.get('account_id') == account_id] if 'account_id' in df.columns else None
                if account_row is not None and not account_row.empty:
                    account_name = account_row.iloc[0].get('label', account_id)
                else:
                    account_name = account_id

                with st.expander(f"📊 {account_name}"):
                    # Create DataFrame for buckets
                    bucket_df = pd.DataFrame(buckets)

                    # Humanize bucket_type and tax_treatment
                    if 'bucket_type' in bucket_df.columns:
                        bucket_df['bucket_type'] = bucket_df['bucket_type'].apply(humanize_value)
                    if 'tax_treatment' in bucket_df.columns:
                        bucket_df['tax_treatment'] = bucket_df['tax_treatment'].apply(humanize_value)

                    # Format balance as currency
                    if 'balance' in bucket_df.columns:
                        total_bucket_balance = bucket_df['balance'].sum()
                        bucket_df['balance'] = bucket_df['balance'].apply(lambda x: f"${x:,.2f}")

                    # Rename columns
                    bucket_df = bucket_df.rename(columns={
                        'bucket_type': 'Tax Bucket',
                        'tax_treatment': 'Tax Treatment',
                        'balance': 'Balance'
                    })

                    st.dataframe(bucket_df, width='stretch', hide_index=True)

                    # Show total
                    if 'balance' in locals():
                        st.metric("Total", f"${total_bucket_balance:,.2f}")

        # Breakdown by tax treatment
        if 'tax_treatment' in df.columns and 'value' in df.columns:
            st.markdown("### Tax Treatment Breakdown")

            tax_summary = df.groupby('tax_treatment')['value'].sum().reset_index()
            tax_summary.columns = ['Tax Treatment', 'Total Value']

            # Humanize tax treatment values
            tax_summary['Tax Treatment'] = tax_summary['Tax Treatment'].apply(humanize_value)
            tax_summary['Total Value'] = tax_summary['Total Value'].apply(lambda x: f"${x:,.2f}")

            col1, col2 = st.columns(2)

            with col1:
                st.dataframe(tax_summary, width='stretch', hide_index=True)

            with col2:
                # Bar chart with humanized labels
                chart_data = df.groupby('tax_treatment')['value'].sum()
                # Rename index to humanized values
                chart_data.index = chart_data.index.map(humanize_value)
                st.bar_chart(chart_data)

        # Breakdown by income eligibility
        if 'income_eligibility' in df.columns and 'value' in df.columns:
            st.markdown("### Income Eligibility Breakdown")

            eligibility_summary = df.groupby('income_eligibility')['value'].sum().reset_index()
            eligibility_summary.columns = ['Income Eligibility', 'Total Value']

            # Humanize income eligibility values
            eligibility_summary['Income Eligibility'] = eligibility_summary['Income Eligibility'].apply(humanize_value)
            eligibility_summary['Total Value'] = eligibility_summary['Total Value'].apply(lambda x: f"${x:,.2f}")

            col1, col2 = st.columns(2)

            with col1:
                st.dataframe(eligibility_summary, width='stretch', hide_index=True)

            with col2:
                # Bar chart with humanized labels
                chart_data = df.groupby('income_eligibility')['value'].sum()
                # Rename index to humanized values
                chart_data.index = chart_data.index.map(humanize_value)
                st.bar_chart(chart_data)

        # Download options
        st.markdown("### Download Results")

        col1, col2 = st.columns(2)

        with col1:
            # Download CSV
            csv_download = df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv_download,
                file_name=f"financial_statements_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key=f"{key_prefix}_dl_csv" if key_prefix else None,
            )

        with col2:
            # Download as JSON
            json_data = df.to_json(orient='records', indent=2)
            st.download_button(
                label="📥 Download JSON",
                data=json_data,
                file_name=f"financial_statements_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key=f"{key_prefix}_dl_json" if key_prefix else None,
            )

        # Add Excel export if openpyxl is available
        try:
            import openpyxl
            from io import BytesIO

            # Create Excel file in memory
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Accounts')

                # Add tax bucket sheets if available
                if tax_buckets_by_account:
                    for idx, (account_id, buckets) in enumerate(list(tax_buckets_by_account.items())[:10]):  # Limit to 10 sheets
                        bucket_df = pd.DataFrame(buckets)
                        sheet_name = f"Buckets_{idx+1}"[:31]  # Excel sheet name limit
                        bucket_df.to_excel(writer, index=False, sheet_name=sheet_name)

            excel_buffer.seek(0)

            # Add Excel download button
            st.download_button(
                label="📥 Download Excel",
                data=excel_buffer,
                file_name=f"financial_statements_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Download as Excel with separate sheets for tax buckets",
                key=f"{key_prefix}_dl_xlsx" if key_prefix else None,
            )
        except ImportError:
            st.info("💡 Install openpyxl to enable Excel export: `pip install openpyxl`")

    except Exception as e:
        st.error(f"Error parsing data: {str(e)}")
        if format_type == 'csv':
            st.code(data)
        else:
            st.json(data)


def estimate_processing_time(file_count: int, total_size_mb: float) -> float:
    """
    Estimate processing time based on file count and size.

    Args:
        file_count: Number of files to process
        total_size_mb: Total size in MB

    Returns:
        Estimated time in seconds
    """
    # Base time per file (includes AI processing)
    base_time_per_file = 5.0  # seconds

    # Additional time based on file size
    time_per_mb = 2.0  # seconds per MB

    estimated_time = (file_count * base_time_per_file) + (total_size_mb * time_per_mb)

    return max(estimated_time, 10.0)  # Minimum 10 seconds


def display_file_preview_cards(uploaded_files, validation):
    """Display uploaded files as preview cards with status."""
    st.markdown("### 📁 Uploaded Files")

    for file in uploaded_files:
        file_size_kb = file.size / 1024
        file_size_mb = file_size_kb / 1024

        # Find file in validation results
        file_info = None
        is_valid = False
        for valid_file in validation['valid']:
            if valid_file['name'] == file.name:
                file_info = valid_file
                is_valid = True
                break
        if not file_info:
            for invalid_file in validation['invalid']:
                if invalid_file['name'] == file.name:
                    file_info = invalid_file
                    break

        # Create card
        with st.container():
            cols = st.columns([1, 4, 2, 2])

            with cols[0]:
                # Icon based on status
                if is_valid:
                    st.markdown("### ✅")
                else:
                    st.markdown("### ⚠️")

            with cols[1]:
                st.markdown(f"**{file.name}**")
                if file_info and 'keywords' in file_info and file_info['keywords']:
                    keywords_preview = ', '.join(file_info['keywords'][:2])
                    st.caption(f"Keywords: {keywords_preview}")

            with cols[2]:
                if file_size_mb >= 1:
                    st.metric("Size", f"{file_size_mb:.1f} MB")
                else:
                    st.metric("Size", f"{file_size_kb:.1f} KB")

            with cols[3]:
                if file_info:
                    confidence = file_info.get('confidence', 0) * 100
                    st.metric("Confidence", f"{confidence:.0f}%")

            st.markdown("---")


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

_INSTITUTION_DROP_WORDS = {
    "brokerage", "services", "service", "financial", "bank", "investments",
    "investment", "securities", "advisors", "advisory", "group", "trust",
    "wealth", "management", "asset", "assets", "fund", "funds", "capital",
}

def _normalize_institution(inst: str) -> str:
    """
    Reduce institution name to its first significant word so that
    'Vanguard' and 'Vanguard Brokerage Services' both key to 'vanguard'.
    """
    words = inst.lower().strip().split()
    # Keep only the first word that isn't a generic suffix
    for word in words:
        clean = re.sub(r"[^a-z0-9]", "", word)
        if clean and clean not in _INSTITUTION_DROP_WORDS:
            return clean
    return words[0] if words else "unknown"


def _account_key(account: Dict) -> str:
    """Soft match key: normalized_institution + account_type."""
    inst = _normalize_institution(account.get("institution") or "unknown")
    atype = (account.get("account_type") or "unknown").lower().strip()
    return f"{inst}|{atype}"


def compare_accounts(n8n_accounts: List[Dict], py_accounts: List[Dict]) -> Dict:
    """
    Match accounts from both processors and produce a structured diff.

    Matching strategy: group by (institution, account_type). Within each group
    pair by list index so the Nth n8n account matches the Nth Python account.
    Unmatched extras are reported as only-in-one-processor.
    """
    from collections import defaultdict

    def group_by_key(accounts):
        groups: Dict[str, List[Dict]] = defaultdict(list)
        for a in accounts:
            groups[_account_key(a)].append(a)
        return groups

    n8n_groups = group_by_key(n8n_accounts)
    py_groups  = group_by_key(py_accounts)
    all_keys   = set(n8n_groups) | set(py_groups)

    only_n8n:   List[Dict] = []
    only_python: List[Dict] = []
    matched:    List[Dict] = []   # accounts present in both, with diff details
    identical:  int = 0

    for key in sorted(all_keys):
        n8n_list = n8n_groups.get(key, [])
        py_list  = py_groups.get(key, [])
        pair_count = min(len(n8n_list), len(py_list))

        for i in range(pair_count):
            na, pa = n8n_list[i], py_list[i]
            diffs = {}

            nb = na.get("ending_balance") or 0
            pb = pa.get("ending_balance") or 0
            if abs(nb - pb) > 0.01:
                diffs["ending_balance"] = {
                    "n8n": nb, "python": pb,
                    "delta": pb - nb,
                    "delta_pct": ((pb - nb) / nb * 100) if nb else None,
                }

            for field in ("tax_treatment", "balance_as_of_date", "account_type",
                          "purpose", "income_eligibility"):
                nv = na.get(field)
                pv = pa.get(field)
                if nv != pv:
                    diffs[field] = {"n8n": nv, "python": pv}

            entry = {
                "n8n_account": na,
                "python_account": pa,
                "diffs": diffs,
                "label": na.get("account_name") or pa.get("account_name") or key,
            }
            matched.append(entry)
            if not diffs:
                identical += 1

        for extra in n8n_list[pair_count:]:
            only_n8n.append(extra)
        for extra in py_list[pair_count:]:
            only_python.append(extra)

    return {
        "only_n8n":    only_n8n,
        "only_python": only_python,
        "matched":     matched,
        "identical":   identical,
        "total_n8n":   len(n8n_accounts),
        "total_python": len(py_accounts),
    }


def display_comparison(n8n_result: Dict, py_result: Dict) -> None:
    """Render side-by-side results and a structured diff section."""

    n8n_ok = n8n_result.get("success", False)
    py_ok  = py_result.get("success", False)

    # --- status banners ---
    c1, c2 = st.columns(2)
    with c1:
        if not n8n_ok:
            st.error(f"n8n failed: {n8n_result.get('error', 'unknown error')}")
    with c2:
        if not py_ok:
            st.error(f"Python failed: {py_result.get('error', 'unknown error')}")

    # --- timing metrics ---
    n8n_time = n8n_result.get("execution_time", 0.0)
    py_time  = py_result.get("execution_time", 0.0)
    time_delta = py_time - n8n_time  # positive = Python slower, negative = Python faster

    t1, t2, t3 = st.columns(3)
    t1.metric("n8n time",    f"{n8n_time:.1f}s")
    t2.metric("Python time", f"{py_time:.1f}s",
              delta=f"{time_delta:+.1f}s vs n8n",
              delta_color="inverse")   # green when Python is faster (negative delta)
    if n8n_time > 0:
        faster = "n8n" if n8n_time < py_time else "Python"
        ratio  = max(n8n_time, py_time) / min(n8n_time, py_time)
        t3.metric("Faster", faster, delta=f"{ratio:.1f}× faster")

    # --- token usage (Python only — n8n doesn't expose this) ---
    py_tokens = py_result.get("token_usage")
    if py_tokens and py_tokens.get("total_tokens"):
        st.markdown("**OpenAI token usage (Python processor)**")
        u1, u2, u3 = st.columns(3)
        u1.metric("Prompt tokens",     f"{py_tokens['prompt_tokens']:,}")
        u2.metric("Completion tokens", f"{py_tokens['completion_tokens']:,}")
        u3.metric("Total tokens",      f"{py_tokens['total_tokens']:,}")

    if not (n8n_ok and py_ok):
        st.warning("One processor failed — diff not available.")
        if n8n_ok:
            st.markdown("### n8n results")
            display_results(n8n_result["data"], format_type=n8n_result.get("format", "json"),
                            warnings=n8n_result.get("warnings", []), key_prefix="n8n")
        if py_ok:
            st.markdown("### Python results")
            display_results(py_result["data"], format_type="json",
                            warnings=py_result.get("warnings", []), key_prefix="python")
        return

    n8n_accounts = n8n_result["data"] if isinstance(n8n_result["data"], list) else []
    py_accounts  = py_result["data"]

    diff = compare_accounts(n8n_accounts, py_accounts)

    # --- diff summary ---
    st.markdown("---")
    st.markdown("## Diff Summary")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("n8n accounts",    diff["total_n8n"])
    m2.metric("Python accounts", diff["total_python"],
              delta=diff["total_python"] - diff["total_n8n"])
    m3.metric("Matched pairs",   len(diff["matched"]))
    m4.metric("Identical",       diff["identical"],
              delta=f"{diff['identical']}/{len(diff['matched'])} matched" if diff["matched"] else None)

    # --- accounts only in one processor ---
    if diff["only_n8n"]:
        st.warning(f"**{len(diff['only_n8n'])} account(s) found by n8n only** (Python missed these):")
        for a in diff["only_n8n"]:
            name = a.get("account_name") or a.get("account_type") or "Unknown"
            bal  = a.get("ending_balance")
            st.markdown(f"- **{name}** ({a.get('institution') or '?'}) — "
                        f"${bal:,.2f}" if bal is not None else f"- **{name}** — balance unknown")

    if diff["only_python"]:
        st.info(f"**{len(diff['only_python'])} account(s) found by Python only** (n8n missed these):")
        for a in diff["only_python"]:
            name = a.get("account_name") or a.get("account_type") or "Unknown"
            bal  = a.get("ending_balance")
            st.markdown(f"- **{name}** ({a.get('institution') or '?'}) — "
                        f"${bal:,.2f}" if bal is not None else f"- **{name}** — balance unknown")

    # --- matched account diffs ---
    differing = [m for m in diff["matched"] if m["diffs"]]
    if not differing and not diff["only_n8n"] and not diff["only_python"]:
        st.success("Results are identical across both processors.")
    elif differing:
        st.markdown(f"### {len(differing)} matched account(s) with differences")
        for entry in differing:
            label = entry["label"]
            with st.expander(f"**{label}**", expanded=True):
                for field, vals in entry["diffs"].items():
                    nv, pv = vals["n8n"], vals["python"]
                    if field == "ending_balance":
                        delta = vals["delta"]
                        pct   = vals["delta_pct"]
                        pct_str = f" ({pct:+.1f}%)" if pct is not None else ""
                        st.markdown(
                            f"- **Balance**: n8n `${nv:,.2f}` → Python `${pv:,.2f}` "
                            f"(**{'+' if delta >= 0 else ''}{delta:,.2f}{pct_str}**)"
                        )
                    else:
                        field_label = field.replace("_", " ").title()
                        st.markdown(f"- **{field_label}**: n8n `{nv}` → Python `{pv}`")

    # --- warnings from both ---
    all_warnings = []
    for w in n8n_result.get("warnings", []):
        all_warnings.append(("n8n", w))
    for w in py_result.get("warnings", []):
        all_warnings.append(("Python", w))
    if all_warnings:
        with st.expander(f"Warnings ({len(all_warnings)})"):
            for source, w in all_warnings:
                st.caption(f"[{source}] {w}")

    # --- full side-by-side tables ---
    st.markdown("---")
    st.markdown("## Full Results")
    col_n8n, col_py = st.columns(2)
    with col_n8n:
        st.markdown("### n8n")
        display_results(n8n_accounts, format_type="json", warnings=[], key_prefix="n8n")
    with col_py:
        st.markdown("### Python")
        display_results(py_accounts, format_type="json", warnings=[], key_prefix="python")


def main():
    """Main application"""

    load_custom_css()

    # Initialize session state for upload history and retry functionality
    if 'upload_history' not in st.session_state:
        st.session_state.upload_history = []
    if 'last_upload_result' not in st.session_state:
        st.session_state.last_upload_result = None
    if 'retry_data' not in st.session_state:
        st.session_state.retry_data = None

    # Header
    st.markdown('<div class="main-header">📄 Financial Statement Uploader</div>', unsafe_allow_html=True)
    st.markdown("Upload your financial statement PDFs to automatically extract and categorize account data.")

    # Sidebar
    with st.sidebar:
        st.markdown("## About")
        if _USE_PYTHON_PROCESSOR:
            st.info("""
        This tool uses AI to extract structured data from financial statements including:
        - Account balances
        - Tax treatment classification
        - Account types (401k, IRA, etc.)
        - PII removal for privacy

        **Powered by:**
        - Pure Python processor (no n8n)
        - OpenAI GPT-4.1-mini
        - pypdf text extraction
        """)
        else:
            st.info("""
        This tool uses AI to extract structured data from financial statements including:
        - Account balances
        - Tax treatment classification
        - Account types (401k, IRA, etc.)
        - PII removal for privacy

        **Powered by:**
        - n8n workflow automation
        - OpenAI GPT-4o
        - OCR text extraction
        """)

        st.markdown("## Supported Documents")
        st.markdown("""
        - 401(k) statements
        - IRA statements
        - Roth IRA statements
        - Brokerage statements
        - HSA statements
        - Bank statements

        **Format:** PDF only
        """)

        st.markdown("## Privacy")
        st.success("""
        All personal information (names, addresses, SSN, etc.) is automatically removed from the extracted data.
        """)

        st.markdown("---")
        st.markdown("## Debug Mode")
        debug_mode = st.checkbox(
            "Enable verbose detection logging",
            value=False,
            help="Show detailed scoring breakdown for document detection"
        )

        st.markdown("---")
        st.markdown("## Comparison Mode")
        if _COMPARISON_AVAILABLE:
            comparison_mode = st.checkbox(
                "Compare n8n vs Python processor",
                value=False,
                help="Run both processors on the same files and show a side-by-side diff. Useful for validating the Python processor."
            )
        else:
            comparison_mode = False
            missing = []
            if not _N8N_URL:
                missing.append("N8N_WEBHOOK_URL")
            if not _OPENAI_KEY:
                missing.append("OPENAI_API_KEY")
            st.caption(f"Set {' and '.join(missing)} to enable comparison mode.")

    # Check configuration
    is_configured, webhook_url, error_msg = check_configuration()

    if not is_configured:
        st.error(f"❌ Configuration Error: {error_msg}")
        display_configuration_help()
        st.stop()

    # Show configuration status
    with st.expander("ℹ️ Configuration Status"):
        if _USE_PYTHON_PROCESSOR:
            st.success("✓ Python processor active (no n8n required)")
            if st.button("Test OpenAI API Key"):
                with st.spinner("Testing API key..."):
                    try:
                        import openai
                        client_test = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                        client_test.models.list()
                        st.success("✓ OpenAI API key is valid!")
                    except Exception as e:
                        st.error(f"✗ API key test failed: {str(e)}")
        else:
            st.success(f"✓ Webhook configured: {webhook_url}")

            # Test connection
            if st.button("Test Webhook Connection"):
                with st.spinner("Testing connection..."):
                    try:
                        client = N8NClient(webhook_url=webhook_url)
                        if client.test_connection():
                            st.success("✓ Webhook is reachable!")
                        else:
                            st.error("✗ Cannot reach webhook. Check your n8n instance.")
                    except Exception as e:
                        st.error(f"✗ Connection test failed: {str(e)}")

    # Main upload interface
    st.markdown("---")
    st.markdown("## Upload Statements")

    uploaded_files = st.file_uploader(
        "Choose PDF file(s)",
        type=['pdf'],
        accept_multiple_files=True,
        help="Upload one or more financial statement PDFs"
    )

    if uploaded_files:
        st.info(f"📎 {len(uploaded_files)} file(s) selected")

        # Validate files
        with st.spinner("Analyzing documents..."):
            validation = validate_uploaded_files(uploaded_files, debug=debug_mode)

        valid_files = validation['valid']
        invalid_files = validation['invalid']
        stats = validation['stats']

        # Display validation results
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Files", stats['total'])
        with col2:
            st.metric("✅ Financial", stats['valid_count'], delta_color="normal")
        with col3:
            st.metric("⚠️ Non-Financial", stats['invalid_count'], delta_color="inverse")

        # Show valid files
        if valid_files:
            st.success(f"✓ {len(valid_files)} file(s) ready to process")

            with st.expander("📄 Financial documents detected"):
                for idx, file_info in enumerate(valid_files, 1):
                    confidence_pct = file_info['confidence'] * 100
                    keywords_str = ', '.join(file_info['keywords'][:3]) if file_info['keywords'] else 'N/A'

                    st.write(f"**{idx}. {file_info['name']}**")
                    st.write(f"   - Size: {file_info['size'] / 1024:.1f} KB")
                    st.write(f"   - Confidence: {confidence_pct:.0f}%")
                    st.write(f"   - Keywords: {keywords_str}")

                    # Show debug information if enabled
                    if debug_mode and file_info.get('debug_info'):
                        debug_info = file_info['debug_info']
                        st.markdown("   - **🔍 Debug Scoring:**")

                        # Display scores
                        scores = debug_info['scores']
                        st.write(f"     - High Confidence: **{scores.get('high_confidence', 0):.1f}** pts")
                        if debug_info['matched_by_category'].get('high_confidence'):
                            st.write(f"       - {', '.join(debug_info['matched_by_category']['high_confidence'][:5])}")

                        st.write(f"     - Medium Confidence: **{scores.get('medium_confidence', 0):.1f}** pts")
                        if debug_info['matched_by_category'].get('medium_confidence'):
                            st.write(f"       - {', '.join(debug_info['matched_by_category']['medium_confidence'][:5])}")

                        st.write(f"     - Account Types: **{scores.get('account_types', 0):.1f}** pts")
                        if debug_info['matched_by_category'].get('account_types'):
                            st.write(f"       - {', '.join(debug_info['matched_by_category']['account_types'])}")

                        st.write(f"     - Filename: **{scores.get('filename', 0):.1f}** pts")
                        if debug_info['matched_by_category'].get('filename'):
                            st.write(f"       - {', '.join(debug_info['matched_by_category']['filename'])}")

                        st.write(f"     - Date Pattern: **{scores.get('date_pattern', 0):.1f}** pts")
                        st.write(f"     - Dollar Amounts: **{scores.get('dollar_amounts', 0):.1f}** pts")

                        st.write(f"     - **Total:** {debug_info['total_score']:.1f} / {debug_info['max_possible']:.1f} (threshold: {debug_info['threshold']:.1f})")
                        st.write(f"     - **Result:** {'✅ PASS' if file_info['confidence'] >= 0.3 else '❌ FAIL'}")

                    st.write("")

        # Show invalid files
        if invalid_files:
            st.warning(f"⚠️ {len(invalid_files)} file(s) filtered out (non-financial)")

            with st.expander("🚫 Non-financial documents (will be skipped)"):
                for idx, file_info in enumerate(invalid_files, 1):
                    confidence_pct = file_info['confidence'] * 100
                    reason = file_info['keywords'][0] if file_info['keywords'] else 'No financial keywords found'

                    st.write(f"**{idx}. {file_info['name']}**")
                    st.write(f"   - Size: {file_info['size'] / 1024:.1f} KB")
                    st.write(f"   - Confidence: {confidence_pct:.0f}%")
                    st.write(f"   - Reason: {reason}")

                    # Show debug information if enabled
                    if debug_mode and file_info.get('debug_info'):
                        debug_info = file_info['debug_info']
                        # Check for non-financial indicator
                        if debug_info.get('non_financial_indicator'):
                            st.write(f"   - ❌ **Rejected:** Found '{debug_info['non_financial_indicator']}'")

                        st.markdown("   - **🔍 Debug Scoring:**")

                        # Display scores
                        scores = debug_info['scores']
                        st.write(f"     - High Confidence: **{scores.get('high_confidence', 0):.1f}** pts")
                        if debug_info['matched_by_category'].get('high_confidence'):
                            st.write(f"       - {', '.join(debug_info['matched_by_category']['high_confidence'][:5])}")

                        st.write(f"     - Medium Confidence: **{scores.get('medium_confidence', 0):.1f}** pts")
                        if debug_info['matched_by_category'].get('medium_confidence'):
                            st.write(f"       - {', '.join(debug_info['matched_by_category']['medium_confidence'][:5])}")

                        st.write(f"     - Account Types: **{scores.get('account_types', 0):.1f}** pts")
                        if debug_info['matched_by_category'].get('account_types'):
                            st.write(f"       - {', '.join(debug_info['matched_by_category']['account_types'])}")

                        st.write(f"     - Filename: **{scores.get('filename', 0):.1f}** pts")
                        if debug_info['matched_by_category'].get('filename'):
                            st.write(f"       - {', '.join(debug_info['matched_by_category']['filename'])}")

                        st.write(f"     - Date Pattern: **{scores.get('date_pattern', 0):.1f}** pts")
                        st.write(f"     - Dollar Amounts: **{scores.get('dollar_amounts', 0):.1f}** pts")

                        st.write(f"     - **Total:** {debug_info['total_score']:.1f} / {debug_info['max_possible']:.1f} (threshold: {debug_info['threshold']:.1f})")
                        st.write(f"     - **Result:** {'❌ FAIL - Score too low' if file_info['confidence'] < 0.3 else '✅ PASS'}")

                    st.write("")

        # Only show process button if there are valid files
        if valid_files:
            # Option to override and include all files
            include_all = st.checkbox(
                f"Override: Include all {stats['total']} files (not recommended)",
                value=False,
                help="This will process all files, including non-financial documents, which may waste API credits."
            )

            btn_label = "🔍 Compare n8n vs Python" if comparison_mode else "🚀 Extract & Categorize"
            if st.button(btn_label, type="primary", width='stretch'):

                # Progress tracking
                progress_bar = st.progress(0)
                status_text = st.empty()

                try:
                    # Determine which files to process
                    if include_all:
                        files_to_process = uploaded_files
                        st.info(f"Processing all {len(uploaded_files)} file(s) (override enabled)")
                    else:
                        files_to_process = [f['file'] for f in valid_files]
                        if invalid_files:
                            st.info(f"Skipping {len(invalid_files)} non-financial file(s)")

                    files_to_upload = [(f.name, f.getvalue()) for f in files_to_process]

                    if comparison_mode:
                        # ---- Run both processors sequentially then compare ----
                        status_text.text("Running n8n processor...")
                        progress_bar.progress(10)
                        n8n_client = N8NClient(webhook_url=_N8N_URL)
                        n8n_result = n8n_client.upload_statements(files_to_upload)
                        progress_bar.progress(50)

                        status_text.text("Running Python processor...")
                        py_client = StatementProcessor()
                        py_result = py_client.upload_statements(files_to_upload)
                        progress_bar.progress(90)

                        progress_bar.progress(100)
                        status_text.text("✓ Both processors complete!")

                        st.markdown("---")
                        display_comparison(n8n_result, py_result)

                    else:
                        # ---- Single processor ----
                        if _USE_PYTHON_PROCESSOR:
                            status_text.text("Initializing Python processor...")
                        else:
                            status_text.text("Initializing connection to n8n workflow...")
                        progress_bar.progress(10)

                        client = StatementProcessor() if _USE_PYTHON_PROCESSOR else get_processor()

                        if _USE_PYTHON_PROCESSOR:
                            status_text.text(f"Extracting and analysing {len(files_to_process)} file(s)...")
                        else:
                            status_text.text(f"Uploading {len(files_to_process)} file(s)...")
                        progress_bar.progress(30)

                        result = client.upload_statements(files_to_upload)
                        progress_bar.progress(90)

                        if result['success']:
                            progress_bar.progress(100)
                            status_text.text("✓ Processing complete!")

                            st.markdown("---")
                            st.markdown("## Results")
                            st.caption(f"Processed in {result['execution_time']:.2f} seconds")

                            token_usage = result.get("token_usage")
                            if token_usage and token_usage.get("total_tokens"):
                                u1, u2, u3 = st.columns(3)
                                u1.metric("Prompt tokens",     f"{token_usage['prompt_tokens']:,}")
                                u2.metric("Completion tokens", f"{token_usage['completion_tokens']:,}")
                                u3.metric("Total tokens",      f"{token_usage['total_tokens']:,}")

                            format_type = result.get('format', 'csv')
                            warnings = result.get('warnings', [])
                            display_results(result['data'], format_type=format_type, warnings=warnings)

                        else:
                            progress_bar.progress(100)
                            status_text.text("✗ Processing failed")

                            st.markdown('<div class="error-box">', unsafe_allow_html=True)
                            st.markdown("### ❌ Processing Error")
                            st.error(result.get('error', 'Unknown error occurred'))
                            st.markdown('</div>', unsafe_allow_html=True)

                            st.markdown("### Troubleshooting")
                            if _USE_PYTHON_PROCESSOR:
                                st.info("""
                        **Common issues:**
                        - Ensure OPENAI_API_KEY is valid and has available credits
                        - Verify the PDFs contain selectable text (not scanned images)
                        - Check that the PDF is a financial statement with explicit balances
                        """)
                            else:
                                st.info("""
                        **Common issues:**
                        - Ensure your n8n workflow is active
                        - Check OpenAI API credentials in n8n
                        - Verify the PDFs contain actual financial statements
                        - Check n8n execution logs for detailed errors
                        """)

                except (N8NError, StatementProcessorError) as e:
                    progress_bar.progress(100)
                    status_text.text("✗ Configuration error")
                    st.error(f"Configuration Error: {str(e)}")

                except Exception as e:
                    progress_bar.progress(100)
                    status_text.text("✗ Unexpected error")
                    st.error(f"Unexpected Error: {str(e)}")
                    st.exception(e)

        else:
            # No valid financial documents
            st.error("❌ No financial documents detected")
            st.info("""
            **None of the uploaded files appear to be financial statements.**

            Please ensure you're uploading:
            - 401(k) or retirement account statements
            - IRA or Roth IRA statements
            - Brokerage account statements
            - Bank account statements
            - HSA (Health Savings Account) statements

            If you believe this is an error, you can use the "Override" option above.
            """)

    else:
        # Show upload prompt
        st.markdown('<div class="upload-box">', unsafe_allow_html=True)
        st.markdown("""
        ### 👆 Upload your financial statements above

        **Supported formats:** PDF only
        **Multiple files:** Yes
        **Max file size:** No hard limit (selectable-text PDFs work best)
        """)
        st.markdown('</div>', unsafe_allow_html=True)

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; font-size: 0.9rem;'>
        <p>Part of the Smart Retire AI - Retirement Planning Tool</p>
        <p>For support, see the main application documentation</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    # Load environment variables from .env if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    main()
