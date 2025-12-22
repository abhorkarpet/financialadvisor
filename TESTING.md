# Testing Financial Advisor Locally

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
- Enter annual income
- Set retirement income goal
- (Optional) Enter your name for PDF reports
- Click **"Next: Asset Configuration →"**

**Step 2: Asset Configuration**
- **Set Default Growth Rate** - Configure the default annual growth rate for investment accounts (slider: 0-20%)
  - Typical rates: Stocks 7-10%, Bonds 4-5%, Savings 2-4%
  - This rate auto-populates when adding accounts
- Choose one of the 3 setup methods:
  - **Upload Financial Statements (AI)** - Upload PDF statements for AI extraction (requires n8n integration)
  - **Upload CSV File** - Download template, fill it out, and upload
  - **Configure Individual Assets** - Manually add each account one by one
- Click **"Complete Onboarding ✓"**

**View Results**
- After completing onboarding, scroll down to see:
  - Key metrics
  - Portfolio breakdown
  - Tax analysis
  - Summary charts
  - PDF download option

### 4. Adjust Settings (Sidebar)

At any time, you can adjust:
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
python fin_advisor.py --run-tests
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

✅ **Settings (Sidebar)**
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

## Version Information

Current Version: **3.1.0**

### What's New in 3.1.0
**Onboarding Improvements:**
- Reorganized flow into 2 clear sequential steps
- Moved tax settings and inflation rate to sidebar for easy access
- Added progress indicator showing current step
- Implemented step navigation (Next/Previous/Complete buttons)
- Session state persistence across steps
- Results shown only after onboarding completion
- Added reset onboarding functionality

**Asset Configuration Simplification:**
- Removed confusing "Default Portfolio" option
- Removed confusing "Legacy Mode (Simple)" option
- Added user-configurable default growth rate (0-20%)
- Default growth rate auto-populates across all setup methods
- Only 3 clear setup options remain:
  1. Upload Financial Statements (AI)
  2. Upload CSV File
  3. Configure Individual Assets
- Consistent growth rate defaults across all methods
