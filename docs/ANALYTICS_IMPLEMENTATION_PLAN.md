# Analytics Implementation Plan - Smart Retire AI

## 📊 Goals

### 1. Completion Rate & Friction Analysis
- Onboarding completion rate (Step 1 → Step 2 → Results)
- Statement upload success/failure rates
- PDF generation completion
- Monte Carlo simulation usage
- Drop-off points identification

### 2. Diagnostics & Error Tracking
- Application errors and exceptions
- AI extraction failures
- PDF generation errors
- Browser/OS compatibility issues
- Performance bottlenecks

### 3. Privacy Requirements
- ✅ **Opt-in consent** (not opt-out)
- ✅ **First screen during onboarding**
- ✅ **Privacy policy link (pop-up)**
- ✅ **GDPR/CCPA compliant**
- ✅ **No PII tracking by default**

---

## 🔍 Analytics Platform Options

### Option 1: **PostHog** ⭐ RECOMMENDED

**What is it:** Open-source product analytics platform with session recording, funnels, and feature flags

**Pricing:**
- **Free Tier:** 1M events/month, unlimited users, 1 project
- **Paid:** $0.00031/event after free tier (~$300 for 1M additional events)
- **Self-hosted:** Free (requires infrastructure)

**Pros:**
- ✅ Generous free tier (1M events = ~33k daily active users)
- ✅ **Session recording** - Watch user sessions to see friction points
- ✅ **Funnels** - Track onboarding completion rates
- ✅ **User paths** - See where users drop off
- ✅ **Feature flags** - A/B test changes
- ✅ **Python SDK** - Native Streamlit integration
- ✅ **Privacy-focused** - Can be self-hosted, GDPR compliant
- ✅ **No cookies required** for basic tracking
- ✅ **Event autocapture** - Automatic click/pageview tracking
- ✅ **Dashboards** - Pre-built templates for funnels, retention

**Cons:**
- ⚠️ Requires backend SDK integration
- ⚠️ Cloud version stores data on their servers (EU/US options available)
- ⚠️ Learning curve for advanced features

**Implementation Effort:** 🟡 Medium (2-4 hours)

**Code Example:**
```python
import posthog

# Initialize (once per session)
posthog.api_key = 'your-api-key'
posthog.host = 'https://app.posthog.com'  # or self-hosted URL

# Track events
posthog.capture(
    distinct_id=st.session_state.get('user_id'),
    event='onboarding_step_completed',
    properties={
        'step': 1,
        'birth_year': birth_year,
        'has_retirement_goal': retirement_goal > 0
    }
)

# Identify user (if opted-in)
posthog.identify(
    distinct_id=st.session_state.get('user_id'),
    properties={
        'age_group': '30-40',
        'has_assets': len(assets) > 0
    }
)
```

**Best For:**
- Comprehensive product analytics
- Understanding user behavior
- Identifying friction points
- Session replay analysis

---

### Option 2: **Mixpanel**

**What is it:** Product analytics focused on event tracking and user journeys

**Pricing:**
- **Free Tier:** 20M events/year (~1.67M/month), unlimited users
- **Paid:** $28/month for Growth plan (unlimited events)

**Pros:**
- ✅ Good free tier
- ✅ Excellent funnel analysis
- ✅ User journey visualization
- ✅ Python SDK available
- ✅ Mobile app for monitoring
- ✅ Retention cohorts
- ✅ A/B testing capabilities

**Cons:**
- ⚠️ Free tier limited to 20M events/year
- ⚠️ Complex pricing for advanced features
- ⚠️ Data stored on Mixpanel servers (US/EU)
- ⚠️ Steeper learning curve

**Implementation Effort:** 🟡 Medium (2-3 hours)

**Best For:**
- Event-heavy applications
- Detailed user journey analysis
- Marketing analytics

---

### Option 3: **Google Analytics 4 (GA4)**

**What is it:** Google's web analytics platform

**Pricing:**
- **Free Tier:** Unlimited (with some limits on data freshness)
- **GA4 360:** $50k+/year (enterprise, not needed)

**Pros:**
- ✅ Completely free
- ✅ Industry standard
- ✅ Unlimited events and users
- ✅ BigQuery export (for advanced analysis)
- ✅ Integration with Google ecosystem
- ✅ Comprehensive documentation

**Cons:**
- ❌ **Requires JavaScript injection** in Streamlit (hacky)
- ❌ **Privacy concerns** - Google tracks across sites
- ❌ **Cookie consent required** for GDPR
- ❌ Complex setup for Streamlit apps
- ❌ Designed for websites, not web apps
- ❌ 24-48 hour data delay for some reports

**Implementation Effort:** 🔴 Hard (4-6 hours, hacky solutions)

