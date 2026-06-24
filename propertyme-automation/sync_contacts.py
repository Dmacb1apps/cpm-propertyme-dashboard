#!/usr/bin/env python3
"""
CPM Contact Sync
================
Downloads Contact Details reports from PropertyMe (Tenant, Owner, Supplier),
parses them, and syncs to Google Contacts daily.

Required GitHub Secrets:
  PROPERTYME_EMAIL
  PROPERTYME_PASSWORD
  PROPERTYME_TOTP_SECRET
  GOOGLE_CONTACTS_CLIENT_ID
  GOOGLE_CONTACTS_CLIENT_SECRET
  GOOGLE_CONTACTS_REFRESH_TOKEN

Required packages (add to workflow pip install step):
  playwright openpyxl google-api-python-client google-auth pyotp

Set DEBUG_SCREENSHOTS=1 in the environment to capture screenshots
on each step — useful when troubleshooting Playwright navigation.
"""

import os
import re
import time
import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict

import pyotp
import openpyxl  # NOTE: use data_only=True but NOT read_only=True — PropertyMe's
                 # xlsx exports omit the dimension record, which causes read_only
                 # mode to report max_row=1 and return only the header row.
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
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
PM_EMAIL    = os.environ['PROPERTYME_EMAIL']
PM_PASSWORD = os.environ['PROPERTYME_PASSWORD']
PM_TOTP     = os.environ['PROPERTYME_TOTP_SECRET']
GC_CLIENT_ID     = os.environ['GOOGLE_CONTACTS_CLIENT_ID']
GC_CLIENT_SECRET = os.environ['GOOGLE_CONTACTS_CLIENT_SECRET']
GC_REFRESH_TOKEN = os.environ['GOOGLE_CONTACTS_REFRESH_TOKEN']

DOWNLOAD_DIR = Path('/tmp/cpx_contacts')
DEBUG        = os.environ.get('DEBUG_SCREENSHOTS') == '1'

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

# Corporate suffixes to strip from owner/supplier names.
# Order matters: longest/most specific must come first.
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
    contact_type: str       # 'tenant' | 'owner' | 'supplier'
    display_name: str       # final formatted name shown in Google Contacts
    first_name: str
    last_name: str
    mobile: Optional[str]   # normalised 10-digit number or None
    email: Optional[str]
    ref_code: Optional[str] # '01.02' for tenant/owner; None for most suppliers

    @property
    def cpx_id(self) -> str:
        """
        Stable unique ID used to match contacts across sync runs.
        Stored in Google Contacts as an externalId of type CPM_ID.
        """
        t = self.contact_type[0].upper()
        if self.ref_code:
            fn = re.sub(r'\s+', '-', self.first_name.lower().strip())
            ln = re.sub(r'\s+', '-', self.last_name.lower().strip())
            return f"CPM-{t}-{self.ref_code}-{fn}-{ln}"
        slug = re.sub(r'[^a-z0-9]+', '-', self.display_name.lower())
        return f"CPM-S-{slug[:60]}"


# ── Phone normalisation ──────────────────────────────────────────────────────────
def normalise_phone(raw) -> Optional[str]:
    """
    Returns a 10-digit Australian number or None.
    Handles spaces, hyphens, international +61 format.
    """
    if not raw:
        return None
    s = str(raw).strip()
    if not s or s.isspace():
        return None
    s = re.sub(r'[\s\-\(\)\.]', '', s)
    if s.startswith('+61'):
        s = '0' + s[3:]
    return s if re.fullmatch(r'0\d{9}', s) else None


# ── Company name stripping ────────────────────────────────────────────────────────
def strip_corporate(name: str) -> str:
    """
    Remove corporate identifiers from a name field.
    'V & T Scarso Pty Ltd ABN 23...'          → 'V & T Scarso'
    'Michael O Dell Property Pty Ltd ACN 643' → 'Michael O Dell Property'
    """
    for kw in COMPANY_STRIP:
        idx = name.find(kw)
        if idx > 0:
            name = name[:idx].strip().rstrip('&').rstrip('-').strip()
            break
    return name


# ── Display name builder ─────────────────────────────────────────────────────────
def build_display_name(
    first: str,
    last: str,
    ref_code: Optional[str],
    business_header: Optional[str],
    contact_type: str,
) -> str:
    """
    Build the contact name as it will appear on iPhone caller ID.

    Tenants:  'Queenie Coombes T01.02'
    Owners:   'Mahzabin Anindita O01.02'
    Suppliers (person + business): 'Aaron Werner - AKI Electrical (CPM)'
    Suppliers (business only):     'ABC Locksmiths (CPM)'
    """
    t    = {'tenant': 'T', 'owner': 'O', 'supplier': 'S'}[contact_type]
    full = ' '.join(p for p in [first, last] if p).strip()

    if contact_type == 'supplier':
        if not business_header:
            return f"{full} (CPM)" if full else "(CPM Supplier)"

        # Edge case: supplier with a numeric ref (e.g. '12.12 Colin & Michele Cramp')
        m = re.match(r'^(\d{2}\.\d{2})\s+(.*)', business_header)
        if m:
            biz = m.group(2).strip()
            if full and full.lower() not in biz.lower():
                return f"{full} - {biz} (CPM)"
            return f"{(full or biz)} (CPM)"

        # Normal supplier
        if full and full.lower() not in business_header.lower():
            return f"{full} - {business_header} (CPM)"
        elif business_header:
            return f"{business_header} (CPM)"
        return f"{full} (CPM)"

    # Tenant or Owner
    suffix = f"{t}{ref_code}" if ref_code else f"({t})"
    return f"{full} {suffix}" if full else suffix


