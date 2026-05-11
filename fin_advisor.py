"""
Smart Retire AI — Advanced Retirement Planning Tool

Enhanced retirement planning tool with:
- Asset classification (pre_tax, post_tax, tax_deferred)
- Per-asset growth simulation with tax-efficient projections
- Portfolio growth during retirement with inflation-adjusted withdrawals
- One-time life expenses at retirement support
- Comprehensive income gap recommendations

Usage:
    Run the Streamlit web application:
        $ streamlit run fin_advisor.py

    Run unit tests:
        $ python3 fin_advisor.py --run-tests

Author: AI Assistant
Version: 16.6.0
"""

from __future__ import annotations
import argparse
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

# Version Management
VERSION = "16.6.0"

# Streamlit import
import streamlit as st
import streamlit.components.v1 as components
import io
import os
import csv
import time
import urllib.parse
from datetime import datetime

import pandas as pd

# Analytics module
try:
    from financialadvisor.utils.analytics import (
        initialize_analytics,
        set_analytics_consent,
        track_event,
        track_page_view,
        track_onboarding_step_started,
        track_onboarding_step_completed,
        track_pdf_generation,
        track_monte_carlo_run,
        track_statement_upload,
        track_error,
        is_analytics_enabled,
        opt_out,
        opt_in,
        get_age_range,
        get_goal_range,
        get_session_replay_script,
        reset_analytics_session,
    )
    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False
    # Define no-op functions if analytics not available with matching signatures
    def initialize_analytics() -> None: pass
    def set_analytics_consent(consented: bool) -> None: pass
    def track_event(event_name: str, properties: Optional[Dict[str, any]] = None, user_properties: Optional[Dict[str, any]] = None) -> None: pass
    def track_page_view(page_name: str) -> None: pass
    def track_onboarding_step_started(step: int, **kwargs: any) -> None: pass
    def track_onboarding_step_completed(step: int, **kwargs: any) -> None: pass
    def track_pdf_generation(success: bool) -> None: pass
    def track_monte_carlo_run(num_simulations: int, **kwargs: any) -> None: pass
    def track_statement_upload(success: bool, num_statements: int = 0, num_accounts: int = 0, **kwargs: Any) -> None: pass
    def track_error(error_type: str, error_message: str, context: Optional[Dict[str, any]] = None) -> None: pass
    def is_analytics_enabled() -> bool: return False
    def opt_out() -> None: pass
    def opt_in() -> None: pass
    def get_age_range(age: float) -> str: return "unknown"
    def get_goal_range(goal: float) -> str: return "unknown"
    def get_session_replay_script() -> str: return ""
    def reset_analytics_session() -> None: pass

# n8n / Python statement processor integration
try:
    from integrations.n8n_client import N8NError
    from integrations.statement_processor import StatementProcessor, StatementProcessorError
    from integrations.processor_factory import get_processor, check_processor_configured
    from pypdf import PdfReader
    from dotenv import load_dotenv
    load_dotenv()  # Load environment variables from .env file
    _N8N_AVAILABLE = True
except ImportError:
    _N8N_AVAILABLE = False

# Chat advisor (Mode 2 conversational planning)
try:
    from integrations.chat_advisor import (
        chat_with_advisor,
        chat_with_setup_advisor,
        chat_with_results_advisor,
        fields_are_complete,
    )
    _CHAT_AVAILABLE = True
except ImportError:
    _CHAT_AVAILABLE = False

try:
    from financialadvisor.core.chat_context import build_detailed_chat_context
    _CHAT_CONTEXT_AVAILABLE = True
except ImportError:
    _CHAT_CONTEXT_AVAILABLE = False

# PDF generation
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    _REPORTLAB_AVAILABLE = True
except ImportError:
    _REPORTLAB_AVAILABLE = False


def _fmt_inr(n: float) -> str:
    """Format a number using the Indian numbering system (last 3 digits, then groups of 2).

    Examples: 600000 → '6,00,000'  |  8589300 → '85,89,300'  |  10000000 → '1,00,00,000'
    """
    neg = n < 0
    s = str(int(round(abs(n))))
    if len(s) <= 3:
        return ('-' if neg else '') + s
    result = s[-3:]
    s = s[:-3]
    while s:
        result = s[-2:] + ',' + result
        s = s[:-2]
    return ('-' if neg else '') + result


def _fmt_currency(val: float, is_india: bool) -> str:
    """Return currency string: ₹Indian-format for India, $US-format for US."""
    if is_india:
        return f"₹{_fmt_inr(val)}"
    return f"${val:,.0f}"


