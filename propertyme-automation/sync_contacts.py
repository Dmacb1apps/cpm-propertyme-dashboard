#!/usr/bin/env python3
"""
CPM Contact Sync
================
Downloads Contact Details reports from PropertyMe (Tenant, Owner, Supplier),
parses them, and syncs to Google Contacts daily.

Required GitHub Secrets:
  PROPERTYME_COOKIES
  GOOGLE_CONTACTS_CLIENT_ID
  GOOGLE_CONTACTS_CLIENT_SECRET
  GOOGLE_CONTACTS_REFRESH_TOKEN

Required packages (in requirements.txt):
  playwright openpyxl google-api-python-client google-auth

Set DEBUG_SCREENSHOTS=1 to capture screenshots at each navigation step.
"""

import os
import re
import time
import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict

import json
import openpyxl  # NOTE: use data_only=True but NOT read_only=True — PropertyMe's
                 # xlsx exports omit the dimension record, which causes read_only
                 # mode to report max_row=1 and return only the header row.
from playwright.async_api import async_playwright
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ── Logging ─────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────────
GC_CLIENT_ID     = os.environ['GOOGLE_CONTACTS_CLIENT_ID']
GC_CLIENT_SECRET = os.environ['GOOGLE_CONTACTS_CLIENT_SECRET']
GC_REFRESH_TOKEN = os.environ['GOOGLE_CONTACTS_REFRESH_TOKEN']

DOWNLOAD_DIR = Path('/tmp/cpx_contacts')
DEBUG        = os.environ.get('DEBUG_SCREENSHOTS') == '1'
MANAGER_URL  = 'https://manager.propertyme.com'

REPORT_NAMES = {
    'tenant':   'Contact Details - Tenant',
    'owner':    'Contact Details - Owner',
    'supplier': 'Contact Details - Supplier',
}

GROUP_LABELS = {
    'tenant':   'CPM Tenants',
    'owner':    'CPM Owners',
    'supplier': 'CPM Suppliers',
}

COMPANY_STRIP = [
    'Pty. Ltd.', 'Pty Ltd', 'PTY LTD', 'P/L',
    'as Trustee for', 'as Trustee',
    'ACN ', 'ABN ',
    ' Trust', ' Pty', ' Ltd',
]

SCOPES = ['https://www.googleapis.com/auth/contacts']


# ── Data model ───────────────────────────────────────────────────────────────────
@dataclass
class CPMContact:
    contact_type: str
    display_name: str
    first_name: str
    last_name: str
    mobile: Optional[str]
    email: Optional[str]
    ref_code: Optional[str]

    @property
    def cpx_id(self) -> str:
        t = self.contact_type[0].upper()
        if self.ref_code:
            fn = re.sub(r'\s+', '-', self.first_name.lower().strip())
            ln = re.sub(r'\s+', '-', self.last_name.lower().strip())
            return f"CPM-{t}-{self.ref_code}-{fn}-{ln}"
        slug = re.sub(r'[^a-z0-9]+', '-', self.display_name.lower())
        return f"CPM-S-{slug[:60]}"


# ── Utilities ────────────────────────────────────────────────────────────────────
def normalise_phone(raw) -> Optional[str]:
    if not raw:
        return None
    s = str(raw).strip()
    if not s or s.isspace():
        return None
    s = re.sub(r'[\s\-\(\)\.]', '', s)
    if s.startswith('+61'):
        s = '0' + s[3:]
    return s if re.fullmatch(r'0\d{9}', s) else None


def strip_corporate(name: str) -> str:
    for kw in COMPANY_STRIP:
        idx = name.find(kw)
        if idx > 0:
            name = name[:idx].strip().rstrip('&').rstrip('-').strip()
            break
    return name


def build_display_name(first, last, ref_code, business_header, contact_type) -> str:
    t    = {'tenant': 'T', 'owner': 'O', 'supplier': 'S'}[contact_type]
    full = ' '.join(p for p in [first, last] if p).strip()

    if contact_type == 'supplier':
        if not business_header:
            return f"{full} (CPM)" if full else "(CPM Supplier)"
        m = re.match(r'^(\d{2}\.\d{2})\s+(.*)', business_header)
        if m:
            biz = m.group(2).strip()
            if full and full.lower() not in biz.lower():
                return f"{full} - {biz} (CPM)"
            return f"{(full or biz)} (CPM)"
        if full and full.lower() not in business_header.lower():
            return f"{full} - {business_header} (CPM)"
        elif business_header:
            return f"{business_header} (CPM)"
        return f"{full} (CPM)"

    suffix = f"{t}{ref_code}" if ref_code else f"({t})"
    return f"{full} {suffix}" if full else suffix