# ── Excel Parsing ─────────────────────────────────────────────────────────────────
def parse_report(filepath: Path, contact_type: str) -> List[CPMContact]:
    """
    Parse a PropertyMe Contact Details Excel report.

    The file has a two-level structure:
      Group header row:  col A has '{ref} {names}', all other cols are empty.
      Individual rows:   col A is empty, cols B-E have first, last, mobile, email.

    For suppliers, the group header is the business name (no numeric ref code).
    """
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active

    contacts:         List[CPMContact] = []
    current_ref:      Optional[str]    = None
    current_business: Optional[str]    = None
    header_seen                        = False

    for row in ws.iter_rows(values_only=True):

        # Locate and skip the column header row (First Name, Last Name…)
        if not header_seen:
            if row and row[1] == 'First Name':
                header_seen = True
            continue

        col_a      = str(row[0]).strip() if row[0] not in (None, '') else ''
        first_raw  = str(row[1]).strip() if row[1] not in (None, '') else ''
        last_raw   = str(row[2]).strip() if row[2] not in (None, '') else ''
        mobile_raw = row[3]
        email_raw  = str(row[4]).strip() if row[4] not in (None, '') else ''

        # ── Group header: col A has content, First Name is empty ──────────────
        if col_a and not first_raw:
            ref_m = re.match(r'^(\d{2}\.\d{2})', col_a)
            if ref_m:
                current_ref      = ref_m.group(1)
                current_business = None
            else:
                current_ref      = None
                current_business = col_a
            continue

        # Skip entirely blank rows
        if not first_raw and not last_raw:
            continue

        # Strip corporate suffixes from name fields
        first = strip_corporate(first_raw)
        last  = strip_corporate(last_raw)

        # Handle: company name landed entirely in last_name column, first_name blank
        if not first and last:
            first = strip_corporate(last)
            last  = ''

        mobile = normalise_phone(mobile_raw)
        email  = email_raw if '@' in email_raw else None

        display = build_display_name(
            first, last, current_ref, current_business, contact_type
        )

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


