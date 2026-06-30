#!/usr/bin/env python3
"""
Run this locally (once a month or when PropertyMe login breaks) to
capture fresh session cookies. Paste the output into the
PROPERTYME_COOKIES GitHub secret.

Usage:
    python extract_cookies.py

Requirements:
    playwright installed locally with chromium:
        pip install playwright
        playwright install chromium
"""

import asyncio
import json
import sys

from playwright.async_api import async_playwright

LOGIN_URL = "https://manager.propertyme.com/"


async def main() -> None:
    print("=" * 60)
    print("PropertyMe Cookie Extractor")
    print("=" * 60)
    print()
    print("A browser will open. Log in to PropertyMe normally.")
    print("Complete the Cloudflare challenge, email, password, and 2FA.")
    print("Once the dashboard loads fully, return here and press Enter.")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=50,
            args=["--start-maximized"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport=None,
        )
        page = await context.new_page()

        await page.goto(LOGIN_URL)

        input("Press Enter once PropertyMe dashboard is fully loaded... ")

        current_url = page.url
        if "id.propertyme.com" in current_url or "login" in current_url.lower():
            print()
            print("ERROR: Still on the login page.")
            print("Complete login fully before pressing Enter. Try again.")
            await browser.close()
            sys.exit(1)

        cookies = await context.cookies()

        if not cookies:
            print("ERROR: No cookies captured. Something went wrong.")
            await browser.close()
            sys.exit(1)

        cookie_json = json.dumps(cookies)

        # Save to file so you can inspect or copy manually
        output_file = "propertyme_cookies.json"
        with open(output_file, "w") as f:
            f.write(cookie_json)

        print()
        print(f"Extracted {len(cookies)} cookies.")
        print(f"Saved to: {output_file}")
        print()
        print("-" * 60)
        print("NEXT STEP")
        print("-" * 60)
        print("1. Copy the full contents of propertyme_cookies.json")
        print("2. Go to: GitHub repo > Settings > Secrets > Actions")
        print("3. Update the secret named: PROPERTYME_COOKIES")
        print("4. Paste the JSON as the value and save.")
        print()
        print("Do NOT commit propertyme_cookies.json to git.")
        print("Add it to .gitignore if not already there.")
        print()
        print("Cookies typically last 30 days. Run this again when they expire.")

        await browser.close()


asyncio.run(main())
