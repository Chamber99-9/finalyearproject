# Production Payment System Design — Khalti Sandbox (Sajilo Loan)

*Design only — no code. Target: a production-ready EMI payment system for this Nepal-based LOS using **only Khalti (KPG-2) Sandbox**. It preserves the existing layered architecture (routes → services → models → schemas + Next.js BFF proxies) and **reuses the existing payment code** (`payment_service.py`, `payment_gateways.py`, `loan_account_service.record_payment`, `PaymentCheckout`/`PaymentReturn`) rather than introducing a second implementation.*

---

## Guiding principles

- **One gateway: Khalti Sandbox.** No Stripe/PayPal/Razorpay/foreign rails. `payment_provider` is forced to `khalti`; the built-in `mock` path is retained **only** for automated tests / local dev (`app_env == "development"`).
- **Reuse, don't duplicate.** The intent → redirect → **server-side lookup** → idempotent settlement pipeline already exists (`initiate_payment`, `verify_payment`, `_settle`, `khalti_initiate`, `khalti_lookup`). We harden and extend these functions; we do **not** write new gateway or settlement logic beside them.
- **Khalti's own model drives the flow.** KPG-2 is *initiate → redirect → lookup* (not a push webhook). The **authoritative source of truth is the `lookup` call** — redirect params are never trusted. This is already how `verify_payment` works.
- **Fix the security gaps** identified in the architecture review: remove customer self-settlement in production, validate the webhook secret, add duplicate/replay protection, and add officer/admin reconciliation.

---

## 1. Payment workflow (generic)

```
Customer                Frontend (BFF)            Backend                    Khalti Sandbox
   |  Pay                     |                       |                            |
   |------------------------->| POST /loans/{id}/payments/initiate               |
   |                          |---------------------->| initiate_payment()         |
   |                          |                       | - validate active/owned loan
   |                          |                       | - reuse open PENDING intent if any
   |                          |                       | - amount = EMI (capped at outstanding)
   |                          |                       | khalti_initiate() --------->| create payment
   |                          |                       |<-- {pidx, payment_url} -----|
   |                          |<-- {checkout_url} ----| store pidx, status=PENDING  |
   |  redirect to Khalti  <---|                       |                            |
   |=========================================== pay on Khalti hosted page =========>|
   |  redirect back to /payments/return?pidx=..&status=..                          |
   |------------------------->| POST /payments/verify {pidx}                       |
   |                          |---------------------->| verify_payment()           |
   |                          |                       | khalti_lookup(pidx) ------->| authoritative status
   |                          |                       |<-- Completed/Pending/... ---|
   |                          |                       | if Completed -> _settle() (idempotent)
   |                          |                       |   amount-integrity check
   |                          |                       |   record_payment() on loan |
   |                          |<-- receipt payload ---| snapshot receipt           |
   |  Receipt   <-------------|                       |                            |
```

**Key properties (all already partly present, to be completed):**
- The customer is redirected to Khalti's **hosted** checkout (`payment_url`) — no card/wallet data ever touches our servers.
- Settlement only ever happens after a **server-side `lookup`** returns `Completed`.
- `_settle` is **idempotent** (re-verifying a settled payment is a no-op) and **snapshots** the post-payment loan state onto the payment for a self-contained receipt.

---

## 2. EMI payment workflow (loan-specific)

An EMI payment is one installment against an **active** loan the customer owns.

1. **Eligibility.** `initiate_payment` already rejects non-existent, non-owned, or non-active loans. Add: reject if the loan is `defaulted`/`completed`, and compute the **installment being paid** = `installments_paid + 1`.
2. **Amount.** `amount = min(monthly_emi, outstanding_balance)` (final installment absorbs rounding — already the behavior in `record_payment`). Sent to Khalti in **paisa** (`amount * 100`), as `khalti_initiate` already does.
3. **Duplicate guard (new).** Before creating a new intent, reuse any existing **open PENDING** intent for the same `(loan_id, installment_number)` — return its `checkout_url`/`pidx` instead of creating a second one.
4. **Redirect & pay** on Khalti sandbox.
5. **Verify & apply.** On return, `verify_payment` → `khalti_lookup` → on `Completed`, `_settle` calls `record_payment`, which reduces `outstanding_balance`, increments `installments_paid`, resets `missed_installments`, advances `next_due_date`, and marks the loan `completed` when fully repaid.
6. **Receipt** is rendered from the snapshot.

**Reused as-is:** `loan_account_service.record_payment` (no changes to loan mechanics), `emi_service` (no changes).

---

## 3. Khalti Sandbox integration

Everything Khalti-specific stays in the existing `app/services/payment_gateways.py` (`khalti_initiate`, `khalti_lookup`, `_map_status`, `GatewayError`). No new gateway module.

