"""Core Banking Simulator (CBS) — a bounded context that models a commercial
bank's core: customers (CIF), deposit (CASA) accounts, and loan accounts.

It is deliberately isolated from the LOS: its own ``cbs_*`` collections, its own
services/routes, and its own numbering. The LOS talks to it over the internal
API (mounted under ``/cbs/v1``) and stores only references (``cif_no`` /
``loan_account_no``). This first slice implements the Customer Account and Loan
Account modules; the general ledger, disbursement, EMI and end-of-day batch are
added in later features.
"""
