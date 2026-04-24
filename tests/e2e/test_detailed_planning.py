from __future__ import annotations

import os

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import fill_chat_input, wait_for_streamlit, _complete_setup_chat

pytestmark = pytest.mark.e2e

SETUP_CHAT_INPUT = '[data-testid="stChatInput"]'


def _navigate_to_detailed(page: Page) -> None:
    page.get_by_role("button", name="Enter Details →").click()
    wait_for_streamlit(page)
    page.wait_for_selector("text=Your Retirement Goals", timeout=10_000)


def _get_continue_btn(page: Page):
    return page.get_by_role("button", name="Continue: Set Up Accounts →")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="requires OPENAI_API_KEY")
def test_detailed_planning_step1_summary_updates(page: Page) -> None:
    """After providing all facts and confirming, metric cards appear and Continue button is enabled."""
    _navigate_to_detailed(page)

    _complete_setup_chat(page)

    # Summary column should now show Current Age metric
    age_label = page.locator('[data-testid="stMetricLabel"]').filter(has_text="Current Age")
    expect(age_label).to_be_visible(timeout=15_000)

    # Annual Income Goal metric
    income_label = page.locator('[data-testid="stMetricLabel"]').filter(has_text="Annual Income Goal")
    expect(income_label).to_be_visible()

    # Continue button is visible and enabled
    expect(_get_continue_btn(page)).to_be_visible()
    expect(_get_continue_btn(page)).to_be_enabled()


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="requires OPENAI_API_KEY")
def test_detailed_planning_step2_manual_entry(page: Page) -> None:
    """Full Detailed Planning flow via manual asset form → results page."""
    _navigate_to_detailed(page)

    _complete_setup_chat(page)

    continue_btn = _get_continue_btn(page)
    continue_btn.wait_for(state="visible", timeout=30_000)
    continue_btn.click()
    wait_for_streamlit(page)

    page.wait_for_selector("text=Asset Configuration", timeout=10_000)
    expect(page.get_by_text("Step 2 of 2")).to_be_visible()

    page.get_by_text("Configure Individual Assets").click()
    wait_for_streamlit(page)

    expect(page.get_by_text("🏦 Asset 1")).to_be_visible()

    complete_btn = page.get_by_role("button", name="Complete Setup → View Results")
    expect(complete_btn).to_be_visible()
    expect(complete_btn).to_be_enabled()
    complete_btn.click()
    wait_for_streamlit(page)

    page.wait_for_selector("text=Retirement Projection & Analysis", timeout=20_000)
    expect(
        page.get_by_role("heading", name="Retirement Projection & Analysis")
    ).to_be_visible()


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="requires OPENAI_API_KEY")
def test_detailed_planning_back_from_step2_to_step1(page: Page) -> None:
    """'← Back' in Step 2 returns to Step 1 (setup chat)."""
    _navigate_to_detailed(page)

    _complete_setup_chat(page)

    _get_continue_btn(page).wait_for(state="visible", timeout=30_000)
    _get_continue_btn(page).click()
    wait_for_streamlit(page)

    page.wait_for_selector("text=Asset Configuration")

    page.get_by_role("button", name="← Back").click()
    wait_for_streamlit(page)

    expect(page.get_by_text("Your Retirement Goals")).to_be_visible()


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="requires OPENAI_API_KEY")
def test_results_back_to_setup_returns_to_onboarding(detailed_results_page: Page) -> None:
    """'← Back to Setup' from results returns to onboarding."""
    pg = detailed_results_page

    pg.get_by_role("button", name="← Back to Setup").click()
    wait_for_streamlit(pg)

    # Step 2 shows "Step 2 of 2" — unique indicator for the Asset Configuration page
    expect(pg.get_by_text("Step 2 of 2")).to_be_visible()
