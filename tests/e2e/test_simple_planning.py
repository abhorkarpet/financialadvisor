from __future__ import annotations

import os

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import fill_chat_input, wait_for_streamlit

pytestmark = pytest.mark.e2e

CHAT_INPUT = '[data-testid="stChatInput"]'


def _navigate_to_chat(page: Page) -> None:
    page.get_by_role("button", name="Start Chat →").click()
    wait_for_streamlit(page)
    page.wait_for_selector("text=Simple Retirement Planner")


def _complete_simple_chat(page: Page, country: str, birth_year: str, income: str) -> None:
    """Send all facts in one message then confirm defaults. Results appear after confirmation."""
    fill_chat_input(page, CHAT_INPUT, f"{country}, born {birth_year}, {income} income goal")
    wait_for_streamlit(page)
    # LLM responds with defaults block — wait for it then confirm
    page.wait_for_selector("text=Retire at:", timeout=30_000)
    fill_chat_input(page, CHAT_INPUT, "looks good")
    wait_for_streamlit(page)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="requires OPENAI_API_KEY")
def test_simple_planning_happy_path_us(page: Page) -> None:
    """Full US happy path → 'Required Portfolio at Retirement' metric visible."""
    expect(page.get_by_role("button", name="Start Chat →")).to_be_visible()
    expect(page.get_by_role("button", name="Enter Details →")).to_be_visible()

    _navigate_to_chat(page)
    page.wait_for_selector("text=Three quick questions", timeout=10_000)

    _complete_simple_chat(page, "US", "1990", "$60,000 per year")

    # Once done=True, chat_fields has retirement_age + life_expectancy + target_income
    # and the metric renders in the right-hand results box
    metric = page.locator('[data-testid="stMetricLabel"]').filter(
        has_text="Required Portfolio at Retirement"
    )
    expect(metric).to_be_visible(timeout=20_000)


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="requires OPENAI_API_KEY")
def test_simple_planning_india_currency(page: Page) -> None:
    """India path shows 'Required Corpus at Retirement' metric."""
    _navigate_to_chat(page)

    fill_chat_input(page, CHAT_INPUT, "India, born 1985, ₹1,200,000 per year income goal")
    wait_for_streamlit(page)
    page.wait_for_selector("text=Retire at:", timeout=30_000)
    fill_chat_input(page, CHAT_INPUT, "looks good")
    wait_for_streamlit(page)

    # India uses "Corpus" label
    metric = page.locator('[data-testid="stMetricLabel"]').filter(
        has_text="Required Corpus at Retirement"
    )
    expect(metric).to_be_visible(timeout=20_000)


def test_simple_planning_back_navigation(page: Page) -> None:
    """'← Change planning mode' returns to mode_selection. No API key needed."""
    _navigate_to_chat(page)

    page.get_by_role("button", name="← Change planning mode").click()
    wait_for_streamlit(page)

    expect(
        page.get_by_role("heading", name="How would you like to plan your retirement?")
    ).to_be_visible()


def test_simple_planning_shows_warning_without_api_key(page: Page) -> None:
    """When OPENAI_API_KEY is absent, a warning is shown on the chat page."""
    if os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is set — warning will not appear")

    _navigate_to_chat(page)

    warning = page.locator('[data-testid="stAlert"]').filter(has_text="OPENAI_API_KEY")
    expect(warning).to_be_visible()


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="requires OPENAI_API_KEY")
def test_simple_planning_transcript_download_visible(page: Page) -> None:
    """After the first message the '⬇ Download transcript' button appears."""
    _navigate_to_chat(page)

    fill_chat_input(page, CHAT_INPUT, "US")
    wait_for_streamlit(page)

    download_btn = page.get_by_role("button", name="⬇ Download transcript")
    expect(download_btn).to_be_visible()
