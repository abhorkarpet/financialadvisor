import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List

# Add parent directory to path so we can import deadline_agent
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from deadline_agent import AgentConfig, DeadlineAgent, FeedbackLearner, InsufficientFundsError
from deadline_agent.calendar import CalendarEventRequest, CalendarService


FEEDBACK_FILE = "deadline_agent_feedback.jsonl"


def get_config_from_ui() -> AgentConfig:
    st.sidebar.markdown("### Email Configuration")
    with st.sidebar.expander("💡 How to get an app password", expanded=False):
        st.markdown("""
        **Gmail:**
        1. Go to [Google Account](https://myaccount.google.com/)
        2. Click **Security** (left sidebar)
        3. Under "How you sign in to Google", click **2-Step Verification**
        4. Scroll down to find **App passwords** (or search for it)
        5. Click **App passwords** > Select app: **Mail** > Select device: **Other (Custom name)**
        6. Enter a name (e.g., "Deadline Agent") and click **Generate**
        7. Copy the 16-character password (shown only once)
        
        **Note:** If you don't see "App passwords", you may need to enable 2-Step Verification first.
        
        **Yahoo:**
        1. Go to [Account Security](https://login.yahoo.com/account/security)
        2. Click **Generate app password**
        3. Select "Mail" and generate
        4. Copy the password
        
        **Other providers:** Check your email provider's help docs for app password setup.
        """)
    email_address = st.sidebar.text_input("Email address", value=os.getenv("DA_EMAIL_ADDRESS", ""))
    email_password = st.sidebar.text_input("Email app password", type="password", value=os.getenv("DA_EMAIL_PASSWORD", ""))
    imap_host = st.sidebar.text_input("IMAP host", value=os.getenv("DA_IMAP_HOST", "imap.gmail.com"))
    imap_port = st.sidebar.number_input("IMAP port", value=int(os.getenv("DA_IMAP_PORT", "993")))
    mailbox = st.sidebar.text_input("Mailbox", value=os.getenv("DA_MAILBOX", "INBOX"))
    since_days = st.sidebar.number_input("Scan last N days", min_value=1, max_value=365, value=int(os.getenv("DA_SINCE_DAYS", "60")))
    max_messages = st.sidebar.number_input("Max messages", min_value=10, max_value=5000, value=int(os.getenv("DA_MAX_MESSAGES", "50")))
    debug_mode = st.sidebar.toggle("🔍 Debug/Verbose mode", value=False, help="Show detailed scan statistics")
    
    st.sidebar.divider()
    st.sidebar.markdown("### 🤖 LLM Extraction (Optional)")
    st.sidebar.caption("Use AI to find deadlines in invoices, renewal notices, and varied phrasing")
    use_llm = st.sidebar.toggle("Enable LLM extraction", value=False, help="Requires OpenAI API key. More accurate but costs money (~$0.01 per 100 emails)")
    llm_api_key = ""
    llm_model = "gpt-4o-mini"
    if use_llm:
        llm_api_key = st.sidebar.text_input("OpenAI API Key", type="password", value=os.getenv("DA_LLM_API_KEY", ""), help="Get from https://platform.openai.com/api-keys")
        llm_model = st.sidebar.selectbox("Model", ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"], index=0, help="gpt-4o-mini is cheapest and sufficient")
    
    return AgentConfig(
        imap_host=imap_host,
        imap_port=int(imap_port),
        email_address=email_address,
        email_username=email_address,
        email_password=email_password,
        mailbox=mailbox,
        since_days=int(since_days),
        max_messages=int(max_messages),
        use_gmail_api=False,
        debug=debug_mode,
        use_llm_extraction=use_llm,
        llm_api_key=llm_api_key,
        llm_model=llm_model,
    )


def store_feedback(item, reason: str):
    record = {
        "deadline_at": item.deadline_at.isoformat(),
        "title": item.title,
        "source": item.source,
        "reason": reason,
        "ts": datetime.utcnow().isoformat(),
    }
    try:
        with open(FEEDBACK_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")
        # Clear feedback learner cache so it picks up new feedback
        learner = FeedbackLearner(FEEDBACK_FILE)
        learner.clear_cache()
    except Exception:
        pass


def main():
    st.title("Deadline Agent")
    st.caption("Authenticate, scan inbox for deadlines, review results, and create reminders")

    # Optional Welcome / Onboarding
    if "suppress_welcome" not in st.session_state:
        st.session_state.suppress_welcome = False
    if "welcomed" not in st.session_state:
        st.session_state.welcomed = False

    def render_welcome():
        st.subheader("Welcome 👋")
        st.markdown(
            """
            This assistant helps you avoid surprise charges by finding cancellation/refund deadlines from your emails and creating calendar reminders.

            What it does:
            - Connects to your email via IMAP (Gmail, Yahoo, etc. with app password)
            - Scans recent messages for phrases like "free trial ends", "cancel by", "fully refundable until"
            - Lets you review and select the correct items, give feedback, and export reminders to your calendar (.ics)

            Privacy & security:
            - Your data stays local in your browser/session.
            - OAuth tokens (if any) are stored only on your machine as configured.
            - No messages are sent to any external server from this app.

            How to use:
            1) Choose Gmail OAuth (recommended) or IMAP in the sidebar
            2) Click "Authenticate & Scan"
            3) Review detected items, uncheck incorrect ones, and submit feedback if we mis-detected
            4) Click "Create Reminders" and download the .ics file
            """
        )
        st.checkbox("Don't show again", key="suppress_welcome")
        if st.button("I understand, continue →"):
            st.session_state.welcomed = True

    if not st.session_state.suppress_welcome and not st.session_state.welcomed:
        with st.container(border=True):
            render_welcome()
            st.stop()

    cfg = get_config_from_ui()

    if "deadlines" not in st.session_state:
        st.session_state.deadlines = []
    if "selected" not in st.session_state:
        st.session_state.selected = set()
    if "scan_stats" not in st.session_state:
        st.session_state.scan_stats = None

    # Initialize confirmation skip state
    if "skip_scan_confirmation" not in st.session_state:
        st.session_state.skip_scan_confirmation = False
    
    # Function to perform the actual scan
    def perform_scan(cfg):
        """Execute the email scan with progress tracking."""
        try:
            # Validate configuration before attempting connection
            if not cfg.email_address or not cfg.email_password:
                st.error("Please provide your email address and app password in the sidebar.")
                return
            
            # Show cost estimate if LLM enabled
            if cfg.use_llm_extraction:
                estimated_emails = min(cfg.max_messages, 500)
                cost_per_email = 0.0003 if cfg.llm_model == "gpt-4o-mini" else (0.003 if cfg.llm_model == "gpt-4o" else 0.01)
                estimated_cost = estimated_emails * cost_per_email
                st.info(f"💰 Estimated cost: ~${estimated_cost:.2f} - ${estimated_cost * 1.5:.2f} for this scan ({cfg.llm_model}) | [Check usage & costs](https://platform.openai.com/usage)")
            
            agent = DeadlineAgent(cfg)
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(message: str, progress: float):
                progress_bar.progress(progress)
                status_text.text(message)
            
            try:
                deadlines, stats = agent.collect_deadlines(progress_callback=update_progress)
            finally:
                # Clear progress indicators
                progress_bar.empty()
                status_text.empty()
            
            st.session_state.deadlines = deadlines
            st.session_state.selected = set(range(len(deadlines)))
            st.session_state.scan_stats = stats
            
            if len(deadlines) == 0:
                st.warning(f"⚠️ Found 0 deadlines after scanning {stats.emails_fetched} emails")
            else:
                st.success(f"Found {len(deadlines)} potential deadlines")
            
            # Always show stats if debug mode, or if no deadlines found
            if cfg.debug or len(deadlines) == 0:
                with st.expander("📊 Scan Statistics", expanded=cfg.debug or len(deadlines) == 0):
                    st.metric("Emails fetched", stats.emails_fetched)
                    st.metric("Emails processed", stats.emails_processed)
                    st.metric("Deadlines found", stats.deadlines_found)
                    st.metric("Unique senders", stats.unique_senders)
                    if stats.sample_subjects:
                        st.markdown("**Sample email subjects:**")
                        for subj in stats.sample_subjects:
                            st.text(f"  • {subj}")
                    if stats.emails_fetched == 0:
                        st.error("No emails were fetched. Check your email settings and date range.")
        except ValueError as e:
            # User-friendly error messages (like app password required)
            st.error(str(e))
            st.info("💡 **Tip:** Expand 'How to get an app password' in the sidebar for step-by-step instructions.")
        except FileNotFoundError as e:
            st.error(f"File not found: {e}. Please check your file paths in the sidebar.")
        except InsufficientFundsError as e:
            st.error("💳 **Insufficient Funds**")
            st.markdown(f"""
            {str(e)}
            
            **To add funds to your OpenAI account:**
            1. Go to [OpenAI Billing](https://platform.openai.com/account/billing)
            2. Add a payment method or top up your account
            3. Once funds are added, try scanning again
            
            You can also check your current usage and costs at [OpenAI Usage](https://platform.openai.com/usage)
            """)
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            
            # Fallback check for insufficient funds (in case exception wasn't caught properly)
            if "insufficient" in error_msg.lower() and ("fund" in error_msg.lower() or "quota" in error_msg.lower() or "billing" in error_msg.lower()):
                st.error("💳 **Insufficient Funds**")
                st.markdown(f"""
                {error_msg}
                
                **To add funds to your OpenAI account:**
                1. Go to [OpenAI Billing](https://platform.openai.com/account/billing)
                2. Add a payment method or top up your account
                3. Once funds are added, try scanning again
                
                You can also check your current usage and costs at [OpenAI Usage](https://platform.openai.com/usage)
                """)
            elif "Application-specific password" in error_msg or "185833" in error_msg:
                st.error("❌ **App password required!** You're using your regular Gmail password. Please generate an app password - see instructions in the sidebar.")
            else:
                st.error(f"Error during scan: {error_msg}")
                with st.expander("Technical details"):
                    st.exception(e)
    
    col1, col2 = st.columns(2)
    with col1:
        # Check if we're in confirmation mode
        if "show_llm_confirmation" not in st.session_state:
            st.session_state.show_llm_confirmation = False
        
        # Show confirmation dialog if needed
        if st.session_state.show_llm_confirmation and cfg.use_llm_extraction:
            # Calculate estimated cost
            # gpt-4o-mini: ~$0.15 per 1M input tokens, ~$0.60 per 1M output tokens
            # Average email: ~2000 tokens input, ~200 tokens output
            # Cost per email: ~$0.0003 (very rough estimate)
            estimated_emails = min(cfg.max_messages, 500)  # Conservative estimate
            cost_per_email = 0.0003 if cfg.llm_model == "gpt-4o-mini" else (0.003 if cfg.llm_model == "gpt-4o" else 0.01)
            estimated_cost = estimated_emails * cost_per_email
            
            with st.container(border=True):
                st.warning("⚠️ **LLM Extraction Enabled**")
                st.markdown(f"""
                **Estimated cost:** ~${estimated_cost:.2f} - ${estimated_cost * 1.5:.2f} for up to {estimated_emails} emails
                
                - Model: {cfg.llm_model}
                - Cost varies based on email length
                - You'll be charged by OpenAI based on actual usage
                - [Check usage & costs](https://platform.openai.com/usage) to see current spending
                """)
                dont_remind = st.checkbox("Don't remind me again", key="dont_remind_llm")
                col_confirm, col_cancel = st.columns(2)
                with col_confirm:
                    if st.button("Continue with scan", type="primary", key="confirm_scan"):
                        if dont_remind:
                            st.session_state.skip_scan_confirmation = True
                        st.session_state.show_llm_confirmation = False
                        # Proceed directly with scan
                        perform_scan(cfg)
                with col_cancel:
                    if st.button("Cancel", key="cancel_scan"):
                        st.session_state.show_llm_confirmation = False
                        st.rerun()
        elif st.button("Authenticate & Scan", type="primary"):
            # Check if we need to show confirmation
            if cfg.use_llm_extraction and not st.session_state.skip_scan_confirmation:
                st.session_state.show_llm_confirmation = True
                st.rerun()
            else:
                # Proceed directly with scan
                perform_scan(cfg)
    with col2:
        if st.button("Clear Results"):
            st.session_state.deadlines = []
            st.session_state.selected = set()
            st.session_state.scan_stats = None

    deadlines = st.session_state.deadlines
    if deadlines:
        st.subheader("Review detected deadlines")
        
        # Category color mapping
        category_colors = {
            "subscription": "🔵",
            "trial": "🟡",
            "travel": "✈️",
            "billing": "💰",
            "refund": "💸",
            "general": "⚪"
        }
        
        # Group deadlines by category
        deadlines_by_category = {}
        for idx, item in enumerate(deadlines):
            category = getattr(item, 'category', 'general')
            if category not in deadlines_by_category:
                deadlines_by_category[category] = []
            deadlines_by_category[category].append((idx, item))
        
        # Sort categories: subscription, trial, travel, billing, refund, then general
        category_order = ["subscription", "trial", "travel", "billing", "refund", "general"]
        sorted_categories = sorted(
            deadlines_by_category.keys(),
            key=lambda c: (category_order.index(c) if c in category_order else 999, c)
        )
        
        def render_deadline_item(item, actual_idx):
            """Render a single deadline item"""
            item_category = getattr(item, 'category', 'general')
            selected = st.checkbox("Include", value=(actual_idx in st.session_state.selected), key=f"sel_{actual_idx}")
            if selected:
                st.session_state.selected.add(actual_idx)
            else:
                st.session_state.selected.discard(actual_idx)
            col1, col2 = st.columns(2)
            with col1:
                st.text(f"Category: **{item_category.title()}**")
                st.text(f"Source: {item.source}")
                if getattr(item, 'email_date', None):
                    st.text(f"📧 Email received: {item.email_date.strftime('%Y-%m-%d %H:%M')}")
            with col2:
                st.text(f"Confidence: {item.confidence:.2f}")
                st.text(f"⏰ Deadline: {item.deadline_at.strftime('%Y-%m-%d %H:%M')}")
            
            # Show email excerpt or summary
            email_excerpt = getattr(item, 'email_excerpt', None)
            email_summary = getattr(item, 'email_summary', None)
            
            # Always try to show some context - prioritize summary, then excerpt, then context
            if email_summary:
                st.markdown("**📝 LLM Summary:**")
                st.info(email_summary)
                if email_excerpt:
                    with st.expander("📄 View original email excerpt", expanded=False):
                        st.text_area("", value=email_excerpt, height=100, disabled=True, key=f"excerpt_{actual_idx}", label_visibility="collapsed")
            elif email_excerpt and email_excerpt.strip():
                st.markdown("**📄 Email Excerpt:**")
                st.text_area(
                    "", 
                    value=email_excerpt, 
                    height=120, 
                    disabled=True,
                    key=f"excerpt_{actual_idx}",
                    label_visibility="collapsed"
                )
            elif item.context and item.context.strip():
                st.markdown("**📄 Context (from matched pattern):**")
                st.text_area(
                    "",
                    value=item.context,
                    height=80,
                    disabled=True,
                    key=f"context_{actual_idx}",
                    label_visibility="collapsed"
                )
            else:
                st.caption("ℹ️ No excerpt available. Click 'Clear Results' and rescan to get email excerpts.")
            wrong = st.toggle("This is incorrect", key=f"wrong_{actual_idx}")
            if wrong:
                reason = st.text_input("Why is it incorrect? (optional)", key=f"reason_{actual_idx}")
                if st.button("Submit feedback", key=f"fb_{actual_idx}"):
                    store_feedback(item, reason or "")
                    st.success("Thanks for the feedback!")
        
        # Create tabs for each category
        if len(sorted_categories) > 1:
            tab_labels = [f"{category_colors.get(cat, '⚪')} {cat.title()} ({len(deadlines_by_category[cat])})" for cat in sorted_categories]
            tabs = st.tabs(tab_labels)
            
            for tab, category in zip(tabs, sorted_categories):
                with tab:
                    category_deadlines = deadlines_by_category[category]
                    if not category_deadlines:
                        st.info("No deadlines in this category")
                        continue
                    
                    for actual_idx, item in category_deadlines:
                        item_category = getattr(item, 'category', 'general')
                        category_emoji = category_colors.get(item_category, "⚪")
                        with st.expander(f"{item.deadline_at.strftime('%Y-%m-%d %H:%M')} · {category_emoji} {item.title}"):
                            render_deadline_item(item, actual_idx)
        else:
            # If only one category, don't use tabs
            category = sorted_categories[0] if sorted_categories else "general"
            for actual_idx, item in deadlines_by_category.get(category, []):
                item_category = getattr(item, 'category', 'general')
                category_emoji = category_colors.get(item_category, "⚪")
                with st.expander(f"{item.deadline_at.strftime('%Y-%m-%d %H:%M')} · {category_emoji} {item.title}"):
                    render_deadline_item(item, actual_idx)

        st.divider()
        st.subheader("Create calendar reminders for selected")
        remind_minutes_before = st.number_input("Reminder: minutes before", min_value=0, max_value=1440, value=60)
        if st.button("Create Reminders"):
            svc = CalendarService()
            selected_requests: List[CalendarEventRequest] = []
            for idx in sorted(st.session_state.selected):
                item = deadlines[idx]
                selected_requests.append(
                    CalendarEventRequest(
                        title=item.title,
                        starts_at=item.deadline_at,
                        duration_minutes=30,
                        description=item.context or f"Source: {item.source}",
                    )
                )
            if selected_requests:
                ics = svc.generate_ics(selected_requests, reminder_minutes_before=int(remind_minutes_before))
                st.session_state.generated_ics = ics
                st.success(f"Prepared {len(selected_requests)} reminder(s). Download below.")

        if "generated_ics" in st.session_state and st.session_state.generated_ics:
            st.download_button(
                label="Download .ics",
                data=st.session_state.generated_ics.encode("utf-8"),
                file_name="deadlines.ics",
                mime="text/calendar",
            )

    # Feedback section
    st.sidebar.divider()
    with st.sidebar.expander("📊 Feedback Analytics", expanded=False):
        learner = FeedbackLearner(FEEDBACK_FILE)
        stats = learner.get_stats()
        
        if stats.total_feedback > 0:
            st.write(f"**{stats.total_feedback} feedback entries**")
            
            # Top problematic senders
            if stats.false_positives_by_sender:
                st.markdown("**Top flagged senders:**")
                sorted_senders = sorted(stats.false_positives_by_sender.items(), key=lambda x: x[1], reverse=True)[:5]
                for sender, count in sorted_senders:
                    sender_short = sender[:30] + "..." if len(sender) > 30 else sender
                    st.caption(f"  • {sender_short}: {count} time{'s' if count > 1 else ''}")
            
            # Most common reasons
            if stats.most_common_reasons:
                st.markdown("**Common issues:**")
                sorted_reasons = sorted(stats.most_common_reasons.items(), key=lambda x: x[1], reverse=True)[:3]
                for reason, count in sorted_reasons:
                    reason_short = reason[:40] + "..." if len(reason) > 40 else reason
                    st.caption(f"  • {reason_short}: {count}x")
            
            st.caption("💡 System learns from feedback to filter similar false positives")
        else:
            st.write("No feedback collected yet")
            st.caption("Submit feedback on incorrect deadlines to help improve accuracy")


if __name__ == "__main__":
    main()


