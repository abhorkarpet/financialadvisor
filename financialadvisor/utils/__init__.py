"""Utility modules for Smart Retire AI."""

from .analytics import (
    track_event,
    track_error,
    track_page_view,
    is_analytics_enabled,
    set_analytics_consent,
    opt_out,
    opt_in,
    initialize_analytics,
    track_onboarding_step_started,
    track_onboarding_step_completed,
    track_feature_usage,
    track_pdf_generation,
    track_monte_carlo_run,
    track_statement_upload,
    get_session_replay_script,
    reset_analytics_session,
)

__all__ = [
    'track_event',
    'track_error',
    'track_page_view',
    'is_analytics_enabled',
    'set_analytics_consent',
    'opt_out',
    'opt_in',
    'initialize_analytics',
    'track_onboarding_step_started',
    'track_onboarding_step_completed',
    'track_feature_usage',
    'track_pdf_generation',
    'track_monte_carlo_run',
    'track_statement_upload',
    'get_session_replay_script',
    'reset_analytics_session',
]