# ── Excel Parsing ─────────────────────────────────────────────────────────────────
def parse_report(filepath: Path, contact_type: str) -> List[CPMContact]:
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active

    contacts:         List[CPMContact] = []
    current_ref:      Optional[str]    = None
    current_business: Optional[str]    = None
    header_seen                        = False

    for row in ws.iter_rows(values_only=True):
        if not header_seen:
            if row and row[1] == 'First Name':
                header_seen = True
            continue

        col_a      = str(row[0]).strip() if row[0] not in (None, '') else ''
        first_raw  = str(row[1]).strip() if row[1] not in (None, '') else ''
        last_raw   = str(row[2]).strip() if row[2] not in (None, '') else ''
        mobile_raw = row[3]
        email_raw  = str(row[4]).strip() if row[4] not in (None, '') else ''

        if col_a and not first_raw:
            ref_m = re.match(r'^(\d{2}\.\d{2})', col_a)
            if ref_m:
                current_ref = ref_m.group(1); current_business = None
            else:
                current_ref = None; current_business = col_a
            continue

        if not first_raw and not last_raw:
            continue

        first = strip_corporate(first_raw)
        last  = strip_corporate(last_raw)
        if not first and last:
            first = strip_corporate(last); last = ''

        mobile = normalise_phone(mobile_raw)
        email  = email_raw if '@' in email_raw else None
        display = build_display_name(first, last, current_ref, current_business, contact_type)

        contacts.append(CPMContact(
            contact_type=contact_type,
            display_name=display,
            first_name=first,
            last_name=last,
            mobile=mobile,
            email=email,
            ref_code=current_ref,
        ))

    wb.close()
    log.info(f"Parsed {len(contacts)} {contact_type} contacts from {filepath.name}")
    return contacts


# ── PropertyMe Login ──────────────────────────────────────────────────────────────
async def login(context, page):
    """
    Load stored PropertyMe session cookies and navigate to the dashboard.

    Replaces the old email/password/TOTP login flow, which is blocked by
    Cloudflare Turnstile in headless browsers.

    Requires PROPERTYME_COOKIES env var (JSON array of cookie dicts).
    Run extract_cookies.py locally to generate it, store as a GitHub secret.
    Renew roughly monthly.
    """
    cookies_raw = os.environ.get("PROPERTYME_COOKIES")
    if not cookies_raw:
        raise RuntimeError(
            "PROPERTYME_COOKIES is not set. "
            "Run extract_cookies.py locally and store the output as a GitHub secret."
        )

    try:
        cookies = json.loads(cookies_raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"PROPERTYME_COOKIES is not valid JSON: {exc}") from exc

    log.info(f"  Loading {len(cookies)} cookies into browser context...")
    await context.add_cookies(cookies)

    log.info(f"  Navigating to {MANAGER_URL}...")
    await page.goto(MANAGER_URL)
    try:
        await page.wait_for_load_state('networkidle', timeout=20000)
    except Exception:
        await page.wait_for_load_state('domcontentloaded')

    await page.wait_for_timeout(3000)
    current_url = page.url
    log.info(f"  Landed on: {current_url}")

    if 'id.propertyme.com' in current_url:
        if DEBUG:
            await page.screenshot(path='/tmp/pm_session_expired.png', full_page=True)
        raise RuntimeError(
            "PropertyMe session cookies have expired — redirected to login. "
            "Run extract_cookies.py locally and update the PROPERTYME_COOKIES GitHub secret."
        )

    log.info(f"  Session valid — current URL: {current_url}")

    if DEBUG:
        await page.screenshot(path='/tmp/pm_post_login.png', full_page=True)


# ── PropertyMe Report Download ────────────────────────────────────────────────────
async def download_contact_reports() -> Dict[str, Path]:
    """
    Log in to PropertyMe and download the three Contact Details reports as Excel.
    Returns dict mapping contact_type to local file path.
    """
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    downloaded: Dict[str, Path] = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx     = await browser.new_context(accept_downloads=True)
        page    = await ctx.new_page()

        try:
            await login(ctx, page)

            for contact_type, report_name in REPORT_NAMES.items():
                log.info(f"Downloading '{report_name}'...")
                filepath = await _download_single_report(page, contact_type, report_name)
                downloaded[contact_type] = filepath

        finally:
            await browser.close()

    return downloaded


