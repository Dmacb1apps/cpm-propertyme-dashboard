"""
Standalone test: does a full, fresh TOTP login get through Cloudflare
Turnstile when Chromium runs non-headless under xvfb, instead of headless?

This does NOT touch the cookie-based production login in download_reports.py.
It is a login-only test — no report downloads, no data processing.

Reads PROPERTYME_EMAIL, PROPERTYME_PASSWORD, PROPERTYME_TOTP_SECRET from
the environment (same secrets download_reports.py used before the cookie
conversion).

Usage (must run non-headless under a virtual display):
    xvfb-run -a python3 test_xvfb_login.py
"""

import os
import random
import sys
import pyotp
from pathlib import Path
from playwright.sync_api import sync_playwright

SCRIPT_DIR = Path(__file__).parent
SCREENSHOT_DIR = SCRIPT_DIR / "test_screenshots"
MANAGER_URL = "https://manager.propertyme.com"
# Same selector download_reports.py waits on post-login to confirm the
# dashboard shell (not just the branded loading spinner) has rendered.
DASHBOARD_READY_SELECTOR = "[data-test-id='reports-menu']"
# angular-loading-bar element PropertyMe shows during the branded splash
# screen (login_success.png) and on subsequent XHRs; hidden once real
# dashboard content has rendered. Confirmed by live inspection.
LOADING_OVERLAY_SELECTOR = "#loading-bar-spinner"


def looks_like_turnstile(page) -> bool:
    """Check for a Turnstile challenge specifically, distinct from any other failure."""
    if page.locator("iframe[src*='challenges.cloudflare.com']").count() > 0:
        return True
    if page.locator("iframe[title*='Cloudflare']").count() > 0:
        return True
    content = page.content()
    return "Turnstile" in content or "cf-turnstile" in content


def login(page):
    """
    Full pre-cookie-conversion login flow: email, password, TOTP.
    Selectors and success check are copied from the original login()
    (git history, commit before "Refactor login to use session cookies").
    """
    email = os.environ["PROPERTYME_EMAIL"]
    password = os.environ["PROPERTYME_PASSWORD"]

    print(f"Navigating to {MANAGER_URL} (will redirect to login)...")
    page.goto(MANAGER_URL)
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        page.wait_for_load_state("domcontentloaded")
    print(f"  Landed on: {page.url}")

    if looks_like_turnstile(page):
        print("TURNSTILE DETECTED before login form appeared.")
        return "turnstile"

    try:
        page.wait_for_selector("input[type='email']", timeout=15000)
    except Exception:
        if looks_like_turnstile(page):
            print("TURNSTILE DETECTED — email field never appeared.")
            return "turnstile"
        print("FAILED — email field never appeared and no Turnstile detected.")
        return "failed"

    email_input = page.locator("input[type='email']")
    email_input.click()
    email_input.fill(email)
    page.wait_for_timeout(800)

    password_input = page.locator("input[type='password']")
    password_input.click()
    password_input.fill(password)
    page.wait_for_timeout(800)

    btn = page.locator("button:has-text('Log in')")
    btn.wait_for(state="visible")
    btn.scroll_into_view_if_needed()
    page.wait_for_timeout(500)
    btn.click()
    print(f"  URL immediately after Log in click: {page.url}")

    page.wait_for_timeout(2000)
    if looks_like_turnstile(page):
        print("TURNSTILE DETECTED after credential submit.")
        return "turnstile"

    page.wait_for_load_state("networkidle", timeout=20000)
    print(f"  URL after networkidle: {page.url}")

    if "/auth/verify" in page.url:
        print("  2FA page detected.")
        code = pyotp.TOTP(os.environ["PROPERTYME_TOTP_SECRET"]).now()
        print(f"  Entering 2FA code: {code}")

        otp_boxes = page.locator("input[type='text']")
        otp_boxes.first.click()
        page.keyboard.type(code)
        page.wait_for_timeout(500)

        page.get_by_role("button", name="Log in").click()
        print(f"  URL immediately after 2FA submit: {page.url}")
        try:
            page.wait_for_function(
                "() => !window.location.href.includes('id.propertyme.com')",
                timeout=30000,
            )
        except Exception:
            if looks_like_turnstile(page):
                print("TURNSTILE DETECTED after 2FA submit.")
                return "turnstile"
            print("FAILED — never redirected off id.propertyme.com after 2FA.")
            return "failed"
        print(f"  Redirected to: {page.url}")
    else:
        print("  No 2FA page detected — waiting for manager redirect...")
        try:
            page.wait_for_function(
                "() => !window.location.href.includes('id.propertyme.com')",
                timeout=20000,
            )
        except Exception:
            if looks_like_turnstile(page):
                print("TURNSTILE DETECTED — never redirected off id.propertyme.com.")
                return "turnstile"
            print("FAILED — never redirected off id.propertyme.com.")
            return "failed"

    if "id.propertyme.com" in page.url:
        print("FAILED — still on id.propertyme.com after login flow completed.")
        return "failed"

    # Stage 2: leaving the login domain only means the redirect fired, not that
    # the dashboard has rendered — a stuck spinner or silent load failure looks
    # identical to a real success at this point. Confirm the dashboard shell
    # itself appeared before calling this a success.
    print(f"  URL left login domain — waiting for dashboard shell ('{DASHBOARD_READY_SELECTOR}')...")
    try:
        page.wait_for_selector(DASHBOARD_READY_SELECTOR, state="visible", timeout=15000)
    except Exception:
        print(
            f"STUCK LOADING — URL left id.propertyme.com but "
            f"'{DASHBOARD_READY_SELECTOR}' never appeared within timeout. "
            f"Current URL: {page.url}"
        )
        return "stuck"

    print(f"Dashboard selector {DASHBOARD_READY_SELECTOR} found and visible")

    # Stage 3: the dashboard-shell selector can be present in the DOM while the
    # branded loading spinner still covers it (login_success.png showed exactly
    # this). Confirm the spinner overlay has actually gone before calling this
    # a success.
    print(f"  Waiting for loading overlay ('{LOADING_OVERLAY_SELECTOR}') to disappear...")
    try:
        page.wait_for_selector(LOADING_OVERLAY_SELECTOR, state="hidden", timeout=15000)
    except Exception:
        print(
            f"STUCK LOADING — '{DASHBOARD_READY_SELECTOR}' is visible but "
            f"'{LOADING_OVERLAY_SELECTOR}' never disappeared within timeout. "
            f"Current URL: {page.url}"
        )
        return "stuck"

    print(f"  Loading overlay gone — dashboard shell confirmed loaded — current URL: {page.url}")
    return "success"


