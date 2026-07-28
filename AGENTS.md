# Sajilo Loan Agent Guide

## Project Identity
Sajilo Loan is a Digital Loan Origination System for Nepal's banks, cooperatives, and finance companies. The project aims to reduce branch visits, paperwork, and manual review effort while keeping loan officers in control of final lending decisions.

## Required Stack
- Frontend: Next.js with TypeScript
- Styling: Tailwind CSS
- Backend: FastAPI with Python
- Database: MongoDB
- OCR: Tesseract OCR
- Authentication: JWT
- Roles: Customer, Loan Officer, Admin

## Core Product Goals
- Customer registration and login
- Online loan application submission
- Document upload for required supporting files
- OCR extraction with customer verification before final submission
- Rule-based credit risk scoring
- Suspicious application flagging
- Loan officer dashboard for review, requests, approvals, and rejections
- Admin dashboard for user management and audit log review
- Application status tracking for customers

## Engineering Rules
- Do not scaffold or implement the actual app until explicitly requested.
- Keep frontend and backend code separated when the app is created.
- Enforce JWT authentication and role-based access control for protected workflows.
- Treat customer, financial, and document data as sensitive.
- Record audit logs for important actions such as login, application submission, document upload, OCR verification, status change, approval, rejection, and admin changes.
- Keep credit scoring and suspicious flagging as decision-support tools only. They must not automatically approve or reject a loan.
- Build for Nepal-focused lending workflows and keep NRB digital lending compliance in mind.
- Prefer clear, maintainable implementation over premature abstraction.

## MVP Constraints
- Uploaded documents should be stored on the local file system through FastAPI upload handling, with metadata stored in MongoDB.
- Cloud storage, core banking integration, payment gateways, and native mobile apps are outside the MVP.
- OCR accuracy depends on document quality, so extracted data must be shown to the customer for verification and correction.
- Loan officers make the final loan decision even when credit risk scores or suspicious flags are present.
- Email and SMS notifications are useful future additions, but should only be implemented when explicitly requested.

