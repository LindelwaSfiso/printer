# Screenshots for presentation 2

## One command

```powershell
# terminal 1 — leave this running
.\.venv\Scripts\python.exe manage.py runserver

# terminal 2
.\.venv\Scripts\python.exe tools\capture_screens.py
```

That writes `01-…png` to `14-…png` here, plus `15-ledger-check.txt`. The script
creates the states the shots need (a priced job, a queued job, a printed job, a
submitted invoice, a failed job) through the app's own service functions, signs in
by writing real session rows, and deletes those sessions when it finishes.

Options, if your demo data differs:

```powershell
$env:SCREENSHOT_ADMIN="ADMIN001"; $env:SCREENSHOT_MEMBER="202202881"
```

### Why it needs your terminal

Chrome and Edge on Windows build their process tree over named pipes and use
process handles for the crash handler. A coding sandbox that denies those makes
the browser exit before it renders anything (`mojo platform_channel.cc … Access
is denied`, `crashpad_client_win.cc OpenProcess: Access is denied`). Everything
else — sessions, cookie injection, page states — is verified and works; only the
final "launch Chrome" step needs an unrestricted session.

## What you get

| # | File | Page | Account |
|---|---|---|---|
| 01 | `01-login.png` | `/login/` | — |
| 02 | `02-member-dashboard.png` | `/home/` | member |
| 03 | `03-upload.png` | `/jobs/new/` | member |
| 04 | `04-price-confirm.png` | job detail, before confirming | member |
| 05 | `05-queued.png` | the same job after confirming | member |
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

**11 and 12 are the money shots** — they prove the queue ran and credits were
charged exactly once.

`15` is text because a terminal is not a web page: open the file, or run
`.\.venv\Scripts\python.exe manage.py check_credits` and screenshot that window.

## Capturing by hand (fallback)

`Win + Shift + S` for a region, `Alt + PrtSc` for a window, saved as PNG. Use a
consistent window size (~1440 × 900) and hide the bookmarks bar so the set looks
like one deck. Keep student documents out of the presentation.
