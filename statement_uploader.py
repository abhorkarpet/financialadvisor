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
from datetime import datetime
from typing import List, Dict, Tuple
from pypdf import PdfReader
from integrations.n8n_client import N8NClient, N8NError


# Page configuration
st.set_page_config(
    page_title="Financial Statement Uploader",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
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
    'invoice', 'receipt', 'menu', 'syllabus', 'lesson plan',
    'medical record', 'prescription', 'diagnosis'
]


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


def is_likely_financial_document(text: str, filename: str = "") -> Tuple[bool, float, List[str]]:
    """
    Determine if a document is likely a financial statement.

    Args:
        text: Extracted text from document
        filename: Original filename (optional hint)

    Returns:
        Tuple of (is_financial, confidence_score, matched_keywords)
    """
    if not text:
        return False, 0.0, []

    text_lower = text.lower()
    filename_lower = filename.lower()
    matched_keywords = []
    score = 0.0

    # Check for non-financial indicators first
    for indicator in NON_FINANCIAL_INDICATORS:
        if indicator in text_lower or indicator in filename_lower:
            return False, 0.0, [f"non-financial: {indicator}"]

    # High confidence keywords (5 points each)
    for keyword in FINANCIAL_KEYWORDS['high_confidence']:
        if keyword.lower() in text_lower:
            score += 5.0
            matched_keywords.append(keyword)

    # Medium confidence keywords (2 points each)
    for keyword in FINANCIAL_KEYWORDS['medium_confidence']:
        if keyword.lower() in text_lower:
            score += 2.0
            if keyword not in matched_keywords:
                matched_keywords.append(keyword)

    # Account types (3 points each)
    for keyword in FINANCIAL_KEYWORDS['account_types']:
        if keyword.lower() in text_lower:
            score += 3.0
            if keyword not in matched_keywords:
                matched_keywords.append(keyword)

    # Filename hints (bonus points)
    filename_keywords = ['statement', '401k', 'ira', 'roth', 'brokerage', 'invest']
    for keyword in filename_keywords:
        if keyword in filename_lower:
            score += 2.0

    # Look for date patterns (common in statements)
    date_patterns = [
        r'\d{1,2}/\d{1,2}/\d{2,4}',  # 12/31/2024
        r'\d{4}-\d{2}-\d{2}',         # 2024-12-31
        r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4}'
    ]
    for pattern in date_patterns:
        if re.search(pattern, text_lower):
            score += 1.0
            break

    # Look for dollar amounts (common in statements)
    if re.search(r'\$[\d,]+\.\d{2}', text):
        score += 2.0

    # Normalize score to 0-1 range
    confidence = min(score / 20.0, 1.0)  # 20 points = 100% confidence

    # Threshold: 0.3 confidence or higher
    is_financial = confidence >= 0.3

    return is_financial, confidence, matched_keywords


def validate_uploaded_files(uploaded_files) -> Dict:
    """
    Validate and categorize uploaded files.

    Args:
        uploaded_files: List of Streamlit UploadedFile objects

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
        is_financial, confidence, keywords = is_likely_financial_document(text, file.name)

        file_info = {
            'file': file,
            'name': file.name,
            'size': len(content),
            'confidence': confidence,
            'keywords': keywords[:5]  # Top 5 keywords
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
    Check if n8n webhook is properly configured.

    Returns:
        tuple: (is_configured: bool, webhook_url: str, error_message: str)
    """
    webhook_url = os.getenv('N8N_WEBHOOK_URL')

    if not webhook_url:
        return False, None, "N8N_WEBHOOK_URL environment variable not set"

    # Basic URL validation
    if not webhook_url.startswith(('http://', 'https://')):
        return False, webhook_url, "Invalid webhook URL format"

    return True, webhook_url, None


