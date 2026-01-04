# Smart Retire AI - Release Notes v6.0.0

**Release Date:** January 4, 2026
**Release Type:** Major Feature Release

---

## 🎉 What's New in v6.0.0

### 📊 PostHog Analytics Integration (Privacy-First)

This release introduces comprehensive analytics tracking to help us understand how users interact with Smart Retire AI, identify issues, and continuously improve the experience - all while respecting your privacy.

#### Key Features

**✅ Privacy-First Design**
- **Opt-in consent required** - No tracking before explicit user acceptance
- **Anonymous user IDs** - Random UUIDs not tied to personal information
- **Privacy-safe data** - Ages and retirement goals converted to ranges (e.g., "30-40", "$50k-$75k")
- **No financial data collection** - Account balances, numbers, and statements never tracked
- **GDPR & CCPA compliant** - Full regulatory compliance with user rights protected

**📈 Comprehensive Event Tracking**

The app now tracks 20+ events to understand user journeys:

*Onboarding & Consent:*
- Analytics consent acceptance/rejection
- Onboarding step progression (started/completed)
- Asset configuration method selection
- Onboarding completion

*Feature Usage:*
- PDF report generation (success/failure)
- Monte Carlo simulation runs (with parameters)
- AI statement uploads (with file/account counts)
- What-If scenario resets
- Page navigation (Results, Monte Carlo)

*Errors & Diagnostics:*
- PDF generation errors
- Statement upload failures
- Monte Carlo simulation errors
- General error tracking with context

**🎯 Session Analytics**

Every event includes session metadata:
- `$session_id` - Groups events into user sessions
- `$session_start_timestamp` - Session start time
- Enables session duration analysis
- Tracks events per session
- Powers session-based conversion funnels

**🌐 Enhanced Page Tracking**

Page views now include:
- `$current_url` - Readable page URLs (e.g., "streamlit://smart-retire-ai/results")
- `$pathname` - Path component (e.g., "/monte_carlo")
- `$screen_name` - Human-readable names (e.g., "Monte Carlo")

**🔒 User Privacy Controls**

- **In-app privacy policy** - Comprehensive GDPR-compliant policy accessible via dialog
- **Analytics consent screen** - First screen after splash, before any tracking
- **Opt-out controls** - Advanced Settings → Analytics & Privacy
- **Session reset** - Clear all analytics state and start fresh
- **Transparent data collection** - Clear explanation of what is/isn't collected

---

## 🛠️ Technical Changes

### New Dependencies
- **posthog>=3.1.0** - PostHog analytics Python SDK

### New Files
- `financialadvisor/utils/analytics.py` - Analytics module (450+ lines)
  - Event tracking functions
  - Privacy helper functions (age/goal ranges)
  - Session management
  - Consent management
- `financialadvisor/utils/__init__.py` - Utils package initialization
- `debug_analytics.py` - PostHog configuration debugger and tester
- `POSTHOG_LIMITATIONS.md` - Documentation of Streamlit limitations
- `RELEASE_NOTES_v6.0.0.md` - This file

### Modified Files
- `fin_advisor.py` - Analytics integration throughout application
  - Analytics module imports with graceful degradation
  - Consent screen implementation
  - Event tracking in onboarding flow
  - Feature usage tracking (PDF, Monte Carlo, What-If)
  - Error tracking with context
  - Privacy policy dialog
  - Opt-out/opt-in controls in Advanced Settings
- `requirements.txt` - Added PostHog dependency

### New Analytics Functions

**Core Tracking:**
- `track_event(name, properties, user_properties)` - Generic event tracking
- `track_page_view(page_name)` - Page navigation tracking
- `track_error(type, message, context)` - Error diagnostics

**Feature-Specific:**
- `track_onboarding_step_started(step)` - Onboarding progress
- `track_onboarding_step_completed(step, **kwargs)` - Step completion with metadata
- `track_pdf_generation(success)` - PDF feature usage
- `track_monte_carlo_run(num_simulations, volatility)` - Simulation tracking
- `track_statement_upload(success, num_statements, num_accounts)` - Upload tracking
- `track_feature_usage(feature_name)` - Generic feature tracking

**Consent & Session Management:**
- `initialize_analytics()` - Initialize on app startup
- `set_analytics_consent(consented)` - Set user consent
- `is_analytics_enabled()` - Check consent status
- `opt_out()` / `opt_in()` - Toggle analytics
- `reset_analytics_session()` - Clear session state
- `get_or_create_user_id()` - Anonymous user ID
- `get_or_create_session_id()` - Session ID

**Privacy Helpers:**
- `get_age_range(age)` - Convert exact age to range
- `get_goal_range(amount)` - Convert exact goal to range
- `get_session_properties()` - Session metadata

### Debug & Development Tools

