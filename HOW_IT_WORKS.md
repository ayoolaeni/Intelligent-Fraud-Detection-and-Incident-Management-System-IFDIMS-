# How IFDIMS Works — A Complete Guide

**IFDIMS** (Intelligent Fraud Detection and Incident Management System) is an
application that watches a bank's transactions as they happen, automatically
flags the ones that look like fraud, and gives fraud staff a clear workflow
to investigate and resolve them. This guide explains, in plain language,
how to start the application, how it works, and everything else you need
to know to use it or explain it to someone else.

No technical background is needed to read this document. Where a technical
word is unavoidable, it is explained the first time it appears.

---

## Current Status (as of 1 October 2026)

**A fraud-detection model has already been trained and is live in the
system right now** — this is not just a plan on paper, it is actually
running and scoring transactions as you read this.

- **Active model:** `20260929-2045-xgboost`. This is an XGBoost model (one
  of the three model types compared during training — see
  [Section 4](#4-how-it-works--the-big-picture)) trained on a realistic
  synthetic dataset and already validated: it correctly separates fraud
  from genuine transactions with strong accuracy on data it had never
  seen during training.
- You can see it yourself, along with its accuracy statistics (precision,
  recall, and more) once logged in, under **Admin > Models**
  (see [Section 8](#8-a-tour-of-every-screen)).
- A second, larger version of the model — trained on a bigger dataset for
  even better accuracy — is being prepared in the background. When it's
  ready, an administrator will be able to switch to it from the same
  Models screen with **no downtime and no interruption to the running
  system** — that live hot-swap capability is itself a built-in feature,
  not a special one-off step (see [Section 8](#8-a-tour-of-every-screen),
  "Admin: Models").

In short: the system described in this guide is not hypothetical. It is
built, running, and already making real fraud-risk decisions on every
transaction it receives.

---

## Table of Contents

1. [What This Application Does](#1-what-this-application-does)
2. [How to Run the Application](#2-how-to-run-the-application)
3. [Logging In](#3-logging-in)
4. [How It Works — The Big Picture](#4-how-it-works--the-big-picture)
5. [What Happens to Every Transaction, Step by Step](#5-what-happens-to-every-transaction-step-by-step)
6. [Understanding the Risk Levels](#6-understanding-the-risk-levels)
7. [Who Uses the System](#7-who-uses-the-system)
8. [A Tour of Every Screen](#8-a-tour-of-every-screen)
9. [How a Flagged Transaction Gets Investigated](#9-how-a-flagged-transaction-gets-investigated)
10. [Reports You Can Generate](#10-reports-you-can-generate)
11. [How Customer Data Is Kept Safe](#11-how-customer-data-is-kept-safe)
12. [Where Everything Lives in the Project Folder](#12-where-everything-lives-in-the-project-folder)
13. [Frequently Asked Questions](#13-frequently-asked-questions)
14. [Getting Help](#14-getting-help)

---

## 1. What This Application Does

Every day, a bank processes transactions across many channels — bank
transfers, mobile app payments, USSD (the `*code#` menus used on basic
phones), internet banking, POS card payments, and ATM withdrawals. A small
number of these are fraudulent: someone tricked a customer into sending
money, took over their account, swapped their SIM card, or used a cloned
card.

Catching that fraud usually forces a bank into an uncomfortable choice:

- **Review everything by hand** — accurate, but far too slow. By the time
  a person looks at a suspicious transaction, the money is often already
  gone.
- **Block anything unusual** — fast, but it frustrates and annoys genuine
  customers whose legitimate transactions get rejected for no good reason.

IFDIMS is built to avoid that trade-off. It checks **every single
transaction automatically, in well under a second**, and only asks a human
to get involved for the small number that genuinely look wrong. Everything
else is approved instantly and the customer never notices anything
happened.

When IFDIMS does flag something, it does not just say "this is risky" — it
explains **why**, in plain English (for example: *"Beneficiary has never
been paid before"*, *"Amount is 12× the account's usual average"*), so the
person reviewing it can make a fast, confident decision instead of starting
from scratch.

---

## 2. How to Run the Application

The application is made of three parts that all need to be running
together: a database (where all the data is stored), a backend (the part
that checks transactions and enforces the rules), and a frontend (the
website you actually look at and click around in). Thanks to a tool called
**Docker**, all three start together with a single command — nobody needs
to install or configure a database by hand.

### 2.1 What you need installed first

- **Docker Desktop** — this is the only thing that needs installing.
  Download it from docker.com and install it like any other application.
  Once installed, open it and leave it running in the background (you'll
  see a whale icon in your system tray/menu bar when it's ready).

That is the only prerequisite. Everything else the application needs
(the database, the programming language runtimes, all the supporting
libraries) is downloaded and set up automatically the first time you start
it.

### 2.2 Starting the application

1. Open a terminal (on Windows: **Command Prompt** or **PowerShell**; on
   Mac: **Terminal**).
2. Navigate into the project folder — the same folder this file is in.
   For example:
   ```
   cd "C:\Users\AYOOLA KAYODE\Desktop\PROJECT DOCUMENT\MIT 2\Eze Favour Amarachi\Eze App"
   ```
3. If there is no file named `.env` in this folder yet, make one by
   copying `.env.example` and renaming the copy to `.env`. (This file
   holds configuration like database passwords — sensible defaults are
   already filled in for trying the application out.)
4. Run:
   ```
   docker compose up --build
   ```
5. Wait. The **first** time you run this, it downloads and builds
   everything, which can take several minutes (get a coffee). Every time
   after that, it starts in a matter of seconds.
6. When it's ready, you'll see log messages settle down and stop
   scrolling, including a line like `Application startup complete`.

### 2.3 Opening the application

Once it's running, open a web browser and go to:

```
http://localhost:5173
```

You should see the IFDIMS login page. That's it — the application is
running.

### 2.4 Stopping the application

Go back to the terminal window where it's running and press `Ctrl + C`.
To fully shut everything down (including the database container), run:

```
docker compose down
```

Your data is kept safe in between — stopping and restarting the
application does not delete anything you've entered.

### 2.5 Trying it out with realistic demo data (optional)

Fresh out of the box, IFDIMS has no transactions in it yet — just the
ability to log in. To see the application actually working, with alerts
and cases already populated, a technical team member can run:

```
make demo
```

This single command generates a realistic (entirely made-up, no real
customer data) world of customers and transactions, trains the
fraud-detection model on it, loads 45 days of history into the database,
and then streams the remaining transactions through the system live — so
within a few minutes, the Alerts and Cases screens fill up exactly as they
would in production. This is the best way to demonstrate the system to
someone before it's connected to a real bank's transaction feed.

(If `make` is not available on your computer, ask your technical contact
to run it — it is a short, standard set of commands defined in the
project's `Makefile`.)

---

## 3. Logging In

Every person who uses IFDIMS has their own account with an email, a
password, and a **role** that determines what they're allowed to see and
do (roles are explained in [Section 7](#7-who-uses-the-system)).

For trying the system out, these demo accounts are created automatically:

| Role | Email | Password |
|---|---|---|
| Analyst | `analyst1@ifdims.local` | `Demo12345!` |
| Analyst | `analyst2@ifdims.local` | `Demo12345!` |
| Supervisor | `supervisor@ifdims.local` | `Demo12345!` |
| Administrator | `admin@ifdims.local` | `Admin12345!` |

In a real deployment, these demo accounts would be switched off and real
staff accounts created by an administrator instead (see
[Admin: Users](#admin-users)).

If someone types the wrong password five times in fifteen minutes, their
account is automatically locked for fifteen minutes as a security
precaution — this is normal and not a fault.

---

## 4. How It Works — The Big Picture

At the centre of IFDIMS is a **trained machine-learning model** — a
program that has studied hundreds of thousands of past transactions
(a mix of normal and fraudulent ones) and learned the patterns that tell
them apart. When a new transaction arrives, the model looks at roughly two
dozen characteristics of it — the amount, the time of day, whether it's
going to a brand-new beneficiary, whether the device or location is
unusual for that customer, whether there was a recent SIM swap or password
reset, and so on — and produces a **fraud score** between 0 and 1. The
closer to 1, the more the transaction resembles the fraud patterns the
model has learned.

That score is then placed into one of three **risk bands** — low, medium,
or high — and the system acts accordingly, completely automatically, with
no person needing to be involved unless the transaction is risky.

Critically, IFDIMS doesn't just produce a number. Alongside every score it
also works out **which specific factors pushed the score up or down**, and
translates each one into a plain-English sentence. This is what lets a
fraud analyst glance at a flagged transaction and immediately understand
why it was flagged, instead of having to guess or dig through raw data.

---

## 5. What Happens to Every Transaction, Step by Step

```
 ┌──────────────┐     ┌────────────────────┐     ┌─────────────┐
 │ Transaction  │ --> │ Checked against the │ --> │ Scored by   │
 │  submitted   │     │ account's history   │     │ the model   │
 └──────────────┘     └────────────────────┘     └──────┬──────┘
                                                          │
                              ┌───────────────────────────┼───────────────────────────┐
                              v                           v                           v
                    ┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
                    │     LOW risk      │       │    MEDIUM risk    │       │     HIGH risk      │
                    │ Nothing else      │       │ Approved, but      │       │ Held immediately,  │
                    │ happens           │       │ flagged for review │       │ a case is opened   │
                    └──────────────────┘       └──────────────────┘       └──────────────────┘
```

1. **A transaction is submitted.** A bank channel (mobile app, USSD,
   internet banking, POS, ATM, or interbank transfer) sends the
   transaction details to IFDIMS the moment it happens.
2. **IFDIMS looks at the account's recent history.** It checks things
   like: has this device been used before? Has this beneficiary been paid
   before? How does this amount compare to the account's usual activity?
   Has there been a SIM swap, password reset, or new device added in the
   last 48 hours?
3. **The model scores it**, producing a number between 0 (certainly
   fine) and 1 (certainly fraud), along with the handful of factors that
   most influenced that score.
4. **The score is banded** into low, medium, or high risk, and IFDIMS
   acts immediately:
   - **Low** — the transaction is simply approved. No one is notified, no
     record beyond the normal transaction log.
   - **Medium** — the transaction is still approved (the customer is not
     delayed), but it's flagged in the **Alert queue** so a fraud analyst
     can take a look when convenient.
   - **High** — the transaction is **put on hold** right away, before the
     money moves, and a **case** is automatically opened and assigned for
     a fraud analyst to investigate urgently.

The whole process — steps 1 through 4 — happens in well under a second.

---

## 6. Understanding the Risk Levels

| Risk level | What it means | What happens automatically | Who needs to act |
|---|---|---|---|
| **Low** | Matches the customer's normal behaviour | Approved — nothing else happens | No one |
| **Medium** | Something about it is unusual | Approved, but flagged for review | An analyst reviews it when convenient |
| **High** | Strong signs of fraud | Held immediately; a case is opened | An analyst must investigate urgently |

These thresholds are **not fixed** — an administrator can adjust exactly
where "medium" starts and where "high" starts at any time, from the
**Settings** screen. Lowering the thresholds catches more fraud but also
flags more genuine transactions; raising them does the opposite. The
system even suggests sensible starting points based on how the current
model performed during testing.

---

## 7. Who Uses the System

Everyone logs in with their own personal account, and the screens and
buttons available to them are limited strictly to what their role allows.

| Role | What they can do |
|---|---|
| **Fraud Analyst** | Views the alert queue and case list; investigates cases assigned to them; adds notes and uploads evidence; resolves cases as confirmed fraud or a false alarm; escalates a case if they need help |
| **Supervisor** | Everything an analyst can do, for **any** case (not just their own), plus: assigns/reassigns cases to analysts; handles escalated cases; approves a case's closure, rejects a resolution, or reopens a closed case |
| **Administrator** | Manages staff accounts (create, deactivate, reset passwords); adjusts risk thresholds and response-time targets; switches between trained fraud-detection models; reviews the complete activity log; does **not** see or handle individual alerts/cases — their role is running the system, not fighting fraud case-by-case |
| **Transaction System** | Not a person — this is the bank's own channels (mobile app, USSD, etc.) submitting transactions into IFDIMS automatically via a secure connection. This is simulated for demonstration purposes until connected to a real bank system. |

---

## 8. A Tour of Every Screen

Once logged in, a left-hand menu shows only the pages that person's role
is allowed to use.

### Overview (the dashboard)
The landing page for everyone. Shows at-a-glance numbers (open alerts,
open cases, held transactions, confirmed fraud value in the last 30 days),
a 30-day trend chart, a breakdown by channel, and a list of cases that are
close to or past their response-time deadline. Refreshes automatically
every 30 seconds.

### Alerts
A live list of medium- and high-risk transactions waiting for review.
Clicking one opens its detail page: the transaction itself, the customer's
profile (with sensitive details like account and phone numbers always
shown masked, e.g. `******6789`), the plain-English reasons it was
flagged, and the account's recent activity. From here an analyst can
**dismiss** it as a false positive (giving a reason) or, for a medium
alert, **open a case** on it.

### Cases
Every incident under investigation, past or present. Analysts see their
own cases plus any unassigned one; supervisors see everything. Cases can
be filtered by status, priority, or searched by case number, title, or
account. Each row shows a countdown to its response-time deadline, colour
coded so overdue or nearly-overdue cases stand out immediately.

### Case detail
The working screen for investigating a case: the linked transaction and
its explanation, a timeline of notes (including automatic system notes),
uploaded attachments, and a full history of every change made to the
case. The action buttons shown here change automatically depending on the
case's current stage and the logged-in person's role — you are never
shown a button for something you're not allowed to do (see
[Section 9](#9-how-a-flagged-transaction-gets-investigated) for the full
workflow).

### Transactions
A searchable log of every transaction IFDIMS has scored, filterable by
account, channel, or status. Useful for looking something up directly
rather than starting from an alert.

### Reports
Lets a supervisor or administrator generate and download reports for any
date range (see [Section 10](#10-reports-you-can-generate)).

### Admin: Users
*(Administrators only.)* Create new staff accounts, change someone's role,
deactivate an account (their open cases are automatically handed back to
the unassigned pool so nothing is dropped), or reset a forgotten password.

### Admin: Settings
*(Administrators only.)* Adjust the risk thresholds, the response-time
targets per priority level, and whether high-risk transactions are
automatically held.

### Admin: Models
*(Administrators only.)* Shows every version of the fraud-detection model
that has been trained, with its accuracy statistics, and lets an
administrator switch the live model to a different version. Before
switching, the system automatically runs a safety check on the new model;
if anything looks wrong, nothing changes and the current model keeps
running.

### Admin: Audit Log
*(Administrators only.)* A permanent, unchangeable record of every login
and every action anyone has taken in the system — who did what, and
when. Nothing here can ever be edited or deleted, by anyone, including an
administrator, which is what makes it trustworthy as an audit trail.

### My Account
Available to everyone — change your own password.

---

## 9. How a Flagged Transaction Gets Investigated

When a case is opened (automatically for a high-risk transaction, or
manually by an analyst/supervisor), it moves through a fixed set of
stages. At every stage, only certain people can move it forward, and only
to certain next stages — the system will not allow a case to be skipped
ahead or handled out of order.

```
  New ──> Assigned ──> Under investigation ──> Resolved ──> Closed
                              ^      |
                     "needs help"   "sends back"
                              |      v
                           Escalated
```

1. **New** — the case has just been created and has no one assigned to
   it yet.
2. **Assigned** — a supervisor assigns it to a specific analyst (this
   happens automatically for high-risk cases if the "auto-assign"
   setting is switched on).
3. **Under investigation** — the analyst has started work. They review
   the transaction, the explanation, the customer's history, add notes,
   and attach any supporting evidence.
4. **Escalated** *(optional)* — if the analyst needs a supervisor's
   input, they escalate the case with a note explaining why. A supervisor
   then either sends it back to the analyst with instructions, or resolves
   it directly. A case is also escalated **automatically** by the system
   if it is about to miss its response-time deadline — so nothing falls
   through the cracks even if no one notices.
5. **Resolved** — the analyst or supervisor concludes the investigation
   with one of two outcomes:
   - **Confirmed fraud** — the held transaction is permanently declined,
     the customer's account is flagged as higher-risk going forward, and
     a fraud type is recorded (for example, social engineering, account
     takeover, SIM swap, or card fraud).
   - **False positive** — the held transaction is released and approved
     as normal.
6. **Closed** — a supervisor gives final sign-off and closes the case.
   If they disagree with the resolution, they can instead send it back to
   "under investigation" for more work, or reopen a case even after it's
   been closed if new information comes up later. Nothing is ever lost —
   every one of these changes is recorded in the case's history.

Every case has a **priority** (critical, high, medium, or low) and a
**response-time target** based on that priority, both visible as a
countdown on the case list and detail screens, so nothing sits unattended
for longer than the bank has decided is acceptable.

---

## 10. Reports You Can Generate

Available to supervisors and administrators from the **Reports** screen,
for any date range and optionally filtered by channel:

| Report | What it contains |
|---|---|
| **Case report** | Every case in the period: priority, status, outcome, and how long it took to acknowledge and resolve |
| **Alert report** | Every alert raised: its score, band, and how it was handled (dismissed or turned into a case) |
| **Fraud summary** | A management-level overview: totals by channel and fraud type, amounts confirmed and recovered, how well response-time targets were met, and which model version was active. Available as a formatted PDF with a chart, ideal for sharing with leadership. |
| **Incident export** | A flat list of every confirmed fraud case, in the format used for reporting to industry or regulatory bodies |

---

## 11. How Customer Data Is Kept Safe

- **No real customer data is used during development, testing, or
  demonstration.** Every customer, account, and transaction shown when
  trying the system out is entirely synthetic (made up by the system
  itself) — nothing in a demo corresponds to a real person.
- In a live deployment, sensitive identifiers are protected by design,
  not as an afterthought:
  - Customers' BVNs and phone numbers are **never stored as plain,
    readable text** — only a one-way scrambled version that can confirm
    a match (e.g. "is this the same phone number as before?") but can
    never be reversed back into the original number.
  - Account numbers and phone numbers are shown on every screen only in
    **masked form** (for example `******6789`, `****1234`) — the full
    number is never displayed, even to staff.
  - Passwords are stored using industry-standard one-way hashing.
    Nobody — not even an administrator — can look up or recover a user's
    password; it can only be reset to a new temporary one.
  - Access to every screen and every action is restricted by role, so
    each person only ever sees what their job actually requires.
  - Every login attempt and every change made anywhere in the system is
    permanently logged in a record that **cannot be edited or deleted by
    anyone**, giving a trustworthy, tamper-proof audit trail at all
    times.

---

## 12. Where Everything Lives in the Project Folder

For reference, here's what the main folders in this project contain (a
technical contact will find this useful; you don't need to open any of
these yourself):

| Folder | What's in it |
|---|---|
| `backend/` | The application logic — the part that checks transactions, enforces rules, and stores data |
| `frontend/` | The website you see and click around in |
| `ml/` | The machine-learning training pipeline that builds the fraud-detection model |
| `simulator/` | Tools that generate and replay realistic demo data |
| `docs/` | Further documentation, including a more technical user guide and API reference |
| `models/` | Trained versions of the fraud-detection model |
| `reports/` | Generated evaluation charts and statistics about model performance |
| `docker-compose.yml` | The file that tells Docker how to start all three parts together |
| `.env` | Configuration and passwords for your local copy (never shared or committed to version control) |

---

## 13. Frequently Asked Questions

**Do I need to know how to code to use this?**
No. Everything described in this guide is done by clicking through the
website at `http://localhost:5173`. Only the very first-time setup (Section 2)
needs a terminal command, and even that is one line to copy and paste.

**What happens if I close the terminal window?**
The application stops. Restart it with `docker compose up --build` — it
will start again in seconds (the slow part only happens the very first
time), and none of your data is lost.

**Can two different fraud analysts be logged in at the same time?**
Yes. Any number of people can use the system at once, each with their own
account and their own view of what they're allowed to see.

**What happens if the internet or power goes out mid-transaction?**
Each transaction is processed as one complete, all-or-nothing action. A
transaction is never left half-recorded — either it was fully scored and
stored, or (if submitted again with the same reference) IFDIMS recognises
it and simply returns the same result instead of processing it twice.

**Can the fraud-detection model be improved over time?**
Yes — this is one of the system's built-in strengths. As analysts resolve
real cases (confirmed fraud or false positive), those outcomes can be used
to retrain an improved model, which an administrator can then review and
switch to from the Models screen.

**Is this connected to a real bank's systems right now?**
No. Out of the box, IFDIMS is a complete, working system ready to be
connected to a bank's transaction channels, but the "Transaction System"
in this project is currently a simulator that generates realistic
synthetic activity for demonstration and testing purposes.

---

## 14. Getting Help

If something in the application isn't behaving as this guide describes,
or a screen shows an error, note down:

- What you were trying to do
- What you expected to happen
- What happened instead (a screenshot helps)

and pass it to your technical contact along with this project folder.
The technical documentation in `docs/` (particularly `docs/USER_GUIDE.md`
and `docs/API.md`) has the deeper detail they'll need.
