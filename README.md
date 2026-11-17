# ESprints

Printing service for the Engineering Society: members buy print credits, upload a
PDF from their phone, and collect the pages at the department desk. One computer
runs the website, the queue and the printer.

**Repository:** <https://github.com/LindelwaSfiso/printer.git>
**Built with:** Python 3.12+ · Django 6.1 · SQLite · Tailwind CSS 4

---

# Part 1 — Setting it up (no prior experience needed)

This part assumes you have never installed a development tool. Follow it in
order; each step tells you how to check that it worked. Total time: about
15 minutes, most of it downloads.

You will only ever type commands into **PowerShell**. To open it: press the
Windows key, type `powershell`, and press Enter.

> **Copy commands exactly as written.** Where a command is long, it is still one
> single line — copy the whole line.

## Step 0 — What you need before you start

| Tool | Why | Where to get it |
|---|---|---|
| **Git** | downloads (clones) the project from GitHub | <https://git-scm.com/download/win> |
| **Python 3.12 or newer** | runs the website | <https://www.python.org/downloads/windows/> |
| Node.js 20+ | *only* if you want to change the colours or layout | <https://nodejs.org/en/download> |

**Node.js is optional.** The styling is already built and included in the
project, so a normal installation does not need it. Skip Step 1c unless you plan
to edit the appearance.

## Step 1 — Install the tools

### 1a. Git

Download and run the installer from the link above. Click **Next** through every
screen (the defaults are correct), then **Install**.

Check it worked — in PowerShell:

```powershell
git --version
```

You should see something like `git version 2.47.0.windows.1`.

### 1b. Python

Download the installer from the link above and run it. **Important:** on the
first screen, tick **“Add python.exe to PATH”** before clicking *Install Now*.
Without that tick, Windows will not find Python later.

Check it worked:

```powershell
py --version
```

You should see `Python 3.12.x` or newer. If you get an error, reinstall Python and
tick the PATH box this time.

### 1c. Node.js (optional — only for editing the styling)

Download the **LTS** installer, run it, accept the defaults.

```powershell
node --version
npm.cmd --version
```

## Step 2 — Download the project

Choose where to keep it. This puts it in your Documents folder:

```powershell
cd $HOME\Documents
git clone https://github.com/LindelwaSfiso/printer.git
cd printer
```

You should now have a folder `Documents\printer` containing `manage.py`,
`README.md` and several folders. **Every command from here on is run from inside
that folder.**

## Step 3 — Create the project's own Python environment

A *virtual environment* is a private copy of Python for this project, so nothing
here can break other programs on your computer.

```powershell
py -m venv .venv
```

This creates a `.venv` folder. It takes a few seconds and prints nothing when it
succeeds.

## Step 4 — Install the project's dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The second command downloads Django and a few small libraries (about 15 MB). It
prints `Successfully installed …` at the end.

> **Why the long `.\.venv\Scripts\python.exe` instead of just `python`?** It
> guarantees the command uses the project's own Python. It is longer to type but
> it cannot go wrong, and it means you never have to “activate” anything.

## Step 5 — Create the settings file

The project ships a template; your copy holds the real settings and is never
committed to GitHub.

```powershell
Copy-Item .env.example .env
```

The defaults are correct for a local installation. You can open `.env` in Notepad
later to change the society's mobile-money number, the tariff or the email
settings.

