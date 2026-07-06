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
import sys
import pyotp
from pathlib import Path
from playwright.sync_api import sync_playwright

SCRIPT_DIR = Path(__file__).parent
SCREENSHOT_DIR = SCRIPT_DIR / "test_screenshots"
MANAGER_URL = "https://manager.propertyme.com"


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

    print(f"  Login complete — current URL: {page.url}")
    return "success"


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
            result = login(page)
        except Exception as e:
            print(f"ERROR during login: {e}")
            result = "failed"
        finally:
            screenshot_path = SCREENSHOT_DIR / f"login_{result}.png"
            page.screenshot(path=str(screenshot_path))
            print(f"Screenshot saved: {screenshot_path}")
            context.close()
            browser.close()

    print(f"\nRESULT: {result.upper()}")
    if result == "turnstile":
        print("Turnstile challenge blocked the non-headless run — hypothesis disproved.")
        sys.exit(1)
    elif result == "failed":
        print("Login failed for a reason other than Turnstile — see log above.")
        sys.exit(1)
    else:
        print("Non-headless login under xvfb succeeded — hypothesis supported.")
        sys.exit(0)


if __name__ == "__main__":
    main()