- **Base URL:** `khalti_base_url = https://dev.khalti.com/api/v2` (already the sandbox default in `config.py`).
- **Auth:** `Authorization: Key <KHALTI_SECRET_KEY>` (sandbox test key). Already implemented in `_auth_headers`.
- **Initiate:** `POST /epayment/initiate/` with `return_url`, `website_url`, `amount` (paisa), `purchase_order_id` (= our payment id), `purchase_order_name`, `customer_info`. Returns `{pidx, payment_url}`. Already implemented.
- **Lookup:** `POST /epayment/lookup/ {pidx}` → authoritative status (`Completed`, `Pending`, `Initiated`, `Refunded`, `Expired`, `User canceled`). Already implemented; extend `_map_status` to explicitly map `Expired`/`User canceled`/`Initiated` → `failed`/`pending`.
- **Status→internal mapping (extend `_map_status`):**
  | Khalti status | Internal | Action |
  |---|---|---|
  | Completed | success | settle loan, receipt |
  | Pending / Initiated | pending | keep intent open, allow re-verify |
  | User canceled / Expired / Refunded / Partially refunded | failed | mark failed + `failure_reason`, no loan change |
- **Config:** set `payment_provider=khalti`, `khalti_secret_key=<sandbox key>`, `payment_return_url_base`/`payment_website_url` = deployed frontend origin.

---

## 4. Payment verification

- **Authoritative:** `verify_payment` → `khalti_lookup` is the single settlement trigger. The redirect `status` param is only used for UX messaging, never for settlement.
- **Amount integrity (new):** in `_settle` (or `verify_payment` before settling), assert `khalti total_amount == intent.amount_paisa`. On mismatch, mark the payment `failed` with `failure_reason="amount_mismatch"`, do **not** touch the loan, and raise a flag for officer review.
- **Idempotency:** re-calling `verify` after settlement returns the settled payment unchanged (already guarded by `status == SUCCESS`).
- **Optional hardening (Khalti webhook):** KPG-2 sandbox is redirect+lookup, so the existing generic `/payments/webhook` (HMAC-signed) is **optional**. If enabled later, keep the current signature verification, add a **timestamp/nonce for replay protection**, and still confirm via `lookup` before settling. Otherwise the webhook route is disabled in production.

---

## 5. Transaction records

Reuse the existing `payments` collection as the transaction ledger (no new collection). **Formalize** the document via a new `app/models/payment.py` builder (matching the project convention that every collection has a model builder) with these fields — extending, not replacing, today's inline dict:

| Field | Purpose | Status |
|---|---|---|
| `loan_id`, `applicant_id`, `amount` | ownership + value | exists |
| `installment_number` | which EMI this pays (duplicate guard) | **new** |
| `amount_paisa` | exact value sent to Khalti | **new** |
| `provider` = `"khalti"` | rail | exists |
| `provider_ref` (= Khalti `pidx`) | gateway reference | exists |
| `khalti_transaction_id` | from lookup, on success | **new** |
| `idempotency_key` | intent de-dup | exists |
| `status` (pending/success/failed) | lifecycle | exists |
| `failure_reason` | canceled/expired/amount_mismatch | **new** |
| `receipt_number` | human receipt id (e.g. `SL-RCPT-XXXXXX`) | **new** |
| `outstanding_after`, `installments_paid_after`, `installments_total`, `next_due_date` | receipt snapshot | exists |
| `lookup_raw` | last Khalti lookup payload (audit) | **new** |
| `created_at`, `updated_at`, `settled_at` | timestamps | exists |

**Lifecycle audit:** reuse the existing `audit_logs` collection (via `audit_service.create_audit_log`) to record `payment_initiated`, `payment_verified`, `payment_settled`, `payment_failed`, `payment_cancelled` — no new events collection.

---

## 6. Receipt generation

