# Progress report 1 — presentation pack

**Project:** ESprints — Engineering Society printing service
**Student:** Welile Maphosa · **Supervisor:** Dr T. Dlamini
**Period:** month 1 of 6 (November 2026)
**Purpose of this pack:** what to show at presentation 1, what to hold back for
presentation 2, and the figures to put in the written progress report.

Figures live in [`docs/diagrams/`](diagrams/) as **SVG** (vector — insert them in
Word or PowerPoint with *Insert ▸ Pictures*, or open them in a browser).

Regenerate after editing `tools/make_diagrams.py`:

```powershell
.\.venv\Scripts\python.exe tools\make_diagrams.py
```

---

## 1. Position at presentation 1

The system is further along than a month-1 report needs to admit. Present the
**design and the plan**; keep the working build for presentation 2.

| Show now | Hold back for presentation 2 |
|---|---|
| Problem statement and scope | A live end-to-end print |
| Block diagram (architecture) | Screenshots of the dashboards |
| Flow diagram (job lifecycle) | Credit ledger and billing evidence |
| Gantt chart (6-month plan) | Billing accuracy matrix and UAT results |
| Hardware selection and cost | The invoice-approval demo |
| Requirements table (FR-01 … FR-20) | Reliability measurements |

If asked "have you started building?", the honest answer is: *"The development
environment is standing and the account layer is under construction; the
architecture and data model are fixed."* Everything else is scheduled from
month 2, which is exactly what the Gantt chart shows.

---

## 2. Figures

### Figure 1 — Block diagram (`diagrams/block_diagram.svg`)

**Caption:** *System architecture: members reach the portal over the local
network; the portal, the queue and the printer all live on one machine at the
department desk.*

Points to make in 30 seconds:
- The printer is driven by the operating system's print spooler, not by a direct
  cable protocol — this is the standard way any application prints.
- One machine means no cloud, no inbound ports and no internet dependency.
- The member's phone only ever talks HTTP to the portal.

### Figure 2 — Flow diagram (`diagrams/flow_diagram.svg`)

**Caption:** *The lifecycle of a print job: credits are reserved when the job is
queued and only captured after a successful print; a failure releases them.*

Points to make:
- **Reserve, then capture** — a jam or a cancellation never charges the member.
- Every state is recorded, so the member's history and the society's reports come
  from the same source of truth.
- Insufficient credits is a *checked* path, not an error page.

### Figure 3 — Gantt chart (`diagrams/gantt_chart.svg`)

**Caption:** *Six-month project plan with milestones.*

Points to make:
- Design and hardware selection occupy month 1, so implementation starts from a
  fixed specification.
- The critical path runs *upload → queue → printer integration*; that is where
  the risk sits and where the time has been protected.
- Presentation 1 (month 1), presentation 2 (month 4), submission (month 6).

---

## 3. Hardware choices

| Item | Choice | Why this choice | Indicative cost |
|---|---|---|---|
| Computer | Existing Windows laptop, i5 / 8 GB / SSD, one free USB-A port | Runs the portal, the database and the print worker on the same machine; no server to buy | owned (E0) |
| Printer | Mono laser with **automatic duplex** (HP LaserJet / Brother HL-L2300-class); USB + driverless (IPP) support | Duplex is the option most likely to be ignored by a driver, so the printer must support it to prove the billing is right | E1 500 – E3 000 |
| Cable | USB 2.0 A–B, 2–3 m, straight to the laptop (no hub) | Long or unpowered cables are the usual cause of "nothing printed" | E60 – E150 |
| Paper / toner | A4 80 gsm ream + one spare cartridge | Running out mid-demo is the cheapest failure to avoid | E120 + E700 – E1 400 |
| Network | Personal Wi-Fi router (or phone hotspot for a fallback) | Removes the campus network from the demonstration's risk list | E0 – E800 |
| Power | 650 VA UPS | A power cut during a database write is the one failure that loses money | E800 – E1 500 |
| Backup | 32 GB USB stick for nightly database + document copies | A restore you have practised is the difference between an incident and a disaster | E150 |
| Optional | Tablet showing the desk console | Makes the operator's role obvious in the demo video | E1 500 + |

**Total, excluding the laptop: roughly E4 000 – E8 000.** Prices are indicative —
confirm them with local suppliers and cite the date you checked, since examiners
ask.

Why not a Raspberry Pi: the same code runs on one (CUPS instead of the Windows
spooler), but a laptop is already owned, has the printer drivers, and removes one
more unknown from the first demonstration. Keep the Pi in "future work" as the
low-cost production host.

---

## 4. Timeline

| Month | Focus | Milestone |
|---|---|---|
| 1 · Nov 2026 | Requirements, literature, architecture, data model, hardware | **Presentation 1** |
| 2 · Dec | Environment, accounts and roles, credit ledger | Working login and wallet |
| 3 · Jan 2027 | Subscriptions, PDF upload, pricing, job queue | Jobs priced and queued |
| 4 · Feb 2027 | Printer integration, invoices and approval | **Presentation 2** — first real print |
| 5 · Mar 2027 | Dashboard, reports, testing, billing matrix, UAT | Evaluation results |
| 6 · Apr 2027 | Report, corrections, demonstration | **Submission** |

The Gantt chart is the same information; put both in the report (the table in the
text, the chart as a figure).

---

## 5. Decisions to defend (and the one-line reason for each)

| Decision | Why |
|---|---|
| Print through the OS spooler, not the cable | A printer speaks PCL/PostScript, not PDF; the driver is the only component that knows the language. Python submits a job and watches the queue |
| Credits reserved, then captured | A printer can fail after accepting a job; holding credits makes a refund automatic and an overspend impossible |
| Manual mobile-money approval instead of a payment API | Production merchant access in Eswatini is not available to a student project; the workflow keeps real money and a real audit trail |
| One machine, no cloud | Removes hosting, inbound ports and internet dependency from the demonstration; the cost is redundancy, which will be stated as a limitation |

---

## 6. Risks to name (showing you have thought about them scores marks)

1. **Driver ignores colour or duplex** → mitigate by buying a duplex-capable
   printer and verifying with a printed test page before the demo.
2. **Printer fails during the demonstration** → keep a recorded video and a
   printed backup of the ledger check.
3. **Manual approval is a bottleneck** → two approvers, published office hours,
   and a dashboard counter so a pending invoice cannot be forgotten.
4. **Single machine is a single point of failure** → nightly backup plus a
   practised restore, documented as a limitation.

---

## 7. Next milestone

By presentation 2 the system should demonstrate: a member uploading a PDF and
seeing an exact price, the credits reserved and captured once, a real page printed
from the desk console, an invoice approved with credits landing automatically, and
`check_credits` reconciling. The screenshot checklist for that deck is in
[`docs/screenshots/README.md`](screenshots/README.md).
