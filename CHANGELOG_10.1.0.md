# Version 10.1.0 — March 2026

## 🐛 Bug Fixes

### Brokerage Account Tax Calculation
- **Fixed overstated capital gains for brokerage accounts**: The cost basis was previously calculated as contributions only, omitting the account's initial balance. This caused capital gains — and therefore taxes — to be overstated for any brokerage account that had an existing balance at the time of analysis.
- Cost basis is now correctly computed as `initial balance + total contributions`, resulting in more accurate after-tax projections.
- Removed the outdated disclaimer warnings about brokerage taxation that were shown in the PDF report and asset breakdown table, as the underlying limitation has been resolved.

---

## ✨ New Features

### RMD Explanation in Retirement Income Expander
- The "📊 How Is Retirement Income Calculated?" expander now includes a collapsible **"ℹ️ What is a Required Minimum Distribution (RMD)?"** section.
- Provides a plain-English summary of what RMDs are, key facts (age 73 trigger, 25% penalty for missed RMDs, Roth exemption), and a direct link to the official IRS page for further reading.
- First mention in the numbered simulation steps now reads the full term **"Required Minimum Distributions (RMDs)"** for clarity.

### Home Button in Sidebar
- A **"🏠 Results Dashboard"** button now appears in the sidebar whenever the user is on the Detailed Analysis or Monte Carlo pages.
- Provides a persistent, one-click shortcut back to the Results page without requiring users to scroll to the top of the page to find the "← Back to Results" button.

---

## 🎨 UI/UX Improvements

### Cash Flow Table Number Formatting
- Dollar amounts in the year-by-year withdrawal table (inside the retirement income expander and the What-If cash flow dialog) now display with comma thousands separators.
- Example: `$1,234,567` instead of `$1234567`.
- Zero-value cells continue to display as blank (no dash or zero) for cleaner readability.

### Asset Type Labels in Manual Configuration
- The asset type dropdown in the "Configure Individual Assets" setup now shows human-readable tax treatment labels instead of raw enum values.
  - `Pre-Tax` (was: `pre_tax`)
  - `After-Tax` (was: `post_tax`)
  - `Tax-Deferred` (was: `tax_deferred`)
- Format changed from `"401(k) / Traditional IRA (pre_tax)"` to `"401(k) / Traditional IRA — Pre-Tax"`.

### Asset Setup Form State Persistence
- Returning to the Asset Configuration step (Step 2) via the "← Previous" button now correctly restores:
  - The previously selected configuration method (the radio button stays on "Configure Individual Assets" if that was the last used mode).
  - The number of assets the user had entered (no longer resets to 3 on navigation).
- Previously, both the radio selection and the asset count would reset to defaults on every back-navigation.

---

## 🔧 Technical

- `_ASSET_TYPE_LABELS` dict moved out of the per-asset render loop to a single allocation per form render.
- `st.popover` (requires Streamlit ≥1.31) replaced with `st.expander` for the RMD explanation, ensuring compatibility with Streamlit ≥1.28 as specified in `requirements.txt`.
- `st.radio` and `st.number_input` for asset setup now use stable session-state keys (`setup_method_radio`, `num_assets_manual`) to survive page reruns and step navigation.
