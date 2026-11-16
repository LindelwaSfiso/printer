"""Capture the presentation screenshots with Playwright.

    .venv\\Scripts\\python.exe manage.py runserver          # terminal 1
    .venv\\Scripts\\python.exe tools\\capture_screens.py    # terminal 2

Writes docs/screenshots/01-…png … 14-…png and 15-ledger-check.txt.

Install once, if you have not:

    .venv\\Scripts\\python.exe -m pip install playwright
    .venv\\Scripts\\python.exe -m playwright install chromium

That second command downloads a browser (~130 MB). You can skip it: the script
falls back to the Edge or Chrome already installed on this machine, which is why
it tries `channel="msedge"` and `channel="chrome"` before the bundled one.

Why Playwright rather than headless Chrome on the command line: it signs in
through the real login form (so the screenshots prove the login works), waits for
the page to settle instead of guessing a delay, and captures full-page images
without a hand-tuned window height per screen.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")

OUT = ROOT / "docs" / "screenshots"
BASE = os.environ.get("SCREENSHOT_URL", "http://127.0.0.1:8000")
ADMIN_NO = os.environ.get("SCREENSHOT_ADMIN", "ADMIN001")
MEMBER_NO = os.environ.get("SCREENSHOT_MEMBER", "202202881")
PASSWORD = os.environ.get("SCREENSHOT_PASSWORD", "esprints123")
VIEWPORT = {"width": 1440, "height": 900}
SCALE = 2                      # crisp on a projector; PNGs stay under ~800 KB

CHANNELS = ["msedge", "chrome", None]      # None = Playwright's own Chromium


# --------------------------------------------------------------------------- #
# Django side: build the states the screenshots need
# --------------------------------------------------------------------------- #
def setup_django():
    import django
    django.setup()


def demo_pdf(pages=4):
    from io import BytesIO

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    for number in range(1, pages + 1):
        pdf.setFont("Helvetica-Bold", 24)
        pdf.drawString(60, 700, "ESprints — demonstration document")
        pdf.setFont("Helvetica", 12)
        pdf.drawString(60, 665, f"Page {number} of {pages}")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(60, 640, "Generated for the progress presentation.")
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def seed_state():
    """Create a priced job, a printed job, a failed job and a submitted invoice."""
    from django.contrib.auth import get_user_model

    from apps.billing import services as billing
    from apps.billing.models import Invoice
    from apps.credits.services import ensure_account, post_entry
    from apps.printing import services as printing
    from apps.printing.models import PrintJob
    from django.core.files.uploadedfile import SimpleUploadedFile

    User = get_user_model()
    member = User.objects.filter(student_no=MEMBER_NO).first()
    if member is None:
        raise SystemExit(f"No member {MEMBER_NO}. Run: manage.py seed_demo")

    account = ensure_account(member)
    if account.available_credits < 400:
        post_entry(account_id=account.id, delta_credits=500, kind="ADJUSTMENT",
                   reference=f"screens:{member.pk}:{int(time.time())}",
                   memo="Screenshot demo credit")

    def make(pages, sides="DUPLEX"):
        upload = SimpleUploadedFile("Project-proposal.pdf", demo_pdf(pages),
                                    content_type="application/pdf")
        return printing.create_draft(
            member=member, uploaded=upload,
            cleaned={"page_count": pages, "copies": 1, "colour_mode": "MONO",
                     "sides": sides, "paper": "A4"})

    # Clear anything left queued by earlier runs, so the job we choose to print
    # below is unambiguously the next one in line.
    printing.process_all(limit=50)

    priced = make(4)                                    # shot 04, still a draft

    to_print = make(6)
    printing.confirm_job(to_print)
    printing.process_all(limit=1)
    to_print.refresh_from_db()
    if to_print.status != PrintJob.Status.PRINTED:
        print(f"  warning: the job to print ended {to_print.status}")

    waiting = make(3)                                   # shot 05 and the queue page
    printing.confirm_job(waiting)

    failed = make(2, sides="SIMPLEX")
    printing.confirm_job(failed)
    printing.fail_job(failed, "Printer reported: out of paper (tray 1)")

    # A running print worker empties the queue every couple of seconds, which
    # makes shots 05 and 11 (and sometimes 14) impossible to take. Say so plainly
    # instead of producing a screenshot of the wrong state.
    import time as _time
    _time.sleep(2.5)
    waiting.refresh_from_db()
    failed.refresh_from_db()
    if waiting.status != PrintJob.Status.QUEUED:
        print("  NOTE: a print worker is running, so the queued job was picked up.\n"
              "        Stop it (Ctrl+C in the run_worker window) and run this again\n"
              "        so shots 05 and 11 show a job still waiting.")
    if failed.status != PrintJob.Status.FAILED:
        print(f"  NOTE: the failed job ended {failed.status}; retake shot 14 with"
              f" the worker stopped.")

    invoice = Invoice.objects.filter(member=member,
                                     status=Invoice.Status.AWAITING_APPROVAL).first()
    if invoice is None:
        invoice = billing.create_invoice(member=member, amount_cents=2000)
        billing.submit_transaction_id(
            invoice=invoice, txn_id=f"MP{int(time.time())}",
            payer_phone=member.phone or "+26876123456")
        invoice.refresh_from_db()

    return member, priced, waiting, to_print, failed, invoice


# --------------------------------------------------------------------------- #
# Browser side
# --------------------------------------------------------------------------- #
def wait_for_server():
    import urllib.request

    for _ in range(30):
        try:
            with urllib.request.urlopen(f"{BASE}/health/", timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:                                # noqa: BLE001
            time.sleep(0.5)
    raise SystemExit(f"{BASE} is not answering. Start it first:\n"
                     f"  .venv\\Scripts\\python.exe manage.py runserver")


def launch(playwright):
    problems = []
    for channel in CHANNELS:
        label = channel or "playwright chromium"
        try:
            if channel:
                browser = playwright.chromium.launch(channel=channel, headless=True)
            else:
                browser = playwright.chromium.launch(headless=True)
        except Exception as error:                       # noqa: BLE001
            first = str(error).strip().splitlines()[0][:150]
            problems.append(f"  {label:<20} {first}")
            continue
        print(f"browser: {label}")
        return browser
    print("Could not launch a browser:")
    for line in problems:
        print(line)
    raise SystemExit(
        "Install Playwright's own Chromium and retry:\n"
        "  .venv\\Scripts\\python.exe -m playwright install chromium\n"
        "or open Edge/Chrome once by hand and run this again.")


def sign_in(page, student_no):
    page.goto(f"{BASE}/login/", wait_until="domcontentloaded")
    page.fill("#id_username", student_no)
    page.fill("#id_password", PASSWORD)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    if "/login/" in page.url:
        raise SystemExit(
            f"Sign-in failed for {student_no}. Check SCREENSHOT_PASSWORD "
            f"(currently {PASSWORD!r}).")


def snap(page, name, note=""):
    target = OUT / f"{name}.png"
    page.wait_for_timeout(250)                 # let fonts settle
    page.screenshot(path=str(target), full_page=True)
    size = target.stat().st_size
    print(f"  {name:<26} {page.url.replace(BASE, '')[:44]:<46} {size:>8,} B")
    return target


# --------------------------------------------------------------------------- #
def main():
    dry_run = "--dry-run" in sys.argv
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]

    OUT.mkdir(parents=True, exist_ok=True)
    setup_django()
    if not dry_run:
        wait_for_server()
    member, priced, waiting, printed, failed, invoice = seed_state()
    print(f"member {member.student_no} · draft {priced.code} · queued "
          f"{waiting.code} · printed {printed.code} · failed {failed.code} · "
          f"invoice {invoice.reference}")

    plan = [
        ("01-login", "anonymous", "/login/"),
        ("02-member-dashboard", "member", "/home/"),
        ("03-upload", "member", "/jobs/new/"),
        ("04-price-confirm", "member", f"/jobs/{priced.public_id}/"),
        ("05-queued", "member", f"/jobs/{waiting.public_id}/"),
        ("06-credits-statement", "member", "/credits/"),
        ("07-topup-invoice", "member", "/billing/topup/"),
        ("08-transaction-submitted", "member", f"/billing/{invoice.reference}/"),
        ("09-admin-dashboard", "admin", "/manage/"),
        ("10-invoice-review", "admin", f"/manage/invoices/{invoice.reference}/"),
        ("11-queue", "admin", "/manage/queue/"),
        ("12-printed-output", "member", f"/jobs/{printed.public_id}/"),
        ("13-members", "admin", "/manage/members/"),
        ("14-failure", "member", f"/jobs/{failed.public_id}/"),
    ]
    plan = [row for row in plan if not only or row[0].startswith(only)]

    if dry_run:
        print("\n--dry-run: would capture")
        for name, role, path in plan:
            print(f"  {name:<26} {role:<10} {path}")
        return

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit(
            "Playwright is not installed:\n"
            "  .venv\\Scripts\\python.exe -m pip install playwright")

    captured = 0
    with sync_playwright() as playwright:
        browser = launch(playwright)
        contexts = {}
        for role in ("anonymous", "member", "admin"):
            context = browser.new_context(viewport=VIEWPORT,
                                          device_scale_factor=SCALE)
            page = context.new_page()
            page.set_default_timeout(15000)
            if role != "anonymous":
                sign_in(page, ADMIN_NO if role == "admin" else MEMBER_NO)
            contexts[role] = page

        print()
        for name, role, path in plan:
            page = contexts[role]
            page.goto(BASE + path, wait_until="networkidle")
            snap(page, name)
            captured += 1

        browser.close()

    from django.core.management import call_command
    from io import StringIO

    buffer = StringIO()
    try:
        call_command("check_credits", stdout=buffer)
    except SystemExit:
        pass
    (OUT / "15-ledger-check.txt").write_text(
        "$ python manage.py check_credits\n" + buffer.getvalue(), encoding="utf-8")

    print(f"\n{captured} screenshot(s) in {OUT}")
    print("15-ledger-check.txt holds the ledger output — screenshot it in a terminal.")


if __name__ == "__main__":
    main()
