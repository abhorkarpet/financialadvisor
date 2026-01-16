"""
Analytics tracking module using PostHog.

This module provides privacy-first analytics tracking with:
- Opt-in consent requirement
- Anonymous user IDs
- No PII collection
- Session recording (optional)
- Error tracking
"""

import streamlit as st
from typing import Dict, Any, Optional
import uuid
import os

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not required, can use system env vars

# Only import PostHog if user has consented
try:
    import posthog
    POSTHOG_AVAILABLE = True
except ImportError:
    POSTHOG_AVAILABLE = False


# ==========================================
# CONFIGURATION
# ==========================================

# PostHog API key - try Streamlit secrets first, then fall back to .env
POSTHOG_API_KEY = ""
try:
    # Try Streamlit secrets first (for cloud deployment)
    POSTHOG_API_KEY = st.secrets.get("POSTHOG_API_KEY", "")
except Exception:
    # Fall back to environment variable (for local development with .env)
    POSTHOG_API_KEY = os.getenv("POSTHOG_API_KEY", "")

POSTHOG_HOST = "https://us.i.posthog.com"  # or self-hosted URL

# Debug mode (set ANALYTICS_DEBUG=true in .env to enable logging)
DEBUG_MODE = os.getenv("ANALYTICS_DEBUG", "").lower() in ("true", "1", "yes")

# Initialize PostHog once
if POSTHOG_AVAILABLE and POSTHOG_API_KEY:
    posthog.api_key = POSTHOG_API_KEY
    posthog.host = POSTHOG_HOST
    if DEBUG_MODE:
        print(f"[Analytics] PostHog initialized with API key: {POSTHOG_API_KEY[:8]}...{POSTHOG_API_KEY[-4:]}")
        print(f"[Analytics] Host: {POSTHOG_HOST}")
else:
    POSTHOG_AVAILABLE = False
    if DEBUG_MODE:
        if not POSTHOG_API_KEY:
            print("[Analytics] WARNING: No PostHog API key found")
        if not POSTHOG_AVAILABLE:
            print("[Analytics] WARNING: PostHog package not available")


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def get_or_create_user_id() -> str:
    """
    Get or create anonymous user ID.

    Returns:
        Anonymous UUID string (not tied to PII)
    """
    if 'analytics_user_id' not in st.session_state:
        st.session_state.analytics_user_id = str(uuid.uuid4())
    return st.session_state.analytics_user_id


def get_or_create_session_id() -> str:
    """
    Get or create session ID for session analytics.

    Session ID persists for the lifetime of the Streamlit session.

    Returns:
        Session UUID string
    """
    if 'analytics_session_id' not in st.session_state:
        import time
        st.session_state.analytics_session_id = str(uuid.uuid4())
        st.session_state.analytics_session_start_time = int(time.time() * 1000)  # milliseconds
    return st.session_state.analytics_session_id


def get_session_properties() -> Dict[str, Any]:
    """
    Get session properties to attach to all events.

    Returns:
        Dict with session ID and timestamp
    """
    session_id = get_or_create_session_id()
    start_time = st.session_state.get('analytics_session_start_time', 0)

    return {
        '$session_id': session_id,
        '$session_start_timestamp': start_time
    }


def is_analytics_enabled() -> bool:
    """
    Check if user has opted-in to analytics.

    Returns:
        True if analytics consent is True, False otherwise
    """
    return st.session_state.get('analytics_consent', False) == True


def track_event(
    event_name: str,
    properties: Optional[Dict[str, Any]] = None,
    user_properties: Optional[Dict[str, Any]] = None
) -> None:
    """
    Track an analytics event (respects user consent).

    Args:
        event_name: Name of the event (e.g., "onboarding_step_1_completed")
        properties: Event-specific properties (e.g., {'step': 1})
        user_properties: User-level properties (e.g., {'age_range': '30-40'})

    Example:
        track_event('onboarding_step_1_completed', {'assets_count': 3})
    """
    # Only track if user has consented and PostHog is available
    if not is_analytics_enabled():
        if DEBUG_MODE:
            print(f"[Analytics] Event '{event_name}' NOT tracked - consent not given")
        return

    if not POSTHOG_AVAILABLE:
        if DEBUG_MODE:
            print(f"[Analytics] Event '{event_name}' NOT tracked - PostHog not available")
        return

    try:
        user_id = get_or_create_user_id()
        session_props = get_session_properties()

        # Merge session properties with event properties
        event_properties = {**(properties or {}), **session_props}

        if DEBUG_MODE:
            print(f"[Analytics] Tracking event: {event_name}")
            print(f"[Analytics]   User ID: {user_id}")
            print(f"[Analytics]   Session ID: {session_props['$session_id']}")
            print(f"[Analytics]   Properties: {event_properties}")

        # Capture event
        posthog.capture(
            distinct_id=user_id,
            event=event_name,
            properties=event_properties
        )

        # Update user properties if provided
        if user_properties:
            posthog.identify(
                distinct_id=user_id,
                properties=user_properties
            )

        if DEBUG_MODE:
            print(f"[Analytics] ✓ Event '{event_name}' sent successfully")

    except Exception as e:
        # Silently fail - don't let analytics break the app
        print(f"[Analytics] ERROR tracking '{event_name}': {e}")


