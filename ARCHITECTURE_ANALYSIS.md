# Sajilo Loan — Architecture & Readiness Analysis

*Principal architect review of the Digital Loan Origination System. Based on a full read of the current codebase (backend routes/services/models/schemas/auth/config and frontend proxies/auth/components). No assumptions — every claim below is grounded in a specific module.*

---

## 1. Overall architecture

The system is a two-tier web application with a clean separation between an API backend and a browser frontend.

**Backend — FastAPI (Python), async throughout.** Entry point `app/main.py` wires ~18 routers onto a single FastAPI app with CORS restricted to configured origins. It follows a disciplined **layered architecture**:

- **Routes** (`app/routes/*`) — thin HTTP handlers: auth, dependency injection, error → HTTP status mapping. They never touch the DB directly.
- **Services** (`app/services/*`) — all business logic (application lifecycle, risk scoring, EMI, rates, eligibility, payments, OCR, classification, KYC, OTP, notifications, audit).
- **Models** (`app/models/*`) — document builders and enums (StrEnum) that shape MongoDB documents.
- **Schemas** (`app/schemas/*`) — Pydantic v2 request/response contracts (`response_model=` on every route).

**Persistence — MongoDB via Motor** (async driver). A single module-level client (`app/database/connection.py`) exposes `get_database()` as a FastAPI dependency. Collections in use: `users`, `loan_applications`, `application_documents`, `ocr_results`, `credit_risk_scores`, `loan_accounts`, `payments`, `notifications`, `audit_logs`, `document_requests`, `application_flags`, `app_settings`.

**Auth — stateless JWT (HS256)** (`app/auth/security.py`) with `sub`, `exp`, `iat`, `iss`, `aud`, and a `jti`. Bearer tokens are validated by `get_current_user`, and role gates (`require_customer`, `require_officer`, `require_admin`, `require_officer_or_admin`) enforce RBAC per route.

**Frontend — Next.js 16 (App Router).** Pages under `app/`, reusable UI in `components/`. The important architectural choice is a **Backend-for-Frontend (BFF) proxy layer**: every `app/api/**/route.ts` runs server-side, reads the JWT from an **httpOnly cookie** (`sajilo_auth_token`), and forwards it to FastAPI as a `Bearer` header (`app/api/auth/_utils.ts`). The browser never sees the raw token. `middleware.ts` guards `/dashboard`, `/applications`, `/ocr`, `/payments` by presence of the cookie.

**Cross-cutting concerns already present:** pervasive **audit logging** (nearly every state change writes an `audit_logs` entry), **role-scoped notifications**, **rate limiting** (`app/utilities/rate_limit.py`) on auth and expensive endpoints, config via `pydantic-settings` with a production secret-strength validator, and a `seed.py` for demo admin/officer/customer accounts.

**Assessment:** For a student/early-stage project this is a genuinely well-structured, idiomatic FastAPI + Next.js codebase — noticeably cleaner than typical. The layering, typed contracts, and audit trail are real strengths to build on.

---

## 2. Current loan lifecycle

The origination flow is state-machine driven on `ApplicationStatus` (`app/models/application.py`): `draft → submitted → under_review → document_requested → counter_offered → approved | rejected`.

1. **Draft creation.** Customer starts a draft (`POST /applications` or `/applications/draft`). Drafts are de-duplicated per citizenship number / loan type.
2. **Fill & auto-price.** On update (`app/services/application_service.py::update_owned_application`), the **effective interest rate is resolved server-side** (`effective_rate_value`) and **frozen** on the document; EMI, total interest, total payment, EMI-inclusive DTI, and an affordability band are auto-computed (`compute_emi_fields`). The customer never enters a rate.
3. **Submit.** `submit_owned_application` validates completeness, enforces the **salary-based cap** (`max_loan_amount`) and **collateral requirement** (`requires_collateral`, >Rs 200,000 except instant), then moves to `submitted`. Officers and the customer are notified.
4. **Officer review.** `GET /officer/applications/{id}` assembles a full review packet: application, documents, latest OCR results (now with document-type detection), latest credit risk score, and suspicious flags. The officer can:
   - **Request additional documents** → `document_requested` (customer may upload only the requested types).
   - **Send a counter-offer** (a lower amount) → `counter_offered`; the customer accepts (→ `approved`) or declines (→ `rejected`).
   - **Approve / reject** directly (`PUT /officer/applications/{id}/status`).
   - Record a **verification checklist** (PAN / stamp / signature / collateral sign-offs).
