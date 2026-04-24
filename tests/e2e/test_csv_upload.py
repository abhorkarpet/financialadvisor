from __future__ import annotations

import os
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import fill_chat_input, wait_for_streamlit, _complete_setup_chat

pytestmark = pytest.mark.e2e

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_CSV = FIXTURES_DIR / "sample_assets.csv"
SETUP_CHAT_INPUT = '[data-testid="stChatInput"]'


@pytest.fixture()
def step2_page(page: Page) -> Page:
    """Navigate to Detailed Planning Step 2 ready for upload tests."""
    page.get_by_role("button", name="Enter Details →").click()
    wait_for_streamlit(page)
    page.wait_for_selector("text=Your Retirement Goals")

    _complete_setup_chat(page)

    continue_btn = page.get_by_role("button", name="Continue: Set Up Accounts →")
    continue_btn.wait_for(state="visible", timeout=30_000)
    continue_btn.click()
    wait_for_streamlit(page)

    page.wait_for_selector("text=Asset Configuration")
    return page


_needs_key = pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="requires OPENAI_API_KEY")
_needs_csv = pytest.mark.skipif(not SAMPLE_CSV.exists(), reason="fixture CSV not found")


@_needs_key
@_needs_csv
def test_csv_upload_success_banner(step2_page: Page) -> None:
    """Uploading a valid CSV shows the success alert."""
    pg = step2_page

    pg.get_by_text("Upload CSV File").click()
    wait_for_streamlit(pg)

    file_input = pg.locator('[data-testid="stFileUploader"] input[type="file"]')
    file_input.set_input_files(str(SAMPLE_CSV))
    wait_for_streamlit(pg)

    success_msg = pg.locator('[data-testid="stAlert"]').filter(has_text="Successfully loaded")
    expect(success_msg).to_be_visible(timeout=15_000)

    # Expander label includes emoji prefix
    expect(pg.get_by_text("📋 Uploaded Assets (Editable)")).to_be_visible()


@_needs_key
@_needs_csv
def test_csv_upload_row_count(step2_page: Page) -> None:
    """Success banner confirms exactly 4 assets loaded from the fixture CSV."""
    pg = step2_page

    pg.get_by_text("Upload CSV File").click()
    wait_for_streamlit(pg)

    file_input = pg.locator('[data-testid="stFileUploader"] input[type="file"]')
    file_input.set_input_files(str(SAMPLE_CSV))
    wait_for_streamlit(pg)

    # The success banner text is: "✅ Successfully loaded {n} assets from CSV file!"
    # Checking for "4 assets" confirms the exact row count without relying on
    # Glide Data Grid's internal DOM structure (which varies by Streamlit version).
    success_msg = pg.locator('[data-testid="stAlert"]').filter(has_text="Successfully loaded")
    expect(success_msg).to_be_visible(timeout=15_000)
    expect(success_msg).to_contain_text("4 assets")


@_needs_key
@_needs_csv
def test_csv_upload_complete_to_results(step2_page: Page) -> None:
    """Upload valid CSV then complete setup → results page renders."""
    pg = step2_page

    pg.get_by_text("Upload CSV File").click()
    wait_for_streamlit(pg)

    file_input = pg.locator('[data-testid="stFileUploader"] input[type="file"]')
    file_input.set_input_files(str(SAMPLE_CSV))
    wait_for_streamlit(pg)

    pg.locator('[data-testid="stAlert"]').filter(has_text="Successfully loaded").wait_for(
        state="visible", timeout=15_000
    )

    pg.get_by_role("button", name="Complete Setup → View Results").click()
    wait_for_streamlit(pg)

    pg.wait_for_selector("text=Retirement Projection & Analysis", timeout=20_000)
    expect(
        pg.get_by_role("heading", name="Retirement Projection & Analysis")
    ).to_be_visible()
