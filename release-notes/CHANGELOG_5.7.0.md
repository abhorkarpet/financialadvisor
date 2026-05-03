# Version 5.7.0 - January 3, 2026

## 🎉 New Features

### Next Steps Dialog Workflows
- **Generate Report Dialog**: Create PDF reports through a clean pop-up interface with optional name input
- **Scenario Analysis Dialog**: Configure Monte Carlo simulations (renamed for clarity) with an intuitive modal
- **Cash Flow Projection**: Added as "Coming Soon" feature (greyed-out button)
- Reorganized post-analysis workflow with three clear action buttons

### Landing Page
- Added "Scenario Analysis" to key features section

## 🎨 UI/UX Improvements

### Onboarding Redesign
- **Balanced layout**: Two-column Personal Information section (Birth Year + Retirement Age | Life Expectancy + Annual Income)
- **Tooltip help**: Replaced expander dropdowns with native (?) tooltip pop-ups for cleaner interface
- **Simplified flow**: Removed client name from onboarding (now collected only when generating PDF)
- **Removed clutter**: Eliminated "About This Application" expander

### Help System
- Life Expectancy and Annual Income fields now have hover/click tooltips
- Condensed guidance with bullet points for better readability
- Professional appearance using native Streamlit components

## 🔧 Technical

- Made PyPI upload optional in GitHub release workflow
- Session state enhancements for dialog data passing
- Code cleanup: -230 lines, +210 lines (net cleaner codebase)

## 📦 Upgrade

- ✅ Fully backward compatible with 5.6.0
- ✅ No breaking changes
- ✅ No migration required

---

**Full Release Notes:** See RELEASE_NOTES_5.7.0.md