5. **Disbursement.** On `approved` (or counter-offer acceptance), `create_loan_account_for_application` opens a `loan_accounts` record — this is the de-facto disbursement event.
6. **Servicing.** The customer pays EMIs (payment intent → checkout → signed settlement); outstanding balance reduces and the next due date advances. Reminder and overdue/blacklist processors exist (`process_due_reminders`, `process_overdue`).

**Credit risk scoring is available but out-of-band:** `POST /risk/calculate/{id}` is officer/admin-triggered and **advisory only** — it is not run automatically on submission and does not gate the approval decision.

---

## 3. Existing payment implementation

Implemented as a realistic **intent → gateway → signed-webhook settlement** pattern (`app/services/payment_service.py`, `routes/payments.py`).

- **Initiate** (`POST /loans/{loan_id}/payments/initiate`) creates a `PENDING` payment for one EMI on an *active, owned* loan, with a `provider_ref` and `idempotency_key`. Provider-aware: the **mock** provider returns an internal checkout page; **Khalti** (`payment_gateways.py`) calls the real KPG-2 initiate API and returns its hosted checkout URL.
- **Settlement** happens through `process_webhook`, which **verifies an HMAC-SHA256 signature** over the canonical payload before applying the payment. `_settle` is **idempotent** (re-settling a `SUCCESS` payment is a no-op) and snapshots the post-payment loan state (outstanding, installments, next due) onto the payment so the **receipt is self-contained**.
- **Redirect verification** (`verify_payment`) re-checks status via a server-side Khalti *lookup* rather than trusting redirect params.
- **Data isolation:** payments are always fetched with `applicant_id` scoping (`get_payment_for_customer`) — a customer can only see their own.
- **Frontend:** a QR scan-to-pay checkout (`PaymentCheckout.tsx`) plus eSewa/Khalti wallet QR display, and a receipt view.

**Critical caveat (demo-only):** `POST /payments/{payment_id}/simulate` lets the **customer self-settle** a payment — it signs the webhook with the server secret and settles without any real money moving. The QR "I've completed the payment" button calls this. That is correct for a prototype but **must be removed/disabled for production**, where settlement should come only from the authenticated gateway callback / server-side verify.

---

## 4. Existing EMI implementation

Strong and cleanly isolated (`app/services/emi_service.py`) — a **pure, dependency-free** calculation module, which is exactly right.

- **Standard reducing-balance formula** `EMI = P·R·(1+R)^N / ((1+R)^N − 1)` with a safe zero-rate branch (`P/N`) and tenure normalization (months/years).
- **Rounding discipline:** the EMI is rounded first, then totals derive from the rounded EMI so `EMI × N == total_payment` always reconciles for the customer.
- **Amortization schedule builder** (`build_amortization_schedule`) with the final installment absorbing rounding drift so the balance lands exactly at 0.00.
- **Affordability:** EMI-inclusive DTI with bands (≤35 Affordable, ≤50 Moderate, >50 High Risk), reused by both the application and the credit risk service.
- **Integration:** EMI is computed and persisted on the application at draft/update time using the **frozen** rate, and feeds the credit risk DTI.

**Gap:** the disbursed `loan_accounts` record seeds `outstanding_balance = total_payment` (principal + interest) and simply subtracts the EMI on each payment. It does **not** persist a per-account amortization ledger or re-accrue interest, so it tracks "total repayable remaining" rather than a true principal-outstanding + interest-accrual schedule. Prepayment/partial payment and interest savings aren't modeled (the schedule logic exists in `emi_service` but isn't wired into servicing).