**Code Example:**
```python
# Requires HTML/JavaScript injection
components.html(f"""
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', 'G-XXXXXXXXXX');
      gtag('event', 'onboarding_complete', {{
        'step': 2,
        'assets_count': {len(assets)}
      }});
    </script>
""", height=0)
```

**Best For:**
- Websites (not ideal for Streamlit apps)
- SEO/marketing analytics
- When you need Google ecosystem integration

---

### Option 4: **Amplitude**

**What is it:** Product analytics platform for user behavior analysis

**Pricing:**
- **Free Tier:** 10M events/month for up to 4 team members
- **Paid:** Starting at $49/month (growth plan)

**Pros:**
- ✅ Very generous free tier (10M events/month!)
- ✅ Excellent funnel analysis
- ✅ Cohort analysis
- ✅ User segmentation
- ✅ Python SDK available
- ✅ Real-time data

**Cons:**
- ⚠️ Free tier limited to 4 team members
- ⚠️ No session recording in free tier
- ⚠️ Learning curve for advanced features
- ⚠️ Data residency (US/EU options in paid tiers only)

**Implementation Effort:** 🟡 Medium (2-3 hours)

**Best For:**
- Teams needing high event volume
- Advanced cohort analysis
- Product-led growth strategies

---

### Option 5: **Custom Solution (Firebase/Supabase)**

**What is it:** Build your own analytics using Firebase Analytics or Supabase + custom tables

**Pricing:**
- **Firebase Free Tier:** 10GB storage, 50k writes/day
- **Supabase Free Tier:** 500MB database, 2GB bandwidth
- **Cost:** Free for most use cases

**Pros:**
- ✅ Full control over data
- ✅ No third-party tracking
- ✅ GDPR compliant (you control data)
- ✅ Can integrate with existing feedback system
- ✅ Cheap/free
- ✅ Custom queries and analysis

**Cons:**
- ❌ **Manual dashboard creation** - No built-in UI
- ❌ Requires more coding
- ❌ No session recording
- ❌ No automatic funnel visualization
- ❌ Maintenance overhead
- ❌ Limited analytics capabilities

**Implementation Effort:** 🔴 Hard (8-12 hours for full setup)

**Code Example:**
```python
import firebase_admin
from firebase_admin import firestore

# Track event
db = firestore.client()
db.collection('analytics_events').add({
    'event_type': 'onboarding_step_completed',
    'user_id': st.session_state.user_id,
    'step': 1,
    'timestamp': firestore.SERVER_TIMESTAMP,
    'properties': {
        'birth_year': birth_year,
        'has_goal': retirement_goal > 0
    }
})
```

**Best For:**
- Maximum privacy control
- Custom analytics needs
- When you want to own all data
- Integration with existing backend

---

### Option 6: **Plausible Analytics**

**What is it:** Privacy-focused, lightweight analytics (GDPR compliant)

**Pricing:**
- **Paid Only:** $9/month for 10k monthly visitors
- **Self-hosted:** Free (open source)

**Pros:**
- ✅ Privacy-focused (no cookies, GDPR compliant)
- ✅ Simple, lightweight
- ✅ Open source (can self-host)
- ✅ No cookie consent needed
- ✅ Real-time dashboard

**Cons:**
- ❌ **No free cloud tier** ($9/month minimum)
- ❌ Limited event tracking (focused on pageviews)
- ❌ No session recording
- ❌ Basic funnel support
- ❌ Requires JavaScript injection for Streamlit

**Implementation Effort:** 🟡 Medium (3-4 hours)

**Best For:**
- Privacy-conscious applications
- Simple pageview tracking
- When you want lightweight analytics

---

## 📊 Comparison Table

| Feature | PostHog | Mixpanel | GA4 | Amplitude | Custom | Plausible |
|---------|---------|----------|-----|-----------|--------|-----------|
| **Cost (Free Tier)** | 1M events/mo | 20M events/yr | Unlimited | 10M events/mo | Free* | None ($9/mo) |
| **Streamlit Integration** | ✅ Easy (SDK) | ✅ Easy (SDK) | ⚠️ Hacky (JS) | ✅ Easy (SDK) | ✅ Custom | ⚠️ Hacky (JS) |
| **Session Recording** | ✅ Yes | ❌ No (free) | ❌ No | ❌ No (free) | ❌ No | ❌ No |
| **Funnel Analysis** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ⚠️ Manual | ⚠️ Basic |
| **User Paths** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ⚠️ Manual | ❌ No |
| **Privacy Friendly** | ✅ Yes | ⚠️ Moderate | ❌ No | ⚠️ Moderate | ✅ Yes | ✅ Yes |
| **Self-Hostable** | ✅ Yes | ❌ No | ❌ No | ❌ No | ✅ Yes | ✅ Yes |
| **Real-time Data** | ✅ Yes | ✅ Yes | ⚠️ Delayed | ✅ Yes | ✅ Yes | ✅ Yes |
| **Setup Difficulty** | 🟡 Medium | 🟡 Medium | 🔴 Hard | 🟡 Medium | 🔴 Hard | 🟡 Medium |
| **Learning Curve** | 🟡 Medium | 🟢 Easy | 🔴 Hard | 🟡 Medium | 🔴 Hard | 🟢 Easy |