async def _download_single_report(page, contact_type: str, report_name: str) -> Path:
    """
    Navigate to a Contact Details report and download as Excel.

    PropertyMe navigation: Dashboard -> click Reports in left sidebar ->
    find report by name -> Generate -> Export Excel

    If this step fails, set DEBUG_SCREENSHOTS=1 and check /tmp/ images to see
    what's on screen and adjust selectors accordingly.
    """
    # Navigate to dashboard first, then click Reports in the left sidebar.
    # PropertyMe uses hash-based routing so /reports is a dead URL.
    await page.goto(MANAGER_URL, wait_until='domcontentloaded')
    await page.wait_for_timeout(2000)

    # Click Reports in the left nav sidebar
    reports_nav = page.locator("a:has-text('Reports'), [href*='report' i]").first
    try:
        await reports_nav.wait_for(state='visible', timeout=10000)
        await reports_nav.click()
    except Exception:
        # Fallback: try by role
        await page.get_by_role('link', name='Reports').click()

    try:
        await page.wait_for_load_state('networkidle', timeout=15000)
    except Exception:
        await page.wait_for_load_state('domcontentloaded')
    await page.wait_for_timeout(2500)

    if DEBUG:
        await page.screenshot(path=f'/tmp/pm_reports_{contact_type}.png', full_page=True)

    # Find report by text
    report_link = page.get_by_text(report_name, exact=True)
    if await report_link.count() == 0:
        report_link = page.get_by_text(report_name)
    if await report_link.count() == 0:
        raise RuntimeError(
            f"Report '{report_name}' not found on the reports page. "
            f"Set DEBUG_SCREENSHOTS=1 and check /tmp/pm_reports_{contact_type}.png."
        )

    # Report links open in a popup window — wrap click in expect_popup
    async with page.expect_popup() as popup_info:
        await report_link.first.click()
    report = await popup_info.value

    try:
        await report.wait_for_load_state('networkidle', timeout=15000)
    except Exception:
        await report.wait_for_load_state('domcontentloaded')
    await report.wait_for_timeout(2000)

    if DEBUG:
        await report.screenshot(path=f'/tmp/pm_report_open_{contact_type}.png', full_page=True)

    # Click Generate / Run if required
    for btn_text in ['Generate', 'Run Report', 'Run', 'Search']:
        btn = report.get_by_role('button', name=btn_text)
        if await btn.count() > 0:
            log.info(f"  Clicking '{btn_text}'...")
            await btn.first.click()
            try:
                await report.wait_for_load_state('networkidle', timeout=15000)
            except Exception:
                pass
            await report.wait_for_timeout(2500)
            break

    if DEBUG:
        await report.screenshot(path=f'/tmp/pm_report_generated_{contact_type}.png', full_page=True)

    # Download as Excel.
    # Export button opens a dropdown — click Export first, then Export Excel from the dropdown.
    # Both clicks must be inside the same expect_download context.
    xlsx_path = DOWNLOAD_DIR / f"{contact_type}_contacts.xlsx"

    export_btn = report.locator("button:has-text('Export'), a:has-text('Export')")
    try:
        await export_btn.first.wait_for(state='visible', timeout=10000)
    except Exception:
        await report.close()
        raise RuntimeError(
            f"No Export button found for '{report_name}'. "
            f"Set DEBUG_SCREENSHOTS=1 and check /tmp/pm_report_generated_{contact_type}.png."
        )

    log.info("  Clicking 'Export' to open dropdown...")
    async with report.expect_download(timeout=30_000) as dl_info:
        await export_btn.first.click()
        # Wait for dropdown to appear then click Export Excel
        await report.wait_for_timeout(500)
        for excel_text in ['Export Excel', 'Excel', 'Export to Excel']:
            excel_opt = report.get_by_text(excel_text, exact=True)
            if await excel_opt.count() > 0:
                log.info(f"  Clicking '{excel_text}'...")
                await excel_opt.first.click()
                break

    dl = await dl_info.value
    await dl.save_as(xlsx_path)
    log.info(f"  Saved to {xlsx_path}")
    await report.close()
    return xlsx_path