- **Data:** already produced as a self-contained snapshot by `_settle`. Add a stable `receipt_number` at settlement.
- **View:** the existing `Receipt` component (`PaymentCheckout.tsx`, reused by `PaymentReturn.tsx`) already renders amount, status, date, transaction ref, method, remaining balance, installments, next due, and Print/Save. Add `receipt_number` and Khalti `transaction_id` to it.
- **Optional PDF (later phase):** a downloadable PDF receipt can be generated server-side on demand from the same snapshot (reusing the project's PDF tooling) — not required for MVP.

---

## 7. Failed / cancelled payment handling

- **No loan mutation** ever occurs unless `lookup` returns `Completed`.
- On `User canceled` / `Expired` / `Refunded`: `verify_payment` sets `status=failed` + `failure_reason`, leaving the loan untouched. The return page shows a clear "payment not completed — try again" state with a re-pay button (a fresh intent, or the reused open pending intent).
- On `Pending`/`Initiated`: keep the intent open; the return page shows "awaiting confirmation" and allows re-verify.
- **Stale intents:** a scheduled job (ties into the missing-scheduler debt) can expire PENDING intents older than N minutes by calling `lookup` once and closing them `failed` if still unpaid — prevents dangling duplicates.

---

## 8. Duplicate payment prevention

Layered defense:
1. **Reuse open intent:** `initiate_payment` returns the existing open PENDING intent for `(loan_id, installment_number)` instead of creating another.
2. **Partial unique index:** `payments` unique index on `(loan_id, installment_number)` **where `status = "success"`** — a given installment can be settled at most once, enforced by the DB.
3. **Unique `provider_ref`:** unique index on `provider_ref` (Khalti `pidx`).
4. **Installment guard:** reject initiating an installment `<= installments_paid`.
5. **Idempotent settlement:** `_settle` no-ops on already-`success` payments (exists).

---

## 9. Role permissions

| Action | customer | officer | admin | notes |
|---|---|---|---|---|
| Initiate EMI payment | ✅ (own active loan) | ❌ | ❌ | `require_customer`, `applicant_id` scoping (exists) |
| Verify / read own payment + receipt | ✅ (own) | ❌ | ❌ | exists |
| List own payment history | ✅ (own) | ❌ | ❌ | **new** `GET /payments/my` |
| View payments for a loan/application | ❌ | ✅ (read-only) | ✅ | **new** officer/admin reconciliation |
| Reconcile / re-run lookup on a stuck payment | ❌ | ❌ | ✅ | **new** admin-only, reuses `khalti_lookup` |
| Gateway settlement | — | — | — | server→Khalti `lookup`; no user role |
| `POST /payments/{id}/simulate` (self-settle) | dev only | — | — | **disabled** when `app_env != development` |

---

## 10. Database changes

- **New indexes** (also closes the "no indexes" debt from the review), created at startup:
  - `payments`: unique `provider_ref`; `applicant_id`; `loan_id`; partial-unique `(loan_id, installment_number)` where `status="success"`.
  - `loan_accounts`: `applicant_id`, `status`, `next_due_date`.
  - `users`: unique `email`.
- **New `payments` fields:** `installment_number`, `amount_paisa`, `khalti_transaction_id`, `failure_reason`, `receipt_number`, `lookup_raw` (Section 5).
- **No schema migration engine needed** (MongoDB) — new fields are additive and default to `None`; a one-time index-creation hook is sufficient.

---

## 11. API endpoints

**Keep / harden (existing):**
- `POST /loans/{loan_id}/payments/initiate` — reuse open intent + installment guard.
- `GET /payments/{payment_id}` — own payment (checkout + receipt).
- `POST /payments/verify` — authoritative lookup + settle + failure mapping.
- `POST /payments/webhook` — optional, disabled in prod unless Khalti webhook enabled.

**Disable in production:**
- `POST /payments/{payment_id}/simulate` — dev/test only (guard on `app_env`).

**New:**
- `GET /payments/my` — customer's payment history (list, own-scoped).
- `GET /officer/loans/{loan_id}/payments` — officer read-only reconciliation for a loan.
- `GET /admin/payments` — admin reconciliation list (+ filters: status, date).
- `POST /admin/payments/{payment_id}/reconcile` — admin re-runs `khalti_lookup` on a stuck/pending payment.

All new endpoints reuse `serialize_payment` and existing service functions.

---

## 12. Frontend changes

- **`CustomerLoans.tsx`** — already: initiate → `window.location.href = checkout_url`. With `provider=khalti`, `checkout_url` is Khalti's hosted `payment_url`, so the redirect "just works". Keep; ensure error toasts for failed initiate.
- **`PaymentCheckout.tsx`** — for the Khalti path this page becomes a brief "redirecting to Khalti…" state (or is skipped entirely since initiate already returns the hosted URL). The **QR / "I've completed the payment" self-confirm is retained only for the mock/dev provider**, never as a production settlement path.
- **`PaymentReturn.tsx`** — already verifies `pidx` via `/payments/verify`. Extend to render three explicit outcomes: **success** (receipt), **failed/cancelled** (reason + re-pay), **pending** (awaiting confirmation + re-verify).
- **`Receipt`** — add `receipt_number` + Khalti `transaction_id`.
- **New:** customer **payment history** view (list from `GET /payments/my`); officer/admin **reconciliation** table (read-only) reusing `formatMoney` and the existing table styles.
- **BFF proxies:** add `app/api/payments/my/route.ts`, `app/api/officer/loans/[loanId]/payments/route.ts`, `app/api/admin/payments/route.ts`, `app/api/admin/payments/[paymentId]/reconcile/route.ts` — each forwards the cookie JWT (same pattern as existing proxies).

---

# Phased implementation plan

### Phase 0 — Lock to Khalti + close the self-settle hole
- **Goal:** Khalti sandbox is the only production rail; the customer can no longer settle without paying.
- **Modify:** `backend/app/config.py` (validate `khalti_secret_key` + `payment_webhook_secret` strength outside dev; default `payment_provider=khalti`), `backend/app/routes/payments.py` (guard `/simulate` to `app_env=="development"`), `backend/.env.example`, `frontend/.env` docs.
- **New:** none.
- **Outcome:** Production uses Khalti only; `/simulate` is unreachable in prod; weak secrets fail fast.

### Phase 1 — Transaction record model + indexes + duplicate prevention
- **Goal:** every payment is a well-formed, de-duplicated ledger row backed by DB constraints.
- **Modify:** `backend/app/services/payment_service.py` (reuse open PENDING intent, set `installment_number`, `amount_paisa`), `backend/app/database/connection.py` (or startup hook in `main.py` lifespan) to create indexes.
- **New:** `backend/app/models/payment.py` (document builder + `serialize`), `backend/app/database/indexes.py` (index definitions).
- **Outcome:** No duplicate intents/settlements; hot queries indexed; unique email index added.

### Phase 2 — Verification, settlement integrity & failure handling
- **Goal:** settlement is authoritative, amount-checked, and every failure/cancel is captured.
- **Modify:** `backend/app/services/payment_gateways.py` (`_map_status` covers Expired/User canceled/Initiated; return `total_amount`/`transaction_id` — mostly present), `backend/app/services/payment_service.py` (`verify_payment`/`_settle`: amount-integrity check, `failure_reason`, `khalti_transaction_id`, `lookup_raw`, audit events), `backend/app/schemas/payments.py` (expose `installment_number`, `failure_reason`, `receipt_number`, `khalti_transaction_id`).
- **New:** none.
- **Outcome:** Loans only change on a `Completed` lookup with a matching amount; cancelled/expired handled cleanly.

### Phase 3 — Receipts & customer history
- **Goal:** a stable receipt and a customer-visible payment history.
- **Modify:** `backend/app/services/payment_service.py` (assign `receipt_number` on settle), `backend/app/routes/payments.py` (`GET /payments/my`), `frontend/components/PaymentCheckout.tsx` (`Receipt` shows receipt no. + txn id), `frontend/components/CustomerLoans.tsx` (link to history).
- **New:** `frontend/app/api/payments/my/route.ts`, a `PaymentHistory` component + page.
- **Outcome:** Customers see all past EMIs and can reprint receipts.

### Phase 4 — Officer/Admin reconciliation & role permissions
- **Goal:** back-office visibility and a manual re-lookup for stuck payments.
- **Modify:** `backend/app/routes/officer.py`, `backend/app/routes/admin.py`, `backend/app/services/payment_service.py` (`list_payments_for_loan`, `list_all_payments`, `reconcile_payment` reusing `khalti_lookup`).
- **New:** BFF proxies (`app/api/officer/loans/[loanId]/payments/route.ts`, `app/api/admin/payments/route.ts`, `app/api/admin/payments/[paymentId]/reconcile/route.ts`) + officer/admin reconciliation table components.
- **Outcome:** Officers/admins reconcile Khalti payments read-only; admins can re-verify a pending payment.

### Phase 5 — Frontend flow finalization
- **Goal:** a clean Khalti redirect → return experience with explicit success/failed/pending states.
- **Modify:** `frontend/components/CustomerLoans.tsx`, `frontend/components/PaymentCheckout.tsx` (Khalti = redirect; QR only for mock/dev), `frontend/components/PaymentReturn.tsx` (three outcome states + re-pay/re-verify).
- **New:** none.
- **Outcome:** Production users always pay on Khalti's hosted page and land on an accurate result screen.

### Phase 6 — Automated tests & verification
- **Goal:** prove the pipeline without hitting the live gateway.
- **Modify:** `backend/tests/conftest.py` (mock `httpx` for `khalti_initiate`/`khalti_lookup`), extend `backend/tests/test_mfa_kyc_payments.py`.
- **New:** `backend/tests/test_payments_khalti.py` — initiate creates one intent; duplicate initiate reuses it; lookup=Completed settles once (idempotent); amount mismatch fails without touching the loan; cancelled/expired handled; RBAC (customer-only initiate, officer/admin read-only); `/simulate` blocked outside dev.
- **Outcome:** Green suite covering the full Khalti EMI lifecycle and its guardrails.