**Debug Mode:**
Add to `.env` to enable console logging:
```bash
ANALYTICS_DEBUG=true
```

Console output shows:
- PostHog initialization status
- Event tracking confirmations
- User ID and Session ID
- Event properties being sent

**Debug Script:**
```bash
streamlit run debug_analytics.py
```

Tests and validates:
- PostHog package installation
- API key configuration
- PostHog initialization
- Test event sending
- Consent status

---

## 📊 Analytics Dashboard (PostHog)

### What You Can Track

After users opt-in, you'll have access to:

**User Acquisition:**
- New vs returning users
- User growth over time
- Anonymous user cohorts

**Onboarding Funnel:**
- % who accept analytics
- Step 1 completion rate
- Step 2 completion rate (by config method)
- Overall onboarding completion rate
- Drop-off analysis

**Feature Adoption:**
- PDF generation usage
- Monte Carlo simulation runs (with parameters)
- AI statement upload adoption
- What-If scenario usage

**Session Analytics:**
- Average session duration
- Events per session
- Pages visited per session
- Session-based conversion funnels

**User Journeys:**
- Common paths through the app
- Navigation patterns
- Feature usage sequences

**Error Tracking:**
- PDF generation failure rates
- Statement upload error types
- Monte Carlo simulation errors
- Error frequency and patterns

### PostHog Cost Analysis

**Free Tier:** 1 million events/month

**At 1,000 Daily Active Users:**
- 1,000 users × 20 events/session = 600,000 events/month
- **60% of free tier** - Completely FREE
- Can scale to 1,667 DAU before reaching paid tier

**At 2,000 DAU:** $62/month (beyond free tier)

---

## 🚀 Installation & Upgrade

### For Local Development

1. **Pull the latest changes:**
   ```bash
   git pull origin main
   ```

2. **Install new dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   This installs `posthog>=3.1.0`

3. **Configure PostHog API key:**

   Create/update `.env` file in project root:
   ```bash
   POSTHOG_API_KEY=phc_your_project_api_key_here
   ANALYTICS_DEBUG=true  # Optional: for debugging
   ```

4. **Get your PostHog API key:**
   - Sign up at https://app.posthog.com (free tier)
   - Create a project for "Smart Retire AI"
   - Go to Settings → Project
   - Copy **Project API Key** (starts with `phc_`)
   - **DO NOT** use Personal API Key

5. **Test the configuration:**
   ```bash
   streamlit run debug_analytics.py
   ```

   - Verify API key is loaded
   - Send test event
   - Check PostHog dashboard

6. **Run the app:**
   ```bash
   streamlit run fin_advisor.py
   ```

### For Streamlit Cloud Deployment

1. **Go to your Streamlit Cloud app settings**

2. **Navigate to:** Secrets section

3. **Add PostHog API key:**
   ```toml
   POSTHOG_API_KEY = "phc_your_project_api_key_here"
   ```

4. **Save and redeploy**

### Important: .env File Security

**The `.env` file is already in `.gitignore`** - DO NOT commit it!

Your API key should remain:
- ✅ Local only (in `.env`)
- ✅ In Streamlit Cloud secrets
- ❌ Never committed to Git
- ❌ Never shared publicly

---

## 🎯 User Experience Changes

### First-Time User Flow

1. **Splash Screen**
   - Updated button: "✅ Continue" (was "Don't show this again")
   - Optional: "📄 View Privacy Policy"

2. **Analytics Consent Screen** *(NEW)*
   - Shows after splash, before onboarding
   - Clear explanation of data collection
   - Two options:
     - "✅ I Accept" → Analytics enabled
     - "❌ No Thanks" → Analytics disabled
   - Link to full privacy policy
   - Required decision before proceeding

3. **Onboarding**
   - Proceeds as normal
   - If analytics accepted, events are tracked

### Returning User Flow

- No consent screen shown (decision remembered)
- Can change preference in Advanced Settings

### Advanced Settings (Sidebar)

New section: **📊 Analytics & Privacy**

- **Status display:**
  - ✅ Analytics Enabled, or
  - ℹ️ Analytics Disabled

- **Controls:**
  - "📄 View Privacy Policy" - Access full policy
  - "❌ Disable Analytics" - Opt-out
  - "✅ Enable Analytics" - Opt-in

- **Advanced section:**
  - "🔄 Reset Analytics Session" - Clear state for testing

---

## 🔒 Privacy & Compliance

### What We NEVER Collect

- ❌ Financial account information (balances, numbers)
- ❌ Personally identifiable information (names, emails, addresses)
- ❌ Social Security Numbers or tax IDs
- ❌ Uploaded PDF file contents
- ❌ Exact ages or retirement goals (we use ranges)
- ❌ Any data without explicit consent

### What We Collect (With Consent)

