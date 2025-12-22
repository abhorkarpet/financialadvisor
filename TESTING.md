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
- Choose one of the setup methods:
  - **Use Default Portfolio** - Quick start with 4 pre-configured accounts
  - **Upload Financial Statements (AI)** - Upload PDF statements (requires n8n integration)
  - **Upload CSV File** - Upload a CSV with your accounts
  - **Configure Individual Assets** - Manually add each account
  - **Legacy Mode (Simple)** - Single blended calculation
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

✅ **Asset Configuration Methods**
- [ ] Default Portfolio loads 4 accounts
- [ ] CSV upload accepts template format
- [ ] Manual asset configuration works
- [ ] Editable tables update correctly

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
- Reorganized onboarding flow into 2 sequential steps
- Moved tax and growth settings to sidebar
- Added progress indicator
- Implemented step navigation
- Session state persistence across steps
- Results shown only after onboarding completion
- Added reset onboarding functionality