*Custom solution free tier depends on Firebase/Supabase usage

---

## 🎯 Recommendation: **PostHog** (Cloud)

### Why PostHog?

1. **Best Free Tier:** 1M events/month is generous for a growing app
2. **Session Recording:** See exactly where users get stuck
3. **Native Python SDK:** Clean integration with Streamlit
4. **Privacy-Focused:** Can be self-hosted, GDPR compliant
5. **Complete Feature Set:** Funnels, user paths, feature flags, A/B testing
6. **No JavaScript Hacks:** Works cleanly with Streamlit's architecture

### Cost Analysis (PostHog)

Assuming Smart Retire AI has:
- 1,000 daily active users
- Average 20 events per user session
- 30,000 events/day = 900,000 events/month

**Result:** Fits comfortably in free tier (1M events/month)

**If you exceed free tier:**
- Cost: $0.00031/event
- For 2M events/month: ~$310/month
- Can optimize by reducing event granularity

---

## 🔐 Privacy-First Implementation

### 1. Opt-In Consent (First Screen)

```python
if 'analytics_consent' not in st.session_state:
    st.session_state.analytics_consent = None

if st.session_state.analytics_consent is None:
    st.info("📊 **Help us improve Smart Retire AI**")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("""
        We'd like to collect anonymous usage data to:
        - Understand how people use the app
        - Identify and fix errors faster
        - Improve user experience

        **We never collect:**
        - Your financial data (balances, accounts, etc.)
        - Personal information (name, email, SSN, etc.)
        - Any data that can identify you
        """)

    with col2:
        if st.button("📄 Privacy Policy", use_container_width=True):
            show_privacy_policy_popup()

    consent_col1, consent_col2 = st.columns(2)
    with consent_col1:
        if st.button("✅ I Accept", type="primary", use_container_width=True):
            st.session_state.analytics_consent = True
            st.session_state.user_id = str(uuid.uuid4())
            st.rerun()

    with consent_col2:
        if st.button("❌ No Thanks", use_container_width=True):
            st.session_state.analytics_consent = False
            st.rerun()

    st.stop()  # Don't show rest of app until consent decided
```

### 2. Privacy Policy (Pop-up Dialog)

```python
@st.dialog("Privacy Policy")
def show_privacy_policy_popup():
    st.markdown("""
    ## Smart Retire AI Privacy Policy

    ### What We Collect (If You Opt-In)
    - **Anonymous usage events** (e.g., "user completed onboarding step 1")
    - **Error logs** (to fix bugs faster)
    - **Browser/OS information** (for compatibility)
    - **Session duration** (to understand engagement)

    ### What We NEVER Collect
    - ❌ Financial account balances or details
    - ❌ Personal information (name, email, SSN, address)
    - ❌ Uploaded PDF contents
    - ❌ Any personally identifiable information (PII)

    ### How We Use Data
    - ✅ Identify where users encounter problems
    - ✅ Improve app performance and reliability
    - ✅ Understand which features are most valuable

    ### Data Storage
    - Stored securely with PostHog (GDPR compliant)
    - Automatically deleted after 90 days
    - You can opt-out anytime in Settings

    ### Your Rights
    - You can opt-out at any time
    - You can request data deletion
    - Contact us: smartretireai@gmail.com

    **Last Updated:** January 2026
    """)

    if st.button("Close", use_container_width=True):
        st.rerun()
```

### 3. Anonymous User IDs

```python
# Generate anonymous ID (NOT tied to email or PII)
if 'user_id' not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())  # e.g., "a3e4b2c1-..."

# Use this for all analytics tracking
posthog.capture(
    distinct_id=st.session_state.user_id,
    event='event_name'
)
```

### 4. Data Anonymization

**Never track:**
- Account balances
- Account numbers
- Institution names (specific)
- Names, emails, addresses
- Birth year (exact) → Use age ranges instead
- Retirement goal (exact) → Use ranges instead

**Do track:**
- Event names (e.g., "onboarding_completed")
- Step numbers (e.g., "step 1 → step 2")
- Error types (e.g., "pdf_generation_failed")
- Asset count (e.g., "3 assets added")
- Age ranges (e.g., "30-40", "40-50")

---

## 📈 Key Metrics to Track