## Step 6 — Create the database and demo data

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
```

`migrate` builds the database (prints a list of `Applying … OK`).
`seed_demo` creates a tariff, a membership plan, an administrator, two students
and some sample activity:

```
Tariff: mono 10 / colour 40 credits per A4 side
Plan: Semester membership (E150.00, 1,000 credits)
Created administrator: ADMIN001 / esprints123
Created member 202202881
Created member 202203442
```

## Step 7 — Start the website

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Leave that window open — it *is* the website. Open a browser and go to:

**<http://127.0.0.1:8000>**

| Sign in as | Password | You will see |
|---|---|---|
| `ADMIN001` | `esprints123` | the administrator dashboard |
| `202202881` | `esprints123` | a student account with 1,000 credits |

To stop the website, click that PowerShell window and press **Ctrl + C**.

## Step 8 — Start the print queue (optional, second window)

Printing is done by a second program so that the website never freezes while a
printer works. Without it, jobs stay in the queue saying “waiting”.

Open a **second** PowerShell window:

```powershell
cd $HOME\Documents\printer
.\.venv\Scripts\python.exe manage.py run_worker
```

It prints `Worker running …` and then a line for every job it prints. Leave it
running, and stop it with **Ctrl + C** like the website.

> For a quick look you can skip the worker: press **“Print the queue”** on
> `/manage/queue/` and the website will process the waiting jobs itself.

---

# Part 2 — Using it

### The student's side

1. **Top up.** *Top up* → enter an amount → the portal creates an invoice with a
   reference like `ESP-2027-0007`.
2. **Pay.** Send that exact amount by mobile money to the society's number,
   putting the reference in the payment's message box.
3. **Record it.** Back on the invoice, type the transaction ID from the SMS and
   send it for approval.
4. **Print.** *New print job* → upload a PDF → choose colour, sides, paper and
   copies → the exact price in credits is shown → confirm.
5. **Collect.** The pages come out at the desk with a cover sheet showing the job
   code.

### The administrator's side (`/manage/`)

| Page | What it is for |
|---|---|
| Dashboard | money, pages, queue and printer at a glance |
| Members | create accounts (the member is emailed a link to set a password), assign plans, add credits |
| Plans | what a membership costs and how many credits it grants |
| Invoices | approve or reject top-ups after checking the mobile-money statement |
| Print queue | jobs waiting to print; “Print the queue” runs them |
| All jobs | every job ever submitted, with a CSV export |
| Settings | the tariff and the printer configuration, read-only |

**No Django admin.** Everything the society needs is in `/manage/`, deliberately:
a treasurer should not have to learn a developer tool.

### Credits in one line

10 credits = E1.00. One mono A4 side costs 10 credits, one colour side 40, A3
doubles it, and double-sided saves 10%. A subscription **grants** credits but is
not required to print — a member who topped up can print with no plan at all.

---

# Part 3 — How it works (for whoever maintains it)

### Printing to PDF

`PRINT_BACKEND=pdf` in `.env` (the default). When a job is processed, the worker
writes `private_media/printout/ESP-00001.pdf`: a cover sheet followed by the
document, exactly as it would print. Open it from the job page.

The whole pipeline is real — queue, reservation, price, charge, idempotency —
only the last millimetre is a file instead of paper.

### Switching to a real printer

1. Install the printer and confirm it prints a Windows test page.
2. `Get-Printer` gives the exact queue name; `SumatraPDF.exe -list-printers`
   gives the paper names the driver accepts.
3. In `.env`:
   ```ini
   PRINT_BACKEND=windows
   PRINTER_NAME=HP LaserJet M404
   SUMATRA_PATH=C:\Tools\SumatraPDF\SumatraPDF.exe
   ```
   On Linux/CUPS use `PRINT_BACKEND=cups` (`lp` must be on the PATH).

Nothing else changes: `apps/printing/backends.py` is the only file that talks to
a printer.

### The queue

The queue is the `PrintJob` table — a row in `QUEUED` is a job waiting, and
claiming it is a conditional `UPDATE`, so two workers can never take the same
job. `apps/printing/queue.py` exposes `push/pop/depth`, so a Redis or Celery
broker can be dropped in behind the same three methods (see the comment at the
bottom of that file).

### Accounts

There is **no public sign-up**. An administrator creates the account at
`/manage/members/new/`; the member receives an email with a one-time link (valid 3
days) to choose a password. In development the email is printed to the terminal
running the website, and the link is also shown on the member's page while
`DEBUG=1`.

### Money

A payment API is deliberately absent: production mobile-money merchant access is
not available for a student project, so the member pays the society's number and
a treasurer approves the invoice. What makes that auditable is that a transaction
ID can only ever be used on one invoice, approval is idempotent
(`invoice:<id>:credit`), and every decision records who made it.

---

# Part 4 — Project layout

```
config/            settings, urls, wsgi
apps/
  core/            base model, formatting, SVG charts, CSS helpers
  accounts/        User (student-number login), invitations, login, profile
  subscriptions/   Plan, Subscription, credit grant
  credits/         CreditAccount, CreditEntry  <- the only code that moves credits
  printing/        tariff, jobs, backends, queue, worker
  billing/         Invoice, approval workflow
  console/         the administrator dashboard (replaces Django admin)
