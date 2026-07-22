"""
Shared PropertyMe login logic: full email/password/TOTP login with
Cloudflare Turnstile detection and retry-on-Turnstile behavior.

Extracted verbatim from test_xvfb_login.py, which validated this flow
across 21 non-headless runs under xvfb (20 successes, 1 Turnstile
failure that occurred before this retry logic existed).

Requires PROPERTYME_EMAIL, PROPERTYME_PASSWORD, PROPERTYME_TOTP_SECRET
in the environment.
"""

import os
import random
import pyotp

MANAGER_URL = "https://manager.propertyme.com"
# Selector confirming the dashboard shell (not just the branded loading
# spinner) has rendered post-login.
DASHBOARD_READY_SELECTOR = "[data-test-id='reports-menu']"
# angular-loading-bar element PropertyMe shows during the branded splash
# screen and on subsequent XHRs; hidden once real dashboard content has
# rendered. Confirmed by live inspection.
LOADING_OVERLAY_SELECTOR = "#loading-bar-spinner"

MAX_ATTEMPTS = 3
RETRY_WAIT_RANGE_SECONDS = (60, 90)
STUCK_2FA_RETRY_WAIT_SECONDS = (5, 10)

RESULT_LABELS = {
    "success": "SUCCESS",
    "turnstile": "TURNSTILE",
    "failed": "FAILED",
    "stuck": "STUCK_LOADING",
    "2fa_stuck": "2FA_STUCK",
}


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
    Full email/password/TOTP login flow, with Turnstile detection at each
    stage. Returns one of: "success", "turnstile", "failed", "stuck".
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
        page.wait_for_timeout(400)
        page.keyboard.type(code, delay=120)
        page.wait_for_timeout(500)

        try:
            page.wait_for_function(
                """() => {
                    const btns = [...document.querySelectorAll("button[aria-label='Log in']")];
                    return btns.some(b => !b.disabled);
                }""",
                timeout=8000,
            )
        except Exception:
            print("  2FA Log in button never enabled within timeout — treating as retryable race.")
            return "2fa_stuck"

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
    # branded loading spinner still covers it. Confirm the spinner overlay has
    # actually gone before calling this a success.
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


def login_with_retry(page, screenshot_dir=None):
    """
    Run login() up to MAX_ATTEMPTS times, retrying only on confirmed
    Turnstile hits and on "2fa_stuck" (fresh navigation + fresh TOTP each
    retry). Turnstile retries wait 60-90s (Cloudflare cooldown); "2fa_stuck"
    retries wait only 5-10s, since it's a transient client-side race where
    the TOTP field's focus-advance JS loses to fast keystroke typing and
    leaves the submit button disabled, not a Cloudflare block. Non-retryable
    failures ("failed"/"stuck") are not retried, since they indicate a
    script/selector bug rather than a transient block.

    If screenshot_dir is provided, saves a screenshot after each attempt
    (and a confirmation screenshot on success) — used by the standalone
    test script for diagnostics. Left as None in production use.

    Returns the final result: "success", "turnstile", "failed", "stuck", or
    "2fa_stuck".
    """
    result = "failed"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\n=== Login attempt {attempt} of {MAX_ATTEMPTS} ===")
        try:
            result = login(page)
        except Exception as e:
            print(f"ERROR during login: {e}")
            result = "failed"

        if screenshot_dir is not None:
            screenshot_path = screenshot_dir / f"login_attempt{attempt}_{result}.png"
            page.screenshot(path=str(screenshot_path))
            print(f"Screenshot saved: {screenshot_path}")

        if result == "success":
            print(f"SUCCESS on attempt {attempt} of {MAX_ATTEMPTS}")
            if screenshot_dir is not None:
                page.wait_for_timeout(2000)
                confirm_path = screenshot_dir / "login_success_confirmed.png"
                page.screenshot(path=str(confirm_path))
                print(f"Confirmation screenshot saved: {confirm_path}")
            return result

        if result not in ("turnstile", "2fa_stuck"):
            # "stuck" or generic "failed" indicate a script/selector bug,
            # not a transient block — retrying would hide a real problem.
            print(
                f"FAILED after attempt {attempt} of {MAX_ATTEMPTS}, "
                f"final result: {RESULT_LABELS.get(result, result.upper())} "
                "— not retryable, not retrying."
            )
            return result

        if attempt == MAX_ATTEMPTS:
            print(
                f"FAILED after {MAX_ATTEMPTS} attempts, final result: "
                f"{RESULT_LABELS.get(result, result.upper())}"
            )
            return result

        wait_range = (
            RETRY_WAIT_RANGE_SECONDS if result == "turnstile" else STUCK_2FA_RETRY_WAIT_SECONDS
        )
        wait_s = random.uniform(*wait_range)
        print(
            f"{RESULT_LABELS.get(result, result.upper())} on attempt {attempt} of {MAX_ATTEMPTS} — "
            f"waiting {wait_s:.0f}s, then retrying from scratch "
            "(fresh navigation, fresh TOTP code)..."
        )
        page.wait_for_timeout(wait_s * 1000)

    return result
