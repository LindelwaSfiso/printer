"""Capture the presentation screenshots automatically.

    .venv\\Scripts\\python.exe manage.py runserver     # terminal 1, leave it running
    .venv\\Scripts\\python.exe tools\\capture_screens.py

Produces docs/screenshots/01-…png … 14-…png, plus a text file with the
`check_credits` output you can screenshot in a terminal.

How it works
------------
* It writes real Django session rows for an admin and a member (exactly what
  `login()` would write) and runs two tiny local proxies that attach that cookie
  to every request. A headless browser launched with --screenshot runs no script
  of ours, so injecting the session is the only way to photograph a page behind
  a login. No backdoor: the sessions are ordinary, and they are deleted when the
  run finishes.
* It creates the states the shots need — a priced job, a queued job, a printed
  job, a submitted invoice, a failed job — through the same service functions the
  web app uses. Nothing is faked; the numbers in the screenshots are real rows.

Why this cannot run inside a coding sandbox: Chrome/Edge on Windows build their
process tree over named pipes and use process handles for their crash handler, so
a sandbox that denies those makes the browser exit before it renders. Run this
from your own terminal and it works.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import tempfile
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")

OUT = ROOT / "docs" / "screenshots"
# Scratch work lives on a short path with no spaces: Chromium mis-handles a
# --screenshot= value inside a folder such as "Final Years 2026".
WORK = Path(tempfile.gettempdir()) / "esprints-shots"

BASE_FLAGS = [
    "--disable-gpu", "--no-sandbox", "--hide-scrollbars", "--no-first-run",
    "--no-default-browser-check", "--disable-crash-reporter",
    "--disable-extensions", "--disable-background-networking",
    "--force-device-scale-factor=1",
]
FLAG_SETS = [
    ("headless-new", ["--headless=new"]),
    ("headless-old", ["--headless=old"]),
    ("headless", ["--headless"]),
]
UPSTREAM = "http://127.0.0.1:8000"
ADMIN_PORT = 8766
MEMBER_PORT = 8767

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

ADMIN_NO = os.environ.get("SCREENSHOT_ADMIN", "ADMIN001")
MEMBER_NO = os.environ.get("SCREENSHOT_MEMBER", "202202881")


# --------------------------------------------------------------------------- #
# Session cookie injection
# --------------------------------------------------------------------------- #
class CookieProxy(ThreadingHTTPServer):
    """Serves 127.0.0.1:PORT, forwarding to Django with a session cookie attached."""

    daemon_threads = True

    def __init__(self, port, session_key):
        self.session_key = session_key
        super().__init__(("127.0.0.1", port), _Handler)

    def server_bind(self):
        # HTTPServer.server_bind calls getfqdn(), which can hang for seconds here.
        import socketserver
        socketserver.TCPServer.server_bind(self)
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        request = urllib.request.Request(UPSTREAM + self.path)
        if getattr(self.server, "session_key", None):
            request.add_header("Cookie", f"sessionid={self.server.session_key}")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body, status = response.read(), response.status
                content_type = response.headers.get("Content-Type", "text/html")
        except urllib.error.HTTPError as error:
            body, status = error.read(), error.code
            content_type = error.headers.get("Content-Type", "text/html")
        except Exception as error:                        # noqa: BLE001
            body, status = f"proxy error: {error}".encode(), 502
            content_type = "text/plain"

        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def make_session(django, student_no):
    from django.contrib.auth import get_user_model
    from django.contrib.sessions.backends.db import SessionStore

    user = get_user_model().objects.filter(student_no=student_no).first()
    if user is None:
        raise SystemExit(f"No account {student_no}. Run: manage.py seed_demo")
    session = SessionStore()
    session["_auth_user_id"] = str(user.pk)
    session["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
    session["_auth_user_hash"] = user.get_session_auth_hash()
    session.create()
    return session.session_key, user


# --------------------------------------------------------------------------- #
# Demo state (real rows, created through the app's own services)
# --------------------------------------------------------------------------- #
def demo_pdf(pages=4):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    for number in range(1, pages + 1):
        pdf.setFont("Helvetica-Bold", 26)
        pdf.drawString(60, 700, "ESprints — demonstration document")
        pdf.setFont("Helvetica", 13)
        pdf.drawString(60, 665, f"Page {number} of {pages}")
        pdf.setFont("Helvetica", 11)
        pdf.drawString(60, 640, "Generated for the progress presentation.")
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def ensure_credits(member, minimum=400):
    from apps.credits.services import ensure_account, post_entry

    account = ensure_account(member)
    if account.available_credits < minimum:
        post_entry(account_id=account.id, delta_credits=minimum,
                   kind="ADJUSTMENT", reference=f"screens:{member.pk}:topup",
                   memo="Screenshot demo credit")
        account.refresh_from_db()
    return account


def create_job(member, *, pages=4, sides="DUPLEX", colour="MONO"):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.printing import services

    upload = SimpleUploadedFile("Project-proposal.pdf", demo_pdf(pages),
                                content_type="application/pdf")
    return services.create_draft(
        member=member, uploaded=upload,
        cleaned={"page_count": pages, "copies": 1, "colour_mode": colour,
                 "sides": sides, "paper": "A4"})


def create_pending_invoice(member):
    from apps.billing import services

    stamp = time.strftime("%d%H%M%S")
    invoice = services.create_invoice(member=member, amount_cents=2000)
    services.submit_transaction_id(invoice=invoice, txn_id=f"MP2607{stamp}",
                                   payer_phone=member.phone or "+26876123456")
    invoice.refresh_from_db()
    return invoice


# --------------------------------------------------------------------------- #
# Browser
# --------------------------------------------------------------------------- #
def probe_browsers():
    """Find a browser + flag combination that can actually render here.

    Chromium is fussy in ways that depend on the machine: older builds reject
    --headless=new, some profiles refuse to start without --no-sandbox, and a
    screenshot path containing spaces is a long-standing Windows trap. So we
    try a small matrix against a data: URL, and keep the first combination that
    produces a PNG. The user sees exactly what was tried.
    """
    WORK.mkdir(parents=True, exist_ok=True)
    found = [path for path in BROWSERS if Path(path).exists()]
    if not found:
        raise SystemExit("Chrome and Edge were not found. Install one, or edit BROWSERS.")

    page = "data:text/html,<h1 style='font:48px sans-serif'>ESprints probe</h1>"
    for browser in found:
        for label, flags in FLAG_SETS:
            target = WORK / f"probe-{label}.png"
            if target.exists():
                target.unlink()
            ok, detail = attempt(browser, flags, page, target, 400)
            state = "OK" if ok else f"failed ({detail})"
            print(f"  {Path(browser).name:<12} {label:<14} {state}")
            if ok:
                print(f"using: {Path(browser).name} {label}")
                return browser, flags
    raise SystemExit(
        "No browser could render. Run with --probe and paste the output, and check "
        "that Chrome/Edge opens normally when you double-click it.
"
        f"Debug files were left in {WORK}")


def attempt(browser, flags, url, target, height, timeout=60):
    command = [
        browser, *flags, *BASE_FLAGS,
        f"--user-data-dir={WORK / 'profile'}",
        f"--window-size=1440,{height}",
        "--virtual-time-budget=3000",
        f"--screenshot={target}",
        url,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"no answer after {timeout}s"

    for _ in range(60):
        if target.exists() and target.stat().st_size > 2000:
            return True, ""
        time.sleep(0.25)

    lines = (result.stderr or result.stdout or "").strip().splitlines()
    detail = lines[-1][:150] if lines else "exited silently"
    return False, f"exit {result.returncode}, {detail}"


def shoot(browser, flags, url, target: Path, height: int) -> bool:
    """Screenshot to a scratch path, then move it into docs/screenshots."""
    scratch = WORK / f"shot-{target.stem}.png"
    if scratch.exists():
        scratch.unlink()
    ok, detail = attempt(browser, flags, url, scratch, height)
    if ok:
        shutil.move(str(scratch), str(target))
        return True
    if detail:
        print(f"        {detail}")
    return False


# --------------------------------------------------------------------------- #
# The run
# --------------------------------------------------------------------------- #
def main():
    import django
    django.setup()

    from django.contrib.sessions.models import Session
    from apps.billing.models import Invoice
    from apps.credits.services import ensure_account
    from apps.printing import services as printing

    OUT.mkdir(parents=True, exist_ok=True)
    wait_for_server()
    print("looking for a browser that can render:")
    browser, flags = probe_browsers()

    admin_key, admin = make_session(django, ADMIN_NO)
    member_key, member = make_session(django, MEMBER_NO)
    if member.credit_account and member.credit_account.available_credits < 200:
        ensure_credits(member)
    elif not hasattr(member, "credit_account"):
        ensure_credits(member)
    print(f"sessions: {admin.student_no} (admin), {member.student_no} (member)")
    if member.active_subscription is None:
        print("  note: this member has no active plan — they print on top-up credits.")

    admin_proxy = CookieProxy(ADMIN_PORT, admin_key)
    member_proxy = CookieProxy(MEMBER_PORT, member_key)
    for proxy in (admin_proxy, member_proxy):
        threading.Thread(target=proxy.serve_forever, daemon=True).start()

    base = {None: UPSTREAM,
            "admin": f"http://127.0.0.1:{ADMIN_PORT}",
            "member": f"http://127.0.0.1:{MEMBER_PORT}"}

    captured, failed = 0, []

    def shot(name, path, role=None, height=1100):
        nonlocal captured
        target = OUT / f"{name}.png"
        print(f"  {name:<26} {path}")
        if shoot(browser, flags, base[role] + path, target, height):
            captured += 1
            print(f"        {target.name}  ({target.stat().st_size:,} bytes)")
        else:
            failed.append(name)
            print("        FAILED")

    # --- a priced job, photographed before it is confirmed -----------------
    ensure_credits(member)
    job = create_job(member)

    shot("01-login", "/login/", None, 900)
    shot("02-member-dashboard", "/home/", "member", 1180)
    shot("03-upload", "/jobs/new/", "member", 1100)
    shot("04-price-confirm", f"/jobs/{job.public_id}/", "member", 1000)

    printing.confirm_job(job)
    shot("05-queued", f"/jobs/{job.public_id}/", "member", 1000)

    shot("06-credits-statement", "/credits/", "member", 1150)
    shot("07-topup-invoice", "/billing/topup/", "member", 950)

    invoice = create_pending_invoice(member)
    shot("08-transaction-submitted", f"/billing/{invoice.reference}/", "member", 1050)
    shot("09-admin-dashboard", "/manage/", "admin", 1250)
    shot("10-invoice-review", f"/manage/invoices/{invoice.reference}/", "admin", 1000)
    shot("11-queue", "/manage/queue/", "admin", 1050)

    printing.process_all(limit=1)
    shot("12-printed-output", f"/jobs/{job.public_id}/", "member", 1000)

    shot("13-members", "/manage/members/", "admin", 950)

    # --- one honest failure ------------------------------------------------
    broken = create_job(member, pages=2, sides="SIMPLEX")
    printing.confirm_job(broken)
    printing.fail_job(broken, "Printer reported: out of paper (tray 1)")
    shot("14-failure", f"/jobs/{broken.public_id}/", "member", 1000)

    # --- evidence that cannot be photographed from a browser ---------------
    from django.core.management import call_command
    from io import StringIO

    buffer = StringIO()
    try:
        call_command("check_credits", stdout=buffer)
    except SystemExit:
        pass
    (OUT / "15-ledger-check.txt").write_text(
        "$ python manage.py check_credits\n" + buffer.getvalue()
        + "\nScreenshot this file in a terminal, or paste it into the report.\n",
        encoding="utf-8")

    for key in (admin_key, member_key):
        Session.objects.filter(session_key=key).delete()
    admin_proxy.shutdown()
    member_proxy.shutdown()

    print(f"\n{captured} screenshot(s) in {OUT}")
    if failed:
        print("failed: " + ", ".join(failed))
    print("15-ledger-check.txt written — screenshot it in a terminal window.")


if __name__ == "__main__":
    if "--probe" in sys.argv:
        print(f"scratch: {WORK}")
        probe_browsers()
    else:
        main()
