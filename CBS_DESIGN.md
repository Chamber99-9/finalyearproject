# Core Banking Simulator (CBS) — Design for Sajilo Loan

*A realistic Core Banking Simulator that the Sajilo Loan LOS integrates with. The LOS handles origination (KYC, application, underwriting, approval); the CBS is the **system of record for money** — customers, accounts, the general ledger, disbursement, repayment schedules, interest accrual, and end-of-day processing. This mirrors how a commercial bank separates its Loan Origination System from its Core Banking System (Finacle / Flexcube / T24 style). Design only — no code.*

---

## 0. Why split LOS and CBS?

In real banks these are two systems:

- **LOS (originate)** — sales/credit workflow: leads, KYC, documents, credit scoring, approval, sanction terms. It never holds balances or posts to the ledger.
- **CBS (service)** — the accounting engine: it opens accounts, moves money, keeps the double-entry general ledger, accrues interest, runs the day-end batch, and is the single source of truth for balances.

So Sajilo Loan keeps everything it already does **up to approval**, then hands the approved sanction to the CBS. From disbursement onward, the CBS owns the loan. The LOS keeps only a **reference** (`cbs_loan_account_no`) and *reads* servicing state from the CBS for its dashboards. The existing `loan_accounts` and `payments` collections in the LOS are effectively replaced by the CBS.

---

## 1. Architecture

Two services, clear boundary, integrated over a versioned API (plus events).

```
   Customer / Officer / Admin (browser)
                │
        Sajilo Loan LOS  (Next.js BFF + FastAPI + MongoDB)
        - KYC, application, underwriting, approval, documents
        - stores cbs_customer_id, cbs_loan_account_no
                │  REST (service-to-service, signed, idempotent)   ▲ webhooks/events
                ▼                                                   │
        Core Banking Simulator (CBS)  (FastAPI + PostgreSQL)
        ┌───────────────────────────────────────────────────┐
        │ API layer (auth: mTLS or signed service JWT/HMAC)  │
        ├───────────────────────────────────────────────────┤
        │ Domain services:                                   │
        │  CIF · Account · LoanProduct · Loan · Schedule ·   │
        │  Interest/Accrual · Posting Engine · Transaction · │
        │  Standing-Instruction · Classification (DPD/NPL) · │
        │  EOD Batch · Business-Calendar                     │
        ├───────────────────────────────────────────────────┤
        │ Posting Engine  ── the core: every money event     │
        │ becomes a BALANCED double-entry journal            │
        ├───────────────────────────────────────────────────┤
        │ PostgreSQL (ACID) — GL, journals, accounts, sched. │
        └───────────────────────────────────────────────────┘
```

Key decisions, and why they're realistic:

- **PostgreSQL for the CBS** (not Mongo). Money requires ACID transactions, foreign keys, and a constraint that *every journal balances*. A relational store is the correct tool for a ledger; the LOS can stay on MongoDB (document-heavy). Real banks run their core on relational/transactional stores for exactly this reason.
- **A single Posting Engine.** Nothing writes a balance directly. Every financial event (disbursement, EMI, fee, accrual, penalty, reversal) is expressed as a **journal entry** whose debit and credit lines sum to zero. Balances are derived from postings. This guarantees the books always reconcile.
- **Service-to-service auth**, not user JWTs: the LOS calls the CBS with a signed service credential (mutual TLS, or an HMAC-signed request / client-credentials JWT). Every state-changing call carries an **Idempotency-Key** so retries never double-post.
- **Maker-checker (dual control)** on high-risk operations (disbursement, manual GL adjustments, write-offs): one service/officer initiates, another authorizes.
- **Events/webhooks** back to the LOS: `loan.disbursed`, `emi.due`, `emi.paid`, `loan.overdue`, `loan.npl`, `loan.closed` — so the LOS can update its UI, send reminders, or trigger blacklist review without polling.
- **A business date + EOD batch.** The CBS has its own clock ("business date") and a day-end job. Interest accrues and dues are processed by the batch, exactly like a real core. (This also cleanly replaces your current "testing calendar" — you advance the CBS business date and run EOD.)

---

## 2. Database design (CBS — PostgreSQL)

### 2.1 Master / reference

- **cif** (Customer Information File): `cif_no` (PK), `los_user_id` (link to LOS), name, dob, citizenship_no, pan, phone, kyc_status, created_at. One master customer record; both deposit and loan accounts hang off it.
- **branches**: `branch_code`, name (single branch is fine for a simulator; still model it — account/transaction numbering uses it).
- **loan_products**: `product_code`, name, `gl_asset_account`, `gl_interest_income_account`, `gl_fee_income_account`, `gl_penal_income_account`, interest_method (reducing balance), day_count (Actual/365), penal_rate, dpd_grace_days, provisioning_matrix. Product config drives everything — no rates hard-coded in loans.

