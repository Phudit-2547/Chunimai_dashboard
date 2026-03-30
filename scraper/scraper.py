"""
Playwright scraper for SEGA arcade portals.
Adapted from Chunimai-tracker play_counter/scraper.py.
Extracts cumulative play counts and ratings for maimai and CHUNITHM.
"""
import json
import os
import re
import time
from datetime import datetime

import requests
from playwright.sync_api import sync_playwright

from constants import (
    CHUNITHM_HOME_URL,
    CHUNITHM_LOGIN_URL,
    CHUNITHM_PLAY_COUNT_SELECTOR,
    CHUNITHM_PLAYER_DATA_URL,
    CHUNITHM_RATING_SELECTOR,
    MAIMAI_HOME_URL,
    MAIMAI_LOGIN_URL,
    MAIMAI_PLAY_COUNT_REGEX,
    MAIMAI_PLAYER_DATA_URL,
)

COOKIE_DIR = os.path.join(os.path.dirname(__file__), "cookies")
TRACE_DIR = os.path.join(os.path.dirname(__file__), "traces")
MAX_RETRIES = 3
RETRY_DELAY = 2

# Ensure directories exist
os.makedirs(COOKIE_DIR, exist_ok=True)
os.makedirs(TRACE_DIR, exist_ok=True)


def _cookie_path(game: str) -> str:
    return os.path.join(COOKIE_DIR, f"{game}_state.json")


