# Screenshots for presentation 2

Capture these once, save them with the names below, and the deck writes itself.
Use `Win + Shift + S` (region) or `Alt + PrtSc` (window), and save as PNG.

**Before you start**

```powershell
.\.venv\Scripts\python.exe manage.py runserver      # terminal 1
.\.venv\Scripts\python.exe manage.py run_worker     # terminal 2
.\.venv\Scripts\python.exe manage.py seed_demo      # if the database is empty
```

Sign in as **ADMIN001 / esprints123** for admin shots, **202202881 / esprints123**
for member shots. Set the window to a consistent size (about 1440 x 900) so the
screenshots look like one set, and hide the bookmarks bar.

| # | File name | Page | Account | What must be visible |
|---|---|---|---|---|
| 01 | `01-login.png` | `/login/` | — | "Welcome back", the split card, the three-step panel |
| 02 | `02-member-dashboard.png` | `/home/` | member | Credits card, 30-day chart, recent jobs table |
| 03 | `03-upload.png` | `/jobs/new/` | member | The PDF field, options, tariff panel |
| 04 | `04-price-confirm.png` | job detail, before confirming | member | Pages, sides, credits **and** the Confirm button |
| 05 | `05-queued.png` | same job after confirming | member | Status "In the queue", credits reserved, position |
| 06 | `06-credits-statement.png` | `/credits/` | member | Ledger rows with references and running balance |
| 07 | `07-topup-invoice.png` | `/billing/topup/` → invoice | member | Amount, reference, the society's mobile-money number |
| 08 | `08-transaction-submitted.png` | same invoice after submitting | member | Status "Awaiting approval", transaction ID |
| 09 | `09-admin-dashboard.png` | `/manage/` | admin | Four stat cards, chart, "Needs a human" panel |
| 10 | `10-invoice-review.png` | `/manage/invoices/<ref>/` | admin | Transaction ID beside Approve / Reject |
| 11 | `11-queue.png` | `/manage/queue/` | admin | Waiting jobs, printer status, "Print the queue" |
| 12 | `12-printed-output.png` | job page after printing | member | Status "Printed", **Download ESP-xxxxx.pdf** |
| 13 | `13-members.png` | `/manage/members/` | admin | Member rows with plans and credit balances |
| 14 | `14-failure.png` | a failed job | admin | Failure reason and "credits returned" |
| 15 | `15-ledger-check.png` | terminal | — | `check_credits` → `Checked; 0 problem(s)` |

## Notes

* **11 and 12 are the money shots** — they prove the queue ran and the credits were
  charged exactly once. Capture 12 twice if you like, before and after printing.
* For 15, run this and screenshot the terminal window:

  ```powershell
  .\.venv\Scripts\python.exe manage.py check_credits
  ```

* To make 14 honestly, queue a job and stop the worker before it runs, or set
  `PRINT_BACKEND=windows` with an empty `PRINTER_NAME` for one run.
* Keep the PNGs in this folder (they are small) so the deck is reproducible, and
  keep the original uploads out of it — no student documents in the presentation.
