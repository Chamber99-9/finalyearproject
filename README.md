# Sajilo Loan

vercel link : https://finalyearproject-rosy.vercel.app/login
Sajilo Loan is a Digital Loan Origination System for Nepal's banks, cooperatives, and finance companies. This repository is currently a clean starter structure for a Next.js frontend and FastAPI backend.

## Tech Stack
- Frontend: Next.js, TypeScript, Tailwind CSS
- Backend: FastAPI, Python
- Database: MongoDB
- OCR: Tesseract OCR
- Authentication: JWT
- Roles: Customer, Loan Officer, Admin

## Project Structure
```text
los/
  frontend/          Next.js TypeScript app
  backend/           FastAPI app
  AGENTS.md          Agent guidance for future development
  ROADMAP.md         Project roadmap
```

## Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

The frontend development server will run at:

```text
http://localhost:3000
```

Starter frontend routes:

```text
/                   Home page
/login              Login page
/register           Register page
/dashboard/customer Customer dashboard placeholder
/dashboard/officer  Officer dashboard placeholder
/dashboard/admin    Admin dashboard placeholder
/applications/new   Customer loan application form
/applications/documents Customer document upload page
/ocr/verify         Customer OCR verification page
```

Frontend auth proxy:

```text
SAJILO_API_BASE_URL=http://127.0.0.1:8000
```

The frontend login and register pages call Next.js API routes under `/api/auth/*`.
Those route handlers forward requests to FastAPI and store the JWT in an HTTP-only
cookie.

## Backend Setup
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

The backend API will run at:

```text
http://localhost:8000
```

FastAPI docs will be available at:

```text
http://localhost:8000/docs
```

Health check:

```text
GET http://localhost:8000/health
```

Auth endpoints:

```text
POST http://localhost:8000/auth/register
POST http://localhost:8000/auth/login
GET  http://localhost:8000/auth/me
```

Customer application endpoints:

```text
POST http://localhost:8000/applications
GET  http://localhost:8000/applications/my
GET  http://localhost:8000/applications/{application_id}
POST http://localhost:8000/applications/{application_id}/submit
POST http://localhost:8000/applications/{application_id}/documents
```

Notification endpoints:

```text
GET http://localhost:8000/notifications/my
PUT http://localhost:8000/notifications/{notification_id}/read
```

Notifications are in-app only for now. They are created when an application is
submitted, an officer requests documents, or an application is approved or
rejected. SMS and email delivery are not implemented yet.

Loan applications include a `loan_type` field. Current supported values are:

```text
personal | business | education | home | vehicle | agriculture | other
```

Document upload uses multipart form data with one file per request:

```text
document_type=citizenship_document | salary_slip | bank_statement | supporting_document
file=<PDF, JPEG, PNG, or WebP file>
```

For now, all loan types use the same required documents: citizenship document,
salary slip, and bank statement. Loan-type-specific document rules can be added
later without changing uploaded document metadata.

OCR endpoint:

```text
POST http://localhost:8000/ocr/extract/{document_id}
GET  http://localhost:8000/ocr/results/{ocr_result_id}
PUT  http://localhost:8000/ocr/verify/{ocr_result_id}
```

OCR currently supports uploaded image documents only: JPEG, PNG, and WebP. PDF OCR
will require a PDF rendering dependency in a later phase.

Credit risk scoring endpoint:

```text
POST http://localhost:8000/risk/calculate/{application_id}
```

This endpoint requires an officer or admin bearer token. It calculates a
rule-based decision-support score from the stored loan application data, saves a
new historical score record in MongoDB, and does not approve, reject, or change
the application status.

Suspicious application flagging endpoint:

```text
POST http://localhost:8000/flags/check/{application_id}
```

This endpoint requires an officer or admin bearer token. It checks duplicate
citizenship numbers, missing required documents, OCR verification inconsistencies,
duplicate document hashes, low OCR confidence, and unusual loan amounts. Results
are stored in `application_flags` for officer review and audit support only.

Loan officer endpoints:

```text
GET  http://localhost:8000/officer/applications
GET  http://localhost:8000/officer/applications/{application_id}
PUT  http://localhost:8000/officer/applications/{application_id}/status
POST http://localhost:8000/officer/applications/{application_id}/request-document
```

These endpoints require an officer bearer token. Officers can review submitted
applications, related documents, latest OCR results, latest credit risk score,
latest suspicious flags, update application status, and request additional
documents. Status updates and document requests create audit log entries.

Admin endpoints:

```text
GET http://localhost:8000/admin/overview
GET http://localhost:8000/admin/users
PUT http://localhost:8000/admin/users/{user_id}/role
GET http://localhost:8000/admin/audit-logs
```

These endpoints require an admin bearer token. Admins can view overview totals,
view users, update user roles, and review audit logs. New audit entries use the
fields `user_id`, `action`, `entity_type`, `entity_id`, `details`, and
`created_at`.

Security settings live in `backend/.env`. Use a strong `JWT_SECRET_KEY`,
configure `CORS_ALLOWED_ORIGINS` for the frontend origins you trust, and keep
`MAX_UPLOAD_BYTES` plus rate-limit settings appropriate for the deployment.

## Current Status
This repository includes starter frontend/backend flows plus backend modules for
JWT authentication, loan applications, document upload, OCR extraction, OCR
verification, credit risk scoring, suspicious application flagging,
officer/admin review workflows, dashboards, audit logs, and notifications.
Remaining product areas include broader testing, deployment hardening, and real
SMS/email delivery.