- ✅ Anonymous usage events (e.g., "user completed step 1")
- ✅ Anonymous user ID (random UUID)
- ✅ Session analytics (duration, events per session)
- ✅ Feature usage (which features are used)
- ✅ Error logs (for debugging)
- ✅ Browser/device info (for compatibility)
- ✅ Age ranges (e.g., "30-40", not exact age)
- ✅ Goal ranges (e.g., "$50k-$75k", not exact amount)

### Privacy Safeguards

**Age Privacy:**
```python
# Instead of: age=35
# We send: age_range="30-40"
```

**Retirement Goal Privacy:**
```python
# Instead of: goal=$62,500
# We send: goal_range="$50k-$75k"
```

**Anonymous User IDs:**
```python
# Random UUID, not tied to any PII
user_id = "6a47cc51-0de4-451e-97e3-2297cf10d756"
```

### Compliance

- ✅ **GDPR Compliant**
  - Opt-in consent required
  - Data minimization
  - User rights (access, delete, export)
  - Clear privacy policy

- ✅ **CCPA Compliant**
  - Opt-out available
  - No sale of personal data
  - Data disclosure transparency

- ✅ **SOC 2** - PostHog is SOC 2 Type II certified

### Data Retention

- Analytics data automatically deleted after **90 days** (PostHog default)
- Can be configured in PostHog settings

---

## ⚠️ Known Limitations

### Session Replay - Not Available

**What doesn't work:**
- ❌ Video-like session replay (browser playback)
- ❌ Mouse movement tracking
- ❌ Click heatmaps
- ❌ Visual DOM inspection

**Why:**
Session replay requires PostHog's JavaScript SDK running in the browser. Streamlit is a server-side Python application where the browser only receives rendered HTML, making JavaScript-based replay impossible.

**Alternative:**
Session analytics (duration, events, funnels) work perfectly and provide comprehensive insights into user behavior.

### Autocapture - Limited

**What doesn't work:**
- ❌ Automatic click tracking
- ❌ Automatic form submission tracking

**Why:**
Autocapture requires JavaScript DOM event listeners.

**Alternative:**
We manually track all important interactions via `track_event()` calls throughout the app.

**See:** `POSTHOG_LIMITATIONS.md` for full technical details.

---

## 🧪 Testing Instructions

### Test Analytics Configuration

1. **Run the debug script:**
   ```bash
   streamlit run debug_analytics.py
   ```

2. **Verify each check:**
   - ✅ PostHog package installed
   - ✅ API key found
   - ✅ PostHog initialized
   - ✅ Test event sent successfully

3. **Check PostHog dashboard:**
   - Go to https://app.posthog.com
   - Navigate to Activity → Events
   - Look for `debug_test_event`
   - Should appear within 10-60 seconds

### Test Full Analytics Flow

1. **Reset analytics session:**
   - Advanced Settings → Analytics & Privacy
   - Expand "🔧 Advanced: Reset Analytics Session"
   - Click "Reset Analytics Session"

2. **Run the app:**
   ```bash
   streamlit run fin_advisor.py
   ```

3. **Complete user flow:**
   - Splash screen → "✅ Continue"
   - Consent screen → "✅ I Accept"
   - Step 1 → Fill in personal info → "Next"
   - Step 2 → Add assets → "Complete Setup"
   - Results page → Generate PDF
   - Results page → Run Monte Carlo simulation

4. **Check PostHog dashboard:**
   - Activity → Events
   - Should see events:
     - `analytics_consent_accepted`
     - `onboarding_step_1_started`
     - `onboarding_step_1_completed`
     - `onboarding_step_2_started`
     - `asset_config_method_selected`
     - `onboarding_step_2_completed`
     - `onboarding_completed`
     - `page_viewed` (results)
     - `pdf_generation_success`
     - `monte_carlo_simulation_run`

5. **Verify session analytics:**
   - Click any event
   - Look for `$session_id` property
   - All events should have the same session ID
   - Verify `$session_start_timestamp` is present

### Test Privacy Controls

1. **Test opt-out:**
   - Advanced Settings → Analytics & Privacy
   - Click "❌ Disable Analytics"
   - Perform actions (e.g., generate PDF)
   - Check PostHog → No new events should appear

2. **Test opt-in:**
   - Advanced Settings → Analytics & Privacy
   - Click "✅ Enable Analytics"
   - Perform actions
   - Check PostHog → Events should appear

3. **Test privacy policy:**
   - Click "📄 View Privacy Policy"
   - Verify dialog opens with full policy
   - Verify "Close" button works

---

## 📚 Documentation

### New Documentation Files

- **`POSTHOG_LIMITATIONS.md`** - Technical details on what works/doesn't in Streamlit
  - Session replay limitations
  - Autocapture limitations
  - Alternative approaches
  - Example PostHog queries