### Onboarding Funnel
1. **Consent Screen:**
   - `analytics_consent_shown`
   - `analytics_consent_accepted`
   - `analytics_consent_rejected`

2. **Step 1 (Personal Info):**
   - `onboarding_step1_started`
   - `onboarding_step1_completed`
   - Drop-off rate calculation

3. **Step 2 (Asset Config):**
   - `onboarding_step2_started`
   - `asset_added` (count assets)
   - `statement_upload_attempted`
   - `statement_upload_succeeded`
   - `statement_upload_failed` (with error type)
   - `onboarding_step2_completed`

4. **Results Page:**
   - `results_viewed`
   - `projection_calculated`

### Feature Usage
- `pdf_report_dialog_opened`
- `pdf_report_generated`
- `monte_carlo_dialog_opened`
- `monte_carlo_simulation_run` (with num_simulations, volatility)
- `whatif_parameter_changed` (which parameter)

### Errors & Diagnostics
- `error_occurred` (with error_type, error_message)
- `pdf_generation_failed`
- `ai_extraction_failed`
- `calculation_error`

### Session Metrics
- `session_started`
- `session_duration` (calculated)
- `page_visited` (onboarding, results, monte_carlo)

---

## 🛠️ Implementation Steps

### Phase 1: Setup (1-2 hours)
1. ✅ Create PostHog account (free)
2. ✅ Get API key
3. ✅ Install PostHog SDK: `pip install posthog`
4. ✅ Create privacy policy document
5. ✅ Design consent screen

### Phase 2: Consent Flow (2-3 hours)
1. ✅ Add consent screen before onboarding
2. ✅ Create privacy policy pop-up dialog
3. ✅ Store consent in session state
4. ✅ Generate anonymous user IDs
5. ✅ Add opt-out option in sidebar settings

### Phase 3: Event Tracking (3-4 hours)
1. ✅ Wrap PostHog in helper function
2. ✅ Add onboarding funnel events
3. ✅ Add feature usage events
4. ✅ Add error tracking
5. ✅ Test event flow

### Phase 4: Dashboards (1-2 hours)
1. ✅ Create PostHog funnel for onboarding
2. ✅ Create user path visualization
3. ✅ Set up error monitoring
4. ✅ Configure session recording (optional)

**Total Estimated Time:** 7-11 hours

---

## 💰 Cost Projection

### Year 1 (Assuming Growth)
| Month | DAU | Events/Day | Events/Month | Cost |
|-------|-----|------------|--------------|------|
| 1-3 | 100 | 2,000 | 60,000 | $0 (free tier) |
| 4-6 | 500 | 10,000 | 300,000 | $0 (free tier) |
| 7-9 | 1,000 | 20,000 | 600,000 | $0 (free tier) |
| 10-12 | 2,000 | 40,000 | 1,200,000 | ~$62/mo* |

*Only pays for 200k events above free tier: 200,000 × $0.00031 = $62

**Year 1 Total Cost:** ~$186 (last 3 months only)

### Alternative: Optimize Event Volume
- Reduce tracking granularity
- Sample 50% of users
- Remove low-value events
- **Stay in free tier even at 2,000 DAU**

---

## 🎨 Alternative: Start Simple

If you want to start even simpler before committing to PostHog:

### **Lightweight Option: Custom Events to Supabase**
- Use Supabase (free tier)
- Log basic events to a table
- Build simple dashboard with SQL queries
- Upgrade to PostHog later when you need advanced features

**Pros:**
- Nearly zero cost
- Full data control
- Easy to migrate to PostHog later

**Cons:**
- No fancy dashboards
- Manual analysis required
- No session recording

---

## 🚀 Next Steps

### Immediate Actions:
1. **Decide on platform:** PostHog recommended, but review options
2. **Create privacy policy:** Based on template above
3. **Design consent screen:** User-friendly, clear opt-in
4. **Define key events:** What do you want to track?

### Questions to Answer:
1. Are you comfortable with cloud-hosted analytics (PostHog/Mixpanel) or need self-hosted?
2. Is session recording important for debugging user issues?
3. What's your estimated user growth for next 12 months?
4. Do you want A/B testing capabilities (feature flags)?

---

## 📝 Summary

**Recommended:** PostHog (Cloud)
- **Cost:** Free up to 1M events/month
- **Effort:** 7-11 hours to implement
- **Features:** Funnels, user paths, session recording, feature flags
- **Privacy:** GDPR compliant, can self-host
- **Integration:** Clean Python SDK for Streamlit

**Alternative:** Custom Supabase solution if you want maximum control and don't need advanced analytics dashboards.

**Avoid:** Google Analytics (too hacky for Streamlit, privacy concerns)

Would you like me to proceed with PostHog implementation, or would you prefer to discuss other options first?