def track_error(
    error_type: str,
    error_message: str,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Track an error event.

    Args:
        error_type: Type of error (e.g., "pdf_generation_failed")
        error_message: Error message (sanitized, no PII)
        context: Additional context (e.g., {'feature': 'pdf_report'})
    """
    properties = {
        'error_type': error_type,
        'error_message': error_message[:200],  # Limit message length
        **(context or {})
    }

    track_event('error_occurred', properties)


def track_page_view(page_name: str) -> None:
    """
    Track a page/screen view.

    Args:
        page_name: Name of the page (e.g., "onboarding", "results", "monte_carlo")
    """
    # Use PostHog's special properties for better page tracking
    track_event('page_viewed', {
        'page': page_name,
        '$current_url': f'streamlit://smart-retire-ai/{page_name}',
        '$pathname': f'/{page_name}',
        '$screen_name': page_name.replace('_', ' ').title()
    })


def get_age_range(age: int) -> str:
    """
    Convert exact age to age range for privacy.

    Args:
        age: Exact age

    Returns:
        Age range string (e.g., "30-40")
    """
    if age < 20:
        return "<20"
    elif age < 30:
        return "20-30"
    elif age < 40:
        return "30-40"
    elif age < 50:
        return "40-50"
    elif age < 60:
        return "50-60"
    elif age < 70:
        return "60-70"
    else:
        return "70+"


def get_goal_range(goal: float) -> str:
    """
    Convert exact retirement goal to range for privacy.

    Args:
        goal: Exact retirement goal amount

    Returns:
        Goal range string (e.g., "$50k-$75k")
    """
    if goal == 0:
        return "no_goal"
    elif goal < 25000:
        return "<$25k"
    elif goal < 50000:
        return "$25k-$50k"
    elif goal < 75000:
        return "$50k-$75k"
    elif goal < 100000:
        return "$75k-$100k"
    elif goal < 150000:
        return "$100k-$150k"
    else:
        return "$150k+"


# ==========================================
# COMMON EVENT TRACKING FUNCTIONS
# ==========================================

def track_onboarding_step_started(step: int) -> None:
    """Track when user starts an onboarding step."""
    track_event(f'onboarding_step{step}_started', {'step': step})


def track_onboarding_step_completed(step: int, **kwargs) -> None:
    """Track when user completes an onboarding step."""
    track_event(f'onboarding_step{step}_completed', {'step': step, **kwargs})


def track_feature_usage(feature: str, **kwargs) -> None:
    """Track when user uses a feature."""
    track_event(f'{feature}_used', {'feature': feature, **kwargs})


def track_pdf_generation(success: bool) -> None:
    """Track PDF report generation."""
    event = 'pdf_generated_success' if success else 'pdf_generated_failed'
    track_event(event, {'success': success})


def track_monte_carlo_run(num_simulations: int, volatility: float) -> None:
    """Track Monte Carlo simulation run."""
    track_event('monte_carlo_simulation_run', {
        'num_simulations': num_simulations,
        'volatility': volatility
    })


def track_statement_upload(success: bool, num_statements: int = 0, num_accounts: int = 0) -> None:
    """
    Track AI statement upload attempt.

    Args:
        success: Whether the upload succeeded
        num_statements: Number of PDF statements uploaded
        num_accounts: Number of accounts extracted from statements
    """
    event = 'statement_upload_success' if success else 'statement_upload_failed'
    track_event(event, {
        'success': success,
        'num_statements': num_statements,
        'num_accounts': num_accounts if success else 0
    })


# ==========================================
# SESSION REPLAY (JavaScript Integration)
# ==========================================

def get_session_replay_script() -> str:
    """
    Get PostHog session replay JavaScript snippet.

    This should be injected into the app using st.components.v1.html()
    to enable browser-based session recording.

    Returns:
        JavaScript code as string, or empty string if analytics disabled
    """
    if not is_analytics_enabled() or not POSTHOG_API_KEY:
        return ""

    user_id = get_or_create_user_id()

    # PostHog JavaScript snippet with session recording enabled
    return f"""
    <script>
        !function(t,e){{var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){{function g(t,e){{var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){{t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}}}(p=t.createElement("script")).type="text/javascript",p.async=!0,p.src=s.api_host+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){{var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e}},u.people.toString=function(){{return u.toString(1)+".people (stub)"}},o="capture identify alias people.set people.set_once set_config register register_once unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset isFeatureEnabled onFeatureFlags getFeatureFlag getFeatureFlagPayload reloadFeatureFlags group updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures getActiveMatchingSurveys getSurveys".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])}},e.__SV=1)}}(document,window.posthog||[]);

        posthog.init('{POSTHOG_API_KEY}', {{
            api_host: '{POSTHOG_HOST}',
            person_profiles: 'identified_only',
            session_recording: {{
                enabled: true,
                maskAllInputs: true,
                maskTextSelector: '[data-private]',
                recordCrossOriginIframes: false
            }},
            autocapture: false,  // Disable autocapture, use manual tracking
            capture_pageview: false  // We manually track page views
        }});

        // Identify the user with their anonymous ID
        posthog.identify('{user_id}');

        console.log('[PostHog] Session recording initialized for user: {user_id}');
    </script>
    """


# ==========================================
# SESSION MANAGEMENT
# ==========================================

def start_session() -> None:
    """Track session start."""
    if 'session_started' not in st.session_state:
        track_event('session_started')
        st.session_state.session_started = True


def end_session() -> None:
    """Track session end (call this on app unload if possible)."""
    track_event('session_ended')


# ==========================================
# CONSENT MANAGEMENT
# ==========================================

def set_analytics_consent(consented: bool) -> None:
    """
    Set user's analytics consent preference.

    Args:
        consented: True if user opts in, False if opts out
    """
    st.session_state.analytics_consent = consented

    if DEBUG_MODE:
        print(f"[Analytics] Consent set to: {consented}")

    if consented:
        # Generate user ID and track consent acceptance
        user_id = get_or_create_user_id()
        if DEBUG_MODE:
            print(f"[Analytics] User ID created: {user_id}")
        track_event('analytics_consent_accepted')
    else:
        # Track consent rejection (this will be the only event tracked)
        if POSTHOG_AVAILABLE and POSTHOG_API_KEY:
            try:
                if DEBUG_MODE:
                    print("[Analytics] Tracking consent rejection anonymously")
                # Track rejection without storing user ID
                posthog.capture(
                    distinct_id='anonymous',
                    event='analytics_consent_rejected'
                )
            except Exception as e:
                if DEBUG_MODE:
                    print(f"[Analytics] Failed to track consent rejection: {e}")


def opt_out() -> None:
    """Opt user out of analytics."""
    st.session_state.analytics_consent = False
    track_event('analytics_opt_out')


def opt_in() -> None:
    """Opt user in to analytics."""
    set_analytics_consent(True)


def reset_analytics_session() -> None:
    """
    Reset analytics session state.

    This clears:
    - Analytics consent
    - User ID
    - Session ID and timestamp
    - Session started flag

    Useful for testing or when user wants to start fresh.
    """
    if 'analytics_consent' in st.session_state:
        del st.session_state.analytics_consent
    if 'analytics_user_id' in st.session_state:
        del st.session_state.analytics_user_id
    if 'analytics_session_id' in st.session_state:
        del st.session_state.analytics_session_id
    if 'analytics_session_start_time' in st.session_state:
        del st.session_state.analytics_session_start_time
    if 'session_started' in st.session_state:
        del st.session_state.session_started

    if DEBUG_MODE:
        print("[Analytics] Session reset - all analytics state cleared")


# ==========================================
# INITIALIZATION
# ==========================================

def initialize_analytics() -> None:
    """Initialize analytics on app startup."""
    # Initialize session state for consent
    if 'analytics_consent' not in st.session_state:
        st.session_state.analytics_consent = None  # None = not decided yet

    # Start session if consent is given
    if is_analytics_enabled():
        start_session()
