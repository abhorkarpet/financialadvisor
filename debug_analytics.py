"""
Debug script to test PostHog analytics integration.
Run this to verify PostHog is configured correctly.

Usage:
    streamlit run debug_analytics.py
"""

import streamlit as st
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

st.title("🔍 PostHog Analytics Debugger")
st.markdown("---")

# Check 1: PostHog package installed
st.subheader("1️⃣ PostHog Package")
try:
    import posthog
    st.success("✅ PostHog package is installed")
    st.code(f"PostHog version: {posthog.__version__ if hasattr(posthog, '__version__') else 'Unknown'}")
except ImportError as e:
    st.error("❌ PostHog package not installed")
    st.code(f"Error: {e}")
    st.info("Install with: pip install posthog>=3.1.0")
    st.stop()

st.markdown("---")

# Check 2: API Key Configuration
st.subheader("2️⃣ API Key Configuration")

# Check .env file
api_key_from_env = os.getenv("POSTHOG_API_KEY", "")
if api_key_from_env:
    st.success(f"✅ API key found in .env: {api_key_from_env[:8]}...{api_key_from_env[-4:]}")
else:
    st.error("❌ No API key found in .env file")
    st.info("Create a .env file in the project root with:\nPOSTHOG_API_KEY=your_key_here")

# Check Streamlit secrets
try:
    api_key_from_secrets = st.secrets.get("POSTHOG_API_KEY", "")
    if api_key_from_secrets:
        st.success(f"✅ API key found in Streamlit secrets: {api_key_from_secrets[:8]}...{api_key_from_secrets[-4:]}")
    else:
        st.info("ℹ️ No API key in Streamlit secrets (only needed for cloud deployment)")
except Exception as e:
    st.info("ℹ️ No Streamlit secrets found (expected for local development)")

# Determine which key is being used
POSTHOG_API_KEY = ""
try:
    POSTHOG_API_KEY = st.secrets.get("POSTHOG_API_KEY", "")
except Exception:
    POSTHOG_API_KEY = api_key_from_env

if not POSTHOG_API_KEY:
    st.error("❌ No API key available - PostHog will not work!")
    st.stop()
else:
    st.success(f"✅ Using API key: {POSTHOG_API_KEY[:8]}...{POSTHOG_API_KEY[-4:]}")

st.markdown("---")

# Check 3: PostHog Initialization
st.subheader("3️⃣ PostHog Initialization")

try:
    posthog.api_key = POSTHOG_API_KEY
    posthog.host = "https://us.i.posthog.com"
    st.success("✅ PostHog initialized successfully")
    st.code(f"Host: {posthog.host}")
except Exception as e:
    st.error(f"❌ Failed to initialize PostHog: {e}")
    st.stop()

st.markdown("---")

# Check 4: Test Event Sending
st.subheader("4️⃣ Test Event Sending")

if st.button("🚀 Send Test Event to PostHog"):
    try:
        test_user_id = f"debug_test_{os.urandom(4).hex()}"

        with st.spinner("Sending test event..."):
            posthog.capture(
                distinct_id=test_user_id,
                event='debug_test_event',
                properties={
                    'test': True,
                    'source': 'debug_analytics.py',
                    'message': 'Testing PostHog integration'
                }
            )

        st.success("✅ Test event sent successfully!")
        st.info(f"""
**Event Details:**
- Event: `debug_test_event`
- User ID: `{test_user_id}`
- Properties: test=True, source=debug_analytics.py

**Check PostHog Dashboard:**
1. Go to https://app.posthog.com
2. Navigate to Activity → Events
3. Look for event: `debug_test_event`
4. It may take 10-30 seconds to appear
        """)

    except Exception as e:
        st.error(f"❌ Failed to send event: {e}")
        st.code(str(e))

st.markdown("---")

# Check 5: Analytics Consent Flow
st.subheader("5️⃣ Analytics Consent Status")

if 'analytics_consent' not in st.session_state:
    st.warning("⚠️ No analytics consent recorded")
    st.info("In the main app, you need to accept analytics on the consent screen")
else:
    consent = st.session_state.get('analytics_consent', False)
    if consent:
        st.success(f"✅ Analytics consent: ENABLED")
    else:
        st.error(f"❌ Analytics consent: DISABLED")
        st.info("Events will NOT be tracked until you accept analytics in the consent screen")

if 'analytics_user_id' in st.session_state:
    st.info(f"Anonymous User ID: `{st.session_state.analytics_user_id}`")

st.markdown("---")

# Check 6: Common Issues
st.subheader("6️⃣ Common Issues & Solutions")

with st.expander("❓ Events sent but not showing in PostHog"):
    st.markdown("""
    **Possible causes:**

    1. **Wrong Project API Key**
       - Verify you're using the **Project API Key**, not Personal API Key
       - Find it in: PostHog → Settings → Project → Project API Key

    2. **Looking at wrong project**
       - Make sure you're viewing the correct project in PostHog dashboard

    3. **Events still processing**
       - Events can take 10-60 seconds to appear
       - Try refreshing the PostHog dashboard

    4. **API key typo**
       - Double-check your .env file has the correct key
       - No extra spaces or quotes
    """)

with st.expander("❓ Events not being sent (no consent)"):
    st.markdown("""
    **The app requires explicit consent before tracking:**

    1. Run the main app: `streamlit run fin_advisor.py`
    2. Dismiss the splash screen
    3. You should see the **Analytics Consent Screen**
    4. Click "✅ I Accept" to enable analytics
    5. Only then will events be tracked

    **To test consent:**
    - Clear your browser cache/session
    - Restart the app
    - Go through the consent flow
    """)

with st.expander("❓ PostHog package not installed"):
    st.markdown("""
    **Install PostHog:**

    ```bash
    pip install posthog>=3.1.0
    ```

    **Or install all requirements:**

    ```bash
    pip install -r requirements.txt
    ```
    """)

st.markdown("---")
st.caption("💡 If issues persist, check the PostHog Activity tab in your dashboard to see if events are being received at all.")