# ── PropertyMe Download ───────────────────────────────────────────────────────────
async def download_contact_reports() -> Dict[str, Path]:
    """
    Log in to PropertyMe and download the three Contact Details reports as Excel.
    Returns dict mapping contact_type → local file path.

    NOTE: The Playwright selectors below use text-based matching for stability.
    If navigation fails on first run, set DEBUG_SCREENSHOTS=1 and check the
    captured images in /tmp/ to identify the correct element text/structure.
    """
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    downloaded: Dict[str, Path] = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx     = await browser.new_context(accept_downloads=True)
        page    = await ctx.new_page()

        try:
            # ── Login ──────────────────────────────────────────────────────────
            log.info("Logging in to PropertyMe...")
            await page.goto('https://app.propertyme.com', wait_until='domcontentloaded')
            await page.wait_for_timeout(2000)

            await page.locator('input[type="email"], input[name="email"]').first.fill(PM_EMAIL)
            await page.locator('input[type="password"], input[name="password"]').first.fill(PM_PASSWORD)
            await page.locator('button[type="submit"]').first.click()
            await page.wait_for_timeout(2500)

            # Handle TOTP 2FA if prompted
            totp_input = page.locator(
                'input[placeholder*="code" i], input[name*="code" i], '
                'input[name*="otp" i], input[placeholder*="verification" i]'
            )
            if await totp_input.count() > 0:
                log.info("Entering TOTP code...")
                totp_code = pyotp.TOTP(PM_TOTP).now()
                await totp_input.first.fill(totp_code)
                await page.locator('button[type="submit"]').first.click()
                await page.wait_for_load_state('networkidle')

            if DEBUG:
                await page.screenshot(path='/tmp/pm_post_login.png', full_page=True)

            log.info("Logged in successfully.")

            # ── Download each of the three reports ─────────────────────────────
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

    ⚠️  These selectors are based on PropertyMe's report UI as understood at
    time of writing. If any step fails, enable DEBUG_SCREENSHOTS=1 and inspect
    the saved /tmp/ images to find the correct text or element to target.

    PropertyMe navigation path:
      Main nav → Reports → Contacts category → {report_name} → Generate → Export Excel
    """

    # Navigate to the Reports section
    await page.goto('https://app.propertyme.com/reports', wait_until='domcontentloaded')
    await page.wait_for_timeout(2500)

    if DEBUG:
        await page.screenshot(path=f'/tmp/pm_reports_{contact_type}.png', full_page=True)

    # Find and click the report — try exact match first, then partial
    report_link = page.get_by_text(report_name, exact=True)
    if await report_link.count() == 0:
        report_link = page.get_by_text(report_name)
    if await report_link.count() == 0:
        # Fallback: try the short form without the dash
        short = report_name.replace(' - ', ' ')
        report_link = page.get_by_text(short)

    if await report_link.count() == 0:
        raise RuntimeError(
            f"Report '{report_name}' not found on the Reports page. "
            f"Set DEBUG_SCREENSHOTS=1 and check /tmp/pm_reports_{contact_type}.png "
            f"to see what's on screen."
        )

    await report_link.first.click()
    await page.wait_for_load_state('domcontentloaded')
    await page.wait_for_timeout(2000)

    if DEBUG:
        await page.screenshot(path=f'/tmp/pm_report_open_{contact_type}.png', full_page=True)

    # Click Generate / Run if required
    for btn_text in ['Generate', 'Run Report', 'Run', 'Search']:
        btn = page.get_by_role('button', name=btn_text)
        if await btn.count() > 0:
            log.info(f"  Clicking '{btn_text}'...")
            await btn.first.click()
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(2500)
            break

    if DEBUG:
        await page.screenshot(path=f'/tmp/pm_report_generated_{contact_type}.png', full_page=True)

    # Download as Excel
    xlsx_path = DOWNLOAD_DIR / f"{contact_type}_contacts.xlsx"

    for btn_text in ['Export to Excel', 'Excel', 'Export', 'Download']:
        btn = page.get_by_role('button', name=btn_text)
        if await btn.count() == 0:
            btn = page.get_by_text(btn_text, exact=True)
        if await btn.count() > 0:
            log.info(f"  Clicking '{btn_text}' to download...")
            async with page.expect_download(timeout=30_000) as dl_info:
                await btn.first.click()
            dl = await dl_info.value
            await dl.save_as(xlsx_path)
            log.info(f"  Saved to {xlsx_path}")
            return xlsx_path

    raise RuntimeError(
        f"No download button found for '{report_name}'. "
        f"Tried: 'Export to Excel', 'Excel', 'Export', 'Download'. "
        f"Set DEBUG_SCREENSHOTS=1 and check /tmp/pm_report_generated_{contact_type}.png."
    )


# ── Google Contacts Sync ──────────────────────────────────────────────────────────
def get_google_service():
    """Authenticate to the People API using the stored refresh token."""
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
    """Return the resourceName of a Google contact group, creating it if missing."""
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
    """
    Return all Google contacts that carry a CPM_ID externalId.
    Dict key is the cpx_id string; value is the full person dict from the API.
    Only touches contacts CPM created — never personal contacts.
    """
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
    """Build the request body for a People API create or update call."""
    body: dict = {
        'names': [{
            'displayName': contact.display_name,
            'givenName':   contact.first_name or contact.display_name,
            'familyName':  contact.last_name or '',
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
    """Return True if the Google contact differs from the current CPM data."""
    # Check display name
    current_display = ''
    for n in existing_person.get('names', []):
        if n.get('metadata', {}).get('primary'):
            current_display = n.get('displayName', '')
            break
    if current_display != contact.display_name:
        return True

    # Check mobile
    google_mobiles = {p['value'] for p in existing_person.get('phoneNumbers', [])}
    if contact.mobile and contact.mobile not in google_mobiles:
        return True

    # Check email
    google_emails = {e['value'].lower() for e in existing_person.get('emailAddresses', [])}
    if contact.email and contact.email.lower() not in google_emails:
        return True

    return False


def _api_pause():
    """Stay within the People API rate limit of 90 requests/minute."""
    time.sleep(0.7)


def sync_to_google_contacts(contacts: List[CPMContact]):
    """
    Full create/update/delete sync.

    - Creates contacts that don't exist in Google yet.
    - Updates contacts whose name, mobile, or email has changed.
    - Deletes contacts that are no longer in the PropertyMe reports
      (i.e. they've been archived). Only ever touches CPM_ID-tagged contacts.
    """
    service = get_google_service()

    # Ensure all three contact groups exist
    group_resources = {
        ct: get_or_create_group(service, label)
        for ct, label in GROUP_LABELS.items()
    }

    existing    = fetch_existing_cpx_contacts(service)
    current_ids = {c.cpx_id for c in contacts}
    created = updated = deleted = skipped = 0

    # ── Create or update ─────────────────────────────────────────────────────────
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

    # ── Delete archived contacts ──────────────────────────────────────────────────
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

    # 1. Download reports from PropertyMe
    log.info("Step 1: Downloading contact reports from PropertyMe...")
    report_files = await download_contact_reports()

    # 2. Parse all three reports
    log.info("Step 2: Parsing reports...")
    all_contacts: List[CPMContact] = []
    for contact_type, filepath in report_files.items():
        all_contacts.extend(parse_report(filepath, contact_type))

    log.info(f"Total contacts to sync: {len(all_contacts)}")

    # 3. Sync to Google Contacts
    log.info("Step 3: Syncing to Google Contacts...")
    sync_to_google_contacts(all_contacts)

    log.info("=== CPM Contact Sync complete ===")


if __name__ == '__main__':
    asyncio.run(main())