- **`RELEASE_NOTES_v6.0.0.md`** - This file
  - Complete changelog
  - Installation instructions
  - Testing procedures

### Updated Documentation

- Privacy policy accessible in-app via dialog
- Advanced Settings section updated

### Code Documentation

- Extensive inline comments in `analytics.py`
- Docstrings for all analytics functions
- Type hints throughout

---

## 🐛 Bug Fixes

### Fixed in This Release

- **Undefined name error** - Moved `show_privacy_policy()` function before first use
- **Asset attribute access** - Fixed `asset.get()` to `asset.current_balance` for dataclass
- **Session analytics** - Added `$session_id` and `$session_start_timestamp` to all events
- **Page tracking** - Added PostHog special properties for URL/SCREEN column population

---

## 🔄 Breaking Changes

### None

This release is fully backward compatible. The app works identically for users who:
- Decline analytics consent
- Don't have PostHog configured (graceful degradation to no-op functions)

---

## 🎯 Metrics & Analytics Queries

### Example PostHog Queries

**Onboarding Funnel:**
```
1. analytics_consent_accepted
2. onboarding_step_1_completed
3. onboarding_step_2_completed
4. onboarding_completed

→ Shows drop-off at each step
```

**Session Duration:**
```
Events: Any event
Group by: $session_id
Calculate: Time between first and last event
```

**Feature Adoption:**
```
Events: pdf_generation_success, monte_carlo_simulation_run
Breakdown: By event type
Date range: Last 30 days
```

**Error Rates:**
```
Events: error_occurred, pdf_generation_failed, statement_upload_failed
Properties: error_type
Chart: Count over time
```

**Asset Configuration Methods:**
```
Event: asset_config_method_selected
Breakdown: By properties.method
Chart: Pie chart
```

---

## 🚦 Migration Guide

### From v5.x to v6.0.0

**Step 1: Update code**
```bash
git pull origin main
```

**Step 2: Install dependencies**
```bash
pip install -r requirements.txt
```

**Step 3: Configure PostHog** (optional)

If you want analytics:
```bash
# Add to .env
POSTHOG_API_KEY=phc_your_key
```

If you don't want analytics:
- No configuration needed
- App works exactly as before
- Users won't see consent screen

**Step 4: Test**
```bash
streamlit run fin_advisor.py
```

### Configuration Changes

**New environment variables:**
- `POSTHOG_API_KEY` - PostHog project API key (optional)
- `ANALYTICS_DEBUG` - Enable debug logging (optional)

**No changes to existing variables:**
- `N8N_WEBHOOK_URL` - Unchanged
- All other configs - Unchanged

---

## 🎓 Learning Resources

### PostHog Documentation
- Main docs: https://posthog.com/docs
- Python SDK: https://posthog.com/docs/libraries/python
- Event tracking: https://posthog.com/docs/product-analytics/capture-events
- Insights: https://posthog.com/docs/product-analytics/insights

### Privacy Resources
- GDPR guide: https://gdpr.eu/
- CCPA guide: https://oag.ca.gov/privacy/ccpa
- PostHog privacy: https://posthog.com/privacy

---

## 🙏 Credits

### Third-Party Services

- **PostHog** - https://posthog.com
  - Analytics platform
  - GDPR & SOC 2 compliant
  - Privacy policy: https://posthog.com/privacy

- **Streamlit** - https://streamlit.io
  - App framework
  - Privacy policy: https://streamlit.io/privacy-policy

---

## 📞 Support

### Questions or Issues?

**Email:** smartretireai@gmail.com
**Response Time:** 24-48 hours
**Privacy Requests:** Include "Privacy Request" in subject

### GitHub Issues

Report bugs or request features:
https://github.com/abhorkarpet/financialadvisor/issues

---

## 🔮 Future Enhancements

### Planned for Future Releases

- **Feature flags** - A/B testing capabilities
- **Cohort analysis** - User segmentation
- **Custom dashboards** - Pre-built analytics views
- **Alert notifications** - Error spike detection
- **Retention analysis** - User return rates
- **Advanced funnels** - Multi-step conversion tracking

---

## ✅ Release Checklist

- [x] PostHog integration complete
- [x] Privacy policy implemented
- [x] Consent screen functional
- [x] Event tracking (20+ events)
- [x] Session analytics working
- [x] Error tracking implemented
- [x] Opt-out controls added
- [x] Debug tools created
- [x] Documentation written
- [x] No PII collection verified
- [x] Graceful degradation tested
- [x] Linting errors fixed
- [x] All tests passing
- [x] Release notes created

---

**Smart Retire AI v6.0.0** - Empowering better retirement planning through data-driven insights, while respecting your privacy. 🚀

*Released: January 4, 2026*
