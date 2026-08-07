# Sajilo Loan — Senior Architect Review (current state)

*A review of the project as it stands now, based on a direct read of the backend (routes, services, models, schemas, auth, config, database) and the frontend (BFF proxies, components, pages). No new features are proposed here; this is analysis only, ending with a prioritized improvement list.*

---

## 1. Folder structure

Two independently deployable apps in one repo.

**`backend/`** — FastAPI, layered cleanly:
- `app/main.py` wires ~20 routers.
- `app/routes/*` — thin HTTP handlers (auth, applications, officer, admin, payments, kyc, ocr, risk, emi, rates, settings, eligibility, flags, notifications, health).
- `app/services/*` — all business logic (application, officer, admin, payment, payment_gateways, loan_account, loan_rate, loan_settings, loan_eligibility, risk, emi, document, document_service, document_classifier, document_verification, ocr, kyc, otp, clock, email, notification, audit, user, flag, document_request).
- `app/models/*` — Mongo document builders + `StrEnum`s.
- `app/schemas/*` — Pydantic v2 request/response contracts.
- `app/auth/*` — JWT + role dependencies. `app/database/*` — Motor client + `indexes.py`. `app/utilities/rate_limit.py`.
- `tests/` — pytest suites (auth, applications, rbac, risk, rates, eligibility, loans, flags, document_classifier).

**`frontend/`** — Next.js (App Router):
- `app/**` pages (landing, login, register, `dashboard/{customer,officer,admin}`, applications, payments).
- `app/api/**/route.ts` — the BFF proxy layer (one proxy per backend call).
- `components/*`, `lib/*` (typed helpers).

The layering is consistent and idiomatic — genuinely above typical student-project quality.

---

## 2. How frontend and backend communicate

A **Backend-for-Frontend (BFF)** pattern. The browser never calls FastAPI directly and never holds the JWT in JavaScript:

1. Login/register sets an **httpOnly cookie** `sajilo_auth_token` (via `app/api/auth/_utils.ts`).
2. Every `app/api/**/route.ts` runs server-side, reads that cookie, and forwards it to FastAPI as `Authorization: Bearer <jwt>` against `SAJILO_API_BASE_URL`.
3. `middleware.ts` guards `/dashboard`, `/applications`, `/ocr`, `/payments` by cookie presence.
4. FastAPI validates the JWT (`get_current_user`) and enforces roles (`require_customer/officer/admin`).

This is a real strength: tokens are out of reach of XSS, CORS is server-to-server, and the frontend stays a thin view layer.

---

## 3. Database models & relationships (MongoDB)

Collections and how they link (all references are string ids, not DBRefs):

- **users** → 1:0..1 **kyc_records** (`user_id`); 1:* **loan_applications** (`applicant_id`); 1:* **notifications**, **audit_logs** (`user_id`).
- **loan_applications** → 1:* **application_documents** (`application_id`); 1:* **credit_risk_scores**; 1:* **document_requests**; 0..1 **application_flags**; 0..1 **loan_accounts** (created on approval = disbursement).
- **application_documents** → 0..1 **ocr_results** (`document_id`).
- **loan_accounts** → 1:* **payments** (`loan_id`).
- **app_settings** — keyed singletons (base rate, per-type rate, simulated-clock day offset).
- **email_otps** — MFA login codes.

The domain model is coherent and matches a real LOS: applicant → application → documents/OCR/risk → disbursed loan account → payments.

---

## 4. Existing features

Authentication & identity: Gmail-restricted registration with auto-login, JWT sessions (12h), opt-in email-OTP MFA, KYC submission + officer verification, manual blacklist (blocks login).

Loan origination: multiple loan types with a dynamic rate engine (base + type spread + tenure adjustment, rate frozen on the application), salary-based caps, collateral rules, live EMI + amortization + affordability (DTI bands), a real rule-based credit-risk score (300–850-style), document upload with **at-upload type verification** (accept / "Doesnot look like required document"), auto-fill of citizenship number/name/address from the citizenship document, and a cross-document name-match flag for officers.

Officer/admin workflow: review queue, request-more-documents, counter-offer (customer accepts/declines), approve/reject, KYC review, blacklist, confirm QR payments; admin rate control + per-application override, user/role management, audit logs, and a **testing calendar** (skip the simulated date + run billing).