def load_release_notes() -> Optional[str]:
    """Load release notes for the current version from file."""
    notes_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"RELEASE_NOTES_v{VERSION}.md"
    )
    try:
        with open(notes_path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def extract_release_overview(
    content: Optional[str],
    *,
    include_heading: bool = True,
) -> Optional[str]:
    """Extract the release overview section from release notes markdown."""
    if not content:
        return None

    markers = ("## 🎯 Release Overview", "## Release Overview")
    start = -1
    marker_used = ""
    for marker in markers:
        start = content.find(marker)
        if start != -1:
            marker_used = marker
            break

    if start == -1:
        fallback = content.strip()
        return fallback or None

    end = content.find("\n---", start)
    section = content[start:end] if end != -1 else content[start:]
    section = section.strip()
    if not section:
        return None

    if include_heading:
        return section

    body = section[len(marker_used):].strip()
    return body or None


def switch_to_simple_planning_from_onboarding() -> None:
    """Move from detailed onboarding into chat mode while preserving key inputs."""
    seeded_fields: Dict[str, object] = {}

    country = st.session_state.get("country")
    if country in {"US", "India"}:
        seeded_fields["country"] = country

    for source_key, target_key in (
        ("birth_year", "birth_year"),
        ("retirement_age", "retirement_age"),
        ("life_expectancy", "life_expectancy"),
        ("retirement_income_goal", "target_income"),
        ("whatif_retirement_tax_rate", "tax_rate"),
        ("whatif_retirement_growth_rate", "growth_rate"),
        ("whatif_inflation_rate", "inflation_rate"),
        ("legacy_goal", "legacy_goal"),
        ("life_expenses", "life_expenses"),
    ):
        value = st.session_state.get(source_key)
        if value is None:
            continue
        if target_key == "target_income" and float(value) <= 0:
            continue
        seeded_fields[target_key] = value

    summary_lines = []
    if "country" in seeded_fields:
        summary_lines.append(f"- Country: {seeded_fields['country']}")
    if "birth_year" in seeded_fields:
        summary_lines.append(f"- Birth year: {seeded_fields['birth_year']}")
    if "retirement_age" in seeded_fields:
        summary_lines.append(f"- Retirement age: {seeded_fields['retirement_age']}")
    if "life_expectancy" in seeded_fields:
        summary_lines.append(f"- Life expectancy: {seeded_fields['life_expectancy']}")
    if "target_income" in seeded_fields:
        summary_lines.append(f"- Target income: {seeded_fields['target_income']}")

    if summary_lines:
        opening = (
            "I’ve switched you to Simple Planning and carried over your current details:\n\n"
            + "\n".join(summary_lines)
            + "\n\nTell me anything you want to change, or continue from here."
        )
    else:
        opening = (
            "I’ve switched you to Simple Planning. Tell me your country, birth year, "
            "and target retirement income to get started."
        )

    st.session_state.current_page = "chat_mode"
    st.session_state.chat_fields = seeded_fields
    st.session_state.chat_messages = [{"role": "assistant", "content": opening}]
    st.session_state.chat_complete = False
    st.session_state.pop("planning_mode_choice", None)
    st.rerun()


_CHAT_TO_DETAILED_FIELD_MAP: Tuple[Tuple[str, str], ...] = (
    ("birth_year", "birth_year"),
    ("retirement_age", "retirement_age"),
    ("life_expectancy", "life_expectancy"),
    ("target_income", "retirement_income_goal"),
    ("legacy_goal", "legacy_goal"),
    ("life_expenses", "life_expenses"),
    ("tax_rate", "whatif_retirement_tax_rate"),
    ("growth_rate", "whatif_retirement_growth_rate"),
    ("inflation_rate", "whatif_inflation_rate"),
)

_DETAILED_PLANNING_RESET_KEYS: Tuple[str, ...] = (
    "assets",
    "setup_method_radio",
    "num_assets_manual",
    "show_contribution_reminder",
    "contribution_reminder_dismissed",
    "ai_extracted_accounts",
    "ai_tax_buckets",
    "ai_warnings",
    "ai_edited_table",
    "ai_table_data",
    "ai_table_initialized",
    "ai_table_modal_editor",
    "dialog_open",
    "show_extraction_feedback_form",
    "csv_uploaded_file_id",
    "csv_uploaded_assets",
    "csv_uploaded_edited_table",
    "csv_uploaded_assets_table",
)


def collect_detailed_planning_handoff_fields(chat_fields: Dict[str, Any]) -> Dict[str, Any]:
    """Map Simple Planning fields into Detailed Planning state."""
    seeded_fields: Dict[str, Any] = {}

    for source_key, target_key in _CHAT_TO_DETAILED_FIELD_MAP:
        value = chat_fields.get(source_key)
        if value is not None:
            seeded_fields[target_key] = value

    seeded_fields["country"] = "US"
    seeded_fields["_prev_country"] = "US"
    return seeded_fields


def has_existing_detailed_asset_state(state: Dict[str, Any]) -> bool:
    """Return True when Detailed Planning already has account data or editor state."""
    assets = state.get("assets") or []
    if len(assets) > 0:
        return True

    ai_extracted = state.get("ai_extracted_accounts")
    if ai_extracted is not None and len(ai_extracted) > 0:
        return True

    csv_assets = state.get("csv_uploaded_assets") or []
    if len(csv_assets) > 0:
        return True

    csv_edited = state.get("csv_uploaded_edited_table")
    if csv_edited is not None and len(csv_edited) > 0:
        return True

    return False


def clear_detailed_planning_asset_state(state: Dict[str, Any]) -> None:
    """Clear Detailed Planning account/setup state so Step 2 starts fresh."""
    for key in _DETAILED_PLANNING_RESET_KEYS:
        state.pop(key, None)

    state["assets"] = []
    state["ai_upload_widget_version"] = int(state.get("ai_upload_widget_version", 0)) + 1
    state["csv_upload_widget_version"] = int(state.get("csv_upload_widget_version", 0)) + 1


def _apply_detailed_planning_handoff(*, reuse_existing_assets: bool) -> None:
    """Enter Detailed Planning using any queued handoff fields."""
    seeded_fields = st.session_state.get("pending_detailed_switch_fields") or {}

    if not reuse_existing_assets:
        clear_detailed_planning_asset_state(st.session_state)

    for key, value in seeded_fields.items():
        st.session_state[key] = value

    st.session_state.country = "US"
    st.session_state._prev_country = "US"
    st.session_state.onboarding_complete = False
    st.session_state.current_page = "detailed_planning"
    st.session_state.onboarding_step = 1
    st.session_state.show_detailed_asset_choice_dialog = False
    st.session_state.pending_detailed_switch_fields = None
    st.session_state.pending_detailed_switch_source_country = None
    # Clear conversational setup state so user starts fresh
    st.session_state.setup_messages = []
    st.session_state.setup_fields = {}
    st.session_state.setup_fields_locked = False
    st.session_state.dp_goals_done = False
    st.session_state.dp_calculated = False
    st.session_state.dp_chat_messages = []
    st.session_state.dp_chat_pending = False
    st.session_state.pop("dp_assets_hash", None)
    st.rerun()


def switch_to_detailed_planning_from_chat() -> None:
    """Move from chat mode into US-only detailed onboarding, preserving key inputs."""
    fields = st.session_state.get("chat_fields", {})
    st.session_state.pending_detailed_switch_fields = collect_detailed_planning_handoff_fields(fields)
    st.session_state.pending_detailed_switch_source_country = fields.get("country", "US")

    if has_existing_detailed_asset_state(st.session_state):
        st.session_state.show_detailed_asset_choice_dialog = True
        st.rerun()

    _apply_detailed_planning_handoff(reuse_existing_assets=True)


def _format_money_input(value: Any) -> str:
    """Format numeric values for forgiving money text inputs."""
    try:
        amount = float(value or 0.0)
    except (TypeError, ValueError):
        return str(value or "")
    if amount == 0:
        return "0"
    if amount.is_integer():
        return f"{int(amount):,}"
    return f"{amount:,.2f}".rstrip("0").rstrip(".")


def _parse_money_input(raw_value: Any, field_label: str, *, allow_blank: bool = True) -> float:
    """Parse user-friendly money text like $200k, 2.5m, or 150,000."""
    raw = str(raw_value or "").strip()
    if raw == "":
        if allow_blank:
            return 0.0
        raise ValueError(f"{field_label}: enter a value like 200k, $200,000, or 2.5m.")

    normalized = raw.lower().replace("$", "").replace(",", "").replace(" ", "")
    normalized = normalized.replace("/yr", "").replace("peryear", "").replace("year", "")
    match = re.fullmatch(r"(-?\d+(?:\.\d+)?)([kmb])?", normalized)
    if not match:
        raise ValueError(f"{field_label}: use formats like 200k, $200,000, 2.5m, or 5000.")

    amount = float(match.group(1))
    suffix = match.group(2)
    multipliers = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
    if suffix:
        amount *= multipliers[suffix]
    if amount < 0:
        raise ValueError(f"{field_label}: value cannot be negative.")
    return amount


def _dedupe_uploaded_file_payloads(files_to_upload: List[Tuple[str, bytes]]) -> Tuple[List[Tuple[str, bytes]], List[str]]:
    """Remove byte-identical files before upload and return skipped-file messages."""
    import hashlib

    seen_hashes: Dict[str, str] = {}
    deduped_files: List[Tuple[str, bytes]] = []
    skipped_names: List[str] = []
    for fname, fcontent in files_to_upload:
        fhash = hashlib.sha256(fcontent).hexdigest()
        if fhash in seen_hashes:
            skipped_names.append(f"{fname} (identical to {seen_hashes[fhash]})")
        else:
            seen_hashes[fhash] = fname
            deduped_files.append((fname, fcontent))
    return deduped_files, skipped_names


def _dedupe_ai_editor_rows(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Remove likely duplicate extracted accounts and return warnings."""
    if df is None or df.empty:
        return df, []

    working_df = df.copy()

    def _normalize_text(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip().lower())

    def _normalize_last4(value: Any) -> str:
        digits = "".join(ch for ch in str(value or "") if ch.isdigit())
        return digits[-4:]

    def _build_key(row: pd.Series) -> Tuple[str, str, str, float]:
        institution = _normalize_text(row.get("Institution", ""))
        account_name = _normalize_text(row.get("Account Name", ""))
        last4 = _normalize_last4(row.get("Last 4", ""))
        balance = round(float(pd.to_numeric(row.get("Current Balance", 0), errors="coerce") or 0.0), 2)
        return institution, account_name, last4, balance

    duplicate_indexes: List[int] = []
    warnings: List[str] = []
    seen_keys: Dict[Tuple[str, str, str, float], int] = {}
    for idx, row in working_df.iterrows():
        key = _build_key(row)
        if key in seen_keys and any(key[:3]):
            duplicate_indexes.append(idx)
            name = str(row.get("Account Name", "Account")).strip() or "Account"
            institution = str(row.get("Institution", "")).strip()
            source = f"{institution} " if institution else ""
            warnings.append(f"Potential duplicate removed after extraction: {source}{name}")
        else:
            seen_keys[key] = idx

    if not duplicate_indexes:
        return working_df, []

    deduped_df = working_df.drop(index=duplicate_indexes).reset_index(drop=True)
    if "#" in deduped_df.columns:
        deduped_df["#"] = [f"#{i + 1}" for i in range(len(deduped_df))]
    return deduped_df, warnings


def _humanize_ai_account_type(account_type: str) -> str:
    """Convert extracted account types into user-friendly labels."""
    if not account_type:
        return "Unknown"

    mappings = {
        "401k": "401(K)",
        "403b": "403(b)",
        "457": "457 Plan",
        "ira": "IRA",
        "roth_ira": "Roth IRA",
        "traditional_ira": "Traditional IRA",
        "rollover_ira": "Rollover IRA",
        "brokerage": "Brokerage Account",
        "hsa": "HSA (Health Savings Account)",
        "checking": "Checking Account",
        "savings": "Savings Account",
        "high yield savings": "High Yield Savings",
        "stock_plan": "Stock Plan",
        "roth": "Roth IRA",
    }
    account_type_lower = str(account_type).lower().strip()

    if account_type_lower in mappings:
        return mappings[account_type_lower]

    for key, value in mappings.items():
        if key in account_type_lower:
            return value

    return account_type.replace("_", " ").title()


def _humanize_ai_account_name(name: str) -> str:
    """Convert raw extracted account names into human-readable format."""
    name_clean = str(name or "").strip()

    if "STOCK PLAN" in name_clean.upper():
        parts = name_clean.split("-")
        if len(parts) >= 2:
            plan_details = parts[1].strip()
            words = plan_details.split()
            if len(words) >= 2:
                company = words[0].title()
                if "ESPP" in plan_details.upper():
                    return f"{company} ESPP"
                if "STOCK OPTION" in plan_details.upper():
                    return f"{company} Stock Options"
                if "RSU" in plan_details.upper():
                    return f"{company} RSUs"
                return f"{company} {' '.join(words[1:]).title()}"

    if "at Work Self-Directed" in name_clean:
        institution = name_clean.split(" at Work")[0]
        return f"{institution} Brokerage"

    if name_clean.lower() == "brokerage account":
        return "Brokerage"

    replacements = {
        "rollover_ira": "Rollover IRA",
        "roth_ira": "Roth IRA",
        "traditional_ira": "Traditional IRA",
        "health_savings_account": "HSA",
        "401k": "401(K)",
        "403b": "403(b)",
        "457": "457(b)",
        "ira": "IRA",
    }

    name_lower = name_clean.lower()
    for key, value in replacements.items():
        if key == name_lower:
            return value
        if name_lower.startswith(key):
            suffix = name_clean[len(key):].strip()
            return f"{value}{suffix}"

    if name_clean.isupper():
        return name_clean.title().replace("Ira", "IRA").replace("401K", "401(K)")

    return name_clean.replace("Ira", "IRA").replace("401k", "401(K)").replace("401K", "401(K)")
# ---------------------------
# Import refactored modules
# ---------------------------
from financialadvisor.domain.models import (
    AssetType,
    TaxBehavior,
    Asset,
    TaxBracket,
    UserInputs,
    _DEF_ASSET_TYPES,
    infer_tax_behavior,
)

from financialadvisor.core.calculator import (
    years_to_retirement,
    future_value_with_contrib,
)

from financialadvisor.core.tax_engine import (
    get_irs_tax_brackets_2024,
    project_tax_rate,
    calculate_asset_growth,
    apply_tax_logic,
    simple_post_tax,
)

from financialadvisor.core.projector import project

from financialadvisor.core.explainer import explain_projected_balance

# ---------------------------
# Domain Models & Computation (now imported from financialadvisor package)
# ---------------------------

TAX_TREATMENT_OPTIONS = ["Tax-Deferred", "Tax-Free", "Post-Tax"]


def _resolve_tax_settings(
    tax_treatment: str,
    account_name: str,
    tax_rate_pct: float = 0.0,
) -> Tuple[AssetType, TaxBehavior, float]:
    """Convert UI tax labels into explicit internal tax settings."""
    normalized = str(tax_treatment).strip().lower().replace("_", "-")
    account_name = str(account_name).strip()
    rate = float(tax_rate_pct or 0.0)

    if normalized in {"pre-tax", "pre tax", "pre_tax"}:
        return AssetType.PRE_TAX, TaxBehavior.PRE_TAX, 0.0

    if normalized in {"tax-deferred", "tax deferred", "tax_deferred"}:
        lowered_name = account_name.lower()
        if "hsa" in lowered_name or "health savings" in lowered_name:
            return AssetType.TAX_DEFERRED, TaxBehavior.HSA_SPLIT, 0.0
        if "annuity" in lowered_name:
            return AssetType.TAX_DEFERRED, TaxBehavior.ORDINARY_INCOME, 0.0
        return AssetType.PRE_TAX, TaxBehavior.PRE_TAX, 0.0

    if normalized in {"tax-free", "tax free", "tax_free", "roth"}:
        return AssetType.POST_TAX, TaxBehavior.TAX_FREE, 0.0

    if normalized in {"post-tax", "post tax", "post_tax"}:
        tax_behavior = infer_tax_behavior(AssetType.POST_TAX, account_name, rate)
        normalized_rate = rate if tax_behavior == TaxBehavior.CAPITAL_GAINS else 0.0
        return AssetType.POST_TAX, tax_behavior, normalized_rate

    raise ValueError(
        f"Invalid tax treatment: '{tax_treatment}'. Must be 'Tax-Deferred', "
        f"'Tax-Free', or 'Post-Tax' (or legacy: 'pre_tax', 'post_tax', 'tax_deferred')"
    )


def _asset_to_tax_treatment_label(asset: Asset) -> str:
    """Return the stable editor label for an asset's tax treatment."""
    if asset.tax_behavior == TaxBehavior.TAX_FREE:
        return "Tax-Free"
    if asset.asset_type in (AssetType.PRE_TAX, AssetType.TAX_DEFERRED):
        return "Tax-Deferred"
    return "Post-Tax"


def _asset_from_editor_row(row: Dict[str, object]) -> Asset:
    """Create an Asset from a row used in AI-upload and CSV editors."""
    account_name = str(row["Account Name"])
    raw_tax_rate = float(row.get("Tax Rate on Gains (%)", 0.0) or 0.0)
    asset_type, tax_behavior, normalized_tax_rate = _resolve_tax_settings(
        str(row["Tax Treatment"]),
        account_name,
        raw_tax_rate,
    )
    return Asset(
        name=account_name,
        asset_type=asset_type,
        current_balance=float(row["Current Balance"]),
        annual_contribution=float(row["Annual Contribution"]),
        growth_rate_pct=float(row["Growth Rate (%)"]),
        tax_behavior=tax_behavior,
        tax_rate_pct=normalized_tax_rate,
    )


def _raw_accounts_to_assets(accounts: List[Dict]) -> List[Asset]:
    """Convert raw statement-processor account dicts to Asset objects."""
    assets = []
    for acct in accounts:
        institution = (acct.get("institution") or "").strip()
        name = (acct.get("account_name") or "Unknown Account").strip()
        display_name = f"{institution} {name}".strip() if institution else name
        balance = float(acct.get("ending_balance") or 0)
        tax_treatment = acct.get("tax_treatment") or "post-tax"
        account_type = (acct.get("account_type") or "").lower()

        asset_type, tax_behavior, tax_rate = _resolve_tax_settings(tax_treatment, display_name)

        if any(k in account_type for k in ("savings", "checking", "cash", "money market")):
            growth_rate = 3.0
        else:
            growth_rate = 7.0

        assets.append(Asset(
            name=display_name,
            asset_type=asset_type,
            current_balance=balance,
            annual_contribution=0.0,
            growth_rate_pct=growth_rate,
            tax_behavior=tax_behavior,
            tax_rate_pct=tax_rate,
        ))
    return assets


def create_default_assets() -> List[Asset]:
    """Create default asset configuration."""
    return [
        Asset(
            name="401(k) / Traditional IRA",
            asset_type=AssetType.PRE_TAX,
            current_balance=50000,
            annual_contribution=12000,
            growth_rate_pct=7.0,
            tax_behavior=TaxBehavior.PRE_TAX,
        ),
        Asset(
            name="Roth IRA",
            asset_type=AssetType.POST_TAX,
            current_balance=10000,
            annual_contribution=6000,
            growth_rate_pct=7.0,
            tax_behavior=TaxBehavior.TAX_FREE,
        ),
        Asset(
            name="Brokerage Account",
            asset_type=AssetType.POST_TAX,
            current_balance=15000,
            annual_contribution=3000,
            growth_rate_pct=7.0,
            tax_behavior=TaxBehavior.CAPITAL_GAINS,
            tax_rate_pct=15.0  # Capital gains rate
        ),
        Asset(
            name="High-Yield Savings Account",
            asset_type=AssetType.POST_TAX,
            current_balance=25000,
            annual_contribution=2000,
            growth_rate_pct=4.5,
            tax_behavior=TaxBehavior.NO_ADDITIONAL_TAX,
            tax_rate_pct=0.0  # Interest taxed as ordinary income, but no capital gains
        )
    ]


def create_asset_template_csv() -> str:
    """Create a CSV template for asset configuration."""
    template_data = [
        {
            "Account Name": "401(k) / Traditional IRA",
            "Tax Treatment": "Tax-Deferred",
            "Current Balance": 50000,
            "Annual Contribution": 12000,
            "Growth Rate (%)": 7.0,
        },
        {
            "Account Name": "Roth IRA",
            "Tax Treatment": "Tax-Free",
            "Current Balance": 10000,
            "Annual Contribution": 6000,
            "Growth Rate (%)": 7.0,
        },
        {
            "Account Name": "Brokerage Account",
            "Tax Treatment": "Post-Tax",
            "Current Balance": 15000,
            "Annual Contribution": 3000,
            "Growth Rate (%)": 7.0,
        },
        {
            "Account Name": "High-Yield Savings Account",
            "Tax Treatment": "Post-Tax",
            "Current Balance": 25000,
            "Annual Contribution": 2000,
            "Growth Rate (%)": 4.5,
        }
    ]

    # Create CSV string
    output = io.StringIO()
    fieldnames = ["Account Name", "Tax Treatment", "Current Balance", "Annual Contribution", "Growth Rate (%)"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(template_data)

    return output.getvalue()


def parse_uploaded_csv(csv_content: str) -> tuple:
    """Parse uploaded CSV content into Asset objects. Returns (assets, warnings)."""
    assets = []
    warnings = []

    try:
        # Read CSV content
        csv_reader = csv.DictReader(io.StringIO(csv_content))

        # Determine which column name is used for tax treatment
        # Support both "Tax Treatment" (new) and "Asset Type" (legacy) for backward compatibility
        fieldnames = csv_reader.fieldnames or []
        has_tax_treatment = "Tax Treatment" in fieldnames
        has_asset_type = "Asset Type" in fieldnames

        if not has_tax_treatment and not has_asset_type:
            raise ValueError("CSV must contain either 'Tax Treatment' or 'Asset Type' column")

        tax_column = "Tax Treatment" if has_tax_treatment else "Asset Type"

        for row in csv_reader:
            # Validate required fields
            required_fields = ["Account Name", tax_column, "Current Balance", "Annual Contribution", "Growth Rate (%)"]
            for field in required_fields:
                if field not in row or not row[field].strip():
                    raise ValueError(f"Missing or empty required field: {field}")

            asset_type_str = row[tax_column].strip()
            
            # Parse numeric values (handle commas in numbers)
            try:
                def parse_number(value_str):
                    """Parse a number string, removing commas and handling empty values."""
                    if not value_str or str(value_str).strip() == '':
                        return 0.0
                    # Remove commas, dollar signs, and whitespace; strip % suffix
                    cleaned = str(value_str).replace(',', '').replace('$', '').strip()
                    is_percent = cleaned.endswith('%')
                    cleaned = cleaned.rstrip('%').strip()
                    return float(cleaned), is_percent

                def parse_rate(value_str, field_name):
                    """Parse a percentage field accepting 0.25, 25%, or 25 — always returns a value in 0-100 range."""
                    val, is_percent = parse_number(value_str)
                    # Decimal fraction (e.g. 0.25) → multiply to get percentage
                    if not is_percent and 0.0 < val < 1.0:
                        val *= 100
                    # Exactly 0 stays 0; integers >= 1 are already percentages (e.g. 25 → 25%)
                    # Edge case: bare "1" is ambiguous but almost certainly means 1%, not 100%
                    if not is_percent and val == 1.0:
                        warnings.append(
                            f'"{value_str}" entered for {field_name} — assumed **1%** (not 100%). '
                            f'Use "1%" to be explicit.'
                        )
                    return val

                def parse_plain(value_str):
                    val, _ = parse_number(value_str)
                    return val

                current_balance = parse_plain(row["Current Balance"])
                annual_contribution = parse_plain(row["Annual Contribution"])
                growth_rate = parse_rate(row["Growth Rate (%)"], "Growth Rate")
            except ValueError as e:
                raise ValueError(f"Invalid numeric value in row: {e}")

            # Validate ranges
            if current_balance < 0:
                raise ValueError("Current Balance cannot be negative")
            if annual_contribution < 0:
                raise ValueError("Annual Contribution cannot be negative")
            if growth_rate < 0 or growth_rate > 50:
                raise ValueError("Growth Rate must be between 0% and 50%")
            
            # Create asset
            asset = _asset_from_editor_row({
                "Account Name": row["Account Name"].strip(),
                "Tax Treatment": asset_type_str,
                "Current Balance": current_balance,
                "Annual Contribution": annual_contribution,
                "Growth Rate (%)": growth_rate,
                "Tax Rate on Gains (%)": 0.0,
            })
            
            assets.append(asset)
        
        if not assets:
            raise ValueError("No valid assets found in CSV")

        return assets, warnings
        
    except Exception as e:
        raise ValueError(f"Error parsing CSV: {str(e)}")


# ---------------------------------------------------------------------------
# Retirement simulation — sequencing + RMD model
# ---------------------------------------------------------------------------

# IRS contribution limits (2024). Age-50+ values include catch-up contributions.
_IRS_401K_LIMIT: dict = {True: 30_500, False: 23_000}   # key: age >= 50
_IRS_IRA_LIMIT:  dict = {True: 8_000,  False: 7_000}    # key: age >= 50 (Traditional + Roth combined)

# IRS Uniform Lifetime Table (2024) — distribution periods for RMD calculation.
# Source: IRS Publication 590-B.
_IRS_UNIFORM_LIFETIME_TABLE: Dict[int, float] = {
    73: 26.5, 74: 25.5, 75: 24.6, 76: 23.7, 77: 22.9, 78: 22.0, 79: 21.1,
    80: 20.2, 81: 19.4, 82: 18.5, 83: 17.7, 84: 16.8, 85: 16.0, 86: 15.2,
    87: 14.4, 88: 13.7, 89: 12.9, 90: 12.2, 91: 11.5, 92: 10.8, 93: 10.1,
    94: 9.5,  95: 8.9,  96: 8.4,  97: 7.8,  98: 7.3,  99: 6.8, 100: 6.4,
}


def _rmd_distribution_period(age: int) -> float:
    """Return IRS Uniform Lifetime Table distribution period for a given age.

    Returns float('inf') for ages below 73 (no RMD required).
    Uses a linear approximation beyond age 100.
    """
    if age < 73:
        return float('inf')
    if age in _IRS_UNIFORM_LIFETIME_TABLE:
        return _IRS_UNIFORM_LIFETIME_TABLE[age]
    # Linear extrapolation beyond age 100 (approx. -0.4 per year)
    return max(1.9, 6.4 - (age - 100) * 0.4)


def simulate_retirement(
    pretax_bal: float,
    roth_bal: float,
    brokerage_bal: float,
    brokerage_cost_basis: float,
    first_year_aftertax_target: float,
    retirement_age: int,
    life_expectancy: int,
    growth_rate: float,
    inflation_rate: float,
    retirement_tax_rate_pct: float,
    capital_gains_rate_pct: float = 15.0,
) -> list:
    """Year-by-year retirement simulation with withdrawal sequencing and RMDs.

    Withdrawal order each year (annuity due — withdrawals at START of year):
      1. RMD from pre-tax (forced at age >= 73; IRS Uniform Lifetime Table)
      2. Brokerage (capital gains tax on gains portion only)
      3. Roth IRA (tax-free)
      4. Additional pre-tax if still short (ordinary income tax)
      Portfolio grows on the remaining balance after withdrawals.

    Excess RMD beyond spending need is reinvested into brokerage after tax.

    Args:
        pretax_bal: Pre-tax (401k / Trad IRA / TAX_DEFERRED) balance at retirement
        roth_bal: Roth balance at retirement (tax-free)
        brokerage_bal: Taxable brokerage balance at retirement
        brokerage_cost_basis: Cost basis for brokerage account (contributions + original balance)
        first_year_aftertax_target: Desired after-tax income in year 1
        retirement_age: Age at retirement
        life_expectancy: Age at end of retirement
        growth_rate: Annual portfolio growth rate (decimal, e.g. 0.04)
        inflation_rate: Annual inflation rate (decimal, e.g. 0.03)
        retirement_tax_rate_pct: Ordinary income tax rate in retirement (percentage, e.g. 25.0)
        capital_gains_rate_pct: Long-term capital gains rate for brokerage (percentage, e.g. 15.0)

    Returns:
        List of dicts, one per year, with detailed withdrawal and balance data.
    """
    n = life_expectancy - retirement_age
    t_ord = retirement_tax_rate_pct / 100.0
    t_cg = capital_gains_rate_pct / 100.0
    year_data = []

    for year in range(1, n + 1):
        age = retirement_age + year - 1
        annual_target = first_year_aftertax_target * ((1.0 + inflation_rate) ** (year - 1))

        # --- 1. RMD from pre-tax (on start-of-year balance, before growth) ---
        rmd = 0.0
        rmd_tax = 0.0
        rmd_aftertax = 0.0
        if age >= 73 and pretax_bal > 0:
            dist_period = _rmd_distribution_period(age)
            rmd = min(pretax_bal, pretax_bal / dist_period)
            rmd_tax = rmd * t_ord
            rmd_aftertax = rmd - rmd_tax
            pretax_bal -= rmd

        # --- 2. Determine remaining after-tax needed ---
        brokerage_withdrawal = 0.0
        brokerage_tax = 0.0
        roth_withdrawal = 0.0
        extra_pretax_withdrawal = 0.0
        extra_pretax_tax = 0.0
        reinvested_excess = 0.0

        if rmd_aftertax >= annual_target:
            # RMD covers spending; reinvest excess after-tax into brokerage
            reinvested_excess = rmd_aftertax - annual_target
            brokerage_bal += reinvested_excess
            brokerage_cost_basis += reinvested_excess  # after-tax dollars = full cost basis
            actual_spend = annual_target
        else:
            actual_spend = rmd_aftertax
            remaining = annual_target - actual_spend

            # Draw from brokerage (capital gains on gains fraction only)
            if remaining > 0 and brokerage_bal > 0:
                gains_fraction = max(0.0, (brokerage_bal - brokerage_cost_basis) / brokerage_bal)
                effective_cg = gains_fraction * t_cg
                # Solve: withdrawal * (1 - effective_cg) = remaining
                needed_gross = remaining / (1.0 - effective_cg) if effective_cg < 1.0 else remaining
                brokerage_withdrawal = min(brokerage_bal, needed_gross)
                brokerage_tax = brokerage_withdrawal * effective_cg
                brokerage_aftertax = brokerage_withdrawal - brokerage_tax
                # Update cost basis proportionally
                basis_fraction = brokerage_withdrawal / brokerage_bal if brokerage_bal > 0 else 0
                brokerage_cost_basis = max(0.0, brokerage_cost_basis * (1.0 - basis_fraction))
                brokerage_bal -= brokerage_withdrawal
                actual_spend += brokerage_aftertax
                remaining -= brokerage_aftertax

            # Draw from Roth (tax-free)
            if remaining > 0 and roth_bal > 0:
                roth_withdrawal = min(roth_bal, remaining)
                roth_bal -= roth_withdrawal
                actual_spend += roth_withdrawal
                remaining -= roth_withdrawal

            # Draw additional from pre-tax if still short
            if remaining > 0 and pretax_bal > 0:
                needed_gross = remaining / (1.0 - t_ord) if t_ord < 1.0 else remaining
                extra_pretax_withdrawal = min(pretax_bal, needed_gross)
                extra_pretax_tax = extra_pretax_withdrawal * t_ord
                pretax_bal -= extra_pretax_withdrawal
                actual_spend += (extra_pretax_withdrawal - extra_pretax_tax)

        # --- 3. Grow remaining balances (after withdrawals — annuity due) ---
        pretax_bal    *= (1.0 + growth_rate)
        roth_bal      *= (1.0 + growth_rate)
        brokerage_bal *= (1.0 + growth_rate)
        # Cost basis does not grow (only the market value does)

        # --- 4. Clamp balances ---
        pretax_bal    = max(0.0, pretax_bal)
        roth_bal      = max(0.0, roth_bal)
        brokerage_bal = max(0.0, brokerage_bal)

        total_tax = rmd_tax + brokerage_tax + extra_pretax_tax
        total_portfolio_end = pretax_bal + roth_bal + brokerage_bal

        year_data.append({
            "year": year,
            "age": age,
            "rmd": rmd,
            "brokerage_withdrawal": brokerage_withdrawal,
            "roth_withdrawal": roth_withdrawal,
            "extra_pretax_withdrawal": extra_pretax_withdrawal,
            "reinvested_excess": reinvested_excess,
            "total_tax": total_tax,
            "actual_aftertax": actual_spend,
            "pretax_bal_end": pretax_bal,
            "roth_bal_end": roth_bal,
            "brokerage_bal_end": brokerage_bal,
            "total_portfolio_end": total_portfolio_end,
        })

    return year_data


def find_sustainable_withdrawal(
    pretax_bal: float,
    roth_bal: float,
    brokerage_bal: float,
    brokerage_cost_basis: float,
    retirement_age: int,
    life_expectancy: int,
    growth_rate: float,
    inflation_rate: float,
    retirement_tax_rate_pct: float,
    capital_gains_rate_pct: float = 15.0,
    legacy_goal: float = 0.0,
) -> tuple:
    """Binary search for the maximum first-year after-tax withdrawal that leaves
    `legacy_goal` in the portfolio at life_expectancy (default ≈ $0).

    Returns:
        (sustainable_withdrawal, year_data) where year_data is the full simulation
        for the found withdrawal amount.
    """
    total = pretax_bal + roth_bal + brokerage_bal
    if total <= 0:
        return 0.0, []

    low = 0.0
    high = total  # theoretical upper bound

    for _ in range(50):  # 50 iterations → sub-cent precision
        mid = (low + high) / 2.0
        data = simulate_retirement(
            pretax_bal, roth_bal, brokerage_bal, brokerage_cost_basis,
            mid, retirement_age, life_expectancy,
            growth_rate, inflation_rate,
            retirement_tax_rate_pct, capital_gains_rate_pct,
        )
        final_balance = data[-1]["total_portfolio_end"] if data else 0.0
        if final_balance > legacy_goal + 1.0:
            # Portfolio has money left above target — can afford a higher withdrawal
            low = mid
        else:
            # Portfolio fell below legacy target — withdrawal too high
            high = mid

    # Run one final simulation with the converged value to get clean year_data
    final_data = simulate_retirement(
        pretax_bal, roth_bal, brokerage_bal, brokerage_cost_basis,
        low, retirement_age, life_expectancy,
        growth_rate, inflation_rate,
        retirement_tax_rate_pct, capital_gains_rate_pct,
    )
    return low, final_data


def find_breakeven_retirement_age(
    assets_input: list,
    current_age: int,
    start_retirement_age: int,
    life_expectancy: int,
    target_income: float,
    retirement_growth_rate: float,
    inflation_rate: float,
    retirement_tax_rate_pct: float,
    life_expenses: float = 0.0,
    legacy_goal: float = 0.0,
    max_search_age: int = 80,
) -> tuple:
    """Find the exact retirement age where sustainable after-tax income >= target_income.

    Projects each asset forward using its own growth rate and contributions, then runs
    find_sustainable_withdrawal at each candidate age. Searches from
    max(start_retirement_age, current_age) + 1 up to max_search_age.

    Returns:
        (breakeven_age, income_at_that_age) — first age where income >= target_income.
        (None, income_at_max_age) — if the goal is not achievable by max_search_age.
    """
    best_income = 0.0
    for candidate_age in range(max(start_retirement_age, current_age) + 1, max_search_age + 1):
        years = candidate_age - current_age
        pretax = roth = brok = brok_basis = 0.0

        for ai in assets_input:
            balance = float(getattr(ai, "current_balance", 0))
            contrib = float(getattr(ai, "annual_contribution", 0))
            rate = float(getattr(ai, "growth_rate_pct", 7.0))
            fv = future_value_with_contrib(balance, contrib, rate, years)
            name = getattr(ai, "name", "").lower()
            atype = ai.asset_type

            if atype in (AssetType.PRE_TAX, AssetType.TAX_DEFERRED):
                pretax += fv
            elif atype == AssetType.POST_TAX and "roth" in name:
                roth += fv
            elif atype == AssetType.POST_TAX:
                brok += fv
                brok_basis += balance + contrib * years  # contributions at cost basis

        # Deduct life expenses proportionally
        total_fv = pretax + roth + brok
        if life_expenses > 0 and total_fv > 0:
            frac = life_expenses / total_fv
            pretax = max(0.0, pretax * (1.0 - frac))
            roth = max(0.0, roth * (1.0 - frac))
            brok = max(0.0, brok * (1.0 - frac))
            brok_basis = max(0.0, brok_basis * (1.0 - frac))

        income, _ = find_sustainable_withdrawal(
            pretax, roth, brok, brok_basis,
            candidate_age, life_expectancy,
            retirement_growth_rate, inflation_rate,
            retirement_tax_rate_pct,
            legacy_goal=legacy_goal,
        )
        best_income = income
        if income >= target_income:
            return candidate_age, income

    return None, best_income


def find_breakeven_contribution(
    assets_input: list,
    current_age: int,
    retirement_age: int,
    life_expectancy: int,
    target_income: float,
    retirement_growth_rate: float,
    inflation_rate: float,
    retirement_tax_rate_pct: float,
    life_expenses: float = 0.0,
    legacy_goal: float = 0.0,
    max_search: float = 300_000.0,
) -> tuple:
    """Binary search for the minimum additional annual contribution that closes the income gap.

    Distribution priority (tax-optimal):
      1. Pre-tax / 401k — up to IRS annual limit (age-aware, including catch-up)
      2. Taxable brokerage — any overflow above the IRS 401k limit

    All projections use each account type's average growth rate.

    Returns:
        (additional_needed, breakdown, irs_maxed_out) where:
          additional_needed  — total extra annual dollars needed (None if not achievable)
          breakdown          — dict with keys 'pretax', 'brokerage', 'irs_401k_limit',
                               'pretax_current', 'pretax_capacity'
          irs_maxed_out      — True when pre-tax capacity is fully used and overflow hits brokerage
    """
    years = retirement_age - current_age
    if years <= 0 or target_income <= 0:
        return None, {}, False

    age50plus = current_age >= 50
    irs_401k_limit = _IRS_401K_LIMIT[age50plus]

    # Current pre-tax annual contributions (401k, tax-deferred)
    current_pretax_contrib = sum(
        float(getattr(ai, "annual_contribution", 0))
        for ai in assets_input
        if ai.asset_type in (AssetType.PRE_TAX, AssetType.TAX_DEFERRED)
    )
    pretax_capacity = max(0.0, irs_401k_limit - current_pretax_contrib)

    # Average growth rates for the additional-contribution buckets
    _pretax_rates = [
        float(getattr(ai, "growth_rate_pct", 7.0))
        for ai in assets_input
        if ai.asset_type in (AssetType.PRE_TAX, AssetType.TAX_DEFERRED)
    ]
    _brok_rates = [
        float(getattr(ai, "growth_rate_pct", 7.0))
        for ai in assets_input
        if ai.asset_type == AssetType.POST_TAX
        and "roth" not in getattr(ai, "name", "").lower()
    ]
    pretax_growth = sum(_pretax_rates) / len(_pretax_rates) if _pretax_rates else 7.0
    brok_growth   = sum(_brok_rates)  / len(_brok_rates)   if _brok_rates  else 7.0

    def _income_with_extra(extra: float) -> float:
        to_pretax = min(extra, pretax_capacity)
        to_brok   = extra - to_pretax

        pretax = roth = brok = brok_basis = 0.0
        for ai in assets_input:
            balance = float(getattr(ai, "current_balance", 0))
            contrib = float(getattr(ai, "annual_contribution", 0))
            rate    = float(getattr(ai, "growth_rate_pct", 7.0))
            fv      = future_value_with_contrib(balance, contrib, rate, years)
            name    = getattr(ai, "name", "").lower()
            atype   = ai.asset_type
            if atype in (AssetType.PRE_TAX, AssetType.TAX_DEFERRED):
                pretax += fv
            elif atype == AssetType.POST_TAX and "roth" in name:
                roth += fv
            elif atype == AssetType.POST_TAX:
                brok += fv
                brok_basis += balance + contrib * years

        # Additional contributions projected to retirement
        pretax += future_value_with_contrib(0.0, to_pretax, pretax_growth, years)
        brok   += future_value_with_contrib(0.0, to_brok,   brok_growth,   years)
        brok_basis += to_brok * years

        # Deduct life expenses proportionally
        total_fv = pretax + roth + brok
        if life_expenses > 0 and total_fv > 0:
            frac = life_expenses / total_fv
            pretax     = max(0.0, pretax     * (1.0 - frac))
            roth       = max(0.0, roth       * (1.0 - frac))
            brok       = max(0.0, brok       * (1.0 - frac))
            brok_basis = max(0.0, brok_basis * (1.0 - frac))

        income, _ = find_sustainable_withdrawal(
            pretax, roth, brok, brok_basis,
            retirement_age, life_expectancy,
            retirement_growth_rate, inflation_rate,
            retirement_tax_rate_pct,
            legacy_goal=legacy_goal,
        )
        return income

    # Check whether the goal is achievable within the search range
    if _income_with_extra(max_search) < target_income:
        return None, {
            "pretax": round(min(max_search, pretax_capacity)),
            "brokerage": round(max(0.0, max_search - pretax_capacity)),
            "irs_401k_limit": irs_401k_limit,
            "pretax_current": round(current_pretax_contrib),
            "pretax_capacity": round(pretax_capacity),
        }, True

    # Binary search — 60 iterations gives sub-dollar precision
    low, high = 0.0, max_search
    for _ in range(60):
        mid = (low + high) / 2.0
        if _income_with_extra(mid) >= target_income:
            high = mid
        else:
            low = mid

    additional = high
    to_pretax = min(additional, pretax_capacity)
    to_brok   = additional - to_pretax
    breakdown = {
        "pretax":           round(to_pretax),
        "brokerage":        round(to_brok),
        "irs_401k_limit":   irs_401k_limit,
        "pretax_current":   round(current_pretax_contrib),
        "pretax_capacity":  round(pretax_capacity),
    }
    return round(additional), breakdown, to_brok > 100


def find_required_portfolio(
    target_after_tax_income: float,
    retirement_age: int,
    life_expectancy: int,
    retirement_tax_rate_pct: float,
    growth_rate: float = 0.04,
    inflation_rate: float = 0.03,
    legacy_goal: float = 0.0,
    life_expenses: float = 0.0,
) -> dict:
    """Binary search for the minimum pre-tax portfolio that sustains `target_after_tax_income`/year.
    Assumes all assets are pre-tax (uniform treatment). Reuses find_sustainable_withdrawal so the
    reverse calculation stays consistent with the forward simulator.
    life_expenses is a lump sum deducted from the portfolio at retirement before simulation.
    """
    years = max(0, life_expectancy - retirement_age)
    if target_after_tax_income <= 0:
        # No income needed — but must still fund legacy_goal if set.
        # With 0 withdrawals the portfolio grows at growth_rate; solve for the
        # present-value of legacy_goal then add one-time expenses on top.
        if legacy_goal > 0 and years > 0:
            min_for_legacy = legacy_goal / ((1.0 + growth_rate) ** years)
        else:
            min_for_legacy = legacy_goal  # years==0: need full amount today
        required = min_for_legacy + life_expenses
        return {
            "required_pretax_portfolio": required,
            "confirmed_income": 0.0,
            "years_in_retirement": years,
            "growth_rate": growth_rate,
            "inflation_rate": inflation_rate,
            "tax_rate": retirement_tax_rate_pct,
            "legacy_goal": legacy_goal,
            "life_expenses": life_expenses,
        }

    low = 0.0
    # Upper bound: generous enough for high income goals + legacy targets + one-time expenses
    high = (target_after_tax_income + legacy_goal) * 200.0 + life_expenses

    for _ in range(60):
        mid = (low + high) / 2.0
        # Deduct life_expenses before simulating sustainable income
        effective_bal = max(0.0, mid - life_expenses)
        income, _ = find_sustainable_withdrawal(
            pretax_bal=effective_bal, roth_bal=0.0, brokerage_bal=0.0,
            brokerage_cost_basis=0.0,
            retirement_age=retirement_age,
            life_expectancy=life_expectancy,
            growth_rate=growth_rate,
            inflation_rate=inflation_rate,
            retirement_tax_rate_pct=retirement_tax_rate_pct,
            legacy_goal=legacy_goal,
        )
        if income < target_after_tax_income:
            low = mid
        else:
            high = mid

    required = high
    effective_bal = max(0.0, required - life_expenses)
    confirmed_income, _ = find_sustainable_withdrawal(
        pretax_bal=effective_bal, roth_bal=0.0, brokerage_bal=0.0,
        brokerage_cost_basis=0.0,
        retirement_age=retirement_age,
        life_expectancy=life_expectancy,
        growth_rate=growth_rate,
        inflation_rate=inflation_rate,
        retirement_tax_rate_pct=retirement_tax_rate_pct,
        legacy_goal=legacy_goal,
    )
    return {
        "required_pretax_portfolio": required,
        "confirmed_income": confirmed_income,
        "years_in_retirement": years,
        "growth_rate": growth_rate,
        "inflation_rate": inflation_rate,
        "tax_rate": retirement_tax_rate_pct,
        "legacy_goal": legacy_goal,
        "life_expenses": life_expenses,
    }


def generate_pdf_report(result: Dict[str, float], assets: List[Asset], user_inputs: Dict) -> bytes:
    """Generate a comprehensive PDF report of the retirement analysis."""
    if not _REPORTLAB_AVAILABLE:
        raise ImportError("reportlab is required for PDF generation. Install with: pip install reportlab")
    
    # Create PDF in memory
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        textColor=colors.darkblue
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=14,
        spaceAfter=8,
        textColor=colors.darkgreen
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        wordWrap='CJK',
    )
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        alignment=TA_LEFT,
        wordWrap='CJK',
    )
    table_cell_right_style = ParagraphStyle(
        'TableCellRight',
        parent=table_cell_style,
        alignment=TA_RIGHT,
    )
    
    # Build PDF content
    story = []
    
    # Title
    client_name = user_inputs.get('client_name', 'Client')
    story.append(Paragraph(f"Retirement Planning Analysis Report", title_style))
    story.append(Paragraph(f"Prepared for: {client_name}", 
                          ParagraphStyle('ClientName', parent=styles['Heading2'], fontSize=16, alignment=TA_CENTER, textColor=colors.darkgreen)))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Legal Disclaimer
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.red,
        alignment=TA_LEFT,
        spaceAfter=12,
        borderWidth=1,
        borderColor=colors.red,
        borderPadding=6
    )
    
    story.append(Paragraph("IMPORTANT LEGAL DISCLAIMER", 
                          ParagraphStyle('DisclaimerTitle', parent=styles['Heading3'], fontSize=12, textColor=colors.red, alignment=TA_CENTER)))
    story.append(Paragraph(
        "This report provides educational and informational content only. It is NOT financial, tax, legal, or investment advice. "
        "Results are based on general assumptions and may not be suitable for your specific situation. "
        "Past performance does not guarantee future results; all projections are estimates. "
        "Always consult with qualified financial advisors, tax professionals, and legal counsel before making financial decisions. "
        "You are solely responsible for your financial decisions and their consequences. "
        "The creators and operators of this application disclaim all liability for any losses, damages, or consequences arising from the use of this information. "
        "By using this report, you acknowledge and agree to these terms.",
        disclaimer_style
    ))
    story.append(Spacer(1, 20))
    
    # Executive Summary
    story.append(Paragraph("Executive Summary", heading_style))
    
    summary_data = [
        ["Metric", "Value"],
        ["Years Until Retirement", f"{result.get('Years Until Retirement', 0):.0f} years"],
        ["Total Future Value (Pre-Tax)", f"${result.get('Total Future Value (Pre-Tax)', 0):,.0f}"],
        ["Total After-Tax Balance", f"${result.get('Total After-Tax Balance', 0):,.0f}"],
        ["Total Tax Liability", f"${result.get('Total Tax Liability', 0):,.0f}"],
        ["Tax Efficiency", f"{result.get('Tax Efficiency (%)', 0):.1f}%"]
    ]
    
    summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(summary_table)
    story.append(Spacer(1, 20))

    # Asset Breakdown
    story.append(Paragraph("Asset Breakdown", heading_style))

    # Asset details table with proper formatting
    asset_data = [[
        Paragraph("Account", table_header_style),
        Paragraph("Tax Treatment", table_header_style),
        Paragraph("Current Balance", table_header_style),
        Paragraph("Annual Contribution", table_header_style),
        Paragraph("Growth Rate", table_header_style),
    ]]
    for asset in assets:
        asset_data.append([
            Paragraph(asset.name, table_cell_style),
            Paragraph(asset.asset_type.value.replace('_', ' ').title(), table_cell_style),
            Paragraph(f"${asset.current_balance:,.0f}", table_cell_right_style),
            Paragraph(f"${asset.annual_contribution:,.0f}", table_cell_right_style),
            Paragraph(f"{asset.growth_rate_pct}%", table_cell_right_style),
        ])

    # Wider account/tax columns and wrapped paragraphs prevent clipped text.
    asset_table = Table(asset_data, colWidths=[2.2*inch, 1.15*inch, 0.95*inch, 1.05*inch, 0.65*inch], repeatRows=1)
    asset_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9)
    ]))
    
    story.append(asset_table)
    story.append(Spacer(1, 12))

    story.append(Spacer(1, 20))

    # Individual Asset Results
    story.append(Paragraph("Individual Asset Projections", heading_style))
    
    # Find individual asset results
    asset_results = []
    for key, value in result.items():
        if "Asset" in key and "After-Tax" in key:
            asset_name = key.split(" - ")[1].replace(" (After-Tax)", "")
            asset_results.append([asset_name, f"${value:,.0f}"])
    
    if asset_results:
        asset_results_data = [["Account", "After-Tax Value at Retirement"]]
        asset_results_data.extend(asset_results)
        
        results_table = Table(asset_results_data, colWidths=[3*inch, 2*inch])
        results_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(results_table)
        story.append(Spacer(1, 20))
    
    # Retirement Income Analysis
    story.append(Paragraph("Retirement Income Analysis", heading_style))

    life_expectancy = user_inputs.get('life_expectancy', 85)
    retirement_age = user_inputs.get('retirement_age', 65)
    years_in_retirement = life_expectancy - retirement_age

    # Validate years in retirement
    if years_in_retirement <= 0:
        raise ValueError(f"Life expectancy ({life_expectancy}) must be greater than retirement age ({retirement_age})")

    # Use the same sequencing + RMD simulation as the What-If section.
    retirement_growth_rate = user_inputs.get('retirement_growth_rate', 4.0)
    inflation_rate = user_inputs.get('inflation_rate', 3)

    pdf_pretax_fv = sum(
        ar['pre_tax_value']
        for ar, ai in zip(result.get('asset_results', []), result.get('assets_input', []))
        if ai.asset_type in (AssetType.PRE_TAX, AssetType.TAX_DEFERRED)
    )
    pdf_roth_fv = sum(
        ar['pre_tax_value']
        for ar, ai in zip(result.get('asset_results', []), result.get('assets_input', []))
        if ai.asset_type == AssetType.POST_TAX and 'roth' in ai.name.lower()
    )
    pdf_brok_fv = sum(
        ar['pre_tax_value']
        for ar, ai in zip(result.get('asset_results', []), result.get('assets_input', []))
        if ai.asset_type == AssetType.POST_TAX and 'roth' not in ai.name.lower()
    )
    pdf_brok_basis = sum(
        ar['total_contributions'] + ai.current_balance
        for ar, ai in zip(result.get('asset_results', []), result.get('assets_input', []))
        if ai.asset_type == AssetType.POST_TAX and 'roth' not in ai.name.lower()
    )

    annual_retirement_income, cashflow_data = find_sustainable_withdrawal(
        pdf_pretax_fv, pdf_roth_fv, pdf_brok_fv, pdf_brok_basis,
        int(retirement_age), int(life_expectancy),
        retirement_growth_rate / 100.0, inflation_rate / 100.0,
        float(user_inputs.get('retirement_marginal_tax_rate_pct', 25.0)),
    )

    retirement_income_goal = user_inputs.get('retirement_income_goal', 0)
    income_shortfall = retirement_income_goal - annual_retirement_income
    income_ratio = (annual_retirement_income / retirement_income_goal * 100) if retirement_income_goal > 0 else 0
    
    income_data = [
        ["Metric", "Value"],
        ["Projected Annual Retirement Income", f"${annual_retirement_income:,.0f}"],
        ["Desired Annual Retirement Income", f"${retirement_income_goal:,.0f}"],
        ["Annual Shortfall/Surplus", f"${income_shortfall:,.0f}"],
        ["Income Goal Achievement", f"{income_ratio:.1f}%"]
    ]
    
    income_table = Table(income_data, colWidths=[3*inch, 2*inch])
    income_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(income_table)
    story.append(Spacer(1, 20))

    # Model limitation note for retirement income projection
    income_note_style = ParagraphStyle(
        'IncomeNote',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.orangered,
        borderWidth=1,
        borderColor=colors.orangered,
        borderPadding=6,
        spaceAfter=20
    )
    story.append(Paragraph(
        "<b>Important Modeling Note:</b> Retirement income is estimated from a one-time after-tax portfolio adjustment at retirement. "
        "This model does not yet simulate year-by-year withdrawal taxation, tax bracket changes, or dynamic withdrawal sequencing.",
        income_note_style
    ))
    story.append(Spacer(1, 12))
    
    # Tax Analysis
    story.append(Paragraph("Tax Analysis", heading_style))
    
    tax_liability = result.get("Total Tax Liability", 0)
    total_pre_tax = result.get("Total Future Value (Pre-Tax)", 1)
    tax_percentage = (tax_liability / total_pre_tax * 100) if total_pre_tax > 0 else 0
    tax_efficiency = result.get("Tax Efficiency (%)", 0)
    
    tax_analysis = f"""
    <b>Tax Efficiency Rating:</b> {tax_efficiency:.1f}%<br/>
    <b>Total Tax Liability:</b> ${tax_liability:,.0f}<br/>
    <b>Tax as % of Pre-Tax Value:</b> {tax_percentage:.1f}%<br/>
    <b>Current Marginal Tax Rate:</b> {user_inputs.get('current_marginal_tax_rate_pct', 0)}%<br/>
    <b>Projected Retirement Tax Rate:</b> {user_inputs.get('retirement_marginal_tax_rate_pct', 0)}%
    """
    
    story.append(Paragraph(tax_analysis, styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Recommendations
    story.append(Paragraph("Recommendations", heading_style))
    
    recommendations = []
    tax_percentage = (result.get("Total Tax Liability", 0) / result.get("Total Future Value (Pre-Tax)", 1) * 100) if result.get("Total Future Value (Pre-Tax)", 0) > 0 else 0
    if tax_efficiency > 85:
        recommendations.append("🎉 <b>Excellent tax efficiency!</b> Your portfolio is well-optimized with minimal tax liability.")
    elif tax_efficiency > 75:
        recommendations.append(f"⚠️ <b>Good tax efficiency</b> ({tax_percentage:.1f}% tax burden), but there may be room for improvement. <i>Goal: Lower this percentage by shifting assets to tax-advantaged accounts.</i>")
        recommendations.append("💡 <b>Tax Optimization Tips:</b>")
        recommendations.append("• Optimize asset location (taxable vs tax-advantaged accounts)")
        recommendations.append("• Consider Roth vs Traditional contributions based on tax rates")
        recommendations.append("• Maximize employer 401(k) match and HSA contributions")
        recommendations.append("• Use tax-loss harvesting and strategic withdrawal order")
    else:
        recommendations.append("🚨 <b>Consider tax optimization</b> strategies to improve efficiency.")
        recommendations.append("⚠️ <b>Priority Actions:</b>")
        recommendations.append("• Review asset allocation across account types")
        recommendations.append("• Maximize tax-advantaged contributions (401k, IRA, HSA)")
        recommendations.append("• Consider Roth conversions during low-income years")
        recommendations.append("• Switch to tax-efficient index funds")
    
    if len(assets) < 3:
        recommendations.append("💡 Consider diversifying across more account types for better tax optimization.")
    
    # Check for high-growth assets
    high_growth_assets = [a for a in assets if a.growth_rate_pct > 8]
    if high_growth_assets:
        recommendations.append("📈 You have high-growth assets - ensure proper risk management.")
    
    # Check for low-growth assets
    low_growth_assets = [a for a in assets if a.growth_rate_pct < 5]
    if low_growth_assets:
        recommendations.append("💰 Consider if low-growth assets align with your retirement timeline.")
    
    for rec in recommendations:
        story.append(Paragraph(rec, styles['Normal']))
        story.append(Spacer(1, 6))
    
    story.append(Spacer(1, 20))

    # Cash Flow Table (year-by-year) at bottom of report.
    story.append(PageBreak())
    story.append(Paragraph("Cash Flow Projection (Year-by-Year)", heading_style))

    cashflow_header = [
        Paragraph("Year", table_header_style),
        Paragraph("Age", table_header_style),
        Paragraph("RMD", table_header_style),
        Paragraph("Brokerage W/D", table_header_style),
        Paragraph("Roth W/D", table_header_style),
        Paragraph("Extra Pre-Tax", table_header_style),
        Paragraph("Tax Paid", table_header_style),
        Paragraph("After-Tax Income", table_header_style),
        Paragraph("Total Portfolio", table_header_style),
    ]
    cashflow_rows = [cashflow_header]

    for row in cashflow_data:
        cashflow_rows.append([
            Paragraph(str(int(row["year"])), table_cell_right_style),
            Paragraph(str(int(row["age"])), table_cell_right_style),
            Paragraph(f"${row['rmd']:,.0f}" if row["rmd"] > 0 else "-", table_cell_right_style),
            Paragraph(f"${row['brokerage_withdrawal']:,.0f}" if row["brokerage_withdrawal"] > 0 else "-", table_cell_right_style),
            Paragraph(f"${row['roth_withdrawal']:,.0f}" if row["roth_withdrawal"] > 0 else "-", table_cell_right_style),
            Paragraph(f"${row['extra_pretax_withdrawal']:,.0f}" if row["extra_pretax_withdrawal"] > 0 else "-", table_cell_right_style),
            Paragraph(f"${row['total_tax']:,.0f}", table_cell_right_style),
            Paragraph(f"${row['actual_aftertax']:,.0f}", table_cell_right_style),
            Paragraph(f"${row['total_portfolio_end']:,.0f}", table_cell_right_style),
        ])

    cashflow_table = Table(
        cashflow_rows,
        colWidths=[0.35*inch, 0.35*inch, 0.55*inch, 0.7*inch, 0.55*inch, 0.7*inch, 0.55*inch, 0.85*inch, 0.85*inch],
        repeatRows=1,
    )
    cashflow_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(cashflow_table)
    story.append(Spacer(1, 12))

    # Footer Disclaimer
    story.append(Paragraph("DISCLAIMER: This report is for educational purposes only and does not constitute professional financial advice. Consult qualified professionals before making financial decisions.",
                          ParagraphStyle('FooterDisclaimer', parent=styles['Normal'], fontSize=7, alignment=TA_CENTER, textColor=colors.red)))
    story.append(Spacer(1, 12))

    # Contact Information
    contact_style = ParagraphStyle('ContactInfo', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER, textColor=colors.darkblue)
    story.append(Paragraph(f"<b>Smart Retire AI v{VERSION}</b>", contact_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Questions or feedback? Contact us at <b>smartretireai@gmail.com</b>", contact_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"Report generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
                          ParagraphStyle('ReportDate', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, textColor=colors.grey)))

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ==========================================
# DIALOG FUNCTIONS FOR NEXT STEPS
# ==========================================

@st.dialog("📄 Generate PDF Report")
def generate_report_dialog():
    """Dialog for generating and downloading PDF report."""
    st.markdown("""
    Create a comprehensive PDF report with:
    - Executive summary of your retirement plan
    - Detailed portfolio breakdown
    - Individual asset projections
    - Tax analysis and optimization strategies
    - Personalized recommendations
    """)

    st.markdown("---")

    # Name input
    report_name = st.text_input(
        "Your Name (Optional)",
        value=st.session_state.get('client_name', ''),
        placeholder="Enter your name for the report",
        help="This will appear on the PDF report"
    )

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("❌ Cancel",use_container_width=True):
            st.rerun()

    with col2:
        if st.button("📥 Generate PDF", type="primary",use_container_width=True):
            if not _REPORTLAB_AVAILABLE:
                st.error("⚠️ **PDF generation not available.** Install reportlab to enable PDF downloads:")
                st.code("pip install reportlab", language="bash")
                return

            try:
                # Get the result and assets from session state
                if 'last_result' not in st.session_state or 'assets' not in st.session_state:
                    st.error("❌ No analysis results found. Please run the analysis first.")
                    return

                result = st.session_state.last_result
                assets = st.session_state.assets

                # Prepare user inputs for PDF
                user_inputs = {
                    'client_name': report_name if report_name else 'Client',
                    'current_marginal_tax_rate_pct': st.session_state.get('whatif_current_tax_rate', 22),
                    'retirement_marginal_tax_rate_pct': st.session_state.get('whatif_retirement_tax_rate', 25),
                    'inflation_rate_pct': st.session_state.get('whatif_inflation_rate', 3),
                    'age': datetime.now().year - st.session_state.birth_year,
                    'retirement_age': int(st.session_state.get('whatif_retirement_age', 65)),
                    'life_expectancy': int(st.session_state.get('whatif_life_expectancy', 85)),
                    'birth_year': st.session_state.birth_year,
                    'retirement_income_goal': st.session_state.get('whatif_retirement_income_goal', 0),
                    'retirement_growth_rate': st.session_state.get('whatif_retirement_growth_rate', 4.0),
                    'inflation_rate': st.session_state.get('whatif_inflation_rate', 3)
                }

                # Generate PDF
                with st.spinner("Generating PDF report..."):
                    pdf_bytes = generate_pdf_report(result, assets, user_inputs)

                # Create filename
                client_name_clean = report_name.replace(" ", "_").replace(",", "").replace(".", "") if report_name else "Client"
                filename = f"retirement_analysis_{client_name_clean}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

                # Track successful PDF generation
                track_pdf_generation(success=True)

                # Show download button
                st.success("✅ PDF report generated successfully!")
                st.download_button(
                    label="📥 Download PDF Report",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    use_container_width=True
                )

            except Exception as e:
                # Track failed PDF generation
                track_pdf_generation(success=False)
                track_error('pdf_generation_error', str(e), {'report_name': report_name})

                st.error(f"❌ Error generating PDF: {str(e)}")
                st.info("💡 Try refreshing the page and running the analysis again.")


@st.dialog("🎲 Run Scenario Analysis")
def monte_carlo_dialog():
    """Dialog for configuring and running Monte Carlo simulation."""
    st.markdown("""
    Explore thousands of possible retirement scenarios to understand:
    - Range of potential retirement income
    - Best-case and worst-case outcomes
    - Probability of meeting your goals
    - Impact of market volatility
    """)

    st.markdown("---")

    # Configuration options
    col1, col2 = st.columns(2)

    with col1:
        num_simulations = st.select_slider(
            "Number of Scenarios",
            options=[100, 500, 1000, 5000, 10000],
            value=1000,
            help="More scenarios = more accurate results but slower processing"
        )

    with col2:
        volatility = st.slider(
            "Market Volatility (%)",
            min_value=5.0,
            max_value=30.0,
            value=15.0,
            step=1.0,
            help="Historical stock market volatility is ~15-20%. Higher = more uncertainty."
        )

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("❌ Cancel",use_container_width=True):
            st.rerun()

    with col2:
        if st.button("🚀 Run Analysis", type="primary",use_container_width=True):
            # Store configuration in session state and navigate to Monte Carlo page
            st.session_state.monte_carlo_config = {
                'num_simulations': num_simulations,
                'volatility': volatility
            }
            st.session_state.current_page = 'monte_carlo'
            st.rerun()


_ADJUST_EDITOR_COLUMN_CONFIG = {
    "Account Name": st.column_config.TextColumn("Account Name"),
    "Tax Treatment": st.column_config.SelectboxColumn(
        "Tax Treatment",
        options=["Pre-Tax", "Tax-Deferred", "Tax-Free", "Post-Tax"],
        required=True,
    ),
    "Current Balance": st.column_config.NumberColumn(
        "Current Balance", format="$%.2f", min_value=0
    ),
    "Annual Contribution": st.column_config.NumberColumn(
        "Annual Contribution", format="$%.0f", min_value=0
    ),
    "Growth Rate (%)": st.column_config.NumberColumn(
        "Growth Rate (%)", format="%.1f%%", min_value=0.0, max_value=30.0
    ),
    "Tax Rate on Gains (%)": st.column_config.NumberColumn(
        "Tax Rate on Gains (%)", disabled=True, format="%.1f%%"
    ),
}


def _assets_to_editor_df(assets) -> "pd.DataFrame":
    """Convert a list of Asset objects to a DataFrame for st.data_editor."""
    rows = [
        {
            "Account Name": a.name,
            "Tax Treatment": _asset_to_tax_treatment_label(a),
            "Current Balance": a.current_balance,
            "Annual Contribution": a.annual_contribution,
            "Growth Rate (%)": a.growth_rate_pct,
            "Tax Rate on Gains (%)": a.tax_rate_pct,
        }
        for a in assets
    ]
    return pd.DataFrame(rows)


@st.dialog("Manage Your Portfolio", width="large")
def adjust_assets_dialog():
    def _clear_preview():
        st.session_state.pop("adjust_assets_table_df", None)
        st.session_state.pop("adjust_assets_result", None)
        st.session_state.pop("adjust_assets_new_names", None)
        st.session_state.pop("adjust_assets_edit_mode", None)

    def _do_clear_all():
        _clear_preview()
        clear_detailed_planning_asset_state(st.session_state)
        for _k in ("results_chat_messages", "results_chat_context", "results_chat_whatif_modified"):
            st.session_state.pop(_k, None)
        st.session_state.show_adjust_assets_dialog = False
        st.session_state.current_page = "detailed_planning"
        st.session_state.onboarding_step = 2

    # ── Edit mode: edit existing portfolio without uploading ──────────────
    if st.session_state.get("adjust_assets_edit_mode"):
        existing = list(st.session_state.get("assets", []))
        st.caption(f"Edit your **{len(existing)} existing account(s)**. Changes take effect when you save.")

        edit_df = st.data_editor(
            _assets_to_editor_df(existing),
            column_config=_ADJUST_EDITOR_COLUMN_CONFIG,
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            key="adjust_assets_edit_editor",
        )

        col_save, col_cancel = st.columns(2)
        with col_save:
            if st.button("Save Changes", type="primary", use_container_width=True):
                try:
                    updated = [_asset_from_editor_row(r) for _, r in edit_df.iterrows()]
                except Exception as _e:
                    st.error(f"Could not save — check account data: {_e}")
                    st.stop()
                st.session_state.assets = updated
                st.session_state.adjust_assets_toast = (
                    f"Portfolio updated — now tracking {len(updated)} account(s)."
                )
                _clear_preview()
                st.session_state.show_adjust_assets_dialog = False
                st.rerun()
        with col_cancel:
            if st.button("← Back", use_container_width=True):
                st.session_state.pop("adjust_assets_edit_mode", None)
                st.rerun()

        st.markdown("---")
        st.markdown("**Start over from scratch?**")
        if st.button("🗑️ Clear All Assets", use_container_width=True, key="clear_all_edit"):
            _do_clear_all()
            st.rerun()
        return

    # ── Phase 2: review & edit merged table ──────────────────────────────
    if "adjust_assets_table_df" in st.session_state:
        _result_meta = st.session_state.get("adjust_assets_result", {})
        new_names: set = st.session_state.get("adjust_assets_new_names", set())
        _df: pd.DataFrame = st.session_state.adjust_assets_table_df

        _n_new = len(new_names)
        _n_total = len(_df)
        _skipped = _result_meta.get("skipped_dupes", 0)
        st.success("✅ Extraction Complete!")
        st.info(
            f"**{_n_new} new account(s)** added to your {_n_total}-account portfolio."
            + (f" {_skipped} duplicate(s) skipped." if _skipped else "")
        )

        _warnings = _result_meta.get("warnings", [])
        if _warnings:
            with st.expander(f"⚠️ {len(_warnings)} warning(s)"):
                for w in _warnings:
                    st.markdown(f"- {w}")

        st.markdown("Adjust contributions or growth rates, then save.")

        edited_df = st.data_editor(
            _df,
            column_config=_ADJUST_EDITOR_COLUMN_CONFIG,
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            key="adjust_assets_editor",
        )

        col_save, col_back = st.columns(2)
        with col_save:
            if st.button("Save & Update Portfolio", type="primary", use_container_width=True):
                try:
                    updated = [_asset_from_editor_row(r) for _, r in edited_df.iterrows()]
                except Exception as _e:
                    st.error(f"Could not save — check account data: {_e}")
                    st.stop()

                st.session_state.assets = updated

                added_names = [a.name for a in updated if a.name.lower() in new_names]
                if added_names:
                    account_list = ", ".join(f"**{n}**" for n in added_names)
                    ack = (
                        f"I've added {len(added_names)} new account(s) to your portfolio: {account_list}. "
                        "The projections above have been updated to reflect your complete portfolio. "
                        "What would you like to explore about your updated retirement outlook?"
                    )
                    chat_msgs = st.session_state.get("results_chat_messages") or []
                    chat_msgs.append({"role": "assistant", "content": ack})
                    st.session_state.results_chat_messages = chat_msgs

                st.session_state.adjust_assets_toast = (
                    f"Portfolio updated — now tracking {len(updated)} account(s)."
                )
                _clear_preview()
                st.session_state.show_adjust_assets_dialog = False
                st.rerun()
        with col_back:
            if st.button("← Upload More", use_container_width=True):
                _clear_preview()
                st.rerun()

        st.markdown("---")
        st.markdown("**Start over from scratch?**")
        if st.button("🗑️ Clear All Assets", use_container_width=True, key="clear_all_phase2"):
            _do_clear_all()
            st.rerun()
        return

    # ── Phase 1: upload ───────────────────────────────────────────────────
    existing = list(st.session_state.get("assets", []))
    st.caption(
        f"Currently tracking **{len(existing)} account(s)**. "
        "Uploaded statements will be merged — existing data is untouched."
    )

    uploaded = st.file_uploader(
        "Upload additional statements (PDF or CSV)",
        type=["pdf", "csv"],
        accept_multiple_files=True,
        key="adjust_assets_uploader",
    )

    if st.button(
        "Process & Add to Portfolio",
        type="primary",
        use_container_width=True,
        disabled=not uploaded,
    ):
        if not _N8N_AVAILABLE:
            st.error("Statement processor not available — required packages are missing.")
            return
        _proc_ok, _proc_err = check_processor_configured()
        if not _proc_ok:
            st.error(_proc_err)
            return
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            import time as _time

            status_text.markdown("**📤 Phase 1/2: Uploading Files**")
            progress_bar.progress(10)

            processor = get_processor()
            _processor_type = "python" if processor.__class__.__name__ == "StatementProcessor" else "n8n"

            files_to_upload = [(f.name, f.getvalue()) for f in uploaded]

            status_text.markdown(
                f"**📤 Uploading** {len(files_to_upload)} file(s)…"
            )
            progress_bar.progress(25)

            _total_files = len(files_to_upload)
            _progress_per_file = 48 / max(_total_files, 1)

            def _make_progress_callback(
                _status=status_text,
                _bar=progress_bar,
                _slice=_progress_per_file,
                _ai_start=_time.time(),
            ):
                def _cb(stage, file_idx, total_files, filename, chunk_idx, total_chunks):
                    short_name = filename if len(filename) <= 30 else f"…{filename[-27:]}"
                    elapsed = int(_time.time() - _ai_start)
                    file_label = f"file {file_idx + 1}/{total_files}"
                    files_done_pct = file_idx * _slice
                    if stage == "text_extract":
                        within = 0.05 * _slice
                        pct = int(40 + files_done_pct + within)
                        _status.markdown(
                            f"**📄 Reading** {short_name} ({file_label}) ⏱️ {elapsed}s"
                        )
                    elif stage == "ai_call":
                        chunk_label = (
                            f" part {chunk_idx + 1}/{total_chunks}"
                            if total_chunks > 1 else ""
                        )
                        within = (0.1 + 0.85 * (chunk_idx / max(total_chunks, 1))) * _slice
                        pct = int(40 + files_done_pct + within)
                        _status.markdown(
                            f"**🤖 Analyzing** {short_name}{chunk_label} ({file_label}) ⏱️ {elapsed}s"
                        )
                    elif stage == "file_done":
                        within = _slice
                        pct = int(40 + files_done_pct + within)
                        _status.markdown(
                            f"**✅ Done** {short_name} ({file_label}) ⏱️ {elapsed}s"
                        )
                    else:
                        pct = int(40 + files_done_pct)
                    _bar.progress(min(pct, 88))
                return _cb

            _progress_cb = _make_progress_callback() if _processor_type == "python" else None

            status_text.markdown(
                f"**🤖 Analyzing** {_total_files} statement(s)…"
            )
            progress_bar.progress(40)

            if _processor_type == "python":
                result = processor.upload_statements(files_to_upload, progress_callback=_progress_cb)
            else:
                result = processor.upload_statements(files_to_upload)

            progress_bar.progress(90)

        except Exception as e:
            st.error(f"Processing failed: {e}")
            return

        if not result.get("success") or not result.get("data"):
            progress_bar.progress(100)
            st.error("No accounts could be extracted from these files.")
            return

        progress_bar.progress(100)
        status_text.markdown(
            "**✅ Extraction Complete!**"
        )

        new_assets = _raw_accounts_to_assets(result["data"])

        # Deduplicate by name (case-insensitive) AND by balance
        # (same exact balance = almost certainly the same account under a different label)
        existing_names = {a.name.lower() for a in existing}
        existing_balance_map = {
            round(a.current_balance, 2): a.name
            for a in existing
            if a.current_balance > 0
        }

        unique_new: list = []
        dupe_warnings: list = []
        for a in new_assets:
            if a.name.lower() in existing_names:
                dupe_warnings.append(
                    f"Skipped **{a.name}** — same name as an existing account."
                )
            elif a.current_balance > 0 and round(a.current_balance, 2) in existing_balance_map:
                matched = existing_balance_map[round(a.current_balance, 2)]
                dupe_warnings.append(
                    f"Skipped **{a.name}** (${a.current_balance:,.2f}) "
                    f"— balance matches existing account **{matched}**."
                )
            else:
                unique_new.append(a)

        skipped = len(new_assets) - len(unique_new)

        if not unique_new:
            st.warning("All extracted accounts already exist in your portfolio — nothing new to add.")
            if dupe_warnings:
                with st.expander("Details"):
                    for w in dupe_warnings:
                        st.markdown(f"- {w}")
            return

        merged = existing + unique_new
        all_warnings = dupe_warnings + list(result.get("warnings", []))
        st.session_state.adjust_assets_table_df = _assets_to_editor_df(merged)
        st.session_state.adjust_assets_new_names = {a.name.lower() for a in unique_new}
        st.session_state.adjust_assets_result = {
            "skipped_dupes": skipped,
            "warnings": all_warnings,
        }
        st.rerun()

    st.markdown("---")
    col_edit, col_clear = st.columns(2)
    with col_edit:
        if st.button("✏️ Edit Existing Portfolio", use_container_width=True):
            st.session_state.adjust_assets_edit_mode = True
            st.rerun()
    with col_clear:
        if st.button("🗑️ Clear All Assets", use_container_width=True, key="clear_all_phase1"):
            _do_clear_all()
            st.rerun()


@st.dialog("📊 Cash Flow Projection", width="large")
def cashflow_dialog():
    """Dialog showing the year-by-year retirement cash flow table."""
    sim_data = st.session_state.get("cashflow_sim_data")

    if not sim_data:
        st.info("Run a retirement analysis first to see the cash flow projection.")
        return

    import pandas as pd

    chart_df = pd.DataFrame({
        "Portfolio Balance": [row["total_portfolio_end"] for row in sim_data],
        "Annual After-Tax Income": [row["actual_aftertax"] for row in sim_data],
    }, index=[row["age"] for row in sim_data])
    chart_df.index.name = "Age"
    st.caption("Portfolio balance and annual after-tax income over retirement (age on x-axis)")
    st.line_chart(chart_df)
    st.markdown("---")

    _col_cfg = {
        "Year":          st.column_config.NumberColumn("Year",          format="%d"),
        "Age":           st.column_config.NumberColumn("Age",           format="%d"),
        "RMD":           st.column_config.TextColumn("RMD"),
        "Brokerage W/D": st.column_config.TextColumn("Brokerage W/D"),
        "Roth W/D":      st.column_config.TextColumn("Roth W/D"),
        "Extra Pre-Tax": st.column_config.TextColumn("Extra Pre-Tax"),
        "Tax Paid":      st.column_config.TextColumn("Tax Paid"),
        "After-Tax Income (adjusted for inflation)": st.column_config.TextColumn(
            "After-Tax Income (adjusted for inflation)",
            help="Each year the model grows all account pots, pays any forced RMD, then draws from brokerage → pre-tax → Roth until the target income is met. The target is the maximum first-year withdrawal that fully depletes the portfolio by your life expectancy.",
        ),
        "Total Portfolio": st.column_config.TextColumn("Total Portfolio"),
    }

    withdrawal_data = []
    for row in sim_data:
        withdrawal_data.append({
            "Year":          row["year"],
            "Age":           row["age"],
            "RMD":           f"${row['rmd']:,.0f}"                     if row["rmd"] > 0                     else None,
            "Brokerage W/D": f"${row['brokerage_withdrawal']:,.0f}"    if row["brokerage_withdrawal"] > 0    else None,
            "Roth W/D":      f"${row['roth_withdrawal']:,.0f}"         if row["roth_withdrawal"] > 0         else None,
            "Extra Pre-Tax": f"${row['extra_pretax_withdrawal']:,.0f}" if row["extra_pretax_withdrawal"] > 0 else None,
            "Tax Paid":      f"${row['total_tax']:,.0f}",
            "After-Tax Income (adjusted for inflation)": f"${row['actual_aftertax']:,.0f}",
            "Total Portfolio": f"${row['total_portfolio_end']:,.0f}",
        })

    df_withdrawals = pd.DataFrame(withdrawal_data)
    st.dataframe(df_withdrawals,use_container_width=True, hide_index=True, column_config=_col_cfg)

    if st.button("Close",use_container_width=True):
        st.rerun()


@st.dialog("💡 Reminder: Adjust Annual Contributions")
def contribution_reminder_dialog():
    """Dialog to remind users to adjust contributions before finishing onboarding."""
    st.markdown("""
    ### 📊 For More Accurate Projections

    We noticed you haven't set any annual contributions yet. Adding your expected annual
    contributions will significantly improve the accuracy of your retirement projections.

    **Why contributions matter:**
    - 🎯 More realistic projections of your future retirement balance
    - 📈 Better understanding of your retirement income potential
    - 💰 More accurate income gap recommendations

    **You can adjust contributions in the asset table above:**
    - Click the "Annual Contribution" cells to edit them
    - Set to $0 if you're no longer contributing to an account
    - Use your actual planned contribution amounts for the most accurate results
    """)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("← Go Back and Adjust",use_container_width=True, type="primary"):
            # Clear the flag and close dialog
            if 'show_contribution_reminder' in st.session_state:
                del st.session_state.show_contribution_reminder
            st.rerun()

    with col2:
        if st.button("Continue Anyway →",use_container_width=True):
            # User chose to proceed without adjusting contributions
            st.session_state.contribution_reminder_dismissed = True
            if 'show_contribution_reminder' in st.session_state:
                del st.session_state.show_contribution_reminder
            # Advance to results page
            st.session_state.current_page = 'results'
            st.session_state.results_source = 'onboarding'
            st.rerun()



def show_mode_selection_page():
    """Full-page mode selection: Simple (chat) vs Detailed (form). Shown after splash."""
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        "<h2 style='text-align:center;'>How would you like to plan your retirement?</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center; color:#666;'>Choose the experience that works best for you.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    col_simple, col_detailed = st.columns(2, gap="large")

    with col_simple:
        st.markdown(
            """
            <div style='border:2px solid #1f77b4; border-radius:12px; padding:28px 24px; min-height:220px;'>
                <div style='font-size:2.2em; text-align:center;'>💬</div>
                <h3 style='text-align:center; color:#1f77b4;'>Simple Planning</h3>
                <p style='text-align:center; color:inherit;'>
                    Tell me your <strong>income goal</strong> and I'll calculate
                    how much you need to retire. Guided chat — no forms.
                </p>
                <p style='text-align:center; font-size:0.85em; color:#888;'>
                    Best for: quick estimates &amp; what-if exploration
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Start Chat →", type="primary",use_container_width=True, key="mode_select_simple"):
            st.session_state.pop("planning_mode_choice", None)
            st.session_state.current_page = "chat_mode"
            st.session_state.chat_messages = []
            st.session_state.chat_fields = {}
            st.session_state.chat_complete = False
            st.rerun()

    with col_detailed:
        st.markdown(
            """
            <div style='border:2px solid #2ca02c; border-radius:12px; padding:28px 24px; min-height:220px;'>
                <div style='font-size:2.2em; text-align:center;'>📊</div>
                <h3 style='text-align:center; color:#2ca02c;'>Detailed Planning</h3>
                <p style='text-align:center; color:inherit;'>
                    Enter your <strong>actual US retirement accounts</strong> and see
                    detailed projections, tax analysis, and withdrawal strategy.
                </p>
                <p style='text-align:center; font-size:0.85em; color:#888;'>
                    US-only detailed account-based planning
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Enter Details →",use_container_width=True, key="mode_select_detailed"):
            st.session_state.pop("planning_mode_choice", None)
            st.session_state.current_page = "detailed_planning"
            st.session_state.onboarding_step = 1
            st.rerun()


def show_chat_mode_page():
    """Chat + live results split-pane for Mode 2 (Income Goal → Portfolio)."""
    _CHAT_DEFAULTS_US = {"retirement_age": 65, "life_expectancy": 90, "tax_rate": 22, "growth_rate": 4.0, "inflation_rate": 3.0}
    _CHAT_DEFAULTS_IN = {"retirement_age": 60, "life_expectancy": 85, "tax_rate": 10, "growth_rate": 10.0, "inflation_rate": 7.0}

    # Initialize chat session state on first visit
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "chat_fields" not in st.session_state:
        st.session_state.chat_fields = {}
    if "chat_complete" not in st.session_state:
        st.session_state.chat_complete = False

    fields = st.session_state.chat_fields
    country = fields.get("country", "US")
    is_india = country == "India"
    _sym = "₹" if is_india else "$"
    _corpus_label = "Corpus" if is_india else "Portfolio"
    _defaults = _CHAT_DEFAULTS_IN if is_india else _CHAT_DEFAULTS_US

    # Header
    st.markdown("### 💬 Simple Retirement Planner")
    _chat_nav_left, _chat_nav_mid, _chat_nav_right = st.columns([1.3, 1.6, 1.3])
    with _chat_nav_left:
        if st.button("← Change planning mode", key="chat_back_to_mode_select",use_container_width=True):
            st.session_state.current_page = "mode_selection"
            st.rerun()
    with _chat_nav_right:
        if st.button("Switch to Detailed Planning (US-only)", key="chat_to_detailed",use_container_width=True, disabled=is_india):
            switch_to_detailed_planning_from_chat()

    st.markdown("---")

    chat_col, results_col = st.columns([1, 1], gap="large")

    # ── LEFT: Chat ──────────────────────────────────────────────────────────
    with chat_col:
        st.markdown("#### Chat")

        # Fixed-height scrollable message history — keeps input always visible below
        _msgs_box = st.container(height=460)
        with _msgs_box:
            # Initial greeting if conversation is empty — append first, then let the loop render
            if not st.session_state.chat_messages and _CHAT_AVAILABLE:
                opening = (
                    "Hi! Three quick questions to get started:\n\n"
                    "1. **Country** — are you planning for 🇺🇸 US or 🇮🇳 India?\n"
                    "2. **Birth year** — so I can calculate your age.\n"
                    "3. **Target income** — how much annual after-tax income would you like in retirement?"
                )
                st.session_state.chat_messages.append({"role": "assistant", "content": opening})

            # Render conversation history (single render path for all messages)
            for msg in st.session_state.chat_messages:
                avatar = "🧑‍💼" if msg["role"] == "assistant" else "🧑"
                with st.chat_message(msg["role"], avatar=avatar):
                    st.markdown(msg["content"])

        if not _CHAT_AVAILABLE:
            st.warning("Chat requires the `openai` package and an `OPENAI_API_KEY`. Run `pip install openai` and set the key in your `.env` file.")
        elif not os.getenv("OPENAI_API_KEY"):
            st.warning("Set `OPENAI_API_KEY` in your `.env` file to enable the chat advisor.")
        else:
            # Chat input sits below the fixed-height box, always visible
            user_input = st.chat_input("Type your answer or ask a what-if question…")
            if user_input:
                st.session_state.chat_messages.append({"role": "user", "content": user_input})

                # Detect country from current message so system prompt uses the right currency
                # before chat_fields has been populated (first-message timing issue)
                _msg_lower = user_input.lower()
                if "india" in _msg_lower:
                    _call_country = "India"
                elif any(w in _msg_lower for w in ("us", "usa", "united states", "america")):
                    _call_country = "US"
                else:
                    _call_country = country  # already confirmed in a prior turn

                with st.spinner(""):
                    try:
                        display_msg, new_fields = chat_with_advisor(
                            st.session_state.chat_messages,
                            country=_call_country,
                            calc_context=st.session_state.get("chat_calc_context"),
                        )
                    except Exception as e:
                        display_msg = f"Sorry, I ran into an error: {e}"
                        new_fields = {}

                # Merge confirmed fields
                for k, v in new_fields.items():
                    if k != "done" and v is not None:
                        st.session_state.chat_fields[k] = v

                if new_fields.get("done"):
                    st.session_state.chat_complete = True

                # Escape bare $ so Streamlit doesn't treat $...$ as LaTeX math
                display_msg = display_msg.replace("$", r"\$")
                st.session_state.chat_messages.append({"role": "assistant", "content": display_msg})
                st.rerun()

        # Download transcript button — visible once there are messages
        if st.session_state.chat_messages:
            def _build_chat_transcript(messages, fields, _is_india):
                sym = "₹" if _is_india else "$"
                lines = [
                    "# Smart Retire AI — Chat Transcript",
                    f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    "",
                    "---",
                    "",
                ]
                for msg in messages:
                    speaker = "**You:**" if msg["role"] == "user" else "**Advisor:**"
                    lines.append(f"{speaker} {msg['content']}")
                    lines.append("")
                if fields:
                    lines += ["---", "", "## Your Retirement Plan Summary", ""]
                    label_map = {
                        "country": "Country",
                        "birth_year": "Birth Year",
                        "retirement_age": "Retirement Age",
                        "life_expectancy": "Life Expectancy (age)",
                        "target_income": f"Target Income ({sym}/yr)",
                        "tax_rate": "Tax Rate (%)",
                        "growth_rate": "Growth Rate (%)",
                        "inflation_rate": "Inflation Rate (%)",
                        "legacy_goal": f"Legacy Goal ({sym})",
                        "life_expenses": f"One-Time Expenses ({sym})",
                    }
                    for key, label in label_map.items():
                        val = fields.get(key)
                        if val is not None:
                            lines.append(f"- **{label}:** {val}")
                return "\n".join(lines)

            _transcript = _build_chat_transcript(
                st.session_state.chat_messages,
                st.session_state.chat_fields,
                is_india,
            )
            _fname = f"retirement_chat_{datetime.now().strftime('%Y%m%d')}.md"
            st.download_button(
                "⬇ Download transcript",
                data=_transcript,
                file_name=_fname,
                mime="text/markdown",
                use_container_width=True,
                key="chat_download_btn",
            )

    # ── RIGHT: Live Results ──────────────────────────────────────────────────
    with results_col:
        st.markdown(f"#### Your {_corpus_label} Estimate")

        # Fixed-height container mirrors the chat box height so the panel floats alongside the chat
        _results_box = st.container(height=460)

        # Check if we have enough to calculate
        _f = st.session_state.chat_fields
        _ret_age = _f.get("retirement_age")
        _life_exp = _f.get("life_expectancy")
        _target = _f.get("target_income")
        _birth_year = _f.get("birth_year")

        _has_required = all(v is not None for v in [_ret_age, _life_exp, _target])

        def _to_float(val, fallback=None):
            """Strip commas/currency symbols and convert to float; return fallback on failure."""
            try:
                return float(str(val).replace(",", "").replace("₹", "").replace("$", "").strip())
            except (ValueError, TypeError):
                return fallback

        def _to_int(val, fallback=None):
            f = _to_float(val)
            return int(f) if f is not None else fallback

        with _results_box:
            if not _has_required:
                st.markdown(
                    """
                    <div style='border:1px dashed #ccc; border-radius:8px; padding:32px; text-align:center; color:#999; margin-top:16px;'>
                        <div style='font-size:2em;'>📋</div>
                        <p>Your plan will appear here as you answer the questions on the left.</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                _ret_age_i  = _to_int(_ret_age)
                _life_exp_i = _to_int(_life_exp)
                _target_f   = _to_float(_target)

                # Validate
                _errors = []
                if _ret_age_i is None or _life_exp_i is None:
                    _errors.append("Could not parse retirement age or life expectancy — please re-enter as plain numbers.")
                elif _life_exp_i <= _ret_age_i:
                    _errors.append("Life expectancy must be greater than retirement age.")
                if _target_f is None:
                    _errors.append("Could not parse target income — please re-enter as a plain number.")
                elif _target_f < 0:
                    _errors.append("Target income cannot be negative.")

                if _errors:
                    for e in _errors:
                        st.error(e)
                else:
                    _tax = _to_float(_f.get("tax_rate", _defaults["tax_rate"]), _defaults["tax_rate"])
                    _growth = _to_float(_f.get("growth_rate", _defaults["growth_rate"]), _defaults["growth_rate"]) / 100.0
                    _inflation = _to_float(_f.get("inflation_rate", _defaults["inflation_rate"]), _defaults["inflation_rate"]) / 100.0
                    _legacy = _to_float(_f.get("legacy_goal", 0), 0)
                    _expenses = _to_float(_f.get("life_expenses", 0), 0)

                    try:
                        _r = find_required_portfolio(
                            target_after_tax_income=_target_f,
                            retirement_age=_ret_age_i,
                            life_expectancy=_life_exp_i,
                            retirement_tax_rate_pct=_tax,
                            growth_rate=_growth,
                            inflation_rate=_inflation,
                            legacy_goal=_legacy,
                            life_expenses=_expenses,
                        )

                        st.metric(
                            f"Required {_corpus_label} at Retirement",
                            _fmt_currency(_r["required_pretax_portfolio"], is_india),
                        )
                        st.metric(
                            "Modeled First-Year After-Tax Income",
                            _fmt_currency(_r["confirmed_income"], is_india),
                        )

                        # Compute and store calculation context so the chat advisor can
                        # explain the numbers if the user asks a follow-up question.
                        _ctx_years = _r["years_in_retirement"]
                        _ctx_gross = _target_f / (1 - _tax / 100) if _tax < 100 else _target_f
                        if abs(_growth - _inflation) > 0.0001:
                            _ctx_pv = (1 - ((1 + _inflation) / (1 + _growth)) ** _ctx_years) / (_growth - _inflation)
                        else:
                            _ctx_pv = _ctx_years
                        _ctx_real_ret = (_growth - _inflation) / (1 + _inflation) * 100
                        st.session_state.chat_calc_context = (
                            f"[CALC CONTEXT]\n"
                            f"Required {_corpus_label}: {_sym}{_r['required_pretax_portfolio']:,.0f}\n"
                            f"Target after-tax income: {_sym}{_target_f:,.0f}/yr\n"
                            f"Gross before {_tax:.0f}% tax: {_sym}{_ctx_gross:,.0f}/yr [= target/(1-tax)]\n"
                            f"Retirement: {_ctx_years} yrs (age {_ret_age_i}→{_life_exp_i})\n"
                            f"Growth {_growth*100:.1f}% | Inflation {_inflation*100:.1f}% | Real return ~{_ctx_real_ret:.1f}%\n"
                            f"PV factor: {_ctx_pv:.2f}× [(1-(1+i)^n/(1+g)^n)/(g-i)]\n"
                            f"Method: year-by-year simulation finds min {_corpus_label.lower()} sustaining "
                            f"{_sym}{_ctx_gross:,.0f}/yr (inflation-adjusted) for {_ctx_years} yrs at {_growth*100:.1f}% growth\n"
                            f"Source: Present Value of Growing Annuity (CFA curriculum, Investopedia)"
                        )

                        # Assumptions
                        if _birth_year:
                            _current_age = datetime.now().year - int(_birth_year)
                            _years_to_retire = max(0, int(_ret_age) - _current_age)
                            st.caption(f"Age {_current_age} today · {_years_to_retire} years to retirement")

                        st.caption(
                            f"Retiring at {_ret_age} · Planning to age {_life_exp} · "
                            f"{_r['years_in_retirement']} years in retirement"
                        )
                        st.caption(
                            f"{_tax:.0f}% tax rate · {_growth*100:.1f}% growth · {_inflation*100:.1f}% inflation"
                        )
                        if _legacy > 0:
                            st.caption(f"Legacy goal: {_fmt_currency(_legacy, is_india)}")
                        if _expenses > 0:
                            st.caption(f"One-time expenses at retirement: {_fmt_currency(_expenses, is_india)}")

                    except Exception as e:
                        st.error(f"Calculation error: {e}")

        # PDF export button — visible once we have enough to calculate
        if _has_required:
            st.markdown("---")

            if not is_india:
                st.warning(
                    "Simple Planning uses a simplified tax model. Your required portfolio may be over- or understated because it does not model the tax treatment of each account."
                )
                if st.button(
                    "Switch to Detailed Planning",
                    key="results_to_detailed",
                    use_container_width=True,
                ):
                    switch_to_detailed_planning_from_chat()

            def _build_results_pdf(fields, calc_result, _is_india, corpus_label):
                """Generate a PDF of the retirement plan estimate (results + assumptions only)."""
                buf = io.BytesIO()
                doc = SimpleDocTemplate(
                    buf,
                    pagesize=A4,
                    rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72,
                )
                styles = getSampleStyleSheet()
                title_style = ParagraphStyle(
                    "ChatTitle",
                    parent=styles["Title"],
                    fontSize=20,
                    spaceAfter=6,
                )
                heading_style = ParagraphStyle(
                    "ChatHeading",
                    parent=styles["Heading2"],
                    fontSize=13,
                    spaceBefore=16,
                    spaceAfter=6,
                    textColor=colors.HexColor("#1f77b4"),
                )

                story = []

                # Header
                story.append(Paragraph("Smart Retire AI", title_style))
                story.append(Paragraph(
                    f"Simple Retirement Plan · {datetime.now().strftime('%B %d, %Y')}",
                    styles["Normal"],
                ))
                story.append(Spacer(1, 20))

                # Key results table
                story.append(Paragraph(f"Required {corpus_label} at Retirement", heading_style))
                req = calc_result["required_pretax_portfolio"]
                inc = calc_result["confirmed_income"]
                result_data = [
                    ["Required Portfolio", _fmt_currency(req, _is_india)],
                    ["Modeled First-Year After-Tax Income", _fmt_currency(inc, _is_india)],
                ]
                tbl = Table(result_data, colWidths=[260, 160])
                tbl.setStyle(TableStyle([
                    ("FONTSIZE", (0, 0), (-1, -1), 12),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#e8f4fd"), colors.HexColor("#f0faf0")]),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ]))
                story.append(tbl)

                # Assumptions table
                story.append(Paragraph("Assumptions", heading_style))
                _birth = fields.get("birth_year")
                rows = []
                if _birth:
                    _age_now = datetime.now().year - int(_birth)
                    rows.append(["Current Age", str(_age_now)])
                    rows.append(["Years to Retirement", str(max(0, int(fields["retirement_age"]) - _age_now))])
                rows += [
                    ["Country", fields.get("country", "US")],
                    ["Retirement Age", str(fields["retirement_age"])],
                    ["Life Expectancy", str(fields["life_expectancy"])],
                    ["Years in Retirement", str(calc_result["years_in_retirement"])],
                    ["Tax Rate on Withdrawals", f"{fields.get('tax_rate', calc_result['tax_rate']):.0f}%"],
                    ["Portfolio Growth Rate", f"{calc_result['growth_rate']*100:.1f}%"],
                    ["Inflation Rate", f"{calc_result['inflation_rate']*100:.1f}%"],
                ]
                if calc_result.get("legacy_goal", 0) > 0:
                    rows.append(["Legacy Goal", _fmt_currency(calc_result["legacy_goal"], _is_india)])
                if calc_result.get("life_expenses", 0) > 0:
                    rows.append(["One-Time Expenses at Retirement", _fmt_currency(calc_result["life_expenses"], _is_india)])

                asmp_tbl = Table(rows, colWidths=[260, 160])
                asmp_tbl.setStyle(TableStyle([
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f9f9f9")]),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ]))
                story.append(asmp_tbl)

                # Disclaimer
                story.append(Spacer(1, 24))
                story.append(Paragraph(
                    "This report is for educational purposes only and does not constitute financial advice. "
                    "Projections are estimates based on the assumptions above.",
                    ParagraphStyle("Disclaimer", parent=styles["Normal"], fontSize=9,
                                   textColor=colors.grey, leading=13),
                ))

                doc.build(story)
                buf.seek(0)
                return buf.getvalue()

            _can_pdf = _REPORTLAB_AVAILABLE and int(_life_exp) > int(_ret_age) and float(_target) >= 0
            if _can_pdf:
                try:
                    _pdf_tax = float(_f.get("tax_rate", _defaults["tax_rate"]))
                    _pdf_growth = float(_f.get("growth_rate", _defaults["growth_rate"])) / 100.0
                    _pdf_inflation = float(_f.get("inflation_rate", _defaults["inflation_rate"])) / 100.0
                    _pdf_r = find_required_portfolio(
                        target_after_tax_income=float(_target),
                        retirement_age=int(_ret_age),
                        life_expectancy=int(_life_exp),
                        retirement_tax_rate_pct=_pdf_tax,
                        growth_rate=_pdf_growth,
                        inflation_rate=_pdf_inflation,
                        legacy_goal=float(_f.get("legacy_goal", 0)),
                        life_expenses=float(_f.get("life_expenses", 0)),
                    )
                    _pdf_bytes = _build_results_pdf(_f, _pdf_r, is_india, _corpus_label)
                    _pdf_fname = f"retirement_plan_{datetime.now().strftime('%Y%m%d')}.pdf"
                    st.download_button(
                        "📥 Download PDF Report",
                        data=_pdf_bytes,
                        file_name=_pdf_fname,
                        mime="application/pdf",
                        use_container_width=True,
                        key="chat_pdf_download",
                    )
                except Exception as _pdf_err:
                    st.caption(f"PDF generation failed: {_pdf_err}")
            else:
                st.caption("Install `reportlab` to enable PDF export.")


def _apply_setup_fields_to_session(fields: dict) -> None:
    """Copy confirmed setup-chat fields into the baseline session state keys the rest of the app reads."""
    current_age = datetime.now().year - int(fields.get("birth_year") or st.session_state.get("birth_year") or 1990)
    ra = max(int(fields.get("retirement_age") or 65), current_age)
    le = int(fields.get("life_expectancy") or 90)
    rig = float(fields.get("retirement_income_goal") or 0)
    lg = float(fields.get("legacy_goal") or 0)
    lx = float(fields.get("life_expenses") or 0)

    if "birth_year" in fields and fields["birth_year"] is not None:
        st.session_state.birth_year = int(fields["birth_year"])

    st.session_state.baseline_retirement_age = ra
    st.session_state.baseline_life_expectancy = le
    st.session_state.baseline_retirement_income_goal = rig
    st.session_state.baseline_life_expenses = lx
    st.session_state.baseline_legacy_goal = lg

    # Working keys read by sidebar, results page, and legacy compat block
    st.session_state.retirement_age = ra
    st.session_state.life_expectancy = le
    st.session_state.retirement_income_goal = rig
    st.session_state.legacy_goal = lg
    st.session_state.life_expenses = lx

    # Reset what-if keys to new baselines so results page starts fresh
    st.session_state.whatif_retirement_age = ra
    st.session_state.whatif_life_expectancy = le
    st.session_state.whatif_retirement_income_goal = rig
    st.session_state.whatif_life_expenses = lx
    st.session_state.whatif_legacy_goal = lg

    st.session_state.country = "US"


def _dp_compute_results() -> bool:
    """Run the retirement projection for Detailed Planning unified page.

    Reads whatif_* values from session state. Writes last_result, last_inputs,
    cashflow_sim_data, last_annual_retirement_income, gap-closing values,
    results_chat_context. Returns True on success, False on validation failure.
    """
    current_year = datetime.now().year
    age = current_year - st.session_state.birth_year
    retirement_age = st.session_state.whatif_retirement_age
    life_expectancy = st.session_state.whatif_life_expectancy
    retirement_income_goal = st.session_state.whatif_retirement_income_goal
    current_tax_rate = st.session_state.whatif_current_tax_rate
    retirement_tax_rate = st.session_state.whatif_retirement_tax_rate
    inflation_rate = st.session_state.whatif_inflation_rate
    retirement_growth_rate = st.session_state.whatif_retirement_growth_rate
    life_expenses = st.session_state.whatif_life_expenses
    legacy_goal = st.session_state.get('whatif_legacy_goal', 0)
    assets = st.session_state.assets

    if int(retirement_age) < int(age):
        st.error(f"⚠️ Retirement age ({int(retirement_age)}) is less than your current age ({int(age)}). Ask the chatbot to update your retirement age.")
        return False

    years_in_retirement = life_expectancy - retirement_age
    if years_in_retirement <= 0:
        st.error(f"⚠️ Life expectancy ({life_expectancy}) must be greater than retirement age ({retirement_age}).")
        return False

    try:
        inputs = UserInputs(
            age=int(age),
            retirement_age=int(retirement_age),
            life_expectancy=int(life_expectancy),
            annual_income=0.0,
            contribution_rate_pct=15.0,
            expected_growth_rate_pct=7.0,
            inflation_rate_pct=float(inflation_rate),
            current_marginal_tax_rate_pct=float(current_tax_rate),
            retirement_marginal_tax_rate_pct=float(retirement_tax_rate),
            assets=assets
        )

        result = project(inputs)
        st.session_state.last_result = result
        st.session_state.last_inputs = inputs

        total_after_tax_original = result['Total After-Tax Balance']
        if life_expenses > total_after_tax_original:
            st.error(f"⚠️ One-time expenses (${life_expenses:,.0f}) exceed projected after-tax balance (${total_after_tax_original:,.0f}). Reduce expenses or increase contributions.")
            return False

        # Retirement income simulation
        pretax_fv = sum(
            ar['pre_tax_value']
            for ar, ai in zip(result['asset_results'], result['assets_input'])
            if ai.asset_type in (AssetType.PRE_TAX, AssetType.TAX_DEFERRED)
        )
        roth_fv = sum(
            ar['pre_tax_value']
            for ar, ai in zip(result['asset_results'], result['assets_input'])
            if ai.asset_type == AssetType.POST_TAX and 'roth' in ai.name.lower()
        )
        brok_fv = sum(
            ar['pre_tax_value']
            for ar, ai in zip(result['asset_results'], result['assets_input'])
            if ai.asset_type == AssetType.POST_TAX and 'roth' not in ai.name.lower()
        )
        brok_cost_basis = sum(
            ar['total_contributions'] + ai.current_balance
            for ar, ai in zip(result['asset_results'], result['assets_input'])
            if ai.asset_type == AssetType.POST_TAX and 'roth' not in ai.name.lower()
        )

        total_fv_all = pretax_fv + roth_fv + brok_fv
        if life_expenses > 0 and total_fv_all > 0:
            frac = life_expenses / total_fv_all
            pretax_fv       = max(0.0, pretax_fv       * (1.0 - frac))
            roth_fv         = max(0.0, roth_fv         * (1.0 - frac))
            brok_fv         = max(0.0, brok_fv         * (1.0 - frac))
            brok_cost_basis = max(0.0, brok_cost_basis * (1.0 - frac))

        annual_retirement_income, sim_data = find_sustainable_withdrawal(
            pretax_fv, roth_fv, brok_fv, brok_cost_basis,
            int(retirement_age), int(life_expectancy),
            retirement_growth_rate / 100.0, inflation_rate / 100.0,
            float(retirement_tax_rate),
            legacy_goal=legacy_goal,
        )
        st.session_state.cashflow_sim_data = sim_data
        st.session_state.last_annual_retirement_income = annual_retirement_income

        # Gap-closing values
        _current_age = datetime.now().year - st.session_state.birth_year
        _breakeven_age: int | None = None
        _income_at_breakeven: float = 0.0
        _breakeven_contrib: int | None = None
        _contrib_breakdown: dict = {}
        _contrib_irs_maxed: bool = False
        _assets_input = result.get("assets_input", assets)

        if retirement_income_goal > 0 and annual_retirement_income < retirement_income_goal:
            _breakeven_age, _income_at_breakeven = find_breakeven_retirement_age(
                assets_input=_assets_input,
                current_age=_current_age,
                start_retirement_age=int(retirement_age),
                life_expectancy=int(life_expectancy),
                target_income=float(retirement_income_goal),
                retirement_growth_rate=retirement_growth_rate / 100.0,
                inflation_rate=inflation_rate / 100.0,
                retirement_tax_rate_pct=float(retirement_tax_rate),
                life_expenses=life_expenses,
                legacy_goal=legacy_goal,
            )
            _breakeven_contrib, _contrib_breakdown, _contrib_irs_maxed = find_breakeven_contribution(
                assets_input=_assets_input,
                current_age=_current_age,
                retirement_age=int(retirement_age),
                life_expectancy=int(life_expectancy),
                target_income=float(retirement_income_goal),
                retirement_growth_rate=retirement_growth_rate / 100.0,
                inflation_rate=inflation_rate / 100.0,
                retirement_tax_rate_pct=float(retirement_tax_rate),
                life_expenses=life_expenses,
                legacy_goal=legacy_goal,
            )

        st.session_state.last_breakeven_age = _breakeven_age
        st.session_state.last_income_at_breakeven = _income_at_breakeven
        st.session_state.last_breakeven_contrib = _breakeven_contrib
        st.session_state.last_contrib_breakdown = _contrib_breakdown
        st.session_state.last_contrib_irs_maxed = _contrib_irs_maxed

        # Monte Carlo for chat context
        _mc_summary: dict = {}
        try:
            from financialadvisor.core.monte_carlo import (
                run_monte_carlo_simulation,
                calculate_probability_of_goal,
            )
            _mc = run_monte_carlo_simulation(inputs, num_simulations=500, seed=42)
            _mc_prob = calculate_probability_of_goal(
                _mc["outcomes"],
                int(retirement_age), int(life_expectancy),
                float(retirement_income_goal) if retirement_income_goal > 0 else 0.0,
            )
            _mc_summary = {
                "income_p10":  _mc["income_percentiles"]["10th"],
                "income_p50":  _mc["income_percentiles"]["50th"],
                "income_p90":  _mc["income_percentiles"]["90th"],
                "bal_p10":     _mc["percentiles"]["10th"],
                "bal_p50":     _mc["percentiles"]["50th"],
                "bal_p90":     _mc["percentiles"]["90th"],
                "prob_success": _mc_prob,
                "volatility":   _mc["volatility"],
                "num_sims":     _mc["num_simulations"],
            }
        except Exception as _mc_err:
            import logging as _logging
            _logging.getLogger(__name__).debug("MC context skipped: %s", _mc_err)

        st.session_state.dp_mc_summary = _mc_summary

        # Build chat context
        if _CHAT_CONTEXT_AVAILABLE:
            _whatif_snapshot = {
                "retirement_age":         retirement_age,
                "life_expectancy":        life_expectancy,
                "retirement_income_goal": retirement_income_goal,
                "inflation_rate":         inflation_rate,
                "retirement_growth_rate": retirement_growth_rate,
                "retirement_tax_rate":    retirement_tax_rate,
                "life_expenses":          life_expenses,
                "legacy_goal":            legacy_goal,
            }
            st.session_state.results_chat_context = build_detailed_chat_context(
                result=result,
                inputs=inputs,
                annual_retirement_income=annual_retirement_income,
                sim_data=sim_data,
                whatif_values=_whatif_snapshot,
                assets=assets,
                birth_year=st.session_state.get("birth_year"),
                breakeven_retirement_age=_breakeven_age,
                income_at_breakeven=_income_at_breakeven,
                breakeven_contribution=_breakeven_contrib,
                contrib_breakdown=_contrib_breakdown,
                contrib_irs_maxed=_contrib_irs_maxed,
                mc_summary=_mc_summary,
            )

        return True

    except Exception as e:
        st.error(f"❌ Error in calculation: {e}")
        return False


def _render_dp_top_bar() -> None:
    """Full-width Key Results + Profile strip rendered above the chat/panel columns."""
    fields = st.session_state.setup_fields
    current_year = datetime.now().year
    _dp_calc = st.session_state.dp_calculated

    by = fields.get("birth_year") or st.session_state.get("birth_year")
    ra = fields.get("retirement_age") or st.session_state.get("retirement_age")
    le = fields.get("life_expectancy") or st.session_state.get("life_expectancy")
    rig = fields.get("retirement_income_goal")
    if rig is None:
        rig = st.session_state.get("retirement_income_goal")

    st.markdown("**📋 Your Profile**")
    if by is not None:
        age_val = current_year - int(by)
        _l1 = f"Age **{age_val}**"
        if ra is not None:
            _l1 += f"  ·  Retire at **{int(ra)}** ({max(0, int(ra) - age_val)} yrs)"
        st.caption(_l1)
        if le is not None and ra is not None:
            _l2 = f"Plan through **{int(le)}**  ·  **{int(le) - int(ra)} yrs** in retirement"
            if rig is not None and float(rig) > 0:
                _l2 += f"  ·  Goal **\\${float(rig):,.0f}/yr**"
            st.caption(_l2)
        elif rig is not None and float(rig) > 0:
            st.caption(f"Income goal **\\${float(rig):,.0f}/yr**")
    else:
        st.caption("Answer the chat questions to fill this in.")

    st.markdown("---")


def _render_dp_right_panel() -> None:
    """Right panel: accounts + action buttons."""
    _goals_done = st.session_state.dp_goals_done
    assets = st.session_state.get("assets", [])
    n_assets = len(assets)
    _no_acct = n_assets == 0
    _no_acct_tip = "Add at least one account to enable this."
    _dp_calc = st.session_state.dp_calculated

    # ── Key Results ───────────────────────────────────────────────────
    st.markdown("**📊 Key Results**")
    if _dp_calc:
        _ok = _dp_compute_results()
        if _ok:
            _result = st.session_state.last_result
            _ai = st.session_state.last_annual_retirement_income
            _life_exp = st.session_state.whatif_life_expenses
            _after_tax = _result.get("Total After-Tax Balance", 0) - _life_exp
            _rig2 = st.session_state.whatif_retirement_income_goal
            _tax_eff = _result.get("Tax Efficiency (%)", 0)
            _mc = st.session_state.get("dp_mc_summary", {})
            _inc_line = f"Income **\\${_ai:,.0f}/yr**"
            if _rig2 and float(_rig2) > 0:
                _gap = _ai - float(_rig2)
                _inc_line += f" ({'▲' if _gap >= 0 else '▼'} \\${abs(_gap):,.0f} vs goal)"
            _mc_part = f"  ·  Monte Carlo Simulation success probability **{_mc['prob_success']:.0f}%**" if _mc.get("prob_success") is not None else ""
            st.markdown(f"Portfolio **\\${_after_tax:,.0f}**  ·  {_inc_line}")
            st.markdown(f"Tax efficiency **{_tax_eff:.1f}%**{_mc_part}")
            st.info(f"Does not account for Social Security, pensions, or other income sources.")
            if st.session_state.get("results_chat_whatif_modified"):
                st.caption("⚠️ Scenario modified via chat.")
    else:
        st.caption("Your projection will appear here once accounts are added.")

    st.markdown("---")

    # ── Accounts ──────────────────────────────────────────────────────
    st.markdown(f"**🏦 Your Accounts** ({n_assets})")

    _can_add = st.session_state.dp_goals_done
    if st.button(
        "+ Add / Manage Accounts",
        use_container_width=True,
        type="primary" if _can_add else "secondary",
        disabled=not _can_add,
        help=None if _can_add else "Complete the setup chat first.",
        key="dp_add_accounts_btn",
    ):
        st.session_state.show_adjust_assets_dialog = True
        st.rerun()
    if st.session_state.get("show_adjust_assets_dialog"):
        adjust_assets_dialog()
    if _toast := st.session_state.pop("adjust_assets_toast", None):
        st.toast(_toast, icon="✅")

    _total_balance = sum(a.current_balance for a in assets)
    if assets and _total_balance > 0:
        # Auto-calculate whenever accounts change (hash-based detection)
        _current_hash = hash(tuple(
            (a.name, a.current_balance, a.annual_contribution)
            for a in sorted(assets, key=lambda x: x.name)
        ))
        if _goals_done and _current_hash != st.session_state.get("dp_assets_hash"):
            st.session_state.dp_assets_hash = _current_hash  # update first to prevent loop
            _ok = _dp_compute_results()
            if _ok:
                _ai = st.session_state.last_annual_retirement_income
                _rig = st.session_state.whatif_retirement_income_goal
                _co_income = f"\\${_ai:,.0f}"
                _is_update = st.session_state.dp_calculated
                if _rig and float(_rig) > 0:
                    _gap = float(_rig) - _ai
                    _co_goal = f"\\${float(_rig):,.0f}"
                    if _gap > 0:
                        _opener = (
                            f"{'Updated projection — p' if _is_update else 'P'}ortfolio projects **{_co_income}/year** "
                            f"— **\\${_gap:,.0f} below** your {_co_goal} goal.\n\n"
                            f"Ask me anything — how this is calculated, RMDs, Social Security, "
                            f"what-ifs, or Monte Carlo scenarios."
                        )
                    else:
                        _opener = (
                            f"{'Updated — p' if _is_update else 'G'}reat news — portfolio projects **{_co_income}/year**, "
                            f"meeting your {_co_goal} goal! "
                            f"Ask me about what-ifs, RMDs, or Monte Carlo scenarios."
                        )
                else:
                    _opener = (
                        f"{'Updated — p' if _is_update else 'P'}ortfolio projects **{_co_income}/year** in retirement.\n\n"
                        f"Ask me anything — how this is calculated, RMDs, Social Security, "
                        f"what-if scenarios, or Monte Carlo simulations."
                    )
                st.session_state.dp_chat_messages.append({"role": "assistant", "content": _opener})
                st.session_state.dp_calculated = True
            st.rerun()
    elif _total_balance == 0 and assets:
        st.caption("All accounts have a $0 balance — add balances to see your projection.")
    else:
        st.caption("No accounts yet — add accounts above to see your projection.")

    st.markdown("---")

    # ── Section D: Action Buttons (always visible, 2×2 grid) ─────────
    _b1, _b2 = st.columns(2)
    with _b1:
        if st.button(
            "📥 PDF Report",
            use_container_width=True,
            disabled=_no_acct,
            help=_no_acct_tip if _no_acct else None,
            key="dp_pdf_btn",
        ):
            generate_report_dialog()
        if st.button(
            "📈 Detailed Analysis",
            use_container_width=True,
            disabled=_no_acct,
            help=_no_acct_tip if _no_acct else None,
            key="dp_detailed_btn",
        ):
            st.session_state.results_source = 'detailed_planning'
            st.session_state.current_page = 'detailed_analysis'
            st.rerun()
    with _b2:
        if st.button(
            "📊 Cash Flow",
            use_container_width=True,
            disabled=_no_acct,
            help=_no_acct_tip if _no_acct else None,
            key="dp_cashflow_btn",
        ):
            cashflow_dialog()
        if st.button("🗑 Reset", use_container_width=True, key="dp_reset_btn"):
            clear_detailed_planning_asset_state(st.session_state)
            for _k in ("dp_goals_done", "dp_calculated", "dp_chat_pending"):
                st.session_state[_k] = False
            st.session_state.dp_chat_messages = []
            st.session_state.setup_fields = {}
            st.session_state.setup_fields_locked = False
            st.session_state.results_chat_whatif_modified = False
            st.session_state.pop("dp_assets_hash", None)
            st.rerun()


def _render_dp_chat() -> None:
    """Unified chat for Detailed Planning — handles goal collection and results advisor in one stream."""
    # Initialize with opening message
    if not st.session_state.dp_chat_messages:
        st.session_state.dp_chat_messages = [{
            "role": "assistant",
            "content": (
                "Hi! I'll guide you through retirement planning.\n\n"
                "Let's start with your goals — **what year were you born, and when are you hoping to retire** "
                "(default is 65)? If you have a target annual retirement income in mind, share that too!\n\n"
                "Once we have your goals set, add your accounts using the panel on the right."
            ),
        }]

    # Pass 2: API call pending
    if (
        st.session_state.get("dp_chat_pending")
        and st.session_state.dp_chat_messages
        and st.session_state.dp_chat_messages[-1]["role"] == "user"
    ):
        st.session_state.dp_chat_pending = False
        _api_key = os.getenv("OPENAI_API_KEY") or (
            st.secrets.get("OPENAI_API_KEY") if hasattr(st, "secrets") else None
        )
        if not st.session_state.dp_calculated:
            # Goals phase — setup advisor
            try:
                display_msg, fields = chat_with_setup_advisor(
                    st.session_state.dp_chat_messages,
                    openai_api_key=_api_key,
                )
                st.session_state.dp_chat_messages.append({"role": "assistant", "content": display_msg})
                if not st.session_state.dp_goals_done:
                    for k, v in fields.items():
                        if v is not None and k != "done":
                            st.session_state.setup_fields[k] = v
                    if fields.get("done"):
                        _apply_setup_fields_to_session(st.session_state.setup_fields)
                        st.session_state.dp_goals_done = True
            except Exception as _err:
                st.session_state.dp_chat_messages.append({
                    "role": "assistant",
                    "content": f"Sorry, I hit a snag: {_err}. Please try again.",
                })
        else:
            # Results phase — results advisor
            try:
                context = st.session_state.results_chat_context or ""
                display_msg, whatif_changes = chat_with_results_advisor(
                    st.session_state.dp_chat_messages,
                    calc_context=context,
                    openai_api_key=_api_key,
                )
                st.session_state.dp_chat_messages.append({"role": "assistant", "content": display_msg})
                if whatif_changes:
                    _whatif_key_map = {
                        "retirement_age":         "whatif_retirement_age",
                        "life_expectancy":        "whatif_life_expectancy",
                        "retirement_income_goal": "whatif_retirement_income_goal",
                        "inflation_rate":         "whatif_inflation_rate",
                        "retirement_growth_rate": "whatif_retirement_growth_rate",
                        "retirement_tax_rate":    "whatif_retirement_tax_rate",
                        "life_expenses":          "whatif_life_expenses",
                        "legacy_goal":            "whatif_legacy_goal",
                    }
                    for param, session_key in _whatif_key_map.items():
                        if param in whatif_changes and whatif_changes[param] is not None:
                            st.session_state[session_key] = whatif_changes[param]
                    st.session_state.results_chat_whatif_modified = True
            except Exception as _err:
                st.session_state.dp_chat_messages.append({
                    "role": "assistant",
                    "content": f"Sorry, I hit a snag: {_err}. Please try again.",
                })
        st.rerun()

    # Render messages
    msg_container = st.container(height=460)
    with msg_container:
        for msg in st.session_state.dp_chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        if st.session_state.get("dp_chat_pending"):
            with st.chat_message("assistant"):
                st.markdown("_Thinking…_")

    # Download transcript
    if len(st.session_state.dp_chat_messages) > 1:
        _transcript_md = _build_chat_transcript_md(st.session_state.dp_chat_messages)
        st.download_button(
            "⬇️ Download chat transcript",
            data=_transcript_md,
            file_name="smart_retire_chat.md",
            mime="text/markdown",
            key="dp_download_transcript",
        )

    if not _CHAT_AVAILABLE:
        st.warning("⚠️ Chat advisor requires `OPENAI_API_KEY`. Set it in your `.env` file.")
        return

    _placeholder = (
        "Ask about your results, run what-ifs, or explore scenarios…"
        if st.session_state.dp_calculated
        else "Type your answer here…"
    )
    if user_input := st.chat_input(_placeholder, key="dp_chat_input"):
        st.session_state.dp_chat_messages.append({"role": "user", "content": user_input})
        st.session_state.dp_chat_pending = True
        st.rerun()


def show_detailed_planning() -> None:
    """Unified Detailed Planning page — single persistent chat + evolving right panel."""
    #st.markdown("---")
    _header_col, _switch_col = st.columns([4, 1.5])
    with _header_col:
        st.subheader("📝 Detailed Planning")
    with _switch_col:
        if st.button("Switch to Simple Planning", use_container_width=True, key="dp_switch_simple_btn"):
            switch_to_simple_planning_from_onboarding()

    st.caption(
        "Detailed Planning is US-focused — USD values and US tax rules apply throughout. "
        "Use Simple Planning for India or a quick estimate."
    )
    st.markdown("---")

    _render_dp_top_bar()

    chat_col, panel_col = st.columns([3, 2], gap="medium")
    with chat_col:
        _render_dp_chat()
    with panel_col:
        _render_dp_right_panel()



def show_detailed_setup_chat() -> None:
    """Chat-based personal information collection — Phase A of conversational Detailed Planning."""
    st.markdown("---")

    _header_col, _switch_col = st.columns([4, 1.5])
    with _header_col:
        st.subheader("📝 Your Retirement Goals")
    with _switch_col:
        if st.button("Switch to Simple Planning",use_container_width=True, key="switch_from_setup_chat"):
            switch_to_simple_planning_from_onboarding()

    st.info(
        "Detailed Planning is US-focused — USD values and US tax rules apply throughout. "
        "Use Simple Planning for India or a quick estimate."
    )
    st.markdown("---")

    chat_col, summary_col = st.columns([3, 2], gap="medium")

    with chat_col:
        msg_container = st.container(height=440)
        with msg_container:
            # Opening greeting shown before the conversation starts
            if not st.session_state.setup_messages:
                with st.chat_message("assistant"):
                    st.markdown(
                        "Hi! Let's get your retirement plan started.\n\n"
                        "Two quick things: **what year were you born and when are you hoping to retire (default is 65)?**\n\nAlso, if you have a target annual retirement income in mind, share that too!\n\n"
                    )

            for msg in st.session_state.setup_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

        if st.session_state.setup_fields_locked:
            if st.button("Continue: Set Up Accounts →", type="primary",use_container_width=True, key="setup_continue_btn"):
                _apply_setup_fields_to_session(st.session_state.setup_fields)
                track_onboarding_step_completed(
                    1,
                    country="US",
                    age_range=get_age_range(datetime.now().year - st.session_state.birth_year),
                    retirement_age=st.session_state.retirement_age,
                    years_to_retirement=st.session_state.retirement_age - (datetime.now().year - st.session_state.birth_year),
                    goal_range=get_goal_range(st.session_state.retirement_income_goal),
                )
                st.session_state.onboarding_step = 2
                st.rerun()
        else:
            if not _CHAT_AVAILABLE:
                st.warning("⚠️ Chat advisor requires `OPENAI_API_KEY`. Set it in your `.env` file.")
            else:
                if st.session_state.setup_messages:
                    if st.button("↩ Start over", key="setup_start_over"):
                        st.session_state.setup_messages = []
                        st.session_state.setup_fields = {}
                        st.session_state.setup_fields_locked = False
                        st.rerun()
                if user_input := st.chat_input("Type your answer here...", key="setup_chat_input"):
                    st.session_state.setup_messages.append({"role": "user", "content": user_input})
                    try:
                        _api_key = os.getenv("OPENAI_API_KEY") or (
                            st.secrets.get("OPENAI_API_KEY") if hasattr(st, "secrets") else None
                        )
                        display_msg, fields = chat_with_setup_advisor(
                            st.session_state.setup_messages,
                            openai_api_key=_api_key,
                        )
                        st.session_state.setup_messages.append({"role": "assistant", "content": display_msg})
                        for k, v in fields.items():
                            if v is not None and k != "done":
                                st.session_state.setup_fields[k] = v
                        if fields.get("done"):
                            st.session_state.setup_fields_locked = True
                    except Exception as _setup_err:
                        st.session_state.setup_messages.append({
                            "role": "assistant",
                            "content": f"Sorry, I hit a snag: {_setup_err}. Please try again.",
                        })
                    st.rerun()

    with summary_col:
        st.markdown("### What we know so far")
        fields = st.session_state.setup_fields
        current_year = datetime.now().year

        by = fields.get("birth_year")
        ra = fields.get("retirement_age")
        le = fields.get("life_expectancy")
        rig = fields.get("retirement_income_goal")

        if by is not None:
            age = current_year - int(by)
            st.metric("Current Age", f"{age} yrs")

        if ra is not None and by is not None:
            ytr = int(ra) - (current_year - int(by))
            st.metric("Retire At", int(ra), delta=f"{max(ytr, 0)} yrs away")

        if le is not None and ra is not None:
            st.metric("Plan Through Age", int(le), delta=f"{int(le) - int(ra)} yrs in retirement")

        if rig is not None:
            st.metric("Annual Income Goal", f"${float(rig):,.0f}/yr")
            st.caption(f"~${float(rig) * 25 / 1e6:.1f}M portfolio needed (25× rule of thumb)")

        lg = fields.get("legacy_goal")
        if lg and float(lg) > 0:
            st.metric("Legacy Goal", f"${float(lg):,.0f}")

        lx = fields.get("life_expenses")
        if lx and float(lx) > 0:
            st.metric("One-time Expenses at Retirement", f"${float(lx):,.0f}")

        if not fields:
            st.caption("Your confirmed details will appear here as we chat.")


def _build_chat_transcript_md(messages: list) -> str:
    """Format chat messages as a downloadable Markdown transcript."""
    lines = ["# Smart Retire AI — Chat Transcript\n"]
    for msg in messages:
        role_label = "**You**" if msg["role"] == "user" else "**Advisor**"
        lines.append(f"{role_label}\n\n{msg['content']}\n")
    return "\n---\n\n".join(lines)


def _render_results_chat_panel(opening_message: str) -> None:
    """Render the post-results conversational chat panel for Detailed Planning.

    Two-pass pattern for instant user-message display:
      Pass 1 — user submits input → append to session state → st.rerun()
              (page re-renders immediately showing the user's message)
      Pass 2 — pending flag is set → call API → append response → st.rerun()
    """
    # Seed opening message on first render
    if not st.session_state.results_chat_messages:
        st.session_state.results_chat_messages = [
            {"role": "assistant", "content": opening_message}
        ]

    # Pass 2: a user message is waiting for an API response
    if (
        st.session_state.get("results_chat_pending")
        and st.session_state.results_chat_messages
        and st.session_state.results_chat_messages[-1]["role"] == "user"
    ):
        st.session_state.results_chat_pending = False
        if _CHAT_AVAILABLE:
            try:
                _api_key = os.getenv("OPENAI_API_KEY") or (
                    st.secrets.get("OPENAI_API_KEY") if hasattr(st, "secrets") else None
                )
                context = st.session_state.results_chat_context or ""
                display_msg, whatif_changes = chat_with_results_advisor(
                    st.session_state.results_chat_messages,
                    calc_context=context,
                    openai_api_key=_api_key,
                )
                st.session_state.results_chat_messages.append(
                    {"role": "assistant", "content": display_msg}
                )
                if whatif_changes:
                    _whatif_key_map = {
                        "retirement_age":         "whatif_retirement_age",
                        "life_expectancy":        "whatif_life_expectancy",
                        "retirement_income_goal": "whatif_retirement_income_goal",
                        "inflation_rate":         "whatif_inflation_rate",
                        "retirement_growth_rate": "whatif_retirement_growth_rate",
                        "retirement_tax_rate":    "whatif_retirement_tax_rate",
                        "life_expenses":          "whatif_life_expenses",
                        "legacy_goal":            "whatif_legacy_goal",
                    }
                    for param, session_key in _whatif_key_map.items():
                        if param in whatif_changes and whatif_changes[param] is not None:
                            st.session_state[session_key] = whatif_changes[param]
                    st.session_state.results_chat_whatif_modified = True
            except Exception as _err:
                st.session_state.results_chat_messages.append({
                    "role": "assistant",
                    "content": f"Sorry, I hit a snag: {_err}. Please try again.",
                })
            st.rerun()

    chat_col, action_col = st.columns([3, 2], gap="medium")
#chat_col, action_col = st.columns([3, 1])

    with action_col:
        st.markdown("### What you can do next")
        if st.button("📥 PDF Report", use_container_width=True, key="results_pdf_report"):
            generate_report_dialog()
        if st.button("📊 View Cash Flow", use_container_width=True, key="results_cashflow"):
            cashflow_dialog()
        if st.button("📈 Detailed Analysis", use_container_width=True, key="results_detailed_analysis"):
            st.session_state.current_page = 'detailed_analysis'
            st.rerun()
        if st.button("🏦 Adjust Assets", use_container_width=True, key="results_adjust_assets"):
            st.session_state.show_adjust_assets_dialog = True
            st.rerun()
        if st.session_state.get("show_adjust_assets_dialog"):
            adjust_assets_dialog()
        if _toast := st.session_state.pop("adjust_assets_toast", None):
            st.toast(_toast, icon="✅")

    with chat_col:
        # Render all messages (including the just-appended user message on Pass 1)
        msg_container = st.container(height=380)
        with msg_container:
            for msg in st.session_state.results_chat_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
            # Show a spinner inside the container while waiting for the API response
            if st.session_state.get("results_chat_pending"):
                with st.chat_message("assistant"):
                    st.markdown("_Thinking…_")

        # Download transcript button (only when there's more than the opening message)
        if len(st.session_state.results_chat_messages) > 1:
            _transcript_md = _build_chat_transcript_md(st.session_state.results_chat_messages)
            st.download_button(
                "⬇️ Download chat transcript",
                data=_transcript_md,
                file_name="smart_retire_chat.md",
                mime="text/markdown",
                key="download_chat_transcript",
            )

        if not _CHAT_AVAILABLE:
            st.warning("⚠️ Chat advisor requires `OPENAI_API_KEY`. Set it in your `.env` file.")
            return

        # Pass 1: capture input, echo immediately, then trigger API pass (inline since inside a column)
        if user_input := st.chat_input(
            "Ask about your results, run what-ifs, or ask about RMDs, Social Security...",
            key="results_chat_input",
        ):
            st.session_state.results_chat_messages.append({"role": "user", "content": user_input})
            st.session_state.results_chat_pending = True
            st.rerun()


@st.dialog("⚠️ Legal Disclaimer", width="large")
def legal_disclaimer_dialog():
    """Full legal disclaimer shown as a popup on non-onboarding pages."""
    st.markdown("""
    ### 🚨 DISCLAIMER - READ CAREFULLY

    **This application provides educational and informational content only. It is NOT financial, tax, legal, or investment advice.**

    **Important Limitations:**
    - **Not Professional Advice**: This tool is for educational purposes only and does not constitute professional financial, tax, legal, or investment advice
    - **No Personal Recommendations**: Results are based on general assumptions and may not be suitable for your specific situation
    - **No Guarantees**: Past performance does not guarantee future results; all projections are estimates
    - **Consult Professionals**: Always consult with qualified financial advisors, tax professionals, and legal counsel before making financial decisions
    - **Your Responsibility**: You are solely responsible for your financial decisions and their consequences

    **No Liability**: The creators and operators of this application disclaim all liability for any losses, damages, or consequences arising from the use of this information.

    **By using this application, you acknowledge and agree to these terms.**
    """)
    if st.button("Close",use_container_width=True, type="primary", key="close_legal_disclaimer"):
        st.rerun()


@st.dialog(f"🆕 What's New in v{VERSION}", width="large")
def whats_new_dialog():
    """Display the Release Overview section of the current version's release notes."""
    content = load_release_notes()
    overview = extract_release_overview(content, include_heading=True)
    if overview:
        st.markdown(overview)
    else:
        st.info(f"Release notes for v{VERSION} are not yet available.")
    st.markdown("---")
    if st.button("Close",use_container_width=True, type="primary", key="close_whats_new"):
        st.rerun()


# Streamlit UI - this runs when using 'streamlit run fin_advisor.py'
# Skip UI code if running tests
import sys
_RUNNING_TESTS = "--run-tests" in sys.argv

if not _RUNNING_TESTS:
    st.set_page_config(
        page_title="Smart Retire AI",
        page_icon="💰",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # Initialize analytics
    initialize_analytics()

    # Scroll to top on page changes
    # This ensures focus starts at top when navigating between pages
    components.html(
        """
        <script>
            window.parent.document.querySelector('section.main').scrollTo(0, 0);
        </script>
        """,
        height=0,
    )

    # Fix tooltip font consistency
    st.markdown("""
        <style>
        /* Ensure tooltips use consistent sans-serif font */
        [role="tooltip"],
        [data-baseweb="tooltip"],
        div[data-baseweb="popover"] {
            font-family: "Source Sans Pro", sans-serif !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # Note: PostHog session replay requires browser JavaScript which doesn't work
    # reliably in Streamlit's server-side architecture. Session analytics (based on
    # events) will still work and show session duration, events per session, etc.
    
    @st.dialog("📊 Help Us Improve Smart Retire AI")
    def analytics_consent_dialog():
        """Display analytics consent dialog for user opt-in."""
        st.markdown("""
        ### We'd like to collect anonymous usage data to improve your experience
    
        **What we collect (if you opt-in):**
        - ✅ Anonymous usage patterns (e.g., which features you use)
        - ✅ Error logs (to fix bugs faster)
        - ✅ Browser/device info (for compatibility)
    
        **What we NEVER collect:**
        - ❌ Your financial data (account balances, numbers)
        - ❌ Personal information (name, email, address)
        - ❌ PDF file contents
        - ❌ Exact ages or retirement goals
    
        **Your data:**
        - Anonymous ID only (not tied to you)
        - Encrypted and stored securely
        - Automatically deleted after 90 days
        - You can opt-out anytime in Advanced Settings
    
        ---
        """)
    
        # Privacy policy link
        if st.button("📄 Read Full Privacy Policy",use_container_width=True, key="analytics_privacy_link"):
            show_privacy_policy()
    
        st.markdown("---")
    
        # Consent buttons
        col1, col2 = st.columns(2)
    
        with col1:
            if st.button("✅ I Accept", type="primary",use_container_width=True, key="analytics_accept"):
                set_analytics_consent(True)
                track_event('analytics_consent_shown')
                st.success("✅ Thank you! Analytics enabled.")
                time.sleep(0.5)  # Brief pause to show success message
                st.rerun()
    
        with col2:
            if st.button("❌ No Thanks",use_container_width=True, key="analytics_decline"):
                set_analytics_consent(False)
                st.info("ℹ️ You can enable analytics later in Advanced Settings.")
                time.sleep(0.5)  # Brief pause to show info message
                st.rerun()
    
        st.caption("**Your choice is saved for this session.** You can change it anytime in Advanced Settings.")
    
    
    @st.dialog("Privacy Policy")
    def show_privacy_policy():
        """Display comprehensive privacy policy in a dialog."""
        st.markdown("""
        ## Smart Retire AI Privacy Policy
    
        **Effective Date:** January 2026
        **Last Updated:** January 3, 2026
    
        ---
    
        ### 📋 Introduction
    
        Smart Retire AI ("we", "our", or "the app") is committed to protecting your privacy. This policy explains what data we collect, how we use it, and your rights.
    
        ---
    
        ### 🔐 Data We NEVER Collect
    
        We want to be crystal clear about what we **DO NOT** collect:
    
        ❌ **Financial Account Information**
        - Account balances, numbers, or statements
        - Investment holdings or transaction details
        - Banking or credit card information
    
        ❌ **Personally Identifiable Information (PII)**
        - Names, email addresses, or phone numbers
        - Social Security Numbers or tax IDs
        - Home addresses or zip codes
        - Birth dates (we use age ranges only)
    
        ❌ **Sensitive Personal Data**
        - Uploaded PDF file contents
        - Exact retirement goals (we use ranges)
        - Specific financial advice or recommendations
    
        ---
    
        ### ✅ Data We May Collect (With Your Consent)
    
        **If you opt-in to analytics**, we collect anonymous usage data:
    
        **1. Anonymous Usage Events**
        - Actions you take in the app (e.g., "user completed step 1")
        - Features you use (e.g., "PDF report generated")
        - Anonymous user ID (random UUID, not linked to you)
    
        **2. Technical Information**
        - Browser type and version (for compatibility)
        - Operating system (for compatibility)
        - Device type (desktop/mobile/tablet)
        - Screen resolution (for UI optimization)
    
        **3. Session Data**
        - Time spent in app
        - Pages/screens visited
        - Navigation patterns (to improve UX)
    
        **4. Error Logs**
        - Error types and frequency (for debugging)
        - Performance metrics (load times, crashes)
    
        **5. Aggregated Statistics**
        - Number of assets added (count only, not values)
        - Age ranges (e.g., 30-40, not exact age)
        - Retirement goal ranges (not exact amounts)
    
        ---
    
        ### 🎯 How We Use Data
    
        **Analytics data is used to:**
        - ✅ Understand how users navigate the app
        - ✅ Identify where users encounter problems
        - ✅ Fix bugs and improve performance
        - ✅ Improve user experience and interface
        - ✅ Measure feature adoption and usage
    
        **We NEVER:**
        - ❌ Sell your data to third parties
        - ❌ Use data for advertising or marketing
        - ❌ Share data with financial institutions
        - ❌ Track you across other websites
        - ❌ Build personal profiles or credit scores
    
        ---
    
        ### 🔒 Data Storage & Security
    
        **If you opt-in to analytics:**
        - Data stored with PostHog (analytics platform)
        - Servers located in US/EU (GDPR compliant)
        - Data encrypted in transit (HTTPS)
        - Data encrypted at rest (AES-256)
        - Data automatically deleted after 90 days
    
        **Financial calculations:**
        - All calculations happen in your browser
        - No financial data sent to our servers
        - No cloud storage of your account information
    
        ---
    
        ### 🌍 GDPR & Privacy Compliance
    
        **Your Rights:**
        - ✅ **Right to Opt-Out**: Decline analytics at any time
        - ✅ **Right to Access**: Request data we've collected
        - ✅ **Right to Delete**: Request deletion of your data
        - ✅ **Right to Export**: Request copy of your data
        - ✅ **Right to Correct**: Request corrections to data
    
        **GDPR Compliance:**
        - ✅ Opt-in consent required (not opt-out)
        - ✅ Clear explanation of data collection
        - ✅ Easy to withdraw consent
        - ✅ Data minimization (only what's needed)
        - ✅ Purpose limitation (analytics only)
    
        ---
    
        ### 🍪 Cookies & Tracking
    
        **Session Cookies (Required):**
        - Used to maintain your session state
        - Stored locally in your browser only
        - Deleted when you close browser
        - Not used for tracking across sites
    
        **Analytics Cookies (Optional):**
        - Only if you opt-in to analytics
        - Used to recognize returning users (anonymously)
        - Can be disabled by declining analytics
        - No third-party advertising cookies
    
        ---
    
        ### 📊 Session Recording (Optional)
    
        **If you opt-in to session recording:**
        - We may record your interactions with the app
        - Used to understand user experience and fix UI issues
        - **Financial data is automatically masked**
        - Recordings deleted after 30 days
        - You can opt-out at any time
    
        **What's Masked in Recordings:**
        - All number inputs (balances, ages, goals)
        - Text inputs (names, custom labels)
        - Uploaded file names and contents
    
        **What's Visible in Recordings:**
        - Mouse movements and clicks
        - Page navigation patterns
        - Button clicks and interactions
        - UI elements (labels, help text)
    
        ---
    
        ### 👤 Children's Privacy
    
        Smart Retire AI is not intended for users under 18 years of age. We do not knowingly collect data from children.
    
        ---
    
        ### 🔄 Third-Party Services
    
        **Analytics Provider:**
        - PostHog (https://posthog.com)
        - GDPR and SOC 2 compliant
        - Privacy policy: https://posthog.com/privacy
    
        **Hosting:**
        - Streamlit Cloud (https://streamlit.io)
        - Privacy policy: https://streamlit.io/privacy-policy
    
        **AI Statement Processing:**
        - n8n webhook (self-hosted)
        - No data retention beyond processing
    
        ---
    
        ### ⚖️ Legal Basis for Processing
    
        We process data based on:
        - **Consent**: You explicitly opt-in to analytics
        - **Legitimate Interest**: Error logging and app improvement
        - **Contract**: Providing the app service you requested
    
        ---
    
        ### 🔔 Changes to Privacy Policy
    
        We may update this policy to reflect:
        - Changes in data practices
        - New features or services
        - Legal or regulatory requirements
    
        **How you'll be notified:**
        - Updated "Last Updated" date above
        - In-app notification on next visit
        - Option to review changes before continuing
    
        ---
    
        ### 📧 Contact Us
    
        Questions about privacy or data practices?
    
        **Email:** smartretireai@gmail.com
        **Response Time:** 24-48 hours
        **Data Requests:** Include "Privacy Request" in subject
    
        ---
    
        ### 📝 Your Consent
    
        By clicking "I Accept" on the analytics consent screen:
        - You acknowledge reading this privacy policy
        - You consent to anonymous analytics collection
        - You understand you can opt-out at any time
        - You agree to the terms described above
    
        By clicking "No Thanks" on the analytics consent screen:
        - No analytics data will be collected
        - The app will function normally
        - You can opt-in later in Settings if desired
    
        ---
    
        **Thank you for trusting Smart Retire AI with your retirement planning!**
        """)
    
        if st.button("Close",use_container_width=True, type="primary"):
            st.rerun()


    @st.dialog("✏️ Edit AI-Extracted Accounts", width="large")
    def edit_ai_accounts_dialog():
        """Modal for editing AI-extracted accounts with isolated context."""
        # Custom CSS to maximize dialog width
        st.markdown("""
            <style>
            [data-testid="stDialog"] {
                width: 95vw !important;
                max-width: 95vw !important;
            }
            </style>
        """, unsafe_allow_html=True)

        st.info("💡 **Make any adjustments to your extracted accounts below.**")

        if st.session_state.ai_edited_table is not None:
            df_display = st.session_state.ai_edited_table.copy()

            # Define column configuration - same as reload view
            column_config = {
                "#": st.column_config.TextColumn("#", disabled=True, help="Row number", width="small"),
                "Institution": st.column_config.TextColumn(
                    "Institution",
                    disabled=True,
                    help="Financial institution (e.g., Fidelity, Morgan Stanley)",
                    width="small"
                ),
                "Account Name": st.column_config.TextColumn(
                    "Account Name",
                    help="Account name/description from statement",
                    width="small"
                ),
                "Last 4": st.column_config.TextColumn(
                    "Last 4",
                    disabled=True,
                    help="Last 4 digits of account number",
                    width="small"
                ),
                "Account Type": st.column_config.TextColumn(
                    "Account Type",
                    disabled=True,
                    help="Type of account (401k, IRA, Savings, etc.)",
                    width="small"
                ),
                "Tax Treatment": st.column_config.SelectboxColumn(
                    "Tax Treatment",
                    options=TAX_TREATMENT_OPTIONS,
                    help="Tax treatment: Tax-Deferred (401k/IRA), Tax-Free (Roth), Post-Tax (Brokerage)"
                ),
                "Current Balance": st.column_config.NumberColumn(
                    "Current Balance ($)",
                    min_value=0,
                    format="$%d",
                    help="Current account balance"
                ),
                "Annual Contribution": st.column_config.NumberColumn(
                    "Annual Contribution ($)",
                    min_value=0,
                    format="$%d",
                    help="How much you contribute annually"
                ),
                "Growth Rate (%)": st.column_config.NumberColumn(
                    "Growth Rate (%)",
                    min_value=0.0,
                    max_value=20.0,
                    format="%.1f%%",
                    help="Expected annual growth rate"
                ),
                "Tax Rate on Gains (%)": st.column_config.NumberColumn(
                    "Tax Rate on Gains (%)",
                    min_value=0.0,
                    max_value=50.0,
                    format="%.1f%%",
                    help="Tax rate on gains (capital gains or income tax)"
                )
            }

            # Add optional column configs if they exist
            if "Income Eligibility" in df_display.columns:
                column_config["Income Eligibility"] = None
            if "Purpose" in df_display.columns:
                column_config["Purpose"] = None

            # Display editable table in modal
            edited_df = st.data_editor(
                df_display,
                column_config=column_config,
                use_container_width=True,
                hide_index=True,
                num_rows="dynamic",
                key="ai_table_modal_editor"
            )

            st.markdown("---")

            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("✅ Save Changes", type="primary",use_container_width=True):
                    st.session_state.ai_edited_table = edited_df
                    st.session_state.dialog_open = False
                    st.rerun()
            with col2:
                if st.button("❌ Cancel",use_container_width=True):
                    st.session_state.dialog_open = False
                    st.rerun()
        else:
            st.warning("No extracted data available to edit.")
            if st.button("Close",use_container_width=True):
                st.session_state.dialog_open = False
                st.rerun()


    @st.dialog("Switch to Detailed Planning", width="medium")
    def detailed_planning_asset_choice_dialog():
        """Let the user decide whether to reuse or reset existing Detailed Planning accounts."""
        source_country = st.session_state.get("pending_detailed_switch_source_country", "US")

        if source_country != "US":
            st.info("Detailed Planning is currently US-only. If you continue, the setup will reopen in USD with US tax assumptions.")

        st.warning("You already have account data saved in Detailed Planning from an earlier session.")
        st.markdown("Choose how you want to continue:")
        st.markdown("- **Reuse existing accounts (Recommended)** keeps your saved accounts and editor state.")
        st.markdown("- **Start fresh** clears the saved uploads, tables, and manual account setup before reopening Detailed Planning.")

        col_reuse, col_fresh, col_cancel = st.columns(3)
        with col_reuse:
            if st.button("Reuse existing accounts", type="primary",use_container_width=True):
                _apply_detailed_planning_handoff(reuse_existing_assets=True)
        with col_fresh:
            if st.button("Start fresh",use_container_width=True):
                _apply_detailed_planning_handoff(reuse_existing_assets=False)
        with col_cancel:
            if st.button("Stay in Simple Planning",use_container_width=True):
                st.session_state.show_detailed_asset_choice_dialog = False
                st.session_state.pending_detailed_switch_fields = None
                st.session_state.pending_detailed_switch_source_country = None
                st.rerun()


    if 'show_whats_new' not in st.session_state:
        st.session_state.show_whats_new = False

    # Trigger What's New dialog if flagged (via footer button)
    if st.session_state.get('show_whats_new', False):
        st.session_state.show_whats_new = False
        whats_new_dialog()

    # Initialize session state for splash screen
    if 'splash_dismissed' not in st.session_state:
        st.session_state.splash_dismissed = False
    
    # Initialize session state for onboarding flow
    if 'onboarding_step' not in st.session_state:
        st.session_state.onboarding_step = 1
    if 'onboarding_complete' not in st.session_state:
        st.session_state.onboarding_complete = False
    
    # Initialize session state for page navigation
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'mode_selection'  # Can be 'mode_selection', 'chat_mode', 'onboarding', or 'results'

    # Initialize chat session state
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
    if 'chat_fields' not in st.session_state:
        st.session_state.chat_fields = {}
    if 'chat_complete' not in st.session_state:
        st.session_state.chat_complete = False
    if 'pending_detailed_switch_fields' not in st.session_state:
        st.session_state.pending_detailed_switch_fields = None
    if 'pending_detailed_switch_source_country' not in st.session_state:
        st.session_state.pending_detailed_switch_source_country = None
    if 'show_detailed_asset_choice_dialog' not in st.session_state:
        st.session_state.show_detailed_asset_choice_dialog = False
    if 'ai_upload_widget_version' not in st.session_state:
        st.session_state.ai_upload_widget_version = 0
    if 'csv_upload_widget_version' not in st.session_state:
        st.session_state.csv_upload_widget_version = 0
    
    # Initialize session state for baseline values (from onboarding)
    if 'birth_year' not in st.session_state:
        st.session_state.birth_year = datetime.now().year - 30
    if 'baseline_retirement_age' not in st.session_state:
        st.session_state.baseline_retirement_age = 65
    if 'baseline_life_expectancy' not in st.session_state:
        st.session_state.baseline_life_expectancy = 85
    if 'baseline_retirement_income_goal' not in st.session_state:
        st.session_state.baseline_retirement_income_goal = 0  # Optional field
    if 'baseline_life_expenses' not in st.session_state:
        st.session_state.baseline_life_expenses = 0
    if 'baseline_legacy_goal' not in st.session_state:
        st.session_state.baseline_legacy_goal = 0
    if 'client_name' not in st.session_state:
        st.session_state.client_name = ""
    if 'assets' not in st.session_state:
        st.session_state.assets = []
    if 'country' not in st.session_state:
        st.session_state.country = 'US'

    # Detailed Planning — conversational setup state
    if 'setup_messages' not in st.session_state:
        st.session_state.setup_messages = []
    if 'setup_fields' not in st.session_state:
        st.session_state.setup_fields = {}
    if 'setup_fields_locked' not in st.session_state:
        st.session_state.setup_fields_locked = False

    # Detailed Planning — post-results chat state
    if 'results_chat_messages' not in st.session_state:
        st.session_state.results_chat_messages = []
    if 'results_chat_context' not in st.session_state:
        st.session_state.results_chat_context = None
    if 'results_chat_whatif_modified' not in st.session_state:
        st.session_state.results_chat_whatif_modified = False
    if 'results_chat_pending' not in st.session_state:
        st.session_state.results_chat_pending = False

    # Detailed Planning — unified page state
    if 'dp_goals_done' not in st.session_state:
        st.session_state.dp_goals_done = False
    if 'dp_calculated' not in st.session_state:
        st.session_state.dp_calculated = False
    if 'dp_chat_messages' not in st.session_state:
        st.session_state.dp_chat_messages = []
    if 'dp_chat_pending' not in st.session_state:
        st.session_state.dp_chat_pending = False
    if 'dp_assets_hash' not in st.session_state:
        st.session_state.dp_assets_hash = None

    # ==========================================
    # SIDEBAR - Advanced Settings (Collapsed by Default)
    # ==========================================
    with st.sidebar:
        with st.expander("⚙️ Advanced Settings", expanded=False):
            _sb_india = st.session_state.get('country', 'US') == 'India'

            st.markdown("### Tax Settings")

            # Current tax rate with helpful guidance
            with st.expander("💡 How to find your current tax rate", expanded=False):
                if _sb_india:
                    st.markdown("""
                    **India Income Tax — New Regime (FY 2024-25):**
                    - 0%:  Up to ₹3,00,000
                    - 5%:  ₹3,00,001 – ₹7,00,000
                    - 10%: ₹7,00,001 – ₹10,00,000
                    - 15%: ₹10,00,001 – ₹12,00,000
                    - 20%: ₹12,00,001 – ₹15,00,000
                    - 30%: Above ₹15,00,000

                    Check your Form 16 or ITR for your effective rate.
                    """)
                else:
                    st.markdown("""
                    **To find your current marginal tax rate:**
                    1. **From your tax return**: Look at your most recent Form 1040, Line 15 (Taxable Income)
                    2. **Use IRS tax brackets**: Find which bracket your income falls into

                    **2024 Tax Brackets (Single):**
                    - 10%: $0 - $11,600
                    - 12%: $11,601 - $47,150
                    - 22%: $47,151 - $100,525
                    - 24%: $100,526 - $191,950
                    - 32%: $191,951 - $243,725
                    - 35%: $243,726 - $609,350
                    - 37%: $609,351+
                    """)

            current_tax_rate = st.slider(
                "Current Marginal Tax Rate (%)", 0, 50,
                key=f"sidebar_current_tax_rate_{st.session_state.get('country','US')}",
                value=10 if _sb_india else 22,
                help="Your current tax bracket based on your income",
            )

            with st.expander("💡 How to estimate retirement tax rate", expanded=False):
                if _sb_india:
                    st.markdown("""
                    **Consider these factors:**
                    1. **Lower income**: Most retirees have lower taxable income
                    2. **EPF / PPF withdrawals**: Fully tax-free at maturity
                    3. **NPS**: 60% lump sum is tax-free; annuity income is taxable
                    4. **Senior citizen benefit**: ₹50,000 standard deduction on pension income

                    **Common scenarios:**
                    - **Conservative**: Same as current rate
                    - **Optimistic**: 10% (EPF/PPF-heavy corpus)
                    - **Pessimistic**: 20–30% (large NPS annuity or rental income)
                    """)
                else:
                    st.markdown("""
                    **Consider these factors:**
                    1. **Lower income**: Most people have lower income in retirement
                    2. **Social Security**: Only 85% is taxable for most people
                    3. **Roth withdrawals**: Tax-free if qualified
                    4. **Required Minimum Distributions**: Start at age 73 (2024)

                    **Common scenarios:**
                    - **Conservative**: Same as current rate
                    - **Optimistic**: 10-15% lower than current
                    - **Pessimistic**: 5-10% higher (if tax rates increase)
                    """)

            retirement_tax_rate = st.slider(
                "Projected Retirement Tax Rate (%)", 0, 50,
                key=f"sidebar_retirement_tax_rate_{st.session_state.get('country','US')}",
                value=10 if _sb_india else 22,
                help="Expected tax rate in retirement",
            )

            st.markdown("---")
            st.markdown("### Growth Rate Assumptions")

            with st.expander("💡 Inflation guidance", expanded=False):
                if _sb_india:
                    st.markdown("""
                    **Historical context (India):**
                    - **Long-term CPI average**: 5–7% annually
                    - **Recent years**: 4–7% (2020–2024)
                    - **RBI target**: 4% annually

                    **Consider:**
                    - **Conservative**: 6–7% (safe for long-term planning)
                    - **Moderate**: 5–6%
                    - **Optimistic**: 4% (RBI target)
                    """)
                else:
                    st.markdown("""
                    **Historical context:**
                    - **Long-term average**: 3.0-3.5% annually
                    - **Recent years**: 2-4% (2020-2024)
                    - **Federal Reserve target**: 2% annually

                    **Consider:**
                    - **Conservative**: 2-3% (Fed target)
                    - **Moderate**: 3-4% (historical average)
                    - **Aggressive**: 4-5% (higher inflation)
                    """)

            inflation_rate = st.slider(
                "Expected Inflation Rate (%)", 0, 15 if _sb_india else 10,
                key=f"sidebar_inflation_rate_{st.session_state.get('country','US')}",
                value=7 if _sb_india else 3,
                help="Long-term inflation assumption (affects purchasing power)",
            )

            st.markdown("---")
            st.markdown("### Investment Growth Rate")

            with st.expander("💡 Growth rate guidance", expanded=False):
                if _sb_india:
                    st.markdown("""
                    **Typical annual growth rates (India):**
                    - **Equity MF (large-cap)**: 10–12%
                    - **Equity MF (flexi/mid-cap)**: 12–15%
                    - **Balanced / hybrid MF**: 8–10%
                    - **Debt MF / FD**: 6–7%
                    - **PPF / EPF**: 7–8%

                    **Note:** This is used as the default when adding investment accounts.
                    """)
                else:
                    st.markdown("""
                    **Typical annual growth rates:**
                    - **Stocks/Equity funds**: 7-10%
                    - **Bonds/Fixed income**: 4-5%
                    - **Savings accounts**: 2-4%
                    - **Conservative portfolio**: 5-6%
                    - **Aggressive portfolio**: 8-10%

                    **Note:** This is used as the default when adding investment accounts.
                    """)

            default_growth_rate = st.slider(
                "Default Growth Rate for Investments (%)",
                min_value=0.0,
                max_value=20.0,
                key=f"sidebar_default_growth_rate_{st.session_state.get('country','US')}",
                value=10.0 if _sb_india else 7.0,
                step=0.5,
                help="Default annual growth rate for investment accounts (stocks, bonds, etc.)",
            )
    
            st.markdown("---")
            st.markdown("### 📊 Analytics & Privacy")
    
            # Show current analytics status
            analytics_enabled = is_analytics_enabled()
            if analytics_enabled:
                st.success("✅ **Analytics Enabled** - Helping us improve Smart Retire AI")
            else:
                st.info("ℹ️ **Analytics Disabled** - No usage data is collected")
    
            # Privacy policy link
            if st.button("📄 View Privacy Policy",use_container_width=True, key="sidebar_privacy_policy"):
                show_privacy_policy()
    
            # Opt-out/Opt-in toggle
            col1, col2 = st.columns(2)
            with col1:
                if st.button("❌ Disable Analytics",use_container_width=True, disabled=not analytics_enabled):
                    opt_out()
                    st.success("✅ Analytics disabled")
                    st.rerun()
            with col2:
                if st.button("✅ Enable Analytics",use_container_width=True, disabled=analytics_enabled):
                    opt_in()
                    st.success("✅ Analytics enabled")
                    st.rerun()
    
            # Reset analytics session (for testing)
            with st.expander("🔧 Advanced: Reset Analytics Session"):
                st.caption("Clear all analytics session data and start fresh. Useful for testing or privacy reset.")
                if st.button("🔄 Reset Analytics Session",use_container_width=True, key="reset_analytics"):
                    reset_analytics_session()
                    st.success("✅ Analytics session reset")
                    st.info("ℹ️ Refresh the page to see the analytics consent screen again.")
                    st.rerun()
    
            st.markdown("---")
            st.markdown("**💡 Tip:** Adjust these settings anytime during the onboarding process.")
    
    # Home button — visible from sub-pages so users can always return to Results
    if st.session_state.get('current_page') in ('detailed_analysis', 'monte_carlo'):
        st.sidebar.markdown("---")
        if st.sidebar.button("🏠 Back to Planning",use_container_width=True, type="primary"):
            if st.session_state.get('results_source') == 'detailed_planning':
                st.session_state.current_page = 'detailed_planning'
            else:
                st.session_state.current_page = 'results'
            st.rerun()

    # Reset button — show during onboarding and after completion
    if st.session_state.onboarding_complete or st.session_state.get('current_page') in ('onboarding', 'detailed_planning'):
        st.sidebar.markdown("---")
        if st.sidebar.button("🔄 Reset Onboarding",use_container_width=True):
            st.session_state.onboarding_step = 1
            st.session_state.onboarding_complete = False
            st.session_state.setup_messages = []
            st.session_state.setup_fields = {}
            st.session_state.setup_fields_locked = False
            if st.session_state.get('current_page') == 'detailed_planning':
                clear_detailed_planning_asset_state(st.session_state)
                st.session_state.dp_goals_done = False
                st.session_state.dp_calculated = False
                st.session_state.dp_chat_messages = []
                st.session_state.dp_assets_hash = None
            st.rerun()
    
    # Initialize session state for what-if scenario values (used on results page)
    if 'whatif_retirement_age' not in st.session_state:
        _current_age = datetime.now().year - st.session_state.get("birth_year", 1990)
        st.session_state.whatif_retirement_age = max(st.session_state.baseline_retirement_age, _current_age)
    if 'whatif_life_expectancy' not in st.session_state:
        st.session_state.whatif_life_expectancy = st.session_state.baseline_life_expectancy
    if 'whatif_retirement_income_goal' not in st.session_state:
        st.session_state.whatif_retirement_income_goal = st.session_state.baseline_retirement_income_goal
    if 'whatif_current_tax_rate' not in st.session_state:
        st.session_state.whatif_current_tax_rate = 22
    if 'whatif_retirement_tax_rate' not in st.session_state:
        st.session_state.whatif_retirement_tax_rate = 22
    if 'whatif_inflation_rate' not in st.session_state:
        st.session_state.whatif_inflation_rate = 3
    if 'whatif_life_expenses' not in st.session_state:
        st.session_state.whatif_life_expenses = st.session_state.baseline_life_expenses
    if 'whatif_legacy_goal' not in st.session_state:
        st.session_state.whatif_legacy_goal = st.session_state.baseline_legacy_goal
    if 'whatif_retirement_growth_rate' not in st.session_state:
        st.session_state.whatif_retirement_growth_rate = 4.0
    
    # Legacy compatibility (keep retirement_age, life_expectancy for backward compatibility)
    if 'retirement_age' not in st.session_state:
        st.session_state.retirement_age = st.session_state.baseline_retirement_age
    if 'life_expectancy' not in st.session_state:
        st.session_state.life_expectancy = st.session_state.baseline_life_expectancy
    if 'retirement_income_goal' not in st.session_state:
        st.session_state.retirement_income_goal = st.session_state.baseline_retirement_income_goal
    
    # ==========================================
    # PRIVACY POLICY DIALOG
    # ==========================================
    
    
    
    # ==========================================
    # SPLASH SCREEN / WELCOME PAGE
    # ==========================================
    if not st.session_state.splash_dismissed:
        # Display splash screen
        # Compact splash header
        st.markdown(
            f"""
            <div style='background: linear-gradient(135deg, #1f77b4 0%, #2ca02c 100%);
                        padding: 28px 32px;
                        border-radius: 16px;
                        text-align: center;
                        color: white;
                        margin: 16px auto 20px auto;
                        max-width: 900px;
                        box-shadow: 0 4px 16px rgba(0,0,0,0.12);'>
                <div style='font-size: 2em; font-weight: bold; margin-bottom: 4px;'>💰 Smart Retire AI</div>
                <div style='font-size: 0.95em; opacity: 0.85; margin-bottom: 6px;'>Version {VERSION} &nbsp;·&nbsp; Best used on a desktop browser</div>
                <div style='font-size: 1.15em; font-weight: 500; opacity: 0.95;'>Your AI-Powered Retirement Planning Companion</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 4 key features in a 2-column grid
        st.markdown("#### ✨ What you can do")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**💬 Simple Planning**")
            st.caption("Answer 3 questions in a chat and get your required corpus/portfolio instantly — no forms.")
            st.markdown("")
            st.markdown("**📊 Detailed Planning (US-only)**")
            st.caption("Upload US retirement statements, enter account balances, and get tax-aware year-by-year projections.")
        with col2:
            st.markdown("**🎯 What-If Scenarios**")
            st.caption("Adjust any assumption — retirement age, income, growth rate — and see results update instantly.")
            st.markdown("")
            st.markdown("**🌍 Planning Coverage**")
            st.caption("Simple Planning supports US and India. Detailed Planning currently supports US households only.")

        st.markdown("---")

        # Analytics notice (auto opt-in)
        st.caption(
            "📊 By continuing you agree to anonymous usage analytics to help us improve the app. "
            "No financial data or personal information is ever collected. "
            "You can opt out anytime in Advanced Settings."
        )

        # Continue button
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("✅ Get Started", type="primary",use_container_width=True):
                st.session_state.splash_dismissed = True
                set_analytics_consent(True)
                st.rerun()

        _rn_content = load_release_notes()
        _rn_overview = extract_release_overview(_rn_content, include_heading=False)
        if _rn_overview:
            with st.expander(f"🆕 What's new in v{VERSION}", expanded=False):
                st.markdown(_rn_overview)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            """
            <div style='text-align: center; color: #999; font-size: 0.85em;'>
                Questions? <a href='mailto:smartretireai@gmail.com' style='color: #1f77b4;'>smartretireai@gmail.com</a>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
        # Stop rendering the rest of the page
        st.stop()
    
    # ==========================================
    # PAGE ROUTING
    # ==========================================
    # Route to appropriate page based on current_page state

    if st.session_state.current_page == 'mode_selection':
        show_mode_selection_page()

    elif st.session_state.current_page == 'chat_mode':
        if st.session_state.get("show_detailed_asset_choice_dialog", False):
            detailed_planning_asset_choice_dialog()
        show_chat_mode_page()

    elif st.session_state.current_page in ('onboarding', 'detailed_planning'):
        show_detailed_planning()

    elif st.session_state.current_page == 'results':

        # ==========================================
        # RESULTS & ANALYSIS PAGE
        # ==========================================
    
        # Track page view
        track_page_view('results')
    
        # Add navigation button to go back to setup
        if st.button("← Back to Setup"):
            track_event('navigation_back_to_setup')
            # Return to whichever page last navigated to results
            if st.session_state.get('results_source') == 'chat_mode':
                st.session_state.current_page = 'chat_mode'
            else:
                st.session_state.current_page = 'detailed_planning'
            st.rerun()
    
        st.markdown("---")
    
        # Header
        st.header("📊 Retirement Projection & Analysis")
        st.markdown("Explore your retirement projections and adjust scenarios with what-if analysis below.")
    
    
        # Calculate values from what-if session state for results
        current_year = datetime.now().year
        age = current_year - st.session_state.birth_year
        retirement_age = st.session_state.whatif_retirement_age
        life_expectancy = st.session_state.whatif_life_expectancy
        retirement_income_goal = st.session_state.whatif_retirement_income_goal
        current_tax_rate = st.session_state.whatif_current_tax_rate
        retirement_tax_rate = st.session_state.whatif_retirement_tax_rate
        inflation_rate = st.session_state.whatif_inflation_rate
        retirement_growth_rate = st.session_state.whatif_retirement_growth_rate
        life_expenses = st.session_state.whatif_life_expenses
        legacy_goal = st.session_state.get('whatif_legacy_goal', 0)
        assets = st.session_state.assets
        
        if int(retirement_age) < int(age):
            st.error(
                f"⚠️ **Retirement age ({int(retirement_age)}) is less than your current age ({int(age)}).**\n\n"
                f"Please ask the chatbot below to update your retirement age to {int(age)} or later."
            )
            st.stop()

        try:
            inputs = UserInputs(
                age=int(age),
                retirement_age=int(retirement_age),
                life_expectancy=int(life_expectancy),
                annual_income=0.0,  # Not used in calculations anymore
                contribution_rate_pct=15.0,  # Not used in new system
                expected_growth_rate_pct=7.0,  # Not used in new system
                inflation_rate_pct=float(inflation_rate),
                current_marginal_tax_rate_pct=float(current_tax_rate),
                retirement_marginal_tax_rate_pct=float(retirement_tax_rate),
                assets=assets
            )
        
            result = project(inputs)
    
            # Save result and inputs to session state for Next Steps dialogs
            st.session_state.last_result = result
            st.session_state.last_inputs = inputs
    
            # Adjust after-tax balance for life expenses
            total_after_tax_original = result['Total After-Tax Balance']
    
            # Validate life expenses don't exceed portfolio balance
            if life_expenses > total_after_tax_original:
                st.error(f"""
                ⚠️ **One-Time Expenses Exceed Portfolio Balance**

                Your one-time expenses at retirement (**${life_expenses:,.0f}**) exceed
                your projected after-tax portfolio balance (**${total_after_tax_original:,.0f}**).

                Please either:
                - Reduce one-time expenses, or
                - Adjust your portfolio contributions/retirement age to build a larger balance
                """)
                st.stop()
    
            total_after_tax = total_after_tax_original - life_expenses

            # Calculate retirement income before rendering Key Metrics so it can be displayed there
            years_in_retirement = life_expectancy - retirement_age

            # Validate years in retirement
            if years_in_retirement <= 0:
                st.error(f"""
                ⚠️ **Invalid Retirement Period**

                Your life expectancy (**{life_expectancy}**) must be greater than
                your retirement age (**{retirement_age}**).

                Please adjust these values in the sliders above.
                """)
                st.stop()

            # --- Retirement income: year-by-year simulation with sequencing + RMDs ---
            # Split projected FVs into three pots by account type.
            pretax_fv = sum(
                ar['pre_tax_value']
                for ar, ai in zip(result['asset_results'], result['assets_input'])
                if ai.asset_type in (AssetType.PRE_TAX, AssetType.TAX_DEFERRED)
            )
            roth_fv = sum(
                ar['pre_tax_value']
                for ar, ai in zip(result['asset_results'], result['assets_input'])
                if ai.asset_type == AssetType.POST_TAX and 'roth' in ai.name.lower()
            )
            brok_fv = sum(
                ar['pre_tax_value']
                for ar, ai in zip(result['asset_results'], result['assets_input'])
                if ai.asset_type == AssetType.POST_TAX and 'roth' not in ai.name.lower()
            )
            brok_cost_basis = sum(
                ar['total_contributions'] + ai.current_balance
                for ar, ai in zip(result['asset_results'], result['assets_input'])
                if ai.asset_type == AssetType.POST_TAX and 'roth' not in ai.name.lower()
            )

            # Deduct life expenses proportionally across all three pots
            total_fv_all = pretax_fv + roth_fv + brok_fv
            if life_expenses > 0 and total_fv_all > 0:
                frac = life_expenses / total_fv_all
                pretax_fv       = max(0.0, pretax_fv       * (1.0 - frac))
                roth_fv         = max(0.0, roth_fv         * (1.0 - frac))
                brok_fv         = max(0.0, brok_fv         * (1.0 - frac))
                brok_cost_basis = max(0.0, brok_cost_basis * (1.0 - frac))

            annual_retirement_income, sim_data = find_sustainable_withdrawal(
                pretax_fv, roth_fv, brok_fv, brok_cost_basis,
                int(retirement_age), int(life_expectancy),
                retirement_growth_rate / 100.0, inflation_rate / 100.0,
                float(retirement_tax_rate),
                legacy_goal=legacy_goal,
            )
            st.session_state.cashflow_sim_data = sim_data
            st.session_state.last_annual_retirement_income = annual_retirement_income

            # --- Pre-compute deterministic gap-closing values (Python-exact) ---
            _current_age = datetime.now().year - st.session_state.birth_year
            _breakeven_age: int | None = None
            _income_at_breakeven: float = 0.0
            _breakeven_contrib: int | None = None
            _contrib_breakdown: dict = {}
            _contrib_irs_maxed: bool = False
            _assets_input = result.get("assets_input", assets)

            if retirement_income_goal > 0 and annual_retirement_income < retirement_income_goal:
                _breakeven_age, _income_at_breakeven = find_breakeven_retirement_age(
                    assets_input=_assets_input,
                    current_age=_current_age,
                    start_retirement_age=int(retirement_age),
                    life_expectancy=int(life_expectancy),
                    target_income=float(retirement_income_goal),
                    retirement_growth_rate=retirement_growth_rate / 100.0,
                    inflation_rate=inflation_rate / 100.0,
                    retirement_tax_rate_pct=float(retirement_tax_rate),
                    life_expenses=life_expenses,
                    legacy_goal=legacy_goal,
                )
                _breakeven_contrib, _contrib_breakdown, _contrib_irs_maxed = find_breakeven_contribution(
                    assets_input=_assets_input,
                    current_age=_current_age,
                    retirement_age=int(retirement_age),
                    life_expectancy=int(life_expectancy),
                    target_income=float(retirement_income_goal),
                    retirement_growth_rate=retirement_growth_rate / 100.0,
                    inflation_rate=inflation_rate / 100.0,
                    retirement_tax_rate_pct=float(retirement_tax_rate),
                    life_expenses=life_expenses,
                    legacy_goal=legacy_goal,
                )

            # Persist gap-closing values so detailed_analysis Income & Gap tab can read them
            st.session_state.last_breakeven_age = _breakeven_age
            st.session_state.last_income_at_breakeven = _income_at_breakeven
            st.session_state.last_breakeven_contrib = _breakeven_contrib
            st.session_state.last_contrib_breakdown = _contrib_breakdown
            st.session_state.last_contrib_irs_maxed = _contrib_irs_maxed

            # --- Quick Monte Carlo for chat context (500 sims, reproducible seed) ---
            _mc_summary: dict = {}
            try:
                from financialadvisor.core.monte_carlo import (
                    run_monte_carlo_simulation,
                    calculate_probability_of_goal,
                )
                _mc = run_monte_carlo_simulation(inputs, num_simulations=500, seed=42)
                _mc_prob = calculate_probability_of_goal(
                    _mc["outcomes"],
                    int(retirement_age), int(life_expectancy),
                    float(retirement_income_goal) if retirement_income_goal > 0 else 0.0,
                )
                _mc_summary = {
                    "income_p10":  _mc["income_percentiles"]["10th"],
                    "income_p50":  _mc["income_percentiles"]["50th"],
                    "income_p90":  _mc["income_percentiles"]["90th"],
                    "bal_p10":     _mc["percentiles"]["10th"],
                    "bal_p50":     _mc["percentiles"]["50th"],
                    "bal_p90":     _mc["percentiles"]["90th"],
                    "prob_success": _mc_prob,
                    "volatility":   _mc["volatility"],
                    "num_sims":     _mc["num_simulations"],
                }
            except Exception as _mc_err:
                import logging as _logging
                _logging.getLogger(__name__).debug("MC context skipped: %s", _mc_err)

            # --- Build chat context for results advisor ---
            if _CHAT_CONTEXT_AVAILABLE:
                _whatif_snapshot = {
                    "retirement_age":         retirement_age,
                    "life_expectancy":        life_expectancy,
                    "retirement_income_goal": retirement_income_goal,
                    "inflation_rate":         inflation_rate,
                    "retirement_growth_rate": retirement_growth_rate,
                    "retirement_tax_rate":    retirement_tax_rate,
                    "life_expenses":          life_expenses,
                    "legacy_goal":            legacy_goal,
                }
                st.session_state.results_chat_context = build_detailed_chat_context(
                    result=result,
                    inputs=inputs,
                    annual_retirement_income=annual_retirement_income,
                    sim_data=sim_data,
                    whatif_values=_whatif_snapshot,
                    assets=assets,
                    birth_year=st.session_state.get("birth_year"),
                    breakeven_retirement_age=_breakeven_age,
                    income_at_breakeven=_income_at_breakeven,
                    breakeven_contribution=_breakeven_contrib,
                    contrib_breakdown=_contrib_breakdown,
                    contrib_irs_maxed=_contrib_irs_maxed,
                    mc_summary=_mc_summary,
                )

            # Key metrics in a prominent container
            with st.container():
                st.subheader("🎯 Key Metrics")
                _baseline_age = datetime.now().year - st.session_state.birth_year
                _baseline_goal = (
                    f"  ·  Income goal: ${st.session_state.baseline_retirement_income_goal:,.0f}/yr"
                    if st.session_state.baseline_retirement_income_goal > 0 else ""
                )
                st.caption(
                    f"Age {_baseline_age}  ·  Retire at {st.session_state.baseline_retirement_age}"
                    f"  ·  Plan through {st.session_state.baseline_life_expectancy}"
                    f"  ·  {len(st.session_state.assets)} account(s){_baseline_goal}"
                    f"  ·  To adjust any values, just ask the chatbot below."
                )
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("Years to Retirement", f"{result['Years Until Retirement']:.0f}")
                with col2:
                    st.metric("Total Pre-Tax Value", f"${result['Total Future Value (Pre-Tax)']:,.0f}")
                with col3:
                    _atv_help = "Estimated using a year-by-year simulation: each year all account pots grow, forced RMDs are paid first, then withdrawals follow brokerage → pre-tax → Roth order. The annual withdrawal is the maximum that sustains the portfolio through your life expectancy."
                    if life_expenses > 0:
                        st.metric(
                            "Total After-Tax Value",
                            f"${total_after_tax:,.0f}",
                            delta=f"-${life_expenses:,.0f} one-time expense",
                            delta_color="normal",
                            help=_atv_help,
                        )
                    else:
                        st.metric("Total After-Tax Value", f"${total_after_tax:,.0f}", help=_atv_help)
                with col4:
                    st.metric("Tax Efficiency", f"{result['Tax Efficiency (%)']:.1f}%")
                with col5:
                    _income_help = "Maximum annual income your portfolio can sustain throughout retirement, modeled with year-by-year withdrawals using optimal sequencing (taxable → pre-tax → Roth) and IRS RMDs starting at age 73."
                    if retirement_income_goal > 0:
                        _income_delta = annual_retirement_income - retirement_income_goal
                        _delta_sign = "+" if _income_delta >= 0 else "-"
                        _delta_abs = abs(_income_delta)
                        st.metric(
                            "Projected Annual Income",
                            f"${annual_retirement_income:,.0f}/yr",
                            delta=f"{_delta_sign}${_delta_abs:,.0f} vs goal",
                            delta_color="normal",
                            help=_income_help,
                        )
                    else:
                        st.metric("Projected Annual Income", f"${annual_retirement_income:,.0f}/yr", help=_income_help)

            if legacy_goal > 0:
                st.metric(
                    "Legacy Goal",
                    f"${legacy_goal:,.0f}",
                    help="Target portfolio balance at end of life — the withdrawal simulation ensures this amount remains for your heirs. Unlike a one-time expense, this is not deducted at retirement; it reduces the sustainable withdrawal rate instead.",
                )
    
            # --- Narrative summary card ---
            _tax_eff = result.get("Tax Efficiency (%)", 0)
            _income_fmt = f"\\${annual_retirement_income:,.0f}"
            if retirement_income_goal > 0:
                _shortfall = retirement_income_goal - annual_retirement_income
                _goal_fmt = f"\\${retirement_income_goal:,.0f}"
                if _shortfall > 0:
                    _shortfall_fmt = f"\\${_shortfall:,.0f}"
                    _income_line = (
                        f"Your portfolio projects **{_income_fmt}/year** "
                        f"— **{_shortfall_fmt} below** your {_goal_fmt} goal."
                    )
                else:
                    _surplus_fmt = f"\\${-_shortfall:,.0f}"
                    _income_line = (
                        f"Your portfolio projects **{_income_fmt}/year** "
                        f"— **{_surplus_fmt} above** your {_goal_fmt} goal. ✅"
                    )
            else:
                _income_line = f"Your portfolio projects **{_income_fmt}/year** in retirement."
            _tax_comment = (
                "excellent" if _tax_eff > 85
                else "good, with room to optimize" if _tax_eff > 75
                else "below average — optimization recommended"
            )
            _tax_line = f"Tax efficiency: **{_tax_eff:.0f}%** ({_tax_comment})."
            _pretax_fmt = f"\\${result.get('Total Future Value (Pre-Tax)', 0):,.0f}"
            _pretax_line = f"Total pre-tax value at retirement: **{_pretax_fmt}**."
            st.info(f"{_income_line}  \n{_tax_line}  \n{_pretax_line}")

            if st.session_state.results_chat_whatif_modified:
                st.warning(
                    "💬 Scenario modified via chat — numbers above reflect your adjusted scenario. "
                    "Use **Reset to Baseline** in the sidebar to restore original values."
                )

            _co_income = f"\\${annual_retirement_income:,.0f}"
            _co_goal = f"\\${retirement_income_goal:,.0f}"
            _co_gap = f"\\${retirement_income_goal - annual_retirement_income:,.0f}"
            if retirement_income_goal > 0 and (retirement_income_goal - annual_retirement_income) > 0:
                _chat_opener = (
                    f"Your portfolio projects **{_co_income}/year** — "
                    f"**{_co_gap} below** your {_co_goal} goal.\n\n"
                    f"I can explain how this is calculated, help you understand RMDs and Social Security, "
                    f"run what-if scenarios, or **run 1,000 Monte Carlo simulations** to see a range of outcomes. "
                    f"What would you like to explore?"
                )
            elif retirement_income_goal > 0:
                _chat_opener = (
                    f"Great news — your portfolio projects **{_co_income}/year**, "
                    f"exceeding your {_co_goal} goal!\n\n"
                    f"I can explain the calculation, discuss RMDs, Social Security, explore what-ifs, "
                    f"or **run 1,000 Monte Carlo simulations** to stress-test your plan. "
                    f"What would you like to know?"
                )
            else:
                _chat_opener = (
                    f"Your portfolio is projected to generate **{_co_income}/year** in retirement.\n\n"
                    f"Ask me anything — how this is calculated, RMDs, Social Security, what-if scenarios, "
                    f"which account has the highest balance, or **run Monte Carlo simulations** to see a range of outcomes."
                )
            _render_results_chat_panel(opening_message=_chat_opener)

            # --- Share & Feedback ---
            st.markdown("---")
            with st.expander("💬 Share & Feedback", expanded=False):
                feedback_tab1, feedback_tab2, feedback_tab3 = st.tabs(["📤 Share", "⭐ Feedback", "📧 Contact"])

                with feedback_tab1:
                    st.markdown("**Share Smart Retire AI with others:** (Tip: Turn the pop-up blocker off for best results)")

                    app_url = "https://smartretireai.streamlit.app"

                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        twitter_text = "Just planned my retirement with Smart Retire AI! 🎯 FREE tool featuring:\n✅ AI-powered analysis\n✅ Tax optimization\n✅ Monte Carlo simulations\n✅ Personalized insights\n\nPlan your financial future →"
                        twitter_encoded = urllib.parse.quote(twitter_text)
                        twitter_url = f"https://twitter.com/intent/tweet?text={twitter_encoded}&url={app_url}"
                        if st.button("🐦 Twitter", use_container_width=True, key="share_twitter"):
                            components.html(f"""<script>window.open("{twitter_url}", "_blank");</script>""", height=0)
                            st.success("Opening Twitter in new tab...")

                    with col2:
                        linkedin_url = f"https://www.linkedin.com/sharing/share-offsite/?url={app_url}"
                        if st.button("💼 LinkedIn", use_container_width=True, key="share_linkedin"):
                            components.html(f"""<script>window.open("{linkedin_url}", "_blank");</script>""", height=0)
                            st.success("Opening LinkedIn in new tab...")

                    with col3:
                        facebook_url = f"https://www.facebook.com/sharer/sharer.php?u={app_url}"
                        if st.button("📘 Facebook", use_container_width=True, key="share_facebook"):
                            components.html(f"""<script>window.open("{facebook_url}", "_blank");</script>""", height=0)
                            st.success("Opening Facebook in new tab...")

                    with col4:
                        if st.button("📧 Email", use_container_width=True, key="share_email"):
                            email_subject = "Powerful FREE Retirement Planning Tool - Smart Retire AI"
                            email_body = (
                                "Hi!%0A%0A"
                                "I discovered Smart Retire AI and thought you might find it helpful for retirement planning.%0A%0A"
                                "✨ What makes it special:%0A"
                                "• AI-powered financial statement analysis%0A"
                                "• Tax-optimized retirement projections%0A"
                                "• Monte Carlo simulations for risk assessment%0A"
                                "• Personalized recommendations based on your goals%0A"
                                "• PDF reports with detailed breakdowns%0A"
                                "• Completely FREE to use%0A%0A"
                                "Check it out: " + app_url + "%0A%0A"
                                "Best regards"
                            )
                            email_url = f"mailto:?subject={email_subject}&body={email_body}"
                            components.html(f"""<script>window.location.href="{email_url}";</script>""", height=0)
                            st.success("Opening email client...")

                    st.markdown("---")
                    st.markdown("**Or copy and share the link:**")
                    st.code(app_url, language=None)

                with feedback_tab2:
                    st.markdown("**We'd love to hear from you!**")

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("👍 Love it!", use_container_width=True, key="feedback_love"):
                            st.success("Thank you! 💚")
                            st.markdown("[Tell us what you love →](mailto:smartretireai@gmail.com?subject=Positive%20Feedback)")
                    with col2:
                        if st.button("👎 Could improve", use_container_width=True, key="feedback_improve"):
                            st.info("Thanks for the feedback!")
                            st.markdown("[Share suggestions →](mailto:smartretireai@gmail.com?subject=Suggestions)")

                    st.markdown("---")

                    with st.form("simple_feedback_nextsteps"):
                        feedback_msg = st.text_area("Your feedback:", placeholder="Share your thoughts, report bugs, or request features...", height=100)
                        if st.form_submit_button("📧 Send Feedback"):
                            if feedback_msg:
                                email_url = f"mailto:smartretireai@gmail.com?subject=Smart%20Retire%20AI%20Feedback&body={feedback_msg}"
                                st.success("Ready to send!")
                                st.markdown(f"[Click to open email →]({email_url})")

                with feedback_tab3:
                    st.markdown("""
                    **Get in touch:**

                    📧 **Email:** [smartretireai@gmail.com](mailto:smartretireai@gmail.com)
                    ⏱️ **Response time:** 24-48 hours
                    🐙 **GitHub:** [Report Issues](https://github.com/abhorkarpet/financialadvisor/issues)

                    We're here to help with questions, bugs, or feature requests!
                    """)

        except Exception as e:
            st.error(f"❌ **Error in calculation**: {e}")
            with st.expander("🔍 Error Details", expanded=False):
                st.exception(e)

    elif st.session_state.current_page == 'detailed_analysis':
        # ==========================================
        # DETAILED ANALYSIS PAGE
        # ==========================================

        track_page_view('detailed_analysis')

        if st.button("← Back"):
            if st.session_state.get('results_source') == 'detailed_planning':
                st.session_state.current_page = 'detailed_planning'
            else:
                st.session_state.current_page = 'results'
            st.rerun()

        st.markdown("---")
        st.header("📈 Detailed Analysis")

        result = st.session_state.get('last_result')
        inputs = st.session_state.get('last_inputs')

        if not result:
            st.warning("No analysis data found. Please run a retirement analysis first.")
            st.stop()

        detail_tab1, detail_tab2, detail_tab3, detail_tab4 = st.tabs(["💰 Asset Breakdown", "📊 Tax Analysis", "📋 Summary", "🎯 Income & Gap"])

        with detail_tab1:
            st.write("**Individual Asset Values at Retirement**")

            if 'asset_results' in result and 'assets_input' in result:
                asset_data = []
                total_current = 0
                total_contributions = 0
                total_growth = 0
                total_pre_tax = 0
                total_taxes = 0
                total_after_tax = 0

                for i, (asset_result, asset_input) in enumerate(zip(result['asset_results'], result['assets_input'])):
                    current_balance = asset_input.current_balance
                    contributions = asset_result['total_contributions']
                    pre_tax_value = asset_result['pre_tax_value']
                    tax_liability = asset_result['tax_liability']
                    after_tax_value = asset_result['after_tax_value']
                    growth = pre_tax_value - current_balance - contributions

                    total_current += current_balance
                    total_contributions += contributions
                    total_growth += growth
                    total_pre_tax += pre_tax_value
                    total_taxes += tax_liability
                    total_after_tax += after_tax_value

                    asset_data.append({
                        "Account": _humanize_ai_account_name(asset_result['name']),
                        "Current Balance": f"${current_balance:,.0f}",
                        "Your Contributions": f"${contributions:,.0f}",
                        "Investment Growth": f"${growth:,.0f}",
                        "Pre-Tax Value": f"${pre_tax_value:,.0f}",
                        "Est. Taxes": f"${tax_liability:,.0f}",
                        "After-Tax Value": f"${after_tax_value:,.0f}"
                    })

                if asset_data:
                    asset_data.append({
                        "Account": "📊 TOTAL",
                        "Current Balance": f"${total_current:,.0f}",
                        "Your Contributions": f"${total_contributions:,.0f}",
                        "Investment Growth": f"${total_growth:,.0f}",
                        "Pre-Tax Value": f"${total_pre_tax:,.0f}",
                        "Est. Taxes": f"${total_taxes:,.0f}",
                        "After-Tax Value": f"${total_after_tax:,.0f}"
                    })
                    st.info("💡 **How to read this table**: Current Balance → Add Your Contributions → Add Investment Growth = Pre-Tax Value → Subtract Taxes = After-Tax Value")
                    st.dataframe(pd.DataFrame(asset_data),use_container_width=True, hide_index=True)
                else:
                    st.info("No individual asset breakdown available")
            else:
                asset_data = []
                for key, value in result.items():
                    if "Asset" in key and "After-Tax" in key:
                        asset_name = key.split(" - ")[1].replace(" (After-Tax)", "")
                        asset_data.append({
                            "Account": _humanize_ai_account_name(asset_name),
                            "After-Tax Value": f"${value:,.0f}"
                        })
                if asset_data:
                    st.dataframe(pd.DataFrame(asset_data),use_container_width=True, hide_index=True)
                else:
                    st.info("No individual asset breakdown available")

            st.markdown("---")
            with st.expander("📊 How Are These Numbers Calculated?", expanded=False):
                st.markdown("Click below to see a detailed breakdown of the calculation formula and methodology.")
                if st.button("🔍 Show Detailed Calculation Explanation", key="show_explanation_btn"):
                    explanation = explain_projected_balance(inputs)
                    st.text(explanation)
                    st.download_button(
                        label="📥 Download Explanation",
                        data=explanation,
                        file_name=f"retirement_calculation_explanation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain",
                        key="download_explanation_btn"
                    )

        with detail_tab2:
            tax_liability = result.get("Total Tax Liability", 0.0)
            total_pre_tax = result.get("Total Future Value (Pre-Tax)", 1.0)
            tax_percentage = (tax_liability / total_pre_tax * 100) if total_pre_tax > 0 else 0.0

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Tax Liability", f"${tax_liability:,.0f}")
                st.metric("Tax as % of Pre-Tax Value", f"{tax_percentage:.1f}%")
            with col2:
                if result["Tax Efficiency (%)"] > 85:
                    st.success("🎉 **Excellent tax efficiency!** Your portfolio is well-optimized with minimal tax liability.")
                elif result["Tax Efficiency (%)"] > 75:
                    st.warning(f"⚠️ **Good tax efficiency** ({tax_percentage:.1f}% tax burden), but there may be room for improvement. *Goal: Lower this percentage by shifting assets to tax-advantaged accounts.*")
                    with st.expander("💡 **Get Tax Optimization Advice**", expanded=False):
                        st.markdown("""
                        ### 🎯 **Tax Optimization Strategies**

                        **1. Asset Location Optimization:**
                        - **Taxable accounts**: Hold tax-efficient index funds, municipal bonds
                        - **401(k)/IRA**: Hold high-dividend stocks, REITs, bonds
                        - **Roth IRA**: Hold high-growth stocks, international funds

                        **2. Contribution Strategy:**
                        - **Maximize employer 401(k) match** (free money!)
                        - **Consider Roth vs Traditional** based on current vs future tax rates
                        - **Backdoor Roth IRA** if income exceeds limits

                        **3. Withdrawal Strategy:**
                        - **Tax-loss harvesting** in taxable accounts
                        - **Roth conversion** during low-income years
                        - **Strategic withdrawal order**: Taxable → Traditional → Roth

                        **4. Advanced Strategies:**
                        - **HSA triple tax advantage** for medical expenses
                        - **Municipal bonds** for high tax brackets
                        - **Tax-efficient fund selection** (low turnover, index funds)

                        💡 **Next Steps**: Consider consulting a tax professional for personalized advice based on your specific situation.
                        """)
                else:
                    st.error("🚨 **Consider tax optimization** strategies to improve efficiency.")
                    with st.expander("🚨 **Urgent Tax Optimization Needed**", expanded=True):
                        st.markdown("""
                        ### ⚠️ **Your Tax Efficiency Needs Immediate Attention**

                        **Priority Actions:**
                        1. **Review asset allocation** across account types
                        2. **Maximize tax-advantaged contributions** (401k, IRA, HSA)
                        3. **Consider Roth conversions** if in lower tax bracket
                        4. **Optimize fund selection** for tax efficiency

                        **Quick Wins:**
                        - Switch to index funds (lower turnover = less taxes)
                        - Use tax-loss harvesting strategies
                        - Consider municipal bonds for taxable accounts
                        - Maximize HSA contributions if eligible

                        📞 **Recommendation**: Consult a financial advisor for comprehensive tax optimization strategy.
                        """)

        with detail_tab3:
            summary_data = {
                "Metric": [
                    "Years Until Retirement",
                    "Total Future Value (Pre-Tax)",
                    "Total After-Tax Balance",
                    "Total Tax Liability",
                    "Tax Efficiency (%)"
                ],
                "Value": [
                    f"{result['Years Until Retirement']:.0f} years",
                    f"${result['Total Future Value (Pre-Tax)']:,.0f}",
                    f"${result['Total After-Tax Balance']:,.0f}",
                    f"${result['Total Tax Liability']:,.0f}",
                    f"{result['Tax Efficiency (%)']:.1f}%"
                ]
            }
            st.dataframe(pd.DataFrame(summary_data),use_container_width=True, hide_index=True)

        with detail_tab4:
            _da_income = st.session_state.get('last_annual_retirement_income', 0)
            _da_goal = st.session_state.get('whatif_retirement_income_goal', 0)
            _da_ret_age = st.session_state.get('whatif_retirement_age', 65)
            _da_life_exp = st.session_state.get('whatif_life_expectancy', 90)
            _da_years_in_ret = _da_life_exp - _da_ret_age
            _da_breakeven_age = st.session_state.get('last_breakeven_age')
            _da_income_at_breakeven = st.session_state.get('last_income_at_breakeven', 0.0)
            _da_breakeven_contrib = st.session_state.get('last_breakeven_contrib')
            _da_contrib_breakdown = st.session_state.get('last_contrib_breakdown', {})
            _da_contrib_irs_maxed = st.session_state.get('last_contrib_irs_maxed', False)

            if _da_goal <= 0:
                st.info("💡 Set a retirement income goal during setup to see gap analysis here.")
            else:
                _da_shortfall = _da_goal - _da_income
                _da_ratio = (_da_income / _da_goal * 100) if _da_goal > 0 else 0.0

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(
                        "Projected Annual Income",
                        f"${_da_income:,.0f}",
                        help=f"First-year after-tax income from optimal withdrawal sequencing over a {_da_years_in_ret}-year retirement.",
                    )
                with col2:
                    st.metric("Income Goal", f"${_da_goal:,.0f}", help="Your desired annual retirement income.")
                with col3:
                    if _da_shortfall > 0:
                        st.metric(
                            "Annual Shortfall",
                            f"${_da_shortfall:,.0f}",
                            delta=f"-{100 - _da_ratio:.1f}% of goal",
                            delta_color="inverse",
                        )
                    else:
                        st.metric(
                            "Annual Surplus",
                            f"${-_da_shortfall:,.0f}",
                            delta=f"+{_da_ratio - 100:.1f}% above goal",
                            delta_color="normal",
                        )

                if _da_ratio >= 100:
                    st.success(f"🎉 You're projected to exceed your goal by {_da_ratio - 100:.1f}%.")
                elif _da_ratio >= 80:
                    st.warning(f"⚠️ On track for {_da_ratio:.1f}% of your goal.")
                elif _da_ratio >= 60:
                    st.warning(f"🚨 Projected to achieve {_da_ratio:.1f}% of your goal.")
                else:
                    st.error(f"❌ Projected to achieve only {_da_ratio:.1f}% of your goal.")

                if _da_shortfall > 0:
                    st.markdown("---")
                    st.subheader("Gap-Closing Options")

                    gap_rows = []
                    if _da_breakeven_age is not None:
                        gap_rows.append({
                            "Option": "Retire later",
                            "Detail": f"Retire at age {_da_breakeven_age}",
                            "Projected Income": f"${_da_income_at_breakeven:,.0f}/yr",
                            "Note": f"+{_da_breakeven_age - _da_ret_age} year(s) vs current plan",
                        })
                    else:
                        gap_rows.append({
                            "Option": "Retire later",
                            "Detail": "Goal not reachable by age 80",
                            "Projected Income": f"${_da_income_at_breakeven:,.0f}/yr at 80",
                            "Note": "Consider adjusting income goal",
                        })

                    if _da_breakeven_contrib is not None:
                        if _da_contrib_irs_maxed:
                            gap_rows.append({
                                "Option": "Save more",
                                "Detail": "IRS contribution limits already maxed",
                                "Projected Income": "—",
                                "Note": "Consider taxable brokerage contributions",
                            })
                        else:
                            total_extra = sum(_da_contrib_breakdown.values()) if _da_contrib_breakdown else _da_breakeven_contrib
                            gap_rows.append({
                                "Option": "Save more",
                                "Detail": f"+${total_extra:,.0f}/yr across accounts",
                                "Projected Income": f"${_da_goal:,.0f}/yr (at goal)",
                                "Note": "Ask the chatbot for a per-account breakdown",
                            })

                    st.dataframe(pd.DataFrame(gap_rows), use_container_width=True, hide_index=True)

                    if _da_contrib_breakdown and not _da_contrib_irs_maxed and _da_breakeven_contrib is not None:
                        with st.expander("Per-account contribution breakdown", expanded=False):
                            bd_rows = [
                                {"Account": acct, "Additional Annual Contribution": f"${amt:,.0f}"}
                                for acct, amt in _da_contrib_breakdown.items()
                                if amt > 0
                            ]
                            if bd_rows:
                                st.dataframe(pd.DataFrame(bd_rows), use_container_width=True, hide_index=True)

    elif st.session_state.current_page == 'monte_carlo':
        # Show analytics consent dialog on first load
        if st.session_state.get('analytics_consent') is None:
            analytics_consent_dialog()

        # ==========================================
        # MONTE CARLO SIMULATION PAGE
        # ==========================================

        # Track page view
        track_page_view('monte_carlo')
    
        # Add navigation buttons to go back
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("← Back to Results",use_container_width=True):
                track_event('navigation_back_to_results')
                st.session_state.current_page = 'results'
                st.rerun()
    
        st.markdown("---")
    
        # Header
        st.header("🎲 Monte Carlo Simulation")
        st.markdown("Explore thousands of possible retirement scenarios with probabilistic analysis")
    
        st.markdown("---")
    
        # Educational explanation
        with st.expander("📚 What is Monte Carlo Simulation?", expanded=False):
            st.markdown("""
            ### What is Monte Carlo Simulation?
    
            Monte Carlo simulation runs **thousands of possible market scenarios** to show you the range of
            potential retirement outcomes, not just a single projection.
    
            **Why use it?**
            - Markets don't deliver consistent returns every year
            - See probability ranges (best case, worst case, most likely)
            - Understand uncertainty in your retirement plan
            - Make more informed decisions with probabilistic analysis
    
            **How it works:**
            1. Runs 1,000+ simulations with varying market returns
            2. Returns vary randomly around your expected growth rate
            3. Shows distribution of possible outcomes
            4. Calculates probability of meeting your retirement goals
            5. **Shows projected annual income variation** (not just final balance)
            """)
    
        st.markdown("---")
    
        # Configuration Section
        st.subheader("⚙️ Simulation Settings")
    
        # Get default values from session state if coming from dialog
        default_num_sims = 1000
        default_volatility = 15.0
        if 'monte_carlo_config' in st.session_state:
            default_num_sims = st.session_state.monte_carlo_config.get('num_simulations', 1000)
            default_volatility = st.session_state.monte_carlo_config.get('volatility', 15.0)
            # Clear the config after using it
            del st.session_state.monte_carlo_config
    
        col1, col2 = st.columns(2)
    
        with col1:
            num_simulations = st.select_slider(
                "Number of Simulations",
                options=[100, 500, 1000, 5000, 10000],
                value=default_num_sims,
                help="More simulations = more accurate results (but slower)"
            )
    
        with col2:
            volatility = st.slider(
                "Market Volatility (Standard Deviation %)",
                min_value=5.0,
                max_value=30.0,
                value=default_volatility,
                step=1.0,
                help="Historical stock market volatility is ~15-20%. Higher = more uncertainty."
            )
    
        st.markdown("---")
    
        # Run Simulation Button
        if st.button("🎲 Run Monte Carlo Simulation", type="primary",use_container_width=True, key="run_monte_carlo_main"):
            try:
                from financialadvisor.core.monte_carlo import (
                    run_monte_carlo_simulation,
                    calculate_probability_of_goal,
                    get_confidence_interval
                )
    
                # Prepare inputs for simulation
                current_year_mc = datetime.now().year
    
                simulation_inputs = UserInputs(
                    age=current_year_mc - st.session_state.birth_year,
                    retirement_age=int(st.session_state.whatif_retirement_age),
                    life_expectancy=int(st.session_state.whatif_life_expectancy),
                    annual_income=0.0,
                    contribution_rate_pct=15.0,
                    expected_growth_rate_pct=7.0,
                    inflation_rate_pct=float(st.session_state.whatif_inflation_rate),
                    current_marginal_tax_rate_pct=float(st.session_state.whatif_current_tax_rate),
                    retirement_marginal_tax_rate_pct=float(st.session_state.whatif_retirement_tax_rate),
                    assets=st.session_state.assets
                )
    
                with st.spinner(f"Running {num_simulations:,} simulations..."):
                    results = run_monte_carlo_simulation(
                        simulation_inputs,
                        num_simulations=num_simulations,
                        volatility=volatility
                    )
    
                    # Calculate probability of meeting income goal
                    prob_success: Optional[float]
                    if st.session_state.whatif_retirement_income_goal > 0:
                        prob_success = calculate_probability_of_goal(
                            results["outcomes"],
                            int(st.session_state.whatif_retirement_age),
                            int(st.session_state.whatif_life_expectancy),
                            float(st.session_state.whatif_retirement_income_goal)
                        )
                    else:
                        prob_success = None
    
                    # Get confidence interval
                    ci_lower, ci_upper = get_confidence_interval(results["outcomes"], confidence=0.95)
                    ci_income_lower, ci_income_upper = get_confidence_interval(results["annual_income_outcomes"], confidence=0.95)

                # Escape currency for markdown so "$...$" is not parsed as LaTeX/math.
                def md_currency(v):
                    return f"\\${v:,.0f}"
    
                # Track successful Monte Carlo run
                track_monte_carlo_run(num_simulations=num_simulations, volatility=volatility)
    
                # Display Results
                st.success(f"✅ Completed {num_simulations:,} simulations!")
    
            except Exception as e:
                # Track Monte Carlo error
                track_error('monte_carlo_error', str(e), {
                    'num_simulations': num_simulations,
                    'volatility': volatility
                })
                st.error(f"❌ Error running Monte Carlo simulation: {str(e)}")
                st.info("💡 Try reducing the number of simulations or refreshing the page.")
                st.stop()
    
            st.markdown("---")
    
            # Key Metrics - Annual Income (Primary Focus)
            st.markdown("### 💰 Projected Annual Income Distribution")
            st.info("This shows how much annual income you could have in retirement across different market scenarios")
    
            metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    
            with metric_col1:
                st.metric(
                    "Median Annual Income",
                    f"${results['income_percentiles']['50th']:,.0f}",
                    help="50th percentile - half of outcomes above, half below"
                )
    
            with metric_col2:
                st.metric(
                    "Mean Annual Income",
                    f"${results['mean_annual_income']:,.0f}",
                    help="Average annual income across all simulations"
                )
    
            with metric_col3:
                st.metric(
                    "Best Case (90th %ile)",
                    f"${results['income_percentiles']['90th']:,.0f}",
                    help="90% of outcomes are below this annual income"
                )
    
            with metric_col4:
                st.metric(
                    "Worst Case (10th %ile)",
                    f"${results['income_percentiles']['10th']:,.0f}",
                    help="Only 10% of outcomes are below this annual income"
                )
    
            # Annual Income Percentile Breakdown
            st.markdown("#### Annual Income Range (Percentiles)")
    
            income_percentile_data = {
                "Percentile": ["10th", "25th", "50th (Median)", "75th", "90th"],
                "Annual Income": [
                    f"${results['income_percentiles']['10th']:,.0f}",
                    f"${results['income_percentiles']['25th']:,.0f}",
                    f"${results['income_percentiles']['50th']:,.0f}",
                    f"${results['income_percentiles']['75th']:,.0f}",
                    f"${results['income_percentiles']['90th']:,.0f}",
                ]
            }
    
            st.table(income_percentile_data)
    
            # 95% Confidence Interval for Income
            ci_lines = [
                f"**95% Confidence Interval for Annual Income:** {md_currency(ci_income_lower)} - {md_currency(ci_income_upper)}",
                "",
                "There's a 95% probability your annual retirement income will fall within this range.",
            ]
            st.markdown("\n".join(ci_lines))
    
            # Probability of success
            if prob_success is not None:
                st.markdown("")
                if prob_success >= 80:
                    st.success(f"🎯 **{prob_success:.1f}% probability** of meeting your ${st.session_state.whatif_retirement_income_goal:,.0f}/year income goal")
                elif prob_success >= 60:
                    st.warning(f"⚠️ **{prob_success:.1f}% probability** of meeting your ${st.session_state.whatif_retirement_income_goal:,.0f}/year income goal")
                else:
                    st.error(f"🚨 **{prob_success:.1f}% probability** of meeting your ${st.session_state.whatif_retirement_income_goal:,.0f}/year income goal")
    
            # Distribution visualization for Annual Income
            st.markdown("#### Distribution of Annual Income Outcomes")
    
            # Create histogram data for income
            import math
            num_bins = 30
            min_val = results['min_income']
            max_val = results['max_income']
            bin_width = (max_val - min_val) / num_bins
    
            # Store bins with numeric centers for proper sorting
            bins_data: Dict[float, int] = {}
            for outcome in results['annual_income_outcomes']:
                bin_idx = min(int((outcome - min_val) / bin_width), num_bins - 1)
                bin_center = min_val + (bin_idx + 0.5) * bin_width
                bins_data[bin_center] = bins_data.get(bin_center, 0) + 1
    
            # Sort by bin_center and create labels
            sorted_bins = sorted(bins_data.items())
            bins_df = pd.DataFrame([
                {"Income Range": f"${center/1000:.0f}K", "Count": count}
                for center, count in sorted_bins
            ])
    
            # Use categorical index to preserve sort order (prevent alphabetical re-sorting)
            bins_df["Income Range"] = pd.Categorical(
                bins_df["Income Range"],
                categories=bins_df["Income Range"].tolist(),
                ordered=True
            )
            bins_df = bins_df.set_index("Income Range")
    
            # Display as bar chart
            st.bar_chart(bins_df)
    
            st.info("""
            💡 **Interpretation Tips:**
            - The median (50th percentile) is your most likely annual income
            - The 10th-90th percentile range shows 80% of possible income outcomes
            - Higher volatility = wider range of annual income outcomes
            - Conservative planning often targets the 25th percentile or lower
            """)
    
            st.markdown("---")
    
            # Secondary Metrics - Total Balance
            st.markdown("### 📊 Total Retirement Balance Distribution")
    
            metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    
            with metric_col1:
                st.metric(
                    "Median Balance",
                    f"${results['percentiles']['50th']:,.0f}",
                    help="50th percentile - half of outcomes above, half below"
                )
    
            with metric_col2:
                st.metric(
                    "Mean Balance",
                    f"${results['mean']:,.0f}",
                    help="Average of all simulated outcomes"
                )
    
            with metric_col3:
                st.metric(
                    "Best Case (90th %ile)",
                    f"${results['percentiles']['90th']:,.0f}",
                    help="90% of outcomes are below this value"
                )
    
            with metric_col4:
                st.metric(
                    "Worst Case (10th %ile)",
                    f"${results['percentiles']['10th']:,.0f}",
                    help="Only 10% of outcomes are below this value"
                )
    
            # Percentile breakdown for balance
            st.markdown("#### Total Balance Range (Percentiles)")
    
            percentile_data = {
                "Percentile": ["10th", "25th", "50th (Median)", "75th", "90th"],
                "After-Tax Balance": [
                    f"${results['percentiles']['10th']:,.0f}",
                    f"${results['percentiles']['25th']:,.0f}",
                    f"${results['percentiles']['50th']:,.0f}",
                    f"${results['percentiles']['75th']:,.0f}",
                    f"${results['percentiles']['90th']:,.0f}",
                ]
            }
    
            st.table(percentile_data)
    
            # 95% Confidence Interval for Balance
            ci_balance_lines = [
                f"**95% Confidence Interval for Total Balance:** {md_currency(ci_lower)} - {md_currency(ci_upper)}",
                "",
                "There's a 95% probability your retirement balance will fall within this range.",
            ]
            st.markdown("\n".join(ci_balance_lines))
    
            # Distribution visualization for Balance
            st.markdown("#### Distribution of Balance Outcomes")
    
            # Create histogram data for balance
            min_val_balance = results['min']
            max_val_balance = results['max']
            bin_width_balance = (max_val_balance - min_val_balance) / num_bins
    
            # Store bins with numeric centers for proper sorting
            bins_balance_data: Dict[float, int] = {}
            for outcome in results['outcomes']:
                bin_idx = min(int((outcome - min_val_balance) / bin_width_balance), num_bins - 1)
                bin_center = min_val_balance + (bin_idx + 0.5) * bin_width_balance
                bins_balance_data[bin_center] = bins_balance_data.get(bin_center, 0) + 1
    
            # Sort by bin_center and create labels
            sorted_bins_balance = sorted(bins_balance_data.items())
            bins_balance_df = pd.DataFrame([
                {"Balance Range": f"${center/1000:.0f}K", "Count": count}
                for center, count in sorted_bins_balance
            ])
    
            # Use categorical index to preserve sort order (prevent alphabetical re-sorting)
            bins_balance_df["Balance Range"] = pd.Categorical(
                bins_balance_df["Balance Range"],
                categories=bins_balance_df["Balance Range"].tolist(),
                ordered=True
            )
            bins_balance_df = bins_balance_df.set_index("Balance Range")
    
            # Display as bar chart
            st.bar_chart(bins_balance_df)
    
    # Page footer
    st.markdown("---")
    st.markdown(
        f"""
        <div style='text-align: center; color: #666; font-size: 0.85em; padding: 20px 10px; background-color: #f8f9fa; border-radius: 8px; margin-top: 30px;'>
            <div style='margin-bottom: 8px;'>
                <strong style='color: #1f77b4;'>Smart Retire AI v{VERSION}</strong>
            </div>
            <div style='margin-bottom: 8px; color: #888;'>
                Advanced Retirement Planning with Asset Classification & Tax Optimization
            </div>
            <div style='margin-bottom: 8px;'>
                <span style='color: #555;'>© 2025-2026 Smart Retire AI. All rights reserved.</span>
            </div>
            <div>
                <span style='color: #555;'>Questions? Contact us: </span>
                <a href='mailto:smartretireai@gmail.com' style='color: #1f77b4; text-decoration: none; font-weight: 500;'>
                    smartretireai@gmail.com
                </a>
            </div>
            <div style='margin-top: 12px; font-size: 0.75em; color: #999;'>
                <em>Disclaimer: This tool provides estimates for educational purposes. Consult a financial advisor for personalized advice.</em>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    
# ---------------------------
# Tests (unittest)
# ---------------------------

import unittest


# ---------------------------
# Entrypoint
# ---------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Smart Retire AI - Advanced Retirement Planning")
    p.add_argument("--run-tests", action="store_true", help="Run unit tests and exit")
    return p


# Test runner - only runs when called with --run-tests
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and "--run-tests" in sys.argv:
        # Discover only unit tests; exclude e2e/ which requires Playwright + live server
        import glob as _glob
        import importlib as _importlib
        _loader = unittest.defaultTestLoader
        suite = unittest.TestSuite()
        for _path in sorted(_glob.glob("tests/test_*.py")):
            _mod = _path.replace("/", ".")[:-3]  # "tests/test_foo.py" → "tests.test_foo"
            suite.addTests(_loader.loadTestsFromModule(_importlib.import_module(_mod)))
        test_result = unittest.TextTestRunner(verbosity=2).run(suite)
        sys.exit(0 if test_result.wasSuccessful() else 1)
    else:
        print("🚀 Smart Retire AI - Advanced Retirement Planning")
        print("=" * 60)
        print("\nThis application requires the Streamlit web interface.")
        print("\nTo run the application:")
        print("  streamlit run fin_advisor.py")
        print("\nThis will open your web browser with the interactive interface.")
        print("\nFor testing, use:")
        print("  python3 fin_advisor.py --run-tests")