---

## 5. Strengths of the current design

- **Clean, idiomatic layering** (routes → services → models/schemas) with pure calculation modules (EMI, rates, eligibility, classifier) that are trivial to test.
- **Typed end-to-end** — Pydantic v2 request/response models on every route; StrEnum state machines.
- **Security foundations** — httpOnly-cookie BFF (no token in JS), RBAC dependencies, rate limiting on auth/expensive routes, magic-byte file validation, a production JWT-secret-strength validator, MFA (email OTP), and hashed OTP storage.
- **Auditability** — near-comprehensive `audit_logs` on state changes; role-scoped notifications.
- **Correct money mechanics where it counts** — idempotent, signature-verified payment settlement; frozen interest rate so back-office rate changes never rewrite existing applications; reconciling EMI rounding.
- **Real domain modeling** — a genuine credit-scoring model (300–850-style normalized score with weighted factors), a dynamic rate engine (base + type spread + tenure), salary caps + collateral rules, KYC scaffold, OCR + document-type classifier.
- **Thoughtful UX flows** — counter-offer negotiation, officer document requests, self-contained receipts, notifications.
- **Test coverage exists** — multiple pytest suites (auth, RBAC, applications, eligibility, rates, risk, loans, MFA/KYC/payments, flags, document classifier).

---

## 6. Technical debt

Ordered by impact.

- **[High] Counter-offer amount is not honored at disbursement.** Accepting a counter-offer sets `approved` and calls `create_loan_account_for_application`, which reads `requested_loan_amount` and the stale `monthly_emi` — **not** `offered_loan_amount`. The loan is opened for the *original* requested amount with an EMI that doesn't match the accepted (lower) offer. The offer needs to be applied to the application (amount + recomputed EMI) before the account is created.
- **[High] No true loan ledger / accrual.** `outstanding_balance` = principal + total interest, decremented by EMI. No persisted amortization schedule per account, no interest accrual, no principal/interest split on payments, no partial payment/prepayment/foreclosure, no penal interest.
- **[High] No scheduler.** `process_due_reminders` and `process_overdue` (reminders, missed-installment counting, blacklisting) exist but **nothing invokes them** — there is no cron/worker. In production, reminders never fire and no one is ever actually blacklisted.
- **[High] No database indexes.** `connection.py` creates none. Hot queries filter on `applicant_id`, `email`, `provider_ref`, `application_id`, `file_hash` — all unindexed. Email uniqueness is enforced only in application code, so a **unique index is missing** and a race can create duplicate accounts.
- **[Medium] Risk score is manual and non-binding.** Not auto-computed on submit; doesn't gate approval. An officer can approve a High-Risk application with no control or threshold.
- **[Medium] Local-disk document storage.** Files are written under `upload_dir` on the local filesystem — ephemeral on most cloud/serverless hosts, no object storage, no encryption at rest, no malware scan.
- **[Medium] Mock verifications.** PAN tax-registry and salary checks are deliberate stubs; fine for demo, not real assurance.
- **[Low] In-memory rate limiter** won't hold across multiple instances (bypassable when scaled horizontally).
- **[Low] OCR text loses layout** (word-joined into one line); classifier field extraction is best-effort (e.g. name capture can over-run).
- **[Low] Config is cached at import** (`lru_cache` settings + module-level DB client); runtime setting changes need a restart.

---

## 7. Security concerns

