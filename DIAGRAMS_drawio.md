# Sajilo Loan — Diagrams for draw.io (Mermaid)

**How to use in draw.io / diagrams.net:**
1. Open draw.io → a blank diagram.
2. Click **+ (Insert)** in the top toolbar → **Advanced** → **Mermaid…**
   (or menu **Extras → Insert → Advanced → Mermaid**).
3. Paste one block below → **Insert**. It becomes editable draw.io shapes.
4. Repeat per diagram (put each on its own page/tab).

Order enforced everywhere: **register → submit KYC → officer verifies → then apply for loan**.

---

## 1. Use Case Diagram

```mermaid
flowchart LR
  Customer([Customer])
  Officer([Loan Officer])
  Admin([Admin])
  Gateway([eSewa / Khalti])

  subgraph SYS[Sajilo Loan - Digital LOS]
    R((Register - Gmail))
    L((Login + email OTP))
    K((Submit KYC))
    A((Apply for loan))
    D((Upload & verify documents))
    E((See EMI / affordability))
    CO((Respond to counter-offer))
    P((Pay EMI))
    PP((Advance payment))
    RM((Receive due reminders))
    RV((Review application))
    RQ((Request more documents))
    SO((Send counter-offer))
    DE((Approve / Reject))
    VK((Verify KYC))
    CF((Confirm QR payment))
    RS((Calculate credit risk))
    BL((Blacklist customer))
    UM((Manage users / roles))
    RT((Set base & type rates))
    OR((Override application rate))
    CK((Skip date & run billing))
    AU((View audit logs))
  end

  Customer --- R
  Customer --- L
  Customer --- K
  Customer --- A
  Customer --- D
  Customer --- E
  Customer --- CO
  Customer --- P
  Customer --- PP
  Customer --- RM
  A -. requires verified KYC .-> K
  P --- Gateway
  PP --- Gateway

  Officer --- RV
  Officer --- RQ
  Officer --- SO
  Officer --- DE
  Officer --- VK
  Officer --- CF
  Officer --- RS
  Officer --- BL

  Admin --- UM
  Admin --- RT
  Admin --- OR
  Admin --- CK
  Admin --- AU
  Admin --- BL
```

---

## 2. Class Diagram

```mermaid
classDiagram
  class UserRole {
    <<enumeration>>
    CUSTOMER
    OFFICER
    ADMIN
  }
  class ApplicationStatus {
    <<enumeration>>
    DRAFT
    SUBMITTED
    UNDER_REVIEW
    DOCUMENT_REQUESTED
    COUNTER_OFFERED
    APPROVED
    REJECTED
  }
  class PaymentStatus {
    <<enumeration>>
    PENDING
    AWAITING_CONFIRMATION
    SUCCESS
    FAILED
  }
  class LoanAccountStatus {
    <<enumeration>>
    ACTIVE
    COMPLETED
    DEFAULTED
  }

  class User {
    +ObjectId id
    +string full_name
    +string email
    -string password_hash
    +UserRole role
    +bool is_blacklisted
    +bool mfa_enabled
    +string kyc_status
  }
  class KycRecord {
    +string user_id
    +string pan_number
    +string citizenship_number
    +string date_of_birth
    +string status
    +map checks
  }
  class LoanApplication {
    +ObjectId id
    +string applicant_id
    +string loan_type
    +float monthly_income
    +float requested_loan_amount
    +int loan_duration_months
    +float interest_rate_used
    +float monthly_emi
    +float emi_dti_ratio
    +string affordability
    +float offered_loan_amount
    +ApplicationStatus status
  }
  class ApplicationDocument {
    +ObjectId id
    +string application_id
    +string document_type
    +string file_path
    +string file_hash
  }
  class OcrResult {
    +ObjectId id
    +string document_id
    +string detected_document_type
    +float detection_confidence
    +map detected_fields
    +bool type_match
  }
  class CreditRiskScore {
    +ObjectId id
    +string application_id
    +int normalized_score
    +string risk_level
    +float dti_ratio
    +map score_breakdown
  }
  class LoanAccount {
    +ObjectId id
    +string application_id
    +float principal
    +float monthly_emi
    +float outstanding_balance
    +int installments_paid
    +int missed_installments
    +date next_due_date
    +LoanAccountStatus status
  }
  class Payment {
    +ObjectId id
    +string loan_id
    +float amount
    +string kind
    +PaymentStatus status
    +string provider
    +string merchant_name
    +string qr_url
    +float fee_total
  }
  class Notification {
    +string user_id
    +string title
    +bool is_read
  }
  class AuditLog {
    +string user_id
    +string action
    +string entity_type
  }

  User "1" --> "0..1" KycRecord
  User "1" --> "0..*" LoanApplication : applies
  LoanApplication "1" --> "0..*" ApplicationDocument
  ApplicationDocument "1" --> "0..1" OcrResult
  LoanApplication "1" --> "0..*" CreditRiskScore
  LoanApplication "1" --> "0..1" LoanAccount : disburses
  LoanAccount "1" --> "0..*" Payment
  User "1" --> "0..*" Notification
  User "1" --> "0..*" AuditLog
```

