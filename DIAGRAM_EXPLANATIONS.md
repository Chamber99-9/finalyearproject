# Sajilo Loan — Diagram Explanations

---

## 1. Use Case Diagram

**Description:**

- **Use Case Description:** Shows how the Customer, Loan Officer, and Admin interact with the system — registering, verifying KYC and applying for a loan, uploading and verifying documents, reviewing and deciding applications, making and confirming payments, and managing users. An external Payment Gateway (eSewa / Khalti) participates in the payment use cases.
- **Actor:** Customer, Loan Officer, Admin, Payment Gateway (external).
- **Precondition:** The actor has access to the system — a registered account for the Customer, and an assigned role for the Officer/Admin. Applying for a loan additionally requires the Customer's KYC to be verified.
- **Postcondition:** The system reflects the action performed — an account is created, KYC is submitted/verified, an application is created/reviewed/decided, a document is accepted or rejected, a payment is made and confirmed, or a user is managed/blacklisted.

---

## 2. Class Diagram

**Description:**

- **Class Description:** Shows the main domain objects of the system and how they relate. Core classes are `User`, `KycRecord`, `LoanApplication`, `ApplicationDocument`, `OcrResult`, `CreditRiskScore`, `LoanAccount`, `Payment`, `Notification`, and `AuditLog`, together with enumerations for `UserRole`, `ApplicationStatus`, `PaymentStatus`, and `LoanAccountStatus`.
- **Key relationships:** A `User` has at most one `KycRecord` and many `LoanApplication`s. A `LoanApplication` has many `ApplicationDocument`s (each with at most one `OcrResult`) and many `CreditRiskScore`s, and — once approved — one `LoanAccount` (disbursement). A `LoanAccount` receives many `Payment`s. A `User` receives many `Notification`s and generates many `AuditLog`s.
- **Precondition:** The classes represent persisted records; an instance exists only after the corresponding action (registration, application, upload, disbursement, payment) has occurred.
- **Postcondition:** Object state changes are reflected through the enumerations (e.g. application status moves DRAFT → SUBMITTED → APPROVED; payment status moves PENDING → AWAITING_CONFIRMATION → SUCCESS).

---

## 3. ER Diagram

**Description:**

- **ER Description:** Shows the database entities (MongoDB collections) and the relationships between them. Entities are `users`, `kyc_records`, `loan_applications`, `application_documents`, `ocr_results`, `credit_risk_scores`, `loan_accounts`, `payments`, `document_requests`, `notifications`, and `audit_logs`.
- **Relationships (cardinality):** `users` 1–0..1 `kyc_records`; `users` 1–* `loan_applications`; `loan_applications` 1–* `application_documents`; `application_documents` 1–0..1 `ocr_results`; `loan_applications` 1–* `credit_risk_scores` and 1–* `document_requests`; `loan_applications` 1–0..1 `loan_accounts`; `loan_accounts` 1–* `payments`; `users` 1–* `notifications` and 1–* `audit_logs`.
- **Keys:** Each entity has a primary key `_id`. Foreign keys link records by id (e.g. `applicant_id`, `application_id`, `document_id`, `loan_id`, `user_id`). `email` and `phone` on `users`, and `provider_ref` on `payments`, are unique.
- **Precondition:** A child record can only reference a parent that already exists (e.g. a payment must reference an existing loan account).
- **Postcondition:** The stored data remains referentially consistent — application, documents, scores, loan account, and payments all trace back to a single customer.

---

## 4. Schema Diagram

**Description:**

- **Schema Description:** Shows each MongoDB collection as a table with its fields and data types (ObjectId, string, number, int, bool, date, object), i.e. the detailed database schema behind the ER diagram.
- **Main collections:** `users`, `kyc_records`, `loan_applications`, `application_documents`, `ocr_results`, `credit_risk_scores`, `loan_accounts`, `payments`, `notifications`, `audit_logs`, and `app_settings`.
- **Indexes / constraints:** `users.email` and `users.phone` are unique; `payments.provider_ref` is unique; foreign-key fields (`applicant_id`, `application_id`, `document_id`, `loan_id`, `user_id`) link collections.
- **Precondition:** A document is written only with the required typed fields present and valid (enforced by the Pydantic schemas on the API).
- **Postcondition:** Each collection stores well-typed, indexed records that reconcile with the ER relationships.

---

## 5. Sequence Diagram

**Description:**

- **Sequence Description:** Shows the time-ordered messages exchanged between the Customer, Frontend, Backend, Loan Officer, and Payment Gateway across the full loan journey — KYC verification, document upload and verification, application submission, officer review and decision, and EMI payment.
- **Participants:** Customer, Frontend (Next.js BFF), Backend (FastAPI), MongoDB, Loan Officer, eSewa/Khalti gateway.
- **Precondition:** The Customer is registered and logged in. The loan application steps run only after KYC has been submitted and verified by an officer (the application is blocked until `kyc_status = verified`).
- **Main flow:** Submit KYC → officer verifies → upload document → backend runs OCR + classification (accepts, or rejects a wrong document as "Doesnot look like required document") → submit application (KYC + salary-cap + collateral-document checks) → officer reviews and approves → backend creates the loan account (disbursement) → Customer pays the EMI (eSewa QR with officer confirmation, or Khalti) → backend settles and returns a receipt.
- **Postcondition:** Each message advances the record state (KYC verified, document accepted/rejected, application decided, loan disbursed, EMI settled), leaving the system in a consistent state.

---

## 6. Activity Diagram

**Description:**

- **Activity Description:** Shows the step-by-step workflow of the system across three swimlanes — Customer, System, and Loan Officer — from registration through KYC, document verification, application, officer decision, disbursement, and repayment.
- **Swimlanes (roles):** Customer (registers, submits KYC, uploads documents, fills and submits the application, pays EMIs), System (sends/verifies OTP, runs OCR and document verification, checks eligibility, computes EMI, settles payments), Loan Officer (verifies KYC, reviews the application, approves/rejects, confirms QR payments).
- **Precondition:** The actor has access to the system; loan-application activities begin only once KYC has been verified.
- **Main flow and decisions:** Register & login → submit KYC → officer reviews → **[KYC verified?]** (No → resubmit; Yes → continue) → choose loan type → upload documents → OCR + classify → **[Matches required type?]** (No → deny "Doesnot look like required document" and re-upload; Yes → auto-fill identity fields) → submit application → **[Within salary cap?]** and **[Collateral docs uploaded?]** checks → officer reviews and **[Approve / Counter-offer / Reject]** → create loan account (disbursed) → pay EMI within the 7-day window → **[Outstanding > 0?]** loop until the loan is completed.
- **Postcondition:** The workflow ends with the application decided and, if approved, a disbursed loan being repaid to completion; the system state reflects every decision taken along the way.