Servicing & payments: loan account on approval, EMI with a 7-day-before-due payment window, advance/lump-sum prepayment (flat fee + %), a payment gateway abstraction supporting **eSewa personal-QR (officer-confirmed)**, **Khalti KPG-2**, eSewa ePay, and a dev mock; idempotent settlement; 3-day email reminders; overdue counting and auto-blacklist after 3 misses (run via the calendar).

---

## 5. The complete loan workflow

Register (Gmail) → **submit KYC → officer verifies (loan requests are blocked until `kyc_status = verified`)** → choose loan type → upload documents (each verified at upload; wrong type denied; citizenship auto-fills identity fields) → complete details (live EMI/rate) → submit (KYC gate + salary cap + collateral-docs gate) → officer reviews (documents, credit score, name-match) → approve / counter-offer / reject → on approval a **loan account is created (disbursement)** → customer pays EMIs inside the 7-day window (eSewa QR + officer confirmation, or Khalti) or prepays → each settlement reduces the outstanding balance and advances the due date → reminders/overdue/blacklist run on the (simulated) clock → loan completes when the balance hits zero.

---

## 6. Modules already implemented

Auth/JWT/RBAC, MFA, KYC, applications + drafts, dynamic rates + admin control, EMI + amortization + affordability, credit risk scoring, eligibility (caps/collateral), document upload + storage + hashing, OCR (Tesseract images / pdfplumber PDFs) + document classifier + at-upload verification, officer review workflow (status, document requests, counter-offers, verification checklist), admin (users, rates, overview, audit logs, testing calendar, blacklist), loan accounts + EMI/prepayment payments, payment gateways (eSewa QR / Khalti / eSewa / mock), reminders/overdue/blacklist jobs, notifications, audit logging, rate limiting, DB indexes, seeding.

---

## 7. Bugs and correctness risks

- **No true amortization ledger.** `loan_accounts.outstanding_balance` is seeded to `total_payment` (principal + all interest) and decremented by the flat EMI. It tracks "total repayable remaining," not principal outstanding with interest accrual, so prepayment interest savings and a real payment schedule are not modelled. *(High.)*
- **Reminders/overdue/blacklist never run on their own.** `process_due_reminders`/`process_overdue` exist but are only triggered by the admin "Run billing" button (and, in production, nothing calls them automatically). Without the testing calendar, no reminder is ever emailed and no one is ever blacklisted for missed payments. *(High.)*
- **Blacklist doesn't revoke live sessions.** Blacklisting sets `is_blacklisted` and blocks new logins, but an already-issued JWT stays valid until its 12h expiry — a blacklisted user with an open session is not immediately locked out. *(High for a banking app.)*
- **Simulated clock is half-applied.** Payment-window, reminders, and overdue use `simulated_now`, but a loan account's `next_due_date` is set from the real clock at creation. Fine for the testing flow, but the two clocks can diverge. *(Low.)*
- **DB indexes only in production/seed.** `ensure_indexes` runs in `lifespan` only when `app_env == production`, and in `seed.py`. Dev/most self-hosted runs have no indexes and no enforced unique email/phone. *(Medium.)*
- **OCR is a hard dependency for the upload gate to actually gate.** If Tesseract/pdfplumber aren't installed on the backend host, `verify_document_type` fails open (accepts) — correct as a safety choice, but it means the "deny wrong document" behaviour silently disappears on a mis-provisioned server. *(Medium — deployment risk.)*

---

## 8. Unused / dead code

- **Customer-facing OCR surface is orphaned** after the move to at-upload verification: `frontend/app/ocr/verify/page.tsx`, `components/OCRVerificationForm.tsx`, the `app/api/ocr/{extract,results,verify}` proxies, and `app/api/applications/[id]/ocr-results` are no longer reached by any UI. The backend `routes/ocr.py` (and `ocr_service.extract_and_save_ocr_result`) is still mounted but unused by the live flow.
- **`components/AdminKyc.tsx`** is orphaned — KYC review moved to officers and `app/dashboard/admin/kyc/page.tsx` now just redirects.
- Likely-legacy components (`DashboardPlaceholder.tsx`, possibly `DocumentUploadForm.tsx`) appear superseded.
- Stale docs from earlier phases (`ARCHITECTURE_ANALYSIS.md`, `PAYMENT_SYSTEM_DESIGN.md`) predate the current payment/OCR/KYC design.

