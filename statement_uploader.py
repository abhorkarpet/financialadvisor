"""
Financial Statement Uploader - Standalone Streamlit App

This app allows users to upload financial statement PDFs and extract
structured account data using an n8n workflow with AI processing.

Run with: streamlit run statement_uploader.py
"""

import os
import io
import pandas as pd
import streamlit as st
from datetime import datetime
from integrations.n8n_client import N8NClient, N8NError


# Page configuration
st.set_page_config(
    page_title="Financial Statement Uploader",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)


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


def display_csv_results(csv_content: str):
    """
    Display extracted CSV data in a formatted table.

    Args:
        csv_content: CSV string with extracted financial data
    """
    try:
        # Parse CSV
        df = pd.read_csv(io.StringIO(csv_content))

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

        # Format value column as currency
        if 'value' in display_df.columns:
            display_df['value'] = display_df['value'].apply(lambda x: f"${x:,.2f}")

        # Format confidence column as percentage
        if 'confidence' in display_df.columns:
            display_df['confidence'] = display_df['confidence'].apply(lambda x: f"{x*100:.0f}%")

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
            tax_summary['Total Value'] = tax_summary['Total Value'].apply(lambda x: f"${x:,.2f}")

            col1, col2 = st.columns(2)

            with col1:
                st.dataframe(tax_summary, use_container_width=True, hide_index=True)

            with col2:
                # Pie chart
                chart_data = df.groupby('tax_treatment')['value'].sum()
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

        # Display file details
        with st.expander("View uploaded files"):
            for idx, file in enumerate(uploaded_files, 1):
                st.write(f"{idx}. {file.name} ({file.size / 1024:.1f} KB)")

        # Process button
        if st.button("🚀 Extract & Categorize", type="primary", use_container_width=True):

            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                # Initialize client
                status_text.text("Initializing connection to n8n workflow...")
                progress_bar.progress(10)

                client = N8NClient()

                # Prepare files
                status_text.text(f"Uploading {len(uploaded_files)} file(s)...")
                progress_bar.progress(30)

                # Upload to n8n
                files_to_upload = [(f.name, f.getvalue()) for f in uploaded_files]

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