def _trace_path(game: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(TRACE_DIR, f"{game}_failure_{timestamp}.zip")


def _save_cookies(context, game: str):
    path = _cookie_path(game)
    cookies = context.cookies()
    with open(path, "w") as f:
        json.dump(cookies, f)
    print(f"[SAVE] Cookies saved to {path}")


def _load_cookies(context, game: str) -> bool:
    path = _cookie_path(game)
    if not os.path.exists(path):
        return False
    try:
        with open(path) as f:
            cookies = json.load(f)
        context.add_cookies(cookies)
        print(f"[LOAD] Cookies loaded from {path}")
        return True
    except Exception as e:
        print(f"[WARN] Failed to load cookies: {e}")
        return False


def _send_failure_notification(game: str, failure_reason: str, trace_path: str = None):
    """Send notification to Discord when scraping fails."""
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not webhook_url:
        print("[SKIP] DISCORD_WEBHOOK_URL not configured")
        return

    trace_info = f"\n[TRACE] Trace saved: `{trace_path}`" if trace_path else ""
    payload = {
        "content": (
            f"[FAIL] **Scraping Failed** [FAIL]\n\n"
            f"**Game:** {game}\n"
            f"**Reason:** `{failure_reason}`\n"
            f"**All {MAX_RETRIES} retries exhausted.**"
            f"{trace_info}"
        )
    }

    try:
        response = requests.post(webhook_url, json=payload)
        if response.status_code == 204:
            print("[OK] Discord notification sent")
        else:
            print(f"[WARN] Discord notification failed: {response.status_code}")
    except Exception as e:
        print(f"[WARN] Error sending notification: {e}")


def _capture_failure_details(page) -> str:
    """Capture URL and page text when failure occurs."""
    try:
        url = page.url if page else "N/A"
        try:
            page_text = page.inner_text("body")
            page_text = page_text.strip()[:500]
        except Exception:
            page_text = "(could not capture page text)"
        return f"url: {url} | body: {page_text}"
    except Exception:
        return "Failed to capture failure details"


def _is_logged_in(page, game: str) -> bool:
    """Check if page is already logged in (cookies are valid)."""
    try:
        login_url = MAIMAI_LOGIN_URL if game == "maimai" else CHUNITHM_LOGIN_URL
        home_url = MAIMAI_HOME_URL if game == "maimai" else CHUNITHM_HOME_URL
        page.goto(login_url, wait_until="domcontentloaded")
        if not page.url.startswith(home_url):
            return False
        # Verify by checking for a logged-in element
        if game == "maimai":
            user_el = page.query_selector(".rating_block")
        else:
            user_el = page.query_selector(".player_rating_num_block")
        if user_el:
            print("[OK] Using cached session (already logged in)")
            return True
        return False
    except Exception:
        return False


def login_sega(page, game: str, sid: str, password: str):
    """Login to SEGA via Aime gateway."""
    login_url = MAIMAI_LOGIN_URL if game == "maimai" else CHUNITHM_LOGIN_URL
    home_url = MAIMAI_HOME_URL if game == "maimai" else CHUNITHM_HOME_URL

    page.goto(login_url, wait_until="domcontentloaded")

    # Check if already logged in (cookies worked)
    if page.url.startswith(home_url):
        return

    # Click SEGA ID OpenID button
    page.locator("span.c-button--openid--segaId").click()
    page.wait_for_selector("#sid")

    # Fill credentials
    page.locator("#sid").fill(sid)
    page.locator("#password").fill(password)

    # Handle checkbox (different per game)
    if game == "maimai":
        page.locator("label.c-form__label--bg.agree input#agree").click()
        page.wait_for_timeout(1000)

        for i in range(3):
            is_checked = page.locator("label.c-form__label--bg.agree input#agree").is_checked()
            if is_checked:
                break
            print(f"[RETRY] Checkbox unchecked, clicking again... (attempt {i + 1})")
            page.locator("label.c-form__label--bg.agree input#agree").click()
            page.wait_for_timeout(500)
    else:
        page.get_by_text("Agree to the terms of use for Aime service").click()
        page.wait_for_timeout(1000)

        for i in range(3):
            is_checked = page.locator("label.c-form__label--bg:not(.agree) input#agree").is_checked()
            if is_checked:
                break
            print(f"[RETRY] Checkbox unchecked, clicking again... (attempt {i + 1})")
            page.get_by_text("Agree to the terms of use for Aime service").click()
            page.wait_for_timeout(500)

    # Wait for submit button and click
    page.wait_for_selector("button#btnSubmit:not([disabled])", timeout=10000)
    page.locator("button#btnSubmit").click()

    # Wait for redirect to home page
    page.wait_for_url(f"{home_url}**", timeout=15000)


def get_maimai_data(page) -> dict:
    """Extract maimai rating and cumulative play count."""
    home_url = MAIMAI_HOME_URL
    result = {"rating": 0, "cumulative": 0, "failed": False, "failure_reason": None}

    try:
        # Get rating from home page
        page.goto(home_url, wait_until="domcontentloaded")
        # Try multiple possible selectors
        for selector in [".rating_block", ".rating_block .rate", ".c-rating"]:
            rating_el = page.query_selector(selector)
            if rating_el:
                rating_text = rating_el.inner_text().strip()
                if rating_text.isdigit():
                    result["rating"] = int(rating_text)
                    break

        # Get cumulative play count from player data page
        page.goto(MAIMAI_PLAYER_DATA_URL, wait_until="domcontentloaded")
        body_text = page.inner_text("body")
        match = re.search(MAIMAI_PLAY_COUNT_REGEX, body_text)
        if match:
            result["cumulative"] = int(match.group(1))

    except Exception as e:
        result["failed"] = True
        result["failure_reason"] = str(e)

    return result


def get_chunithm_data(page) -> dict:
    """Extract CHUNITHM rating and cumulative play count."""
    result = {"rating": 0.0, "cumulative": 0, "failed": False, "failure_reason": None}

    try:
        # Get rating from home page (parsed from img tag filenames)
        page.goto(CHUNITHM_HOME_URL, wait_until="domcontentloaded")
        rating_block = page.query_selector(CHUNITHM_RATING_SELECTOR)
        if rating_block:
            images = rating_block.query_selector_all("img")
            rating_str = ""
            for img in images:
                src = img.get_attribute("src") or ""
                filename = src.split("/")[-1]
                if "comma" in filename:
                    rating_str += "."
                elif "rating_" in filename:
                    digit = filename.split("_")[-1].replace(".png", "")
                    rating_str += str(int(digit))
            result["rating"] = float(rating_str) if rating_str else 0.0
        print(f"[OK] chunithm rating: {result['rating']}")

        # Get cumulative play count
        page.goto(CHUNITHM_PLAYER_DATA_URL, wait_until="domcontentloaded")
        count_el = page.query_selector(CHUNITHM_PLAY_COUNT_SELECTOR)
        if count_el:
            count_text = count_el.inner_text().strip()
            result["cumulative"] = int(count_text) if count_text.isdigit() else 0
        print(f"[OK] chunithm cumulative: {result['cumulative']}")

    except Exception as e:
        result["failed"] = True
        result["failure_reason"] = str(e)

    return result


def scrape(games: list[str], sid: str, password: str) -> dict:
    """
    Scrape SEGA portals for play data.

    Args:
        games: List of games to scrape ("maimai", "chunithm")
        sid: SEGA ID
        password: SEGA password

    Returns:
        Dict with per-game data: {game: {rating, cumulative, failed, failure_reason}}
    """
    results = {}

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)

        for game in games:
            context = browser.new_context()
            page = context.new_page()

            # Start tracing for failure debugging
            context.tracing.start(screenshots=True, snapshots=True)

            last_failure_reason = None
            last_trace_path = None

            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    # Always do fresh login for reliability
                    print(f"[INFO] Logging in to {game}...")
                    login_sega(page, game, sid, password)
                    _save_cookies(context, game)

                    if game == "maimai":
                        results[game] = get_maimai_data(page)
                    else:
                        results[game] = get_chunithm_data(page)

                    if results[game]["failed"]:
                        raise Exception(results[game]["failure_reason"])

                    break  # Success, exit retry loop

                except Exception as e:
                    failure_reason = _capture_failure_details(page)
                    last_failure_reason = f"Attempt {attempt}: {e} | {failure_reason}"
                    print(f"[WARN] Attempt {attempt} failed: {e}")

                    if attempt < MAX_RETRIES:
                        print(f"[WAIT] Retrying in {RETRY_DELAY} seconds...")
                        time.sleep(RETRY_DELAY)
                    else:
                        print(f"[ERROR] {game} failed after {MAX_RETRIES} attempts")
                        _send_failure_notification(game, last_failure_reason)
                        results[game] = {
                            "rating": 0 if game == "maimai" else 0.0,
                            "cumulative": 0,
                            "failed": True,
                            "failure_reason": last_failure_reason,
                        }

            # Save failure trace if failed
            if results[game].get("failed"):
                try:
                    trace_path = _trace_path(game)
                    context.tracing.stop(path=trace_path)
                    last_trace_path = trace_path
                    _send_failure_notification(game, last_failure_reason, last_trace_path)
                except Exception as e:
                    print(f"[WARN] Failed to save trace: {e}")

            page.close()
            context.close()

        browser.close()

    return results