def display_configuration_help():
    """Display help for configuring the n8n webhook"""
    st.markdown('<div class="info-box">', unsafe_allow_html=True)
    st.markdown("### ⚙️ Configuration Required")

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
    N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/financial-statement-upload
    N8N_WEBHOOK_TOKEN=your_optional_auth_token
    ```

    **Step 3: Load Environment**
    ```bash
    # Install python-dotenv if needed
    pip install python-dotenv

    # Run the app
    streamlit run statement_uploader.py
    ```

    **For Testing:**
    You can also set the environment variable directly:
    ```bash
    export N8N_WEBHOOK_URL="https://your-webhook-url"
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
    }

    # Account type mappings
    account_mappings = {
        '401k': '401(k)',
        'ira': 'IRA',
        'roth_ira': 'Roth IRA',
        'traditional_ira': 'Traditional IRA',
        'rollover_ira': 'Rollover IRA',
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

    # Check mappings
    if value_str.lower() in tax_mappings:
        return tax_mappings[value_str.lower()]
    if value_str.lower() in account_mappings:
        return account_mappings[value_str.lower()]
    if value_str.lower() in asset_category_mappings:
        return asset_category_mappings[value_str.lower()]
    if value_str.lower() in investment_type_mappings:
        return investment_type_mappings[value_str.lower()]

    # Default: capitalize first letter of each word (replace _ with space)
    if '_' in value_str:
        return value_str.replace('_', ' ').title()

    return value_str


def display_csv_results(csv_content: str):
    """
    Display extracted CSV data in a formatted table.

    Args:
        csv_content: CSV string with extracted financial data
    """
    try:
        # Parse CSV
        df = pd.read_csv(io.StringIO(csv_content))

        # Convert numeric columns
        if 'value' in df.columns:
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
        if 'confidence' in df.columns:
            df['confidence'] = pd.to_numeric(df['confidence'], errors='coerce')

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
        text_columns = ['tax_treatment', 'account_type', 'asset_category', 'instrument_type']
        for col in text_columns:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(humanize_value)

        # Format value column as currency
        if 'value' in display_df.columns:
            display_df['value'] = display_df['value'].apply(lambda x: f"${x:,.2f}")

        # Format confidence column as percentage
        if 'confidence' in display_df.columns:
            display_df['confidence'] = display_df['confidence'].apply(lambda x: f"{x*100:.0f}%")

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
            'confidence': 'Confidence',
            'notes': 'Notes'
        }
        display_df = display_df.rename(columns=column_renames)

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )

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
                st.dataframe(tax_summary, use_container_width=True, hide_index=True)

            with col2:
                # Bar chart with humanized labels
                chart_data = df.groupby('tax_treatment')['value'].sum()
                # Rename index to humanized values
                chart_data.index = chart_data.index.map(humanize_value)
                st.bar_chart(chart_data)

        # Download options
        st.markdown("### Download Results")

        col1, col2 = st.columns(2)

        with col1:
            # Download CSV
            st.download_button(
                label="📥 Download CSV",
                data=csv_content,
                file_name=f"financial_statements_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

        with col2:
            # Download as JSON
            json_data = df.to_json(orient='records', indent=2)
            st.download_button(
                label="📥 Download JSON",
                data=json_data,
                file_name=f"financial_statements_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )

    except Exception as e:
        st.error(f"Error parsing CSV data: {str(e)}")
        st.code(csv_content)


def main():
    """Main application"""

    load_custom_css()

    # Header
    st.markdown('<div class="main-header">📄 Financial Statement Uploader</div>', unsafe_allow_html=True)
    st.markdown("Upload your financial statement PDFs to automatically extract and categorize account data.")

    # Sidebar
    with st.sidebar:
        st.markdown("## About")
        st.info("""
        This tool uses AI to extract structured data from financial statements including:
        - Account balances
        - Tax treatment classification
        - Account types (401k, IRA, etc.)
        - PII removal for privacy

        **Powered by:**
        - n8n workflow automation
        - OpenAI GPT-4.1
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

    # Check configuration
    is_configured, webhook_url, error_msg = check_configuration()

    if not is_configured:
        st.error(f"❌ Configuration Error: {error_msg}")
        display_configuration_help()
        st.stop()

    # Show configuration status
    with st.expander("ℹ️ Configuration Status"):
        st.success(f"✓ Webhook configured: {webhook_url[:50]}...")

        # Test connection
        if st.button("Test Webhook Connection"):
            with st.spinner("Testing connection..."):
                try:
                    client = N8NClient()
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
            validation = validate_uploaded_files(uploaded_files)

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
                    st.write("")

        # Only show process button if there are valid files
        if valid_files:
            # Option to override and include all files
            include_all = st.checkbox(
                f"Override: Include all {stats['total']} files (not recommended)",
                value=False,
                help="This will send all files to n8n, including non-financial documents, which may waste API credits."
            )

            # Process button
            if st.button("🚀 Extract & Categorize", type="primary", use_container_width=True):

                # Progress tracking
                progress_bar = st.progress(0)
                status_text = st.empty()

                try:
                    # Determine which files to upload
                    if include_all:
                        files_to_process = uploaded_files
                        st.info(f"Processing all {len(uploaded_files)} file(s) (override enabled)")
                    else:
                        files_to_process = [f['file'] for f in valid_files]
                        if invalid_files:
                            st.info(f"Skipping {len(invalid_files)} non-financial file(s)")

                    # Initialize client
                    status_text.text("Initializing connection to n8n workflow...")
                    progress_bar.progress(10)

                    client = N8NClient()

                    # Prepare files
                    status_text.text(f"Uploading {len(files_to_process)} file(s)...")
                    progress_bar.progress(30)

                    # Upload to n8n
                    files_to_upload = [(f.name, f.getvalue()) for f in files_to_process]

                    result = client.upload_statements(files_to_upload)

                    progress_bar.progress(90)

                    # Handle result
                    if result['success']:
                        progress_bar.progress(100)
                        status_text.text("✓ Processing complete!")

                        # Display results
                        st.markdown("---")
                        st.markdown("## Results")

                        # Show execution time
                        st.caption(f"Processed in {result['execution_time']:.2f} seconds")

                        # Display CSV data
                        display_csv_results(result['data'])

                    else:
                        progress_bar.progress(100)
                        status_text.text("✗ Processing failed")

                        st.markdown('<div class="error-box">', unsafe_allow_html=True)
                        st.markdown("### ❌ Processing Error")
                        st.error(result.get('error', 'Unknown error occurred'))
                        st.markdown('</div>', unsafe_allow_html=True)

                        # Troubleshooting tips
                        st.markdown("### Troubleshooting")
                        st.info("""
                        **Common issues:**
                        - Ensure your n8n workflow is active
                        - Check OpenAI API credentials in n8n
                        - Verify the PDFs contain actual financial statements
                        - Check n8n execution logs for detailed errors
                        """)

                except N8NError as e:
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
        **Max file size:** Check your n8n instance limits
        """)
        st.markdown('</div>', unsafe_allow_html=True)

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; font-size: 0.9rem;'>
        <p>Part of the Financial Advisor - Retirement Planning Tool</p>
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
