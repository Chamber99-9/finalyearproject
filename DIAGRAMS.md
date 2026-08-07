# Sajilo Loan — PlantUML Diagrams

Paste any block into [PlantText](https://www.planttext.com), [PlantUML online](https://www.plantuml.com/plantuml), or a `.puml` file. Each diagram reflects the actual system: FastAPI backend + MongoDB, Next.js BFF frontend, roles Customer / Officer / Admin, and the eSewa-QR / Khalti / eSewa payment rails.

---

## 1. Use Case Diagram

```plantuml
@startuml Sajilo_Loan_UseCase
left to right direction
skinparam packageStyle rectangle
actor Customer
actor "Loan Officer" as Officer
actor Admin
actor "Payment Gateway\n(eSewa / Khalti)" as Gateway

rectangle "Sajilo Loan — Digital Loan Origination System" {
  usecase "Register (Gmail)" as UC_Reg
  usecase "Login (+ optional email OTP)" as UC_Login
  usecase "Submit KYC" as UC_KYC
  usecase "Apply for a loan" as UC_Apply
  usecase "Upload & verify documents" as UC_Docs
  usecase "See EMI / affordability" as UC_EMI
  usecase "Respond to counter-offer" as UC_Counter
  usecase "Pay EMI" as UC_Pay
  usecase "Advance (lump-sum) payment" as UC_Prepay
  usecase "Receive due reminders (email)" as UC_Remind

  usecase "Review application" as UC_Review
  usecase "Request more documents" as UC_ReqDoc
  usecase "Send counter-offer" as UC_SendOffer
  usecase "Approve / Reject" as UC_Decide
  usecase "Verify KYC" as UC_VerifyKYC
  usecase "Confirm QR payment" as UC_Confirm
  usecase "Calculate credit risk" as UC_Risk
  usecase "Blacklist customer" as UC_Blacklist

  usecase "Manage users / roles" as UC_Users
  usecase "Set base & type rates" as UC_Rates
  usecase "Override application rate" as UC_OverrideRate
  usecase "Skip date & run billing" as UC_Clock
  usecase "View audit logs" as UC_Audit
}

Customer --> UC_Reg
Customer --> UC_Login
Customer --> UC_KYC
Customer --> UC_Apply
Customer --> UC_Docs
Customer --> UC_EMI
Customer --> UC_Counter
Customer --> UC_Pay
Customer --> UC_Prepay
Customer --> UC_Remind

UC_Apply ..> UC_KYC : <<precondition: verified>>
UC_Pay ..> Gateway
UC_Prepay ..> Gateway

Officer --> UC_Review
Officer --> UC_ReqDoc
Officer --> UC_SendOffer
Officer --> UC_Decide
Officer --> UC_VerifyKYC
Officer --> UC_Confirm
Officer --> UC_Risk
Officer --> UC_Blacklist

Admin --> UC_Users
Admin --> UC_Rates
Admin --> UC_OverrideRate
Admin --> UC_Clock
Admin --> UC_Audit
Admin --> UC_Blacklist
@enduml
```

---

## 2. Class Diagram (domain + service layer)

```plantuml
@startuml Sajilo_Loan_Class
skinparam classAttributeIconSize 0
hide empty members

enum UserRole {
  CUSTOMER
  OFFICER
  ADMIN
}
enum ApplicationStatus {
  DRAFT
  SUBMITTED
  UNDER_REVIEW
  DOCUMENT_REQUESTED
  COUNTER_OFFERED
  APPROVED
  REJECTED
}
enum LoanType {
  PERSONAL
  INSTANT
  HOME
  AUTO
  EDUCATION
  LOAN_AGAINST_SHARES
  BUSINESS
}
enum LoanAccountStatus {
  ACTIVE
  COMPLETED
  DEFAULTED
}
enum DocumentType {
  CITIZENSHIP_DOCUMENT
  SALARY_SLIP
  BANK_STATEMENT
  VALUATION_REPORT
  PROPERTY_PAPERS
  RECOMMENDATION_LETTER
  SUPPORTING_DOCUMENT
}
enum PaymentStatus {
  PENDING
  AWAITING_CONFIRMATION
  SUCCESS
  FAILED
}

class User {
  +id : ObjectId
  +full_name : str
  +email : str
  -password_hash : str
  +role : UserRole
  +is_blacklisted : bool
  +mfa_enabled : bool
  +kyc_status : str
  +created_at : datetime
}
class KycRecord {
  +user_id : str
  +pan_number : str
  +citizenship_number : str
  +date_of_birth : str
  +status : str
  +checks : map
  +review_note : str
}
class LoanApplication {
  +id : ObjectId
  +applicant_id : str
  +full_name : str
  +citizenship_number : str
  +address : str
  +loan_type : LoanType
  +monthly_income : float
  +existing_monthly_debt : float
  +requested_loan_amount : float
  +loan_duration_months : int
  +interest_rate_used : float
  +monthly_emi : float
  +emi_dti_ratio : float
  +affordability : str
  +pan_number : str
  +collateral_value : float
  +offered_loan_amount : float
  +offer_status : str
  +verification : map
  +status : ApplicationStatus
}
class ApplicationDocument {
  +id : ObjectId
  +application_id : str
  +user_id : str
  +document_type : DocumentType
  +filename : str
  +file_path : str
  +file_hash : str
  +uploaded_at : datetime
}
class OcrResult {
  +id : ObjectId
  +document_id : str
  +application_id : str
  +extracted_text : str
  +detected_document_type : str
  +detection_confidence : float
  +detected_fields : map
  +type_match : bool
  +verified_by_user : bool
}
class CreditRiskScore {
  +id : ObjectId
  +application_id : str
  +raw_score : int
  +normalized_score : int
  +risk_level : str
  +dti_ratio : float
  +lti_ratio : float
  +score_breakdown : map
}
class LoanAccount {
  +id : ObjectId
  +application_id : str
  +applicant_id : str
  +principal : float
  +interest_rate : float
  +tenure_months : int
  +monthly_emi : float
  +outstanding_balance : float
  +installments_paid : int
  +installments_total : int
  +missed_installments : int
  +next_due_date : datetime
  +status : LoanAccountStatus
}
class Payment {
  +id : ObjectId
  +loan_id : str
  +applicant_id : str
  +amount : float
  +kind : str
  +status : PaymentStatus
  +provider : str
  +provider_ref : str
  +merchant_name : str
  +qr_url : str
  +prepay_principal : float
  +fee_total : float
  +amount_paid : float
  +settled_at : datetime
}
class DocumentRequest {
  +id : ObjectId
  +application_id : str
  +requested_by : str
  +document_types : list
  +status : str
}
class ApplicationFlags {
  +id : ObjectId
  +application_id : str
  +flags : list
  +suspicion_level : str
}
class Notification {
  +id : ObjectId
  +user_id : str
  +title : str
  +message : str
  +is_read : bool
}
class AuditLog {
  +id : ObjectId
  +user_id : str
  +action : str
  +entity_type : str
  +entity_id : str
  +details : map
}
class AppSetting {
  +key : str
  +value : any
}

User "1" -- "0..1" KycRecord
User "1" -- "0..*" LoanApplication : applies >
LoanApplication "1" -- "0..*" ApplicationDocument
ApplicationDocument "1" -- "0..1" OcrResult
LoanApplication "1" -- "0..*" CreditRiskScore
LoanApplication "1" -- "0..1" LoanAccount : disburses >
LoanApplication "1" -- "0..*" DocumentRequest
LoanApplication "1" -- "0..1" ApplicationFlags
LoanAccount "1" -- "0..*" Payment
User "1" -- "0..*" Notification
User "1" -- "0..*" AuditLog

class ApplicationService <<service>>
class RiskService <<service>>
class EmiService <<service>>
class DocumentClassifier <<service>>
class DocumentVerification <<service>>
class PaymentService <<service>>
class LoanAccountService <<service>>
class ClockService <<service>>
class OtpService <<service>>

ApplicationService ..> LoanApplication
ApplicationService ..> EmiService
RiskService ..> CreditRiskScore
DocumentVerification ..> DocumentClassifier
DocumentVerification ..> OcrResult
PaymentService ..> Payment
PaymentService ..> LoanAccountService
LoanAccountService ..> LoanAccount
LoanAccountService ..> ClockService
OtpService ..> User
@enduml
```

---

## 3. ER Diagram

```plantuml
@startuml Sajilo_Loan_ER
hide circle
skinparam linetype ortho

entity users {
  * _id : ObjectId <<PK>>
  --
  full_name
  email <<unique>>
  phone <<unique>>
  password_hash
  role
  is_blacklisted
  mfa_enabled
  kyc_status
  created_at
}
entity kyc_records {
  * _id : ObjectId <<PK>>
  --
  * user_id <<FK>>
  pan_number
  citizenship_number
  date_of_birth
  status
  review_note
}
entity loan_applications {
  * _id : ObjectId <<PK>>
  --
  * applicant_id <<FK>>
  loan_type
  requested_loan_amount
  interest_rate_used
  monthly_emi
  offered_loan_amount
  offer_status
  status
}
entity application_documents {
  * _id : ObjectId <<PK>>
  --
  * application_id <<FK>>
  * user_id <<FK>>
  document_type
  file_path
  file_hash
  uploaded_at
}
entity ocr_results {
  * _id : ObjectId <<PK>>
  --
  * document_id <<FK>>
  application_id <<FK>>
  detected_document_type
  detection_confidence
  type_match
}
entity credit_risk_scores {
  * _id : ObjectId <<PK>>
  --
  * application_id <<FK>>
  normalized_score
  risk_level
  dti_ratio
}
entity loan_accounts {
  * _id : ObjectId <<PK>>
  --
  * application_id <<FK>>
  * applicant_id <<FK>>
  outstanding_balance
  installments_paid
  next_due_date
  status
}
entity payments {
  * _id : ObjectId <<PK>>
  --
  * loan_id <<FK>>
  * applicant_id <<FK>>
  amount
  provider
  provider_ref
  kind
  status
}
entity document_requests {
  * _id : ObjectId <<PK>>
  --
  * application_id <<FK>>
  requested_by <<FK>>
  status
}
entity notifications {
  * _id : ObjectId <<PK>>
  --
  * user_id <<FK>>
  title
  is_read
}
entity audit_logs {
  * _id : ObjectId <<PK>>
  --
  * user_id <<FK>>
  action
  entity_type
  entity_id
}
entity app_settings {
  * key : string <<PK>>
  --
  value
}

users            ||--o| kyc_records
users            ||--o{ loan_applications
loan_applications ||--o{ application_documents
application_documents ||--o| ocr_results
loan_applications ||--o{ credit_risk_scores
loan_applications ||--o| loan_accounts
loan_accounts    ||--o{ payments
loan_applications ||--o{ document_requests
users            ||--o{ notifications
users            ||--o{ audit_logs
@enduml
```

---

## 4. Schema Diagram (MongoDB collections with types)

```plantuml
@startuml Sajilo_Loan_Schema
skinparam linetype ortho
skinparam class {
  BackgroundColor #f8fafc
  BorderColor #64748b
}

class users << (C,#8ee0a1) collection >> {
  _id : ObjectId <<PK>>
  full_name : string
  email : string  <<unique idx>>
  phone : string  <<unique idx>>
  password_hash : string
  role : string  (customer|officer|admin)
  is_blacklisted : bool
  mfa_enabled : bool
  kyc_status : string
  created_at : date
}
class kyc_records << (C,#8ee0a1) collection >> {
  _id : ObjectId <<PK>>
  user_id : string  <<FK -> users>>
  full_name : string
  pan_number : string
  citizenship_number : string
  date_of_birth : string
  status : string  (pending|verified|rejected)
  checks : object
  review_note : string
}
class loan_applications << (C,#8ee0a1) collection >> {
  _id : ObjectId <<PK>>
  applicant_id : string  <<FK -> users>>
  loan_type : string
  monthly_income : number
  existing_monthly_debt : number
  requested_loan_amount : number
  loan_duration_months : int
  interest_rate_used : number
  monthly_emi : number
  emi_dti_ratio : number
  affordability : string
  pan_number : string
  collateral_value : number
  offered_loan_amount : number
  offer_status : string
  verification : object
  status : string
  created_at : date
}
class application_documents << (C,#8ee0a1) collection >> {
  _id : ObjectId <<PK>>
  application_id : string  <<FK>>
  user_id : string  <<FK>>
  document_type : string
  filename : string
  file_path : string
  content_type : string
  file_hash : string
  uploaded_at : date
}
class ocr_results << (C,#8ee0a1) collection >> {
  _id : ObjectId <<PK>>
  document_id : string  <<FK>>
  application_id : string  <<FK>>
  extracted_text : string
  detected_document_type : string
  detection_confidence : number
  detected_fields : object
  type_match : bool
  verified_by_user : bool
  created_at : date
}
class credit_risk_scores << (C,#8ee0a1) collection >> {
  _id : ObjectId <<PK>>
  application_id : string  <<FK>>
  raw_score : int
  normalized_score : int
  risk_level : string
  dti_ratio : number
  lti_ratio : number
  score_breakdown : object
  created_at : date
}
class loan_accounts << (C,#8ee0a1) collection >> {
  _id : ObjectId <<PK>>
  application_id : string  <<FK>>
  applicant_id : string  <<FK>>
  principal : number
  interest_rate : number
  tenure_months : int
  monthly_emi : number
  outstanding_balance : number
  installments_paid : int
  installments_total : int
  missed_installments : int
  next_due_date : date
  status : string
}
class payments << (C,#8ee0a1) collection >> {
  _id : ObjectId <<PK>>
  loan_id : string  <<FK>>
  applicant_id : string  <<FK>>
  amount : number
  kind : string  (emi|prepayment)
  status : string
  provider : string  (esewa_qr|khalti|esewa|mock)
  provider_ref : string  <<unique idx>>
  merchant_name : string
  qr_url : string
  prepay_principal : number
  fee_total : number
  amount_paid : number
  settled_at : date
}
class notifications << (C,#8ee0a1) collection >> {
  _id : ObjectId <<PK>>
  user_id : string  <<FK>>
  title : string
  message : string
  is_read : bool
  created_at : date
}
class audit_logs << (C,#8ee0a1) collection >> {
  _id : ObjectId <<PK>>
  user_id : string  <<FK>>
  action : string
  entity_type : string
  entity_id : string
  details : object
  created_at : date
}
class app_settings << (C,#8ee0a1) collection >> {
  key : string <<PK>>
  value : any
}

users <.. kyc_records : user_id
users <.. loan_applications : applicant_id
loan_applications <.. application_documents : application_id
application_documents <.. ocr_results : document_id
loan_applications <.. credit_risk_scores : application_id
loan_applications <.. loan_accounts : application_id
loan_accounts <.. payments : loan_id
users <.. notifications : user_id
users <.. audit_logs : user_id
@enduml
```

---

## 5. Sequence Diagram (apply → review → approve → pay EMI)

```plantuml
@startuml Sajilo_Loan_Sequence
autonumber
actor Customer
participant "Next.js BFF" as BFF
participant "FastAPI Backend" as API
database "MongoDB" as DB
actor "Loan Officer" as Officer
participant "eSewa / Khalti" as GW

== KYC verification (required first, before applying) ==
Customer -> BFF : Submit KYC (PAN, citizenship no., DOB)
BFF -> API : POST /kyc/submit
API -> DB : kyc_status = pending; notify officers
Officer -> BFF : Open KYC queue
BFF -> API : GET /kyc  (pending)
Officer -> BFF : Approve KYC
BFF -> API : PUT /kyc/{user_id}/review {approved:true}
API -> DB : kyc_status = verified
note over Customer, API : Loan application is blocked until KYC is verified\n(require_verified_kyc gate on create / draft / submit)

== Upload & verify document ==
Customer -> BFF : Upload citizenship (JPG/PDF)
BFF -> API : POST /applications/{id}/documents (JWT)
API -> API : OCR (Tesseract/pdfplumber) + classify
alt type mismatch
  API --> BFF : 400 "Doesnot look like required document"
  BFF --> Customer : re-upload
else accepted
  API -> DB : save document + ocr_result
  API --> BFF : 201 {detected citizenship no / name / address}
  BFF --> Customer : auto-fill application
end

== Submit application ==
Customer -> BFF : Submit
BFF -> API : POST /applications/{id}/submit
API -> API : KYC-verified gate + salary cap + collateral docs
API -> DB : status = submitted
API -> DB : notify officers

== Officer review ==
Officer -> BFF : Open review
BFF -> API : GET /officer/applications/{id}
API -> DB : application + docs + risk + name-match
API --> Officer : review packet
Officer -> BFF : Approve
BFF -> API : PUT /officer/applications/{id}/status
API -> DB : status = approved
API -> DB : create loan_account (disbursement)

== Pay EMI (method = qr | khalti) ==
Customer -> BFF : Pay EMI
BFF -> API : POST /loans/{id}/payments/initiate?method
API -> API : check payment window (>= 7 days before due)
alt Khalti
  API -> GW : initiate (KPG-2)
  GW --> API : payment_url + pidx
  Customer -> GW : pay on hosted page
  GW --> Customer : redirect back (pidx)
  Customer -> BFF : /payments/verify
  BFF -> API : verify
  API -> GW : lookup(pidx)
  GW --> API : Completed
else eSewa personal QR
  API --> Customer : show eSewa QR (Sudin khanal)
  Customer -> GW : scan & pay merchant
  Customer -> BFF : "I've completed the payment"
  BFF -> API : POST /payments/{id}/submitted
  API -> DB : status = awaiting_confirmation
  Officer -> BFF : Confirm payments
  BFF -> API : POST /officer/payments/{id}/confirm
end
API -> DB : settle: reduce outstanding, advance next_due_date
API --> Customer : receipt
@enduml
```

---

## 6. Activity Diagram (loan origination + repayment)

```plantuml
@startuml Sajilo_Loan_Activity
start
:Register (Gmail) & login;
:Submit KYC;
:Officer reviews KYC;
if (KYC verified?) then (no)
  :Resubmit KYC;
  stop
else (yes)
endif

:Choose loan type;
:Upload documents;
:System reads (OCR/PDF) & classifies;
if (Matches required type?) then (no)
  :Deny — "Doesnot look like required document";
  :Re-upload correct document;
  stop
else (yes)
  :Accept; auto-fill citizenship no. / name / address;
endif

:Fill application details;
:Submit application;
if (Within salary-based cap?) then (no)
  :Reject — exceeds cap;
  stop
else (yes)
endif
if (Collateral loan (> 2 lakh)?) then (yes)
  if (Statement + property + valuation uploaded?) then (no)
    :Block — collateral documents required;
    stop
  else (yes)
  endif
else (no)
endif
:Status = Submitted;

:Officer reviews application, documents, risk score, name-match;
if (Officer decision) then (Counter-offer)
  if (Customer accepts offer?) then (yes)
    :Approved at offered amount;
  else (no)
    :Rejected;
    stop
  endif
elseif (Reject) then (rejected)
  :Rejected;
  stop
else (Approve)
  :Approved;
endif
:Create loan account (disbursed);

repeat
  :Wait until 7 days before due date;
  :Customer pays EMI (eSewa QR / Khalti) or advance payment;
  if (Method = QR?) then (yes)
    :Officer confirms payment received;
  else (Khalti)
    :Verify via gateway lookup;
  endif
  :Settle — reduce outstanding, advance due date;
  note right
    Missed EMIs are counted by the
    scheduled/clock-run billing job;
    3 consecutive misses -> blacklisted.
  end note
repeat while (Outstanding balance > 0?) is (yes)
->no;
:Loan completed;
stop
@enduml
```