### 2.2 Accounts (sub-ledgers)

- **deposit_accounts (CASA)**: `account_no` (PK), `cif_no` (FK), type (savings/current), `gl_account` (customer deposit control), balance, status (active/dormant/closed), opened_at. This is where disbursement lands and EMIs are auto-debited from.
- **loan_accounts**: `loan_account_no` (PK), `cif_no` (FK), `product_code` (FK), sanction_amount, disbursed_amount, interest_rate, tenure_months, emi_amount, `disbursement_account_no` (FK → CASA), principal_outstanding, interest_accrued, penal_accrued, next_due_date, installments_paid, installments_total, dpd (days past due), classification (pass/watchlist/substandard/doubtful/loss), status, disbursed_at, closed_at. **`principal_outstanding` is real principal**, not "total repayable."

### 2.3 Schedule

- **repayment_schedules**: `schedule_id`, `loan_account_no` (FK), version (re-generated on prepayment/restructure).
- **schedule_installments**: `installment_no`, `schedule_id` (FK), due_date, opening_principal, principal_due, interest_due, emi_due, closing_principal, status (pending/paid/partially_paid/overdue), paid_date. This is the amortization table — the contractual promise.

### 2.4 General Ledger (the accounting core)

- **gl_accounts** (Chart of Accounts): `gl_code` (PK), name, type (ASSET/LIABILITY/INCOME/EXPENSE/CONTRA), parent_code, normal_side (Dr/Cr). Balances are **derived** from journal lines (or kept as a materialized `gl_balances` for speed and reconciled to postings).
- **journal_entries** (transaction header): `journal_id`, business_date, value_date, posting_date, `transaction_ref`, narration, source (disbursement/emi/fee/accrual/penalty/reversal), status (posted/reversed), maker, checker.
- **journal_lines**: `line_id`, `journal_id` (FK), `gl_code` (FK), `sub_account_no` (loan/CASA account this line touches, nullable), dr_amount, cr_amount. **Constraint: for each `journal_id`, Σ dr = Σ cr** (enforced in-app and, ideally, by a deferred DB check). Lines are never edited or deleted — corrections are contra postings.

### 2.5 Operational