---

## 3. ER Diagram

```mermaid
erDiagram
  users ||--o| kyc_records : has
  users ||--o{ loan_applications : applies
  loan_applications ||--o{ application_documents : contains
  application_documents ||--o| ocr_results : produces
  loan_applications ||--o{ credit_risk_scores : scored_by
  loan_applications ||--o| loan_accounts : disburses
  loan_accounts ||--o{ payments : receives
  loan_applications ||--o{ document_requests : requests
  users ||--o{ notifications : receives
  users ||--o{ audit_logs : records

  users {
    ObjectId _id PK
    string email UK
    string phone UK
    string role
    bool is_blacklisted
    string kyc_status
  }
  kyc_records {
    ObjectId _id PK
    string user_id FK
    string status
    string pan_number
    string citizenship_number
  }
  loan_applications {
    ObjectId _id PK
    string applicant_id FK
    string loan_type
    float requested_loan_amount
    float monthly_emi
    string status
  }
  application_documents {
    ObjectId _id PK
    string application_id FK
    string user_id FK
    string document_type
    string file_hash
  }
  ocr_results {
    ObjectId _id PK
    string document_id FK
    string detected_document_type
    bool type_match
  }
  credit_risk_scores {
    ObjectId _id PK
    string application_id FK
    int normalized_score
    string risk_level
  }
  loan_accounts {
    ObjectId _id PK
    string application_id FK
    string applicant_id FK
    float outstanding_balance
    date next_due_date
    string status
  }
  payments {
    ObjectId _id PK
    string loan_id FK
    string applicant_id FK
    float amount
    string provider
    string status
  }
  document_requests {
    ObjectId _id PK
    string application_id FK
    string status
  }
  notifications {
    ObjectId _id PK
    string user_id FK
    bool is_read
  }
  audit_logs {
    ObjectId _id PK
    string user_id FK
    string action
  }
```

---

## 4. Schema Diagram (MongoDB collections, fully typed)

```mermaid
erDiagram
  users ||--o| kyc_records : user_id
  users ||--o{ loan_applications : applicant_id
  loan_applications ||--o{ application_documents : application_id
  application_documents ||--o| ocr_results : document_id
  loan_applications ||--o{ credit_risk_scores : application_id
  loan_applications ||--o| loan_accounts : application_id
  loan_accounts ||--o{ payments : loan_id
  users ||--o{ notifications : user_id
  users ||--o{ audit_logs : user_id

  users {
    ObjectId _id PK
    string full_name
    string email UK
    string phone UK
    string password_hash
    string role
    bool is_blacklisted
    bool mfa_enabled
    string kyc_status
    date created_at
  }
  kyc_records {
    ObjectId _id PK
    string user_id FK
    string full_name
    string pan_number
    string citizenship_number
    string date_of_birth
    string status
    object checks
    string review_note
  }
  loan_applications {
    ObjectId _id PK
    string applicant_id FK
    string loan_type
    number monthly_income
    number existing_monthly_debt
    number requested_loan_amount
    int loan_duration_months
    number interest_rate_used
    number monthly_emi
    number emi_dti_ratio
    string affordability
    string pan_number
    number collateral_value
    number offered_loan_amount
    string offer_status
    object verification
    string status
    date created_at
  }
  application_documents {
    ObjectId _id PK
    string application_id FK
    string user_id FK
    string document_type
    string filename
    string file_path
    string content_type
    string file_hash
    date uploaded_at
  }
  ocr_results {
    ObjectId _id PK
    string document_id FK
    string application_id FK
    string extracted_text
    string detected_document_type
    number detection_confidence
    object detected_fields
    bool type_match
    bool verified_by_user
    date created_at
  }
  credit_risk_scores {
    ObjectId _id PK
    string application_id FK
    int raw_score
    int normalized_score
    string risk_level
    number dti_ratio
    number lti_ratio
    object score_breakdown
    date created_at
  }
  loan_accounts {
    ObjectId _id PK
    string application_id FK
    string applicant_id FK
    number principal
    number interest_rate
    int tenure_months
    number monthly_emi
    number outstanding_balance
    int installments_paid
    int installments_total
    int missed_installments
    date next_due_date
    string status
  }
  payments {
    ObjectId _id PK
    string loan_id FK
    string applicant_id FK
    number amount
    string kind
    string status
    string provider
    string provider_ref UK
    string merchant_name
    string qr_url
    number prepay_principal
    number fee_total
    number amount_paid
    date settled_at
  }
  notifications {
    ObjectId _id PK
    string user_id FK
    string title
    string message
    bool is_read
    date created_at
  }
  audit_logs {
    ObjectId _id PK
    string user_id FK
    string action
    string entity_type
    string entity_id
    object details
    date created_at
  }
  app_settings {
    string key PK
    string value
  }
```