MAX_ATTEMPTS = 3
RETRY_WAIT_RANGE_SECONDS = (60, 90)

RESULT_LABELS = {
    "success": "SUCCESS",
    "turnstile": "TURNSTILE",
    "failed": "FAILED",
    "stuck": "STUCK_LOADING",
}


def main():
    SCREENSHOT_DIR.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        result = "failed"
        try:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                print(f"\n=== Login attempt {attempt} of {MAX_ATTEMPTS} ===")
                try:
                    result = login(page)
                except Exception as e:
                    print(f"ERROR during login: {e}")
                    result = "failed"

                screenshot_path = SCREENSHOT_DIR / f"login_attempt{attempt}_{result}.png"
                page.screenshot(path=str(screenshot_path))
                print(f"Screenshot saved: {screenshot_path}")

                if result == "success":
                    print(f"SUCCESS on attempt {attempt} of {MAX_ATTEMPTS}")
                    page.wait_for_timeout(2000)
                    confirm_path = SCREENSHOT_DIR / "login_success_confirmed.png"
                    page.screenshot(path=str(confirm_path))
                    print(f"Confirmation screenshot saved: {confirm_path}")
                    break

                if result != "turnstile":
                    # "stuck" or generic "failed" indicate a script/selector bug,
                    # not a transient block — retrying would hide a real problem.
                    print(
                        f"FAILED after attempt {attempt} of {MAX_ATTEMPTS}, "
                        f"final result: {RESULT_LABELS.get(result, result.upper())} "
                        "— not a Turnstile block, not retrying."
                    )
                    break

                if attempt == MAX_ATTEMPTS:
                    print(f"FAILED after {MAX_ATTEMPTS} attempts, final result: TURNSTILE")
                    break

                wait_s = random.uniform(*RETRY_WAIT_RANGE_SECONDS)
                print(
                    f"TURNSTILE on attempt {attempt} of {MAX_ATTEMPTS} — "
                    f"waiting {wait_s:.0f}s, then retrying from scratch "
                    "(fresh navigation, fresh TOTP code)..."
                )
                page.wait_for_timeout(wait_s * 1000)
        finally:
            context.close()
            browser.close()

    print(f"\nRESULT: {RESULT_LABELS.get(result, result.upper())}")
    if result == "turnstile":
        print("Turnstile challenge blocked every attempt — hypothesis disproved for this run.")
        sys.exit(1)
    elif result == "stuck":
        print(
            "URL left the login domain but the dashboard shell never rendered — "
            "possible stuck spinner, slow API call, or silent load failure. "
            "This is NOT a confirmed success."
        )
        sys.exit(1)
    elif result == "failed":
        print("Login failed for a reason other than Turnstile — see log above.")
        sys.exit(1)
    else:
        print("Non-headless login under xvfb succeeded — hypothesis supported.")
        sys.exit(0)


if __name__ == "__main__":
    main()
