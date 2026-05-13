"""
Debug script: logs all network responses and download/popup events
after clicking Export Excel on the Monthly Rent report.
Run this once to see how PropertyMe triggers the file download.

Usage:
    python3 debug_export.py
"""

from playwright.sync_api import sync_playwright

SESSION_FILE = "session.json"
BASE_URL = "https://manager.propertyme.com/#/"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=SESSION_FILE, accept_downloads=True)

        # Catch downloads on any page in the context
        context.on("page", lambda pg: (
            pg.on("download", lambda d: print(f"[DOWNLOAD on new page] {d.suggested_filename} url={d.url}")),
            pg.on("response", lambda r: print(f"[RESPONSE on new page] {r.status} {r.url[:80]} ct={r.headers.get('content-type','')[:60]}")),
        ))

        page = context.new_page()
        page.on("download", lambda d: print(f"[DOWNLOAD on main page] {d.suggested_filename} url={d.url}"))

        page.goto(BASE_URL)
        page.wait_for_load_state("domcontentloaded")
        page.locator("[data-test-id='reports-menu']").wait_for(state="visible", timeout=15000)
        page.locator("[data-test-id='reports-menu']").click()
        page.wait_for_timeout(500)
        page.get_by_role("tab", name="Custom").click()

        with page.expect_popup() as popup_info:
            page.get_by_role("link", name="Monthly Property/Rent").click()
        report = popup_info.value
        report.wait_for_load_state("domcontentloaded")

        report.on("download", lambda d: print(f"[DOWNLOAD on report page] {d.suggested_filename} url={d.url}"))

        export_clicked = {"done": False}

        def log_response(r):
            url = r.url
            ct = r.headers.get("content-type", "")
            is_json = "json" in ct
            print(f"[RESPONSE] {r.status} {url} ct={ct[:60]}")
            if not export_clicked["done"]:
                return
            if is_json:
                try:
                    body = r.body()
                    safe_name = url.split("/")[-1].split("?")[0][:40]
                    fname = f"debug_{safe_name}.json"
                    with open(fname, "wb") as f:
                        f.write(body)
                    print(f"  ^ Saved {len(body)} bytes -> {fname}")
                except Exception as e:
                    print(f"  ^ Could not read body: {e}")

        report.on("response", log_response)

        print("\n--- Clicking Export button ---")
        report.get_by_role("button", name="Export").click()
        report.get_by_role("link", name="Export Excel").wait_for(state="visible", timeout=10000)

        print("--- Clicking Export Excel ---")
        report.get_by_role("link", name="Export Excel").click()

        print("--- Waiting 10s for any events ---")
        report.wait_for_timeout(10000)

        print("\n--- Done. Check output above for DOWNLOAD or RESPONSE lines. ---")
        input("Press Enter to close the browser > ")
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
