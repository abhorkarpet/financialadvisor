from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Generator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

APP_PORT = 8501
APP_URL = f"http://localhost:{APP_PORT}"
PROJECT_ROOT = Path(__file__).parent.parent.parent
STREAMLIT_CMD = [
    sys.executable, "-m", "streamlit", "run", "fin_advisor.py",
    "--server.headless", "true",
    "--server.port", str(APP_PORT),
    "--server.enableCORS", "false",
    "--server.enableXsrfProtection", "false",
]
SERVER_STARTUP_TIMEOUT = 30
DEFAULT_TIMEOUT = 20_000
STREAMLIT_SETTLE_MS = 3_000


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------

def _wait_for_port(host: str, port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


@pytest.fixture(scope="session")
def streamlit_server() -> Generator[None, None, None]:
    already_running = _wait_for_port("localhost", APP_PORT, timeout=1)
    proc = None

    if not already_running:
        proc = subprocess.Popen(
            STREAMLIT_CMD,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ},
        )
        ready = _wait_for_port("localhost", APP_PORT, timeout=SERVER_STARTUP_TIMEOUT)
        if not ready:
            proc.terminate()
            raise RuntimeError(f"Streamlit server did not start within {SERVER_STARTUP_TIMEOUT}s")
        time.sleep(2)

    yield

    if proc is not None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="session")
def browser_session(streamlit_server) -> Generator[Browser, None, None]:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        yield browser
        browser.close()


# ---------------------------------------------------------------------------
# Per-test page — fresh browser context, splash dismissed
# ---------------------------------------------------------------------------

@pytest.fixture()
def page(browser_session: Browser) -> Generator[Page, None, None]:
    context: BrowserContext = browser_session.new_context(
        viewport={"width": 1280, "height": 900},
        service_workers="block",
    )
    pg = context.new_page()
    pg.set_default_timeout(DEFAULT_TIMEOUT)

    # Wait for full network idle so Streamlit's initial render is complete
    pg.goto(APP_URL, wait_until="networkidle")
    pg.wait_for_selector('[data-testid="stAppViewContainer"]', timeout=30_000)

    # Dismiss splash screen — give extra time for first cold render
    get_started = pg.get_by_role("button", name="✅ Get Started")
    get_started.wait_for(state="visible", timeout=30_000)
    get_started.click()
    wait_for_streamlit(pg)

    pg.wait_for_selector("text=How would you like to plan your retirement?", timeout=15_000)

    yield pg

    context.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def wait_for_streamlit(page: Page) -> None:
    """Wait until Streamlit finishes its current rerun cycle."""
    try:
        spinner = page.locator('[data-testid="stSpinner"]')
        if spinner.count() > 0:
            spinner.wait_for(state="hidden", timeout=60_000)
    except Exception:
        pass

    try:
        status = page.locator('[data-testid="stStatusWidget"]')
        if status.count() > 0:
            status.wait_for(state="hidden", timeout=30_000)
    except Exception:
        pass

    page.wait_for_timeout(500)


def fill_chat_input(page: Page, selector: str, text: str) -> None:
    """Fill a Streamlit chat textarea and submit with Enter."""
    textarea = page.locator(f"{selector} textarea")
    textarea.wait_for(state="visible", timeout=20_000)
    textarea.fill(text)
    textarea.press("Enter")


def dismiss_analytics_dialog_if_present(page: Page) -> None:
    """Dismiss the analytics consent dialog if it appears (Monte Carlo page only)."""
    try:
        dialog = page.locator('[data-testid="stDialog"]')
        if dialog.is_visible(timeout=2_000):
            dialog.get_by_role("button", name="❌ No Thanks").click()
            wait_for_streamlit(page)
    except Exception:
        pass


def _complete_setup_chat(page: Page) -> None:
    """
    Drive the setup advisor chat to completion (done=True → Continue button visible).

    The advisor requires 2 user turns:
      Turn 1: Provide birth year, retirement age, income goal in one message.
              LLM responds with defaults confirmation.
      Turn 2: Confirm ("looks good") → LLM sets done=True → Continue button appears.
    """
    fill_chat_input(page, CHAT_INPUT, "Born in 1990, want to retire at 65, income goal $60,000/yr")
    wait_for_streamlit(page)

    # Wait for assistant's defaults-confirmation reply before sending Turn 2
    # The assistant response will contain "Retire at:" as part of the defaults block
    page.wait_for_selector("text=Retire at:", timeout=30_000)

    fill_chat_input(page, CHAT_INPUT, "looks good")
    wait_for_streamlit(page)


# ---------------------------------------------------------------------------
# Composite fixtures
# ---------------------------------------------------------------------------

CHAT_INPUT = '[data-testid="stChatInput"]'


@pytest.fixture()
def results_page(page: Page) -> Generator[Page, None, None]:
    """Complete Simple Planning (US / 1990 / $60k) and yield once the metric is visible."""
    page.wait_for_selector("text=How would you like to plan", timeout=10_000)

    page.get_by_role("button", name="Start Chat →").click()
    wait_for_streamlit(page)
    page.wait_for_selector("text=Simple Retirement Planner", timeout=10_000)

    # Turn 1: all three facts at once
    fill_chat_input(page, CHAT_INPUT, "US, born 1990, $60,000 per year income goal")
    wait_for_streamlit(page)

    # Wait for defaults confirmation, then acknowledge
    page.wait_for_selector("text=Retire at:", timeout=30_000)
    fill_chat_input(page, CHAT_INPUT, "looks good")
    wait_for_streamlit(page)

    # Results appear once target_income + retirement_age + life_expectancy are set
    page.locator('[data-testid="stMetricLabel"]').filter(
        has_text="Required Portfolio at Retirement"
    ).wait_for(state="visible", timeout=20_000)

    yield page


@pytest.fixture()
def detailed_results_page(page: Page) -> Generator[Page, None, None]:
    """Complete Detailed Planning (2-turn chat + manual assets) and yield at results."""
    page.wait_for_selector("text=How would you like to plan", timeout=10_000)

    page.get_by_role("button", name="Enter Details →").click()
    wait_for_streamlit(page)
    page.wait_for_selector("text=Your Retirement Goals", timeout=10_000)

    _complete_setup_chat(page)

    continue_btn = page.get_by_role("button", name="Continue: Set Up Accounts →")
    continue_btn.wait_for(state="visible", timeout=30_000)
    continue_btn.click()
    wait_for_streamlit(page)

    page.wait_for_selector("text=Asset Configuration", timeout=10_000)
    page.get_by_text("Configure Individual Assets").click()
    wait_for_streamlit(page)

    page.get_by_role("button", name="Complete Setup → View Results").click()
    wait_for_streamlit(page)

    page.wait_for_selector("text=Retirement Projection & Analysis", timeout=20_000)
    yield page
