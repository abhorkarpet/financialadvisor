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

POSTHOG_HOST = "https://app.posthog.com"  # or self-hosted URL

# Initialize PostHog once
if POSTHOG_AVAILABLE and POSTHOG_API_KEY:
    posthog.api_key = POSTHOG_API_KEY
    posthog.host = POSTHOG_HOST
else:
    POSTHOG_AVAILABLE = False


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
    if not is_analytics_enabled() or not POSTHOG_AVAILABLE:
        return

    try:
        user_id = get_or_create_user_id()

        # Capture event
        posthog.capture(
            distinct_id=user_id,
            event=event_name,
            properties=properties or {}
        )

        # Update user properties if provided
        if user_properties:
            posthog.identify(
                distinct_id=user_id,
                properties=user_properties
            )

    except Exception as e:
        # Silently fail - don't let analytics break the app
        print(f"Analytics tracking error: {e}")


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
    track_event('page_viewed', {'page': page_name})


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

    if consented:
        # Generate user ID and track consent acceptance
        get_or_create_user_id()
        track_event('analytics_consent_accepted')
    else:
        # Track consent rejection (this will be the only event tracked)
        if POSTHOG_AVAILABLE and POSTHOG_API_KEY:
            try:
                # Track rejection without storing user ID
                posthog.capture(
                    distinct_id='anonymous',
                    event='analytics_consent_rejected'
                )
            except:
                pass


def opt_out() -> None:
    """Opt user out of analytics."""
    st.session_state.analytics_consent = False
    track_event('analytics_opt_out')


def opt_in() -> None:
    """Opt user in to analytics."""
    set_analytics_consent(True)


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