- **transactions**: business-level record referencing a `journal_id` — `transaction_ref`, loan/deposit account, type, amount, channel, idempotency_key, created_at. (The journal is the accounting truth; the transaction is the business view.)
- **standing_instructions**: auto-debit setup (loan → source CASA, on due date).
- **classification_history**: DPD/NPL snapshots per loan per EOD run (for audit + provisioning).
- **business_calendar**: current `business_date`, holidays. **idempotency_keys**: dedupe table. **event_outbox**: events pending delivery to the LOS (transactional outbox pattern so events aren't lost).

### 2.6 Chart of Accounts (illustrative)

| GL code | Name | Type | Normal side |
|---|---|---|---|
| 1100 | Cash / Nostro | Asset | Dr |
| 1200 | Loans & Advances — Personal | Asset | Dr |
| 1210 | Loans & Advances — Home / Auto … | Asset | Dr |
| 1300 | Interest Receivable (accrued) | Asset | Dr |
| 1900 | Loan Loss Provision | Contra-asset | Cr |
| 2100 | Customer Deposits (CASA) | Liability | Cr |
| 2200 | Disbursement Suspense / Clearing | Liability | Cr |
| 4100 | Interest Income | Income | Cr |
| 4200 | Fee Income (processing) | Income | Cr |
| 4300 | Penal Interest Income | Income | Cr |
| 5100 | Provisioning Expense | Expense | Dr |

Sub-ledgers (each loan / each CASA) roll up into their GL control accounts; the sum of sub-ledger balances must equal the GL control balance (reconciliation).

---

## 3. API design (CBS)

RESTful, versioned (`/v1`), service-authenticated, idempotent. Every POST takes an `Idempotency-Key` header and supports an optional `value_date`.

**Customer & accounts**
- `POST /v1/cif` — create/find customer (from LOS). `GET /v1/cif/{cif_no}`
- `POST /v1/deposit-accounts` — open a CASA account for a CIF. `GET /v1/deposit-accounts/{no}/balance`

**Loan account lifecycle**
- `POST /v1/loans` — open a loan account from an approved LOS sanction (amount, rate, tenure, product, disbursement account). Returns `loan_account_no`, status `PENDING_DISBURSEMENT`.
- `POST /v1/loans/{no}/disburse` — disburse (maker-checker). Posts GL, generates schedule, funds CASA → status `ACTIVE`.
- `GET /v1/loans/{no}` — full loan state (outstanding, dpd, classification, next due).
- `GET /v1/loans/{no}/schedule` — the amortization table.
- `POST /v1/loans/{no}/repayments` — apply a repayment (from auto-debit or a customer payment credited to CASA).
- `POST /v1/loans/{no}/prepay` — partial prepayment (recomputes schedule).
- `POST /v1/loans/{no}/foreclose` — full settlement / early closure.
- `POST /v1/loans/{no}/waive` / `restructure` — (maker-checker) fee/penalty waiver, reschedule.

**Transactions & ledger**
- `POST /v1/transactions` — generic posting (used internally; exposed for adjustments under maker-checker).
- `POST /v1/transactions/{ref}/reverse` — contra reversal (never a delete).
- `GET /v1/transactions/{ref}` / `GET /v1/loans/{no}/transactions`
- `GET /v1/gl/accounts` · `GET /v1/gl/{code}/entries` · `GET /v1/gl/trial-balance` — must always balance.

**System / batch**
- `GET /v1/system/business-date` · `POST /v1/system/business-date/advance`
- `POST /v1/eod/run` — run end-of-day (accrual → due processing → DPD/NPL → provisioning → statements).

**Events to LOS (webhooks / outbox):** `loan.disbursed`, `emi.due`, `emi.paid`, `emi.overdue`, `loan.npl`, `loan.closed`.

---

## 4. Data flow (LOS ↔ CBS)

1. **Origination (LOS only).** KYC, application, documents, credit score, approval. No money moves.
2. **On approval**, LOS → CBS: `POST /cif` (ensure customer) → `POST /deposit-accounts` (or reuse) → `POST /loans` (open loan account with the sanctioned terms). LOS stores `cbs_customer_id` + `cbs_loan_account_no` on the application.
3. **Disbursement** (maker-checker): LOS/officer → `POST /loans/{no}/disburse`. CBS posts the GL entry, credits the customer CASA, generates the schedule, sets the loan `ACTIVE`, and emits `loan.disbursed`. LOS marks the application "disbursed."
4. **Servicing.** Repayments (auto-debit or customer-initiated credit to CASA) hit the CBS; the CBS posts transactions, updates the schedule and outstanding, and emits `emi.paid`. The LOS dashboard **reads** balances/schedule from the CBS.
5. **EOD batch** in the CBS accrues interest, processes due installments, rolls DPD, classifies NPL, and books provisions — emitting `emi.due` / `emi.overdue` / `loan.npl`. The LOS reacts (reminders, blacklist review).
6. The LOS remains the **origination + customer-experience** layer; the CBS is the **accounting truth**.

---

## 5. Loan lifecycle (CBS)

`PENDING_DISBURSEMENT` → (disburse) → `ACTIVE / CURRENT` → repayments reduce principal → if a due date passes unpaid: `OVERDUE` with a DPD counter and penal accrual → sustained delinquency reclassifies to **NPL** buckets (`SUBSTANDARD` → `DOUBTFUL` → `LOSS`) with provisioning → terminal states: `CLOSED_REPAID`, `FORECLOSED`, `WRITTEN_OFF`, or `RESTRUCTURED` (new schedule).

**Delinquency / NRB-style classification (illustrative):** Pass (current, ~1% provision) → Watchlist (~5%) → Substandard (overdue 3–6 months, 25%) → Doubtful (6–12 months, 50%) → Loss (>12 months, 100%). Each EOD recomputes DPD and moves the loan between buckets, posting the provision delta.

---

## 6. Account lifecycle (CASA)

`ACTIVE` (opened at/near disbursement, receives the loan proceeds and funds auto-debits) → `DORMANT` (no activity for a configured period) → `CLOSED` (zero balance, on request). The CASA is the customer's money account; the loan account is the bank's asset. Keeping them separate is what makes disbursement and EMI real double-entry events rather than a single balance tweak.

---

## 7. Disbursement workflow

1. LOS calls `POST /loans` with the sanction → CBS creates the loan account (`PENDING_DISBURSEMENT`).
2. LOS/officer calls `POST /loans/{no}/disburse` (Idempotency-Key). **Maker-checker:** initiated by one actor, authorized by another.
3. Posting Engine books a balanced journal (net-of-fee example, principal P, processing fee F):

   | GL | Dr | Cr |
   |---|---|---|
   | 1200 Loans & Advances (loan sub-ledger) | P | |
   | 2100 Customer Deposits (CASA) | | P − F |
   | 4200 Fee Income | | F |

   (Σ Dr = P, Σ Cr = P.) The customer *owes* the full P; their CASA rises by the net; the bank books fee income.
4. CBS sets `disbursed_amount`, `principal_outstanding = P`, generates the **amortization schedule**, sets status `ACTIVE`, and emits `loan.disbursed`.
5. A **standing instruction** is created (auto-debit the CASA on each due date).

---

## 8. EMI workflow

- The schedule fixes each installment's `due_date`, `principal_due`, `interest_due`, `emi_due` (reducing-balance amortization).
- **On the due date (EOD),** the batch attempts auto-debit from the CASA:
  - If funds are sufficient → post the EMI (see §10), mark the installment `PAID`, reduce `principal_outstanding`, advance `next_due_date`.
  - If insufficient → mark `OVERDUE`, start/continue DPD counting, accrue **penal interest**, emit `emi.overdue`.
- **Customer-initiated payment** (via the LOS UI): the customer credits the CASA (this is where your existing payment channel — eSewa QR / bank transfer — lands funds), then the CBS applies it to the earliest unpaid installment.
- **Prepayment** reduces `principal_outstanding` immediately and **regenerates the schedule** (new version) — real interest savings, unlike a flat balance decrement.
- **Foreclosure** = pay outstanding principal + accrued interest + charges, then `CLOSED`.

---

## 9. Ledger workflow

Double-entry is the backbone:

- Every money event → one **journal entry** (header) with ≥2 **journal lines** where **Σ debits = Σ credits**. Enforced; a journal that doesn't balance is rejected atomically.
- **Balances are derived** from journal lines; a materialized balance may be cached but must reconcile to the postings.
- **Sub-ledger ↔ GL reconciliation:** the sum of all loan sub-ledger balances = GL 1200/1210 control; sum of CASA balances = GL 2100. A daily reconciliation report proves they match.
- **Value date vs posting date:** interest and back-dated entries use a value date; the posting date is when it hit the books.
- **No edits or deletes** — corrections are **contra (reversal) entries** that reference the original. The **trial balance** (Σ all Dr = Σ all Cr across the GL) must always be zero-net.

---

## 10. Transaction workflow

1. **Request** (internal from a domain service, or external adjustment) with an `Idempotency-Key`.
2. **Dedupe:** if the key was seen, return the prior result (no double-post).
3. **Validate:** account exists/active, sufficient balance (for debits), within limits, business date open.
4. **Post:** the Posting Engine builds the balanced journal and commits it **atomically** with the balance/schedule updates in a single DB transaction (all-or-nothing).
5. **Emit** an event via the transactional **outbox** (so the LOS is notified reliably).
6. **Return** a `transaction_ref` (e.g. `BRANCH-YYYYMMDD-SEQ`).
7. **Reversal:** never delete — post a mirror-image contra journal referencing the original `transaction_ref`; the original is marked `REVERSED`.

**Worked journals:**

*Daily interest accrual (EOD), day's interest I:* Dr 1300 Interest Receivable I / Cr 4100 Interest Income I.

*EMI paid (EMI E = principal Pp + interest Pi), auto-debit from CASA:*

| GL | Dr | Cr |
|---|---|---|
| 2100 Customer Deposits (CASA) | E | |
| 1200 Loans & Advances | | Pp |
| 1300 Interest Receivable | | Pi |

(Σ Dr = E = Σ Cr.) Principal outstanding falls by `Pp`; the accrued interest booked earlier is cleared.

*Penal interest on overdue (accrued):* Dr 1300 (penal) / Cr 4300 Penal Interest Income.

*NPL provisioning (EOD):* Dr 5100 Provisioning Expense / Cr 1900 Loan Loss Provision (contra-asset), for the provision delta.

*Write-off:* Dr 1900 Loan Loss Provision / Cr 1200 Loans & Advances.

---

## 11. How this maps onto your current LOS

- Keep everything up to **approval** in Sajilo Loan unchanged (KYC, application, documents, credit score, officer review).
- Replace the LOS's own `loan_accounts` + `payments` with **CBS ownership**; the LOS keeps `cbs_customer_id` + `cbs_loan_account_no` and reads servicing state via the CBS API.
- Your existing "testing calendar" becomes the CBS **business-date + EOD** control (advance the date, run EOD, watch accrual/dues/NPL fire).
- Your existing payment channel (eSewa QR / transfer) becomes the way funds **land in the customer's CASA**; the CBS then applies them to the loan — so payments stay, but the *accounting* moves into the core where it belongs.

This gives you a genuinely bank-shaped system: an origination platform (LOS) talking to a core banking engine (CBS) that keeps a real double-entry ledger, accrues interest daily, runs a day-end batch, and classifies NPLs — which is exactly the separation commercial banks operate.
