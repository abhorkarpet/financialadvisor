# Testing Smart Retire AI Locally

## Prerequisites

- Python 3.9 or higher
- pip (Python package installer)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Or install manually:

```bash
pip install streamlit pandas reportlab
```

### 2. Run the Application

```bash
streamlit run fin_advisor.py
```

The application will automatically open in your default browser at `http://localhost:8501`

### 3. Test the Onboarding Flow

**Step 1: Personal Information**
- Enter your birth year
- Set target retirement age
- Set life expectancy
- Set desired annual retirement income (with helpful guidance on typical ranges)
- (Optional) Enter your name for PDF reports
- Click **"Next: Asset Configuration →"**

**Step 2: Asset Configuration**
- Choose one of the 3 setup methods:
  - **Upload Financial Statements (AI)** - Upload PDF statements for AI extraction (requires n8n integration)
  - **Upload CSV File** - Download template, fill it out, and upload
  - **Configure Individual Assets** - Manually add each account one by one
    - Default growth rate is 7% for all accounts
- Click **"Complete Setup → View Results"**

**Results & Analysis Page**
- After completing onboarding, you'll be taken to the Results & Analysis page
- **Fixed Facts Section** (collapsible expander):
  - Shows your baseline data: birth year, current age, baseline retirement age, life expectancy, income goal, and number of accounts
  - These values are locked - use "← Back to Setup" button to change them
- **What-If Scenario Adjustments**:
  - Adjust retirement age, life expectancy, income goal, tax rates, and inflation rate
  - All visualizations update instantly as you change values
  - Use "🔄 Reset to Baseline Values" to restore original onboarding data
- **Navigation**: Click "← Back to Setup" to return to onboarding and modify your accounts

**View Results**
- After completing onboarding, scroll down to see:
  - Key metrics
  - Portfolio breakdown
  - Tax analysis
  - Summary charts
  - PDF download option

### 4. Adjust Advanced Settings (Sidebar)

Click **"⚙️ Advanced Settings"** in the sidebar (collapsed by default) to adjust:
- **Current Marginal Tax Rate** - Your current tax bracket
- **Projected Retirement Tax Rate** - Expected tax rate in retirement
- **Expected Inflation Rate** - Long-term inflation assumption

### 5. Reset and Start Over

Click the **"🔄 Reset Onboarding"** button in the sidebar to start fresh.

## Troubleshooting

### Port Already in Use

If port 8501 is already in use:

```bash
streamlit run fin_advisor.py --server.port 8502
```

### Missing Dependencies

If you get import errors:

```bash
pip install --upgrade streamlit pandas reportlab
```

### Clear Cache

If you encounter unexpected behavior:

```bash
streamlit cache clear
```

Then restart the application.

## Running Tests

```bash
python3 fin_advisor.py --run-tests
```

## Advanced Options

### Run in Headless Mode (for servers)

```bash
streamlit run fin_advisor.py --server.headless true
```

### Custom Host/Port

```bash
streamlit run fin_advisor.py --server.address 0.0.0.0 --server.port 8080
```

### Enable CORS (for API access)

```bash
streamlit run fin_advisor.py --server.enableCORS false
```

## Features to Test

✅ **Onboarding Flow**
- [ ] Step 1: Personal info inputs work correctly
- [ ] Step 2: Asset configuration methods work
- [ ] Navigation buttons (Next/Previous/Complete) work
- [ ] Progress bar shows correct step

✅ **Advanced Settings (Sidebar)**
- [ ] Sidebar expander is collapsed by default
- [ ] Advanced Settings expander opens when clicked
- [ ] Tax rate sliders work
- [ ] Inflation rate slider works
- [ ] Help expanders provide guidance
- [ ] Settings persist across steps

✅ **Asset Configuration**
- [ ] Default growth rate slider works (0-20%)
- [ ] Growth rate help text shows typical rates
- [ ] AI upload uses default growth rate for investment accounts
- [ ] CSV upload accepts template format
- [ ] Manual asset configuration defaults to user's growth rate
- [ ] Editable tables update correctly
- [ ] Only 3 clear setup options (no Legacy or Default Portfolio)

✅ **Results Section**
- [ ] Shows only after onboarding complete
- [ ] Displays key metrics
- [ ] Shows portfolio breakdown
- [ ] Tax analysis displays correctly
- [ ] Charts render properly
- [ ] PDF download works (if reportlab installed)

✅ **Reset Functionality**
- [ ] Reset button appears after onboarding
- [ ] Clicking reset returns to Step 1
- [ ] Session state clears properly

✅ **Share & Feedback Module (Sidebar)**
- [ ] Share & Feedback expander appears in sidebar
- [ ] Thumbs up/down rating buttons work
- [ ] Rating buttons generate mailto links to smartretireai@gmail.com
- [ ] Social share buttons (Twitter, LinkedIn, Facebook) open correctly
- [ ] Email share button creates proper mailto link
- [ ] Copy link functionality works
- [ ] Feedback form accepts input
- [ ] Email/GitHub Issue submission options work
- [ ] Contact Us section displays smartretireai@gmail.com

✅ **AI Extraction Feedback**
- [ ] Feedback module appears after AI extraction
- [ ] "Looks Good" button generates positive feedback email
- [ ] "Needs Work" button shows detailed feedback form
- [ ] Issue type multiselect allows multiple selections
- [ ] Specific issues text area accepts input
- [ ] Statement type input is optional
- [ ] Form validates required fields
- [ ] Submit generates proper feedback email with details
- [ ] Feedback helps identify extraction accuracy issues

## Version Information

Current Version: **12.4.0**

This guide is focused on current local testing rather than historical release notes.
