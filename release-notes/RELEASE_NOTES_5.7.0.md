# Release Notes - Version 5.7.0

**Release Date:** January 3, 2026

## 🎉 What's New

### Major Features

#### Reorganized "Next Steps" Section with Dialog Workflows
The post-analysis workflow has been completely redesigned for a more intuitive and streamlined experience.

**New "Next Steps" Section includes:**
- **📄 Generate Report**: Create comprehensive PDF reports through a clean dialog interface
  - Pop-up modal with optional name input
  - Personalized PDF generation on demand
  - Download with timestamped filename

- **🎲 Scenario Analysis** (renamed from Monte Carlo Simulation):
  - User-friendly dialog for configuring simulations
  - Configure number of scenarios (100-10,000)
  - Adjust market volatility (5-30%)
  - Seamless navigation to analysis page with pre-configured settings

- **📊 Cash Flow Projection** (Coming Soon):
  - Greyed-out button indicating future feature
  - Year-by-year income and expense visualization

**What Changed:**
- PDF report generation moved from Summary tab to Next Steps section
- "What Next?" section replaced with organized three-button layout
- Analysis results saved to session state for dialog access

### Landing Page Enhancement
- Added **"Scenario Analysis"** to key features section
- Highlights Monte Carlo simulation capability to new users
- Positioned alongside other core features (AI Upload, Tax Planning, What-If Scenarios)

---

## 🎨 UI/UX Improvements

### Streamlined Onboarding Experience

#### Personal Information Section Redesign
The onboarding Step 1 has been completely reorganized for better balance and clarity:

**Layout Improvements:**
- **Balanced two-column layout:**
  - Column 1: Birth Year, Target Retirement Age
  - Column 2: Life Expectancy, Annual Income Needed
- Removed "About This Application" expander to reduce clutter
- Improved visual hierarchy with better spacing

**Interactive Help System:**
- Replaced expandable help sections with **tooltip pop-ups**
- Life Expectancy field now has **(?)** icon with hover/click tooltip
- Annual Income field has **(?)** icon with retirement planning guidance
- Cleaner, more professional appearance using native Streamlit tooltips

**Simplified Data Collection:**
- **Removed** client name input from onboarding
- Client name now only collected when generating PDF report (when actually needed)
- Reduces friction in initial onboarding process
- Calculation explanation downloads use timestamp instead of client name

**Help Content Optimization:**
- Condensed guidance text with bullet points
- Key information preserved but more scannable
- Tooltips show on hover for instant access
- Less screen real estate consumed

---

## 🔧 Developer & Infrastructure

### Build & Release Workflow
- **PyPI upload made optional** in GitHub release workflow
- Workflow no longer fails if `PYPI_API_TOKEN` secret is not configured
- GitHub releases can be created independently of PyPI publishing
- Better flexibility for deployment scenarios

---

## 📊 Summary of Changes

### Files Modified
- `fin_advisor.py` - 8 commits with UI/UX improvements and feature additions
- `.github/workflows/release.yml` - Conditional PyPI upload

### Lines Changed
- **Total additions:** ~210 lines
- **Total deletions:** ~230 lines
- **Net change:** Cleaner, more maintainable code with improved UX

### Commits Since 5.6.0
1. `af21bf4` - Make PyPI upload optional in release workflow
2. `7c2a950` - Reorganize Next Steps section with dialog flows for v5.7.0
3. `6012106` - Add Scenario Analysis to landing page key features
4. `f08b6db` - Remove client name input from onboarding
5. `245caa6` - Improve Personal Information section layout balance
6. `a99f466` - Reorganize Personal Information section layout
7. `cc067a2` - Add inline help icons (?) next to field headers
8. `53732b8` - Replace expander dropdowns with tooltip pop-ups for field help

---

## 🚀 Upgrade Notes

This release is **fully backward compatible** with version 5.6.0. No breaking changes.

**What users will notice:**
- Cleaner, more intuitive onboarding flow
- New dialog-based workflow for generating reports and running scenarios
- Tooltip help icons instead of expandable sections
- "Scenario Analysis" listed on landing page

**Session state compatibility:**
- All existing session state keys preserved
- New keys added: `last_result`, `monte_carlo_config`
- Client name field optional (empty string default maintained)

---

## 🙏 Acknowledgments

This release focuses on user experience improvements based on iterative design refinements. Special attention was given to:
- Reducing cognitive load during onboarding
- Improving information hierarchy and visual balance
- Creating more professional, modern UI patterns
- Streamlining workflows with dialog-based interactions

---

## 📝 Version Information

- **Version:** 5.7.0
- **Previous Version:** 5.6.0
- **Release Type:** Minor (Feature + UI Enhancement)
- **Breaking Changes:** None
- **Migration Required:** No

---

For questions or issues, please contact [smartretireai@gmail.com](mailto:smartretireai@gmail.com) or report on [GitHub Issues](https://github.com/abhorkarpet/financialadvisor/issues).