# ── Google Contacts Sync ──────────────────────────────────────────────────────────
def get_google_service():
    creds = Credentials(
        token=None,
        refresh_token=GC_REFRESH_TOKEN,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=GC_CLIENT_ID,
        client_secret=GC_CLIENT_SECRET,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build('people', 'v1', credentials=creds)


def get_or_create_group(service, name: str) -> str:
    groups = service.contactGroups().list().execute().get('contactGroups', [])
    for g in groups:
        if g.get('name') == name:
            return g['resourceName']
    result = service.contactGroups().create(
        body={'contactGroup': {'name': name}}
    ).execute()
    log.info(f"Created contact group: {name}")
    return result['resourceName']


def fetch_existing_cpx_contacts(service) -> Dict[str, dict]:
    existing: Dict[str, dict] = {}
    page_token = None

    while True:
        kwargs = dict(
            resourceName='people/me',
            pageSize=1000,
            personFields='names,phoneNumbers,emailAddresses,externalIds,memberships,metadata',
        )
        if page_token:
            kwargs['pageToken'] = page_token

        resp = service.people().connections().list(**kwargs).execute()

        for person in resp.get('connections', []):
            for ext in person.get('externalIds', []):
                if ext.get('type') == 'CPM_ID':
                    existing[ext['value']] = person
                    break

        page_token = resp.get('nextPageToken')
        if not page_token:
            break

    log.info(f"Found {len(existing)} existing CPM contacts in Google")
    return existing


def _person_body(contact: CPMContact, group_resource: str) -> dict:
    # iOS reconstructs the displayed name from givenName + familyName,
    # ignoring displayName entirely. To ensure the suffix (T01.02, O01.02)
    # appears on the phone, put the full display_name into givenName and
    # leave familyName empty.
    body: dict = {
        'names': [{
            'displayName': contact.display_name,
            'givenName':   contact.display_name,
            'familyName':  '',
        }],
        'externalIds': [{'value': contact.cpx_id, 'type': 'CPM_ID'}],
        'memberships': [{'contactGroupMembership': {'contactGroupResourceName': group_resource}}],
    }
    if contact.mobile:
        body['phoneNumbers'] = [{'value': contact.mobile, 'type': 'mobile'}]
    if contact.email:
        body['emailAddresses'] = [{'value': contact.email, 'type': 'work'}]
    return body


def _needs_update(existing_person: dict, contact: CPMContact) -> bool:
    current_display = ''
    for n in existing_person.get('names', []):
        if n.get('metadata', {}).get('primary'):
            current_display = n.get('displayName', '')
            break
    if current_display != contact.display_name:
        return True
    google_mobiles = {p['value'] for p in existing_person.get('phoneNumbers', [])}
    if contact.mobile and contact.mobile not in google_mobiles:
        return True
    google_emails = {e['value'].lower() for e in existing_person.get('emailAddresses', [])}
    if contact.email and contact.email.lower() not in google_emails:
        return True
    return False


def _api_pause():
    time.sleep(0.7)


def sync_to_google_contacts(contacts: List[CPMContact]):
    service = get_google_service()

    group_resources = {
        ct: get_or_create_group(service, label)
        for ct, label in GROUP_LABELS.items()
    }

    existing    = fetch_existing_cpx_contacts(service)
    current_ids = {c.cpx_id for c in contacts}
    created = updated = deleted = skipped = 0

    for contact in contacts:
        group_res = group_resources[contact.contact_type]

        if contact.cpx_id in existing:
            if _needs_update(existing[contact.cpx_id], contact):
                person        = existing[contact.cpx_id]
                resource_name = person['resourceName']
                etag          = person.get('etag', '')
                body          = _person_body(contact, group_res)
                body['etag']  = etag
                try:
                    service.people().updateContact(
                        resourceName=resource_name,
                        updatePersonFields='names,phoneNumbers,emailAddresses,externalIds,memberships',
                        body=body,
                    ).execute()
                    updated += 1
                    _api_pause()
                except HttpError as e:
                    log.warning(f"Update failed for {contact.display_name}: {e}")
            else:
                skipped += 1
        else:
            body = _person_body(contact, group_res)
            try:
                service.people().createContact(body=body).execute()
                created += 1
                _api_pause()
            except HttpError as e:
                log.warning(f"Create failed for {contact.display_name}: {e}")

    for cpx_id, person in existing.items():
        if cpx_id not in current_ids:
            try:
                service.people().deleteContact(
                    resourceName=person['resourceName']
                ).execute()
                deleted += 1
                log.info(f"Deleted archived contact: {cpx_id}")
                _api_pause()
            except HttpError as e:
                log.warning(f"Delete failed for {cpx_id}: {e}")

    log.info(
        f"Sync complete — "
        f"created: {created}  updated: {updated}  "
        f"deleted: {deleted}  unchanged: {skipped}"
    )


# ── Main ──────────────────────────────────────────────────────────────────────────
async def main():
    log.info("=== CPM Contact Sync starting ===")

    log.info("Step 1: Downloading contact reports from PropertyMe...")
    report_files = await download_contact_reports()

    log.info("Step 2: Parsing reports...")
    all_contacts: List[CPMContact] = []
    for contact_type, filepath in report_files.items():
        all_contacts.extend(parse_report(filepath, contact_type))

    log.info(f"Total contacts to sync: {len(all_contacts)}")

    log.info("Step 3: Syncing to Google Contacts...")
    sync_to_google_contacts(all_contacts)

    log.info("=== CPM Contact Sync complete ===")


if __name__ == '__main__':
    asyncio.run(main())
