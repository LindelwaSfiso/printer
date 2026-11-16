# ESprints

Printing service for the Engineering Society: members buy credits, upload PDFs,
and collect prints at the department desk. **Built to be run without a payment
API and, for now, without a printer** — every job is rendered to a PDF instead.

Django 6.1 · SQLite · server-rendered Tailwind v4 · no Django admin.

---

## Quick start

```powershell
# 1. environment
py -m venv .venv
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. css (once, and after any template change)
npm.cmd install --ignore-scripts
.\node_modules\.bin\tailwindcss.cmd -i ./static/src/input.css -o ./static/css/app.css --minify

# 3. database + demo data
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo

# 4. run
.\.venv\Scripts\python.exe manage.py runserver
```

Open <http://127.0.0.1:8000>.

| Sign in as | Password | Role |
|---|---|---|
| `ADMIN001` | `esprints123` | Administrator (dashboard at `/manage/`) |
| `202202881` | `esprints123` | Student with 1,000 credits |

To make your own administrator instead:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
# Student no: 101010   <- this is the login field, not a username
```

`createsuperuser` asks for the student number, email, first and last name. It
sets `role=ADMIN`, `is_staff` and `is_superuser`, so that account lands on
`/manage/` straight after signing in. (Plain `manage.py shell` users can also be
created from the dashboard: `/manage/members/new/`.)

`seed_demo` also creates a top-up invoice awaiting approval and a little print
history, so the dashboard is not empty on the first run.

---

## How it works

### Printing to PDF (current)

`PRINT_BACKEND=pdf` in `.env`. When a job is processed, the worker renders
`private_media/printout/ESP-00001.pdf`: a cover sheet (job code, student,
options, page count) followed by the document exactly as it would print.

That means the whole pipeline is real — queue, reservation, price, capture,
idempotency — only the last millimetre is file output instead of paper. Open the
file from the job page ("Download ESP-00001.pdf"), or from the queue page.

### Switching to real paper

1. Install the printer and confirm it prints a Windows test page.
2. `Get-Printer` to learn the exact queue name,
   `SumatraPDF.exe -list-printers -console` to learn its paper names.
3. In `.env`:
   ```ini
   PRINT_BACKEND=windows
   PRINTER_NAME=HP LaserJet M404
   SUMATRA_PATH=C:\Tools\SumatraPDF\SumatraPDF.exe
   ```
   (On Linux/CUPS use `PRINT_BACKEND=cups`; `lp` must be on `PATH`.)

Nothing else changes. `apps/printing/backends.py` is the only file that talks to
a printer.

### Printing to PDF *files* while testing a printer
`SumatraPDF -print-to "Microsoft Print to PDF" -print-settings "output=C:\out\x.pdf"`
avoids the save dialog — useful to prove the driver path without paper.

### The queue

The queue is the `PrintJob` table: a row in `QUEUED` is a job waiting, and
claiming it is a conditional `UPDATE`, so two workers can never take the same
job. `apps/printing/queue.py` exposes `push/pop/depth`, so Redis (or Celery) can
be dropped in behind the same three methods — see the comment at the bottom of
that file.

Process the queue in either of two ways:

```powershell
# the real thing: a worker process that loops
.\.venv\Scripts\python.exe manage.py run_worker
.\.venv\Scripts\python.exe manage.py run_worker --once   # one job, then exit
```

or press **Print the queue** in `/manage/queue/` (processes up to ten jobs in
the request). The button is convenient for a demo; the worker is what you run in
production.

### Credits and invoices

* Credits are the print currency: **10 credits = E1.00**, one mono A4 side = 10.
* A plan grants a **fixed** number of credits once (reference
  `sub:<id>:allocation`), so activating twice cannot double-credit.
* Confirming a job **reserves** credits; they are only spent when the job
  prints. A failure releases them automatically.
* Topping up: member creates an invoice (`ESP-2027-0007`), pays the society's
  mobile-money number quoting that reference, enters the transaction ID, and a
  treasurer approves it. Approval posts credits once
  (`invoice:<id>:credit`).
* A transaction ID can only ever be used on one invoice — that is the control
  that stops one payment being claimed twice.

### Accounts

There is **no sign-up**. An administrator creates the account at
`/manage/members/new/`, and the member receives an email with a link to choose a
password (valid 3 days, single use).

With the development email backend the invitation is printed to the terminal,
**and** the link is shown on the member's page while `DEBUG=1` so you can test
the flow without an SMTP server. Switch `EMAIL_BACKEND` to the SMTP backend and
that link disappears from the page.

---

## Project layout

```
config/            settings, urls, wsgi
apps/
  core/            base model, formatting, template tags (svg charts), CSS helpers
  accounts/        User (student_no login), invitation flow, login, profile
  subscriptions/   Plan, Subscription, credit grant
  credits/         CreditAccount, CreditEntry  <- the only code that moves credits
  printing/        tariff, jobs, backends, queue, worker, upload views
  billing/         Invoice, approval workflow
  console/         the administrator dashboard (replaces Django admin)
templates/
  layouts/app.html sidebar + topbar shell
  partials/        sidebar, topbar, messages, stat card, chart
static/src/input.css  Tailwind source
tools/smoke_test.py   end-to-end check of every page and the money flow
```

Rules worth keeping:

1. **Only `apps/credits/services.py` writes a balance.** Everything else imports
   `post_entry`, `place_hold`, `release_hold`.
2. **Every credit movement has a unique `reference`.** That is what makes
   retries and double clicks safe.
3. **Prices are snapshotted on the job** (`tariff_snapshot`), so changing the
   tariff never rewrites yesterday's bills.
4. **Nothing in the print path talks to money directly** — it calls `credits`.

---

## Commands

| Command | What it does |
|---|---|
| `runserver` | development server |
| `run_worker` | process the print queue (`--once` for one job) |
| `seed_demo` | tariff, plan, admin, two members, demo invoice |
| `check_credits` | ledger integrity: `sum(entries) == balance` |
| `expire_jobs` | release reservations on jobs left in the queue |
| `expire_invoices` | close unpaid invoices past their expiry |
| `expire_subscriptions` | mark ended subscriptions |
| `tools\smoke_test.py` | end-to-end check of all pages + both money flows |

## Testing

```powershell
.\.venv\Scripts\python.exe tools\smoke_test.py
```

34 checks: every page renders, a real PDF is uploaded, priced, queued, printed
to PDF, charged exactly once, an invoice is approved idempotently, a duplicate
transaction ID is refused, and `check_credits` is clean.

---

## Notes for this machine (Windows dev box)

* `npm` is blocked by PowerShell's execution policy — always use `npm.cmd`.
* `npm install --ignore-scripts` is required: the sandbox refuses the
  `@parcel/watcher` post-install spawn. Tailwind works fine without it.
* `pip` cannot create its temporary directories here (`mkdir` with mode 0700
  drops the inherited permission). `tools/dev/sitecustomize.py` is copied into
  `.venv\Lib\site-packages\` to work around it. None of this affects Linux.

## Not built yet (deliberate)

* Real printer monitoring beyond the exit code (the `UNKNOWN` job state).
* Redis/Celery broker — the `JobQueue` seam is there, the implementation is not.
* Production serving (`waitress`) and service installation.
* Email over SMTP, notifications beyond the dashboard badges.
