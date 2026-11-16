# Screenshots for presentation 2

## Install once

```powershell
.\.venv\Scripts\python.exe -m pip install playwright
```

Then **either** download Playwright's own Chromium:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

**or** skip the download — the script falls back to the Edge or Chrome already on
this machine (`channel="msedge"`, then `channel="chrome"`), so the browser download
is optional for this project.

The browser cache is shared by every project for your Windows user
(`%LOCALAPPDATA%\ms-playwright`), so it is a one-off cost rather than a
per-project one. Move it to another drive with the `PLAYWRIGHT_BROWSERS_PATH`
environment variable.

## Capture

**Stop the print worker first** — `Ctrl+C` in the `run_worker` window. A worker
empties the queue every couple of seconds, so the "waiting in the queue" shots
would show a job that has already printed. The script warns you if it notices.

```powershell
# terminal 1 — the portal must be running, the worker must not be
.\.venv\Scripts\python.exe manage.py runserver

# terminal 2
.\.venv\Scripts\python.exe tools\capture_screens.py
```

That writes `01-…png` … `14-…png` here plus `15-ledger-check.txt`.

Useful variants:

```powershell
# check the plan and seed the demo state without opening a browser
.\.venv\Scripts\python.exe tools\capture_screens.py --dry-run

# retake one shot while adjusting the UI
.\.venv\Scripts\python.exe tools\capture_screens.py --only 09

# different accounts / password
$env:SCREENSHOT_ADMIN="ADMIN001"; $env:SCREENSHOT_MEMBER="202202881"
$env:SCREENSHOT_PASSWORD="esprints123"
```

## What it does

1. Signs in through the **real login form** for an admin and a member — so the
   screenshots prove the login works, not just that the page renders.
2. Creates the states the deck needs through the app's own services: a priced
   draft job, a job waiting in the queue, a job already printed, a failed job and
   a submitted invoice.
3. Captures each page **full-page** at 2× scale (crisp on a projector), waiting
   for the network to go idle rather than guessing a delay.

It adds a few rows to your development database each run — that is deliberate,
the numbers in the screenshots have to be real.

## What you get

| # | File | Page | Account |
|---|---|---|---|
| 01 | `01-login.png` | `/login/` | — |
| 02 | `02-member-dashboard.png` | `/home/` | member |
| 03 | `03-upload.png` | `/jobs/new/` | member |
| 04 | `04-price-confirm.png` | job detail, before confirming | member |
| 05 | `05-queued.png` | a job waiting in the queue | member |
| 06 | `06-credits-statement.png` | `/credits/` | member |
| 07 | `07-topup-invoice.png` | `/billing/topup/` | member |
| 08 | `08-transaction-submitted.png` | invoice awaiting approval | member |
| 09 | `09-admin-dashboard.png` | `/manage/` | admin |
| 10 | `10-invoice-review.png` | `/manage/invoices/<ref>/` | admin |
| 11 | `11-queue.png` | `/manage/queue/` | admin |
| 12 | `12-printed-output.png` | the printed job | member |
| 13 | `13-members.png` | `/manage/members/` | admin |
| 14 | `14-failure.png` | a failed job | member |
| 15 | `15-ledger-check.txt` | `check_credits` output | — |

**11 and 12 are the money shots** — they prove the queue ran and the credits were
charged exactly once.

`15` is text because a terminal is not a web page: open the file, or run
`.\.venv\Scripts\python.exe manage.py check_credits` and screenshot that window.

## If the browser will not launch

The script prints what each attempt returned. In order:

1. Open Edge or Chrome by hand once, close it, run the script again.
2. Install Playwright's own browser: `python -m playwright install chromium`.
3. Capture by hand: `Win + Shift + S` for a region, `Alt + PrtSc` for a window.
   Use a consistent window (~1440 × 900) and hide the bookmarks bar.

Keep student documents out of the presentation, and delete any stale shots first.
