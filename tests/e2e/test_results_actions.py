from __future__ import annotations

import os

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import dismiss_analytics_dialog_if_present, wait_for_streamlit

pytestmark = pytest.mark.e2e

_needs_key = pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="requires OPENAI_API_KEY")


def _assert_on_results(pg: Page) -> None:
    """Assert we're on the main results page (heading visible)."""
    pg.wait_for_selector("text=Retirement Projection & Analysis", timeout=10_000)


def _navigate_to_full_details(pg: Page) -> None:
    """From results page, click 'View Full Details' to reach full_details page.

    The action buttons (PDF, Scenarios, Detailed Analysis) are rendered in the
    full_details page block, not the results page block.
    """
    _assert_on_results(pg)
    btn = pg.get_by_role("button", name="📊 View Full Details ▼")
    btn.scroll_into_view_if_needed()
    btn.click()
    wait_for_streamlit(pg)
    pg.wait_for_selector("text=Full Details", timeout=10_000)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@_needs_key
def test_results_key_metrics_visible(detailed_results_page: Page) -> None:
    """Five key metric cards are visible on the results page."""
    pg = detailed_results_page
    _assert_on_results(pg)

    for label in [
        "Years to Retirement",
        "Total Pre-Tax Value",
        "Total After-Tax Value",
        "Tax Efficiency",
        "Projected Annual Income",
    ]:
        locator = pg.locator('[data-testid="stMetricLabel"]').filter(has_text=label)
        expect(locator).to_be_visible(timeout=5_000)


@_needs_key
def test_results_view_detailed_analysis(detailed_results_page: Page) -> None:
    """'📈 View Detailed Analysis' navigates to the detailed_analysis page.

    This button lives in the full_details page block — navigate there first.
    """
    pg = detailed_results_page
    _navigate_to_full_details(pg)

    btn = pg.get_by_role("button", name="📈 View Detailed Analysis")
    btn.scroll_into_view_if_needed()
    expect(btn).to_be_visible()
    btn.click()
    wait_for_streamlit(pg)

    pg.wait_for_selector("text=Detailed Analysis", timeout=15_000)


@_needs_key
def test_results_create_pdf_report_dialog(detailed_results_page: Page) -> None:
    """'📥 Create PDF Report' opens the PDF generation dialog.

    This button lives in the full_details page block — navigate there first.
    """
    pg = detailed_results_page
    _navigate_to_full_details(pg)

    btn = pg.get_by_role("button", name="📥 Create PDF Report")
    btn.scroll_into_view_if_needed()
    expect(btn).to_be_visible()
    btn.click()
    wait_for_streamlit(pg)

    dialog = pg.locator('[data-testid="stDialog"]')
    expect(dialog).to_be_visible(timeout=10_000)
    expect(dialog).to_contain_text("Generate PDF Report")


@_needs_key
@pytest.mark.slow
def test_results_run_scenarios_monte_carlo(detailed_results_page: Page) -> None:
    """'🚀 Run Scenarios' opens the scenario dialog then navigates to Monte Carlo page.

    This button lives in the full_details page block — navigate there first.
    """
    pg = detailed_results_page
    _navigate_to_full_details(pg)

    btn = pg.get_by_role("button", name="🚀 Run Scenarios")
    btn.scroll_into_view_if_needed()
    expect(btn).to_be_visible()
    btn.click()
    wait_for_streamlit(pg)

    dialog = pg.locator('[data-testid="stDialog"]')
    expect(dialog).to_be_visible(timeout=10_000)
    expect(dialog).to_contain_text("Scenario Analysis")
    expect(dialog).to_contain_text("Number of Scenarios")

    run_btn = dialog.get_by_role("button").filter(has_text="Run")
    if run_btn.count() == 0:
        run_btn = dialog.locator('[data-testid="stButton"] button[kind="primary"]')
    run_btn.first.click()
    wait_for_streamlit(pg)

    dismiss_analytics_dialog_if_present(pg)
    wait_for_streamlit(pg)

    pg.wait_for_selector("text=Monte Carlo Simulation", timeout=30_000)
    expect(pg.get_by_role("heading", name="Monte Carlo Simulation")).to_be_visible()

    back_btn = pg.get_by_role("button", name="← Back to Results")
    expect(back_btn).to_be_visible()
    back_btn.click()
    wait_for_streamlit(pg)

    _assert_on_results(pg)


@_needs_key
def test_results_back_to_setup_button(detailed_results_page: Page) -> None:
    """'← Back to Setup' on the results page returns to onboarding Step 2."""
    pg = detailed_results_page
    _assert_on_results(pg)

    btn = pg.get_by_role("button", name="← Back to Setup")
    expect(btn).to_be_visible()
    btn.click()
    wait_for_streamlit(pg)

    # Step 2 shows "Step 2 of 2" progress indicator — unique on that page
    expect(pg.get_by_text("Step 2 of 2")).to_be_visible()
