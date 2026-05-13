"""
Run this script manually every ~7 days to refresh your PropertyMe session.
It opens a real browser window so you can log in and complete 2FA.
The session is saved to session.json and loaded by the main automation script.

Usage:
    python3 refresh_session.py
"""

import asyncio
from playwright.async_api import async_playwright

SESSION_FILE = "session.json"
LOGIN_URL = "https://app.propertyme.com"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        context = await browser.new_context()
        page = await context.new_page()

        print(f"Opening {LOGIN_URL} ...")
        print("Log in with your email, password, and 2FA code.")
        print("Once you are fully logged in and see the dashboard, press Enter here.")

        await page.goto(LOGIN_URL)

        input("\nPress Enter once you have fully logged in > ")

        await context.storage_state(path=SESSION_FILE)
        print(f"\nSession saved to {SESSION_FILE}.")
        print("This session should last ~7 days before 2FA is required again.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
