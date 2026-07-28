# Sajilo Loan Roadmap

## Summary
Sajilo Loan will be built as a web-based Digital Loan Origination System for Nepal's banks, cooperatives, and finance companies. The MVP will support customer applications, document upload, OCR-assisted verification, rule-based credit risk scoring, suspicious application flagging, officer review, admin oversight, audit logs, and status tracking.

## Phase 0: Documentation and Planning
- Create project guidance and implementation roadmap.
- Keep the repository documentation-only until app scaffolding is requested.
- Confirm MVP boundaries, roles, stack, and proposal-aligned constraints.

## Phase 1: App Scaffolding and Development Environment
- Create separate frontend and backend workspaces.
- Scaffold Next.js with TypeScript and Tailwind CSS for the frontend.
- Scaffold FastAPI with Python for the backend.
- Add MongoDB connection setup, environment variable examples, and local development instructions.
- Add basic project scripts and dependency management only after app creation is requested.

## Phase 2: Authentication, Roles, and User Management
- Implement customer registration and login.
- Add JWT-based authentication.
- Add role-based access control for Customer, Loan Officer, and Admin.
- Protect dashboards and backend endpoints according to role.

## Phase 3: Customer Loan Application Flow
- Build the online loan application form.
- Capture applicant identity, contact, employment, income, requested loan amount, repayment duration, existing debt, dependents, savings buffer, and repayment history.
- Add application draft, submit, and status tracking flows.

## Phase 4: Document Upload, OCR, and Verification
- Add required document upload support for citizenship ID, salary slips, bank statements, and other supporting documents.
- Store uploaded files locally through FastAPI upload handling.
- Store file metadata in MongoDB.
- Integrate Tesseract OCR for document text extraction.
- Show extracted fields to customers for verification and correction before final submission.

## Phase 5: Credit Risk Scoring and Suspicious Flagging
- Implement rule-based credit risk scoring using income, employment stability, debt-to-income ratio, loan-to-income ratio, repayment history, dependents, and savings buffer.
- Normalize scores to a 300-850 range and classify risk as Low, Medium, or High.
- Add suspicious application flags for duplicate citizenship, name mismatch, income mismatch, bank statement mismatch, missing documents, low OCR confidence, duplicate document hash, and unusual loan request.
- Display credit risk and suspicion outputs together as officer decision support only.

## Phase 6: Loan Officer Dashboard and Workflow
- Build a secure loan officer dashboard.
- Show submitted applications, OCR verification data, uploaded documents, credit risk score, and suspicious flags.
- Allow officers to request additional documents, update application status, approve applications, or reject applications.
- Keep every workflow decision auditable.

## Phase 7: Admin Dashboard and Audit Logs
- Build an admin dashboard for user and role management.
- Add audit log search and review.
- Track important security, application, document, OCR, scoring, and decision events.
- Keep admin actions visible through audit history.

## Phase 8: Testing, Performance, and Deployment Preparation
- Add unit tests for backend business logic and scoring rules.
- Add integration tests for authentication, application submission, document upload, OCR verification, and officer workflow.
- Add frontend workflow tests for customer, officer, and admin paths.
- Validate support for 100 concurrent users.
- Target common API responses under 300 ms.
- Target OCR processing under 5 seconds per document.
- Prepare deployment documentation and security checks before production use.

## MVP Boundaries
- No core banking system integration.
- No payment gateway integration.
- No native mobile app.
- No automatic loan approval or rejection.
- No cloud document storage unless requested later.