None of this breaks the build, but it's confusing surface area and should be pruned.

---

## 9. Duplicate code

- **Payment-gateway dispatch is duplicated.** `initiate_payment` has an inline `if provider == qr/esewa/khalti/else` block, and `_build_gateway_updates` (used by prepayment) has a second copy of the same dispatch. They must be kept in sync by hand.
- **Blacklist logic is duplicated.** The admin route's `_apply_blacklist` and the officer route's inline handler both do set-flag + audit + notify + serialize separately.
- **Two OCR paths:** `extract_and_save_ocr_result` (old `/ocr/extract` route) vs `extract_document_text` + inline `create_ocr_result_document` in the upload route (live path) — overlapping responsibilities.

---

## 10. Architectural issues

- **Credit risk is advisory, not a control.** The score is computed on demand and shown to the officer; nothing gates approval on it and there's no maker-checker/dual-control on approval, disbursement, or rate override — unusual for a banking LOS.
- **PII stored in clear text.** Citizenship numbers, PAN, phone, address, and uploaded ID images are unencrypted (Mongo + local disk). A real Nepalese bank would need field-level encryption and encrypted object storage.
- **Local-disk document storage** (`upload_dir`) is ephemeral on most cloud hosts and not encrypted or virus-scanned.
- **In-memory rate limiter** doesn't hold across multiple instances.
- **eSewa-QR settlement relies on manual officer confirmation** (no gateway callback for a personal QR) — acceptable and honest, but it means "paid" depends on human action; there's no reconciliation against the actual eSewa account.
- **Frontend/backend deploy independently**, so the UI can be ahead of the API (this has already caused confusion, e.g. detected fields not appearing when the backend wasn't redeployed).

---

## 11. Strengths

Clean layered architecture with pure, testable calculation modules (EMI, rates, eligibility, classifier); typed end-to-end with Pydantic + TypeScript; a secure BFF/httpOnly-cookie auth model with RBAC; pervasive audit logging; idempotent, provider-abstracted payment settlement; a real dynamic rate engine, credit-scoring model, and document classifier with an at-upload accept/deny gate; a KYC-gated origination flow; and a clever simulated-clock testing harness. There is a real test suite. For a final-year project this is a strong, coherent system.

## 12. Weaknesses

The servicing layer is simplified (no real amortization/accrual, no automatic scheduler); several controls are advisory rather than enforced (credit score, no maker-checker); security has gaps for a banking context (plaintext PII, no session revocation on blacklist, in-memory rate limiting, local file storage); and there is accumulated dead/duplicate code from rapid iteration (orphaned OCR UI, duplicated gateway/blacklist logic).

---

## 13. Prioritized improvements (highest → lowest impact)

1. **Add a real repayment ledger + interest accrual.** Track principal outstanding and per-payment principal/interest split; make prepayment reduce principal and shorten the schedule. This is the biggest correctness gap for a lending system.
2. **Automate the billing jobs.** Run `process_due_reminders`/`process_overdue` on a scheduler (cron/worker) so reminders email and blacklisting fires without the manual calendar button.
3. **Enforce session revocation on blacklist (and shorten token life / add refresh).** A blacklisted or logged-out user's existing JWT should stop working immediately (denylist by `jti` or a token-version check).
4. **Secure PII.** Field-level encryption for citizenship/PAN/phone/address and encrypted object storage (S3-compatible) for uploaded documents; move files off local disk.
5. **Make DB indexes + unique constraints unconditional** (not production-only), and confirm the unique email/phone/provider_ref indexes exist everywhere.
6. **De-duplicate the gateway dispatch and blacklist logic;** route `initiate_payment` through the single `_build_gateway_updates` helper and extract one shared blacklist service used by both admin and officer.
7. **Prune dead code.** Remove the orphaned customer-OCR surface (page, component, proxies, `/ocr` route) and `AdminKyc`, and delete/refresh the stale design docs.
8. **Turn the credit score into a control** (auto-decision thresholds and/or maker-checker on approve/disburse/rate-override).
9. **Harden the rate limiter** (shared store, e.g. Redis) and add basic reconciliation for eSewa-QR payments (officer confirmation is fine short-term).
10. **Document the deploy contract** so frontend and backend ship together and the backend host always has Tesseract + pdfplumber (otherwise the document gate silently no-ops).