---

## 5. Sequence Diagram

```mermaid
sequenceDiagram
  actor C as Customer
  participant BFF as Next.js BFF
  participant API as FastAPI Backend
  participant DB as MongoDB
  actor O as Loan Officer
  participant GW as eSewa / Khalti

  Note over C,API: KYC first - application blocked until verified
  C->>BFF: Submit KYC (PAN, citizenship, DOB)
  BFF->>API: POST /kyc/submit
  API->>DB: kyc_status = pending
  O->>API: PUT /kyc/{id}/review (approve)
  API->>DB: kyc_status = verified

  C->>BFF: Upload citizenship (JPG/PDF)
  BFF->>API: POST /applications/{id}/documents
  API->>API: OCR + classify document
  alt type mismatch
    API-->>BFF: 400 "Doesnot look like required document"
  else accepted
    API->>DB: save document + ocr_result
    API-->>BFF: 201 (detected citizenship no / name / address)
  end
  C->>BFF: Submit application
  BFF->>API: POST /applications/{id}/submit
  API->>API: KYC gate + salary cap + collateral docs
  API->>DB: status = submitted

  O->>API: GET /officer/applications/{id}
  O->>API: Approve
  API->>DB: create loan_account (disbursement)

  C->>BFF: Pay EMI (method = qr | khalti)
  BFF->>API: POST /loans/{id}/payments/initiate
  API->>API: check window (>= 7 days before due)
  alt Khalti
    API->>GW: initiate (KPG-2)
    C->>GW: pay on hosted page
    BFF->>API: /payments/verify
    API->>GW: lookup
    GW-->>API: Completed
  else eSewa QR
    API-->>C: show eSewa QR (Sudin khanal)
    C->>GW: scan & pay merchant
    C->>BFF: I've completed the payment
    BFF->>API: POST /payments/{id}/submitted
    O->>API: POST /officer/payments/{id}/confirm
  end
  API->>DB: settle - reduce outstanding, advance due date
  API-->>C: receipt
```

---

## 6. Activity Diagram

```mermaid
flowchart TD
  A([Start]) --> B[Register Gmail & login]
  B --> C[Submit KYC]
  C --> D[Officer reviews KYC]
  D --> E{KYC verified?}
  E -- No --> C
  E -- Yes --> F[Choose loan type]
  F --> G[Upload documents]
  G --> H[System reads OCR/PDF & classifies]
  H --> I{Matches required type?}
  I -- No --> J[Deny: Doesnot look like required document]
  J --> G
  I -- Yes --> K[Accept & auto-fill citizenship no / name / address]
  K --> L[Fill application details]
  L --> M[Submit application]
  M --> N{Within salary cap?}
  N -- No --> O([Reject - exceeds cap])
  N -- Yes --> P{Collateral loan > 2 lakh?}
  P -- Yes --> Q{Statement + property + valuation uploaded?}
  Q -- No --> R([Block - collateral docs required])
  Q -- Yes --> S[Status = Submitted]
  P -- No --> S
  S --> T[Officer reviews app, docs, risk, name-match]
  T --> U{Decision}
  U -- Counter-offer --> V{Customer accepts?}
  V -- No --> W([Rejected])
  V -- Yes --> X[Approved at offered amount]
  U -- Reject --> W
  U -- Approve --> X
  X --> Y[Create loan account - disbursed]
  Y --> Z[Wait until 7 days before due]
  Z --> AA[Pay EMI eSewa QR / Khalti or advance]
  AA --> AB{Method = QR?}
  AB -- Yes --> AC[Officer confirms received]
  AB -- No --> AD[Verify via gateway lookup]
  AC --> AE[Settle - reduce outstanding, advance due]
  AD --> AE
  AE --> AF{Outstanding > 0?}
  AF -- Yes --> Z
  AF -- No --> AG([Loan completed])
```