templates/         layouts/, partials/, one folder per app
static/src/input.css   Tailwind source
static/css/app.css     built stylesheet (committed, so Node is optional)
private_media/     uploaded PDFs and printed output (never public)
tools/             make_diagrams.py, capture_screens.py, smoke_test.py
docs/              guides, diagrams, screenshots
```

Rules worth keeping:

1. **Only `apps/credits/services.py` writes a balance.** Everything else calls
   `post_entry`, `place_hold`, `release_hold`.
2. **Every credit movement has a unique reference**, which is what makes retries
   and double clicks safe.
3. **Prices are snapshotted on the job**, so changing the tariff never rewrites
   yesterday's bills.
4. **Nothing in the print path touches money directly** — it calls `credits`.

---

# Part 5 — Commands you will use

Run everything with `.\.venv\Scripts\python.exe` from the project folder.

| Command | What it does |
|---|---|
| `manage.py runserver` | start the website on <http://127.0.0.1:8000> |
| `manage.py run_worker` | process the print queue (`--once` one job, `--drain` all) |
| `manage.py migrate` | apply database changes after an update |
| `manage.py seed_demo` | create demo data (`--reset` to redo the members) |
| `manage.py createsuperuser` | make another administrator (asks for a student number) |
| `manage.py check_credits` | verify every balance matches its ledger |
| `manage.py expire_jobs` | release reservations on abandoned jobs |
| `manage.py expire_invoices` | close unpaid invoices |
| `manage.py expire_subscriptions` | mark ended subscriptions |
| `tools\smoke_test.py` | check every page and both money flows end to end |

## Updating an existing installation

```powershell
git pull
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
```

Restart the website (and the worker) afterwards.

## Changing the styling (needs Node.js)

```powershell
npm.cmd install
.\node_modules\.bin\tailwindcss.cmd -i ./static/src/input.css -o ./static/css/app.css --minify
```

The rebuilt `static/css/app.css` must be committed for other people to see the
change.

---

# Part 6 — If something goes wrong

| What you see | What it means | What to do |
|---|---|---|
| `py: command not found` | Python is not installed, or PATH was not ticked | reinstall Python, tick **Add python.exe to PATH** |
| `pip` says Django needs a newer Python | your Python is older than 3.12 | install Python 3.12+ (recommended), or install an older Django: `pip install "Django<6"` |
| `running scripts is disabled on this system` | PowerShell blocks scripts | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` then answer **Y** |
| `npm.ps1 cannot be loaded` | same policy, affecting `npm` | always type `npm.cmd` instead of `npm` |
| `No module named django` | the system Python was used instead of the project's | put `.\.venv\Scripts\python.exe` in front of the command |
| `Address already in use` | the website is already running in another window | close it, or use `manage.py runserver 8080` |
| The site loads but has no colours | the stylesheet was not built or not committed | run the Tailwind build above |
| Login accepts nothing | the demo password is `esprints123`; after `createsuperuser` use the one you typed | — |
| `DisallowedHost` | opened via a different address than allowed | add it to `DJANGO_ALLOWED_HOSTS` in `.env` |
| Jobs never print | the print queue is not running | start `run_worker`, or press **Print the queue** |
| `database is locked` | two workers writing at once | keep one `run_worker` window only |
| Emails do not arrive | development mode prints them instead of sending | read the website window's output |

## Starting over

To wipe the database and return to the demo data:

```powershell
Remove-Item db.sqlite3
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
```

Uploaded files live in `private_media\`; delete that folder too if you want a
completely clean slate.

---

# Part 7 — Handing this to a real office

The defaults are for a demonstration. Before the society uses it for real:

1. **Change the secret key.** In `.env`, set `DJANGO_SECRET_KEY` to a long random
   string (50+ characters) and `DJANGO_DEBUG=0`.
2. **Set the addresses.** `DJANGO_ALLOWED_HOSTS` and `SITE_URL` must match the
   machine's address on the office network, e.g. `http://192.168.1.50:8000`.
3. **Use a production server**, not `runserver`:
   ```powershell
   .\.venv\Scripts\python.exe -m pip install "waitress>=3.0"
   .\.venv\Scripts\waitress-serve.exe --listen=0.0.0.0:8000 --threads=8 config.wsgi:application
   ```
4. **Make both programs start with Windows** — Task Scheduler (Windows) or two
   `systemd` services (Linux), so the site and the worker survive a reboot.
5. **Back up nightly**: copy `db.sqlite3` and the `private_media` folder to
   another disk. Test a restore once.
6. **Set the real payment details** in `.env`: `SOCIETY_MOMO_NUMBER`,
   `SOCIETY_MOMO_NAME`, and the email settings (`EMAIL_BACKEND`, `EMAIL_HOST`, …)
   so invitations are actually delivered.
7. **Turn on a real printer** (see Part 3) and print a test page each morning.

Not implemented, and worth stating in any handover document: automated payment
verification (there is no payment API), multiple printers, and job monitoring
beyond the printer's own success report.

---

# Part 8 — Notes for developers

* **Windows PATH quirk on this machine:** `npm` is blocked by the execution
  policy — use `npm.cmd`.
* **`npm install --ignore-scripts`** is needed only in restricted environments
  that refuse the `@parcel/watcher` post-install step; Tailwind works without it.
* **Screenshots for the presentation:** `tools\capture_screens.py` (Playwright).
  Stop the print worker first, or the “waiting in the queue” shots will show jobs
  that have already printed. See `docs/screenshots/README.md`.
* **Diagrams:** `tools\make_diagrams.py` regenerates the SVG figures in
  `docs/diagrams/`.
* **Restart after editing templates:** with `runserver --noreload` Django caches
  templates; plain `runserver` reloads them automatically.