- **[Critical for prod] Self-serviced settlement.** `POST /payments/{id}/simulate` allows a customer to mark an EMI paid with no real payment. Must be gated behind a dev flag or removed before real money is involved.
- **[High] No token revocation.** Logout only clears the cookie; the JWT stays valid until `exp` (12h). Blacklisting a user or changing a password does **not** invalidate live tokens. The `jti` is issued but not used for a denylist. Consider short access tokens + refresh, or a server-side session/denylist.
- **[High] PII stored in the clear.** Citizenship numbers, PAN, phone, address live as plaintext in MongoDB; uploaded ID documents are unencrypted on disk. For a Nepalese bank this is a data-protection/NRB exposure — needs field-level encryption and encrypted object storage.
- **[Medium] Weak default webhook secret.** `payment_webhook_secret` defaults to `"change-me-payment-webhook-secret"` and is **not** covered by the JWT-secret strength validator; it should be. The public `/payments/webhook` also has **no replay protection** (no timestamp/nonce), so a captured signed body could be replayed.
- **[Medium] Document download authorization is coarse.** Any officer can download any document by id (`/officer/documents/{id}/download`) — role-checked but not scoped to an assigned queue, and served directly rather than via short-lived signed URLs.
- **[Medium] No CSRF defense on the cookie BFF.** State-changing proxy routes rely on `sameSite=lax` only; add CSRF tokens or an origin check for POST/PUT/DELETE.
- **[Low] Account lockout.** Only IP/email rate limiting exists (in-memory); no progressive lockout on repeated failures. Password policy should be confirmed in the register schema.
- **Good, keep:** httpOnly cookies, `secure` in prod, CORS with explicit credentialed origins, HMAC-verified settlement, hashed OTPs, magic-byte upload validation, production secret validator.

---

## 8. Missing features for a production-grade Nepalese banking LOS

**Regulatory / compliance (NRB & national):**
- **Credit Information Bureau (Karja Suchana Kendra) integration** — mandatory credit history + blacklist check before approval.
- **AML/CFT screening** — sanctions/PEP lists, transaction monitoring, suspicious-activity flags/reporting.
- **NRB loan classification & provisioning** — Pass / Watchlist / Substandard / Doubtful / Loss with provisioning, plus single-obligor limits and regulatory return reporting.
- **Real KYC/CDD** — verified national ID / NID, PAN validation against IRD, optional biometric/liveness, and re-KYC cycles.

**Core lending engine:**
- **Double-entry ledger + GL/core-banking integration**, real **disbursement to a bank account**, **interest accrual** (day-count, EMI due-date posting), **penal interest**, **prepayment/foreclosure/restructuring**, tax certificates and statements.
- **Maker-checker (dual control)** on approvals, disbursement, and rate overrides, with **amount-based approval hierarchy** (four-eyes).
- **Collateral management** — valuation workflow, lien marking, insurance tracking, periodic revaluation.

**Payments & messaging:**
- **Live rails** — eSewa / Khalti / Fonepay / connectIPS with **auto-reconciliation**, plus **standing instructions / auto-debit**.
- **SMS gateway** (Sparrow, Aakash) alongside email for OTP, due reminders, and status updates.

**Platform / operations:**
- **Scheduler/worker** (Celery/APScheduler) for reminders, overdue processing, accrual, statement runs.
- **Object storage (S3-compatible) + encryption**, **DB indexes + migrations**, **backups/DR**.
- **Observability** — structured logging, metrics, tracing, error tracking; **secrets manager**; CI/CD.
- **Immutable, retained audit trail**; consent management; data-subject controls.

**Domain niceties:**
- **Nepali calendar (Bikram Sambat)** dates and fiscal-year handling, holiday calendar for due-date shifting; multi-branch support.
- **Auto-generated, e-signed loan agreement / offer letter**; document detection chip on the officer file list; auto-fill from detected KYC fields.

---

### Recommended sequencing (highest value, lowest friction first)

1. **Fix the counter-offer disbursement bug** and **add DB indexes + unique email index** — correctness and scale, small effort.
2. **Persist a real amortization ledger** on the loan account (principal/interest split, prepayment) and **add the scheduler** so reminders/overdue/blacklist actually run.
3. **Gate approval on the credit score** (auto-compute on submit; maker-checker + threshold), moving risk from advisory to a control.
4. **Harden payments for production** (remove self-settle, strengthen/validate the webhook secret, add replay protection) and **secure PII** (encryption at rest + object storage).
5. **Layer in NRB compliance** (CIB check, loan classification) — the true differentiator for a real Nepalese LOS.
