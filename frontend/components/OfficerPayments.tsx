"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { formatMoney } from "@/lib/officer";

type PendingPayment = {
  id: string;
  loan_id: string;
  applicant_id: string;
  amount: number;
  kind?: string | null;
  provider_ref: string;
  merchant_name?: string | null;
  updated_at: string;
  depositor_account_number?: string | null;
  amount_deposited?: number | null;
  customer_remarks?: string | null;
};

/**
 * Officer review queue for scanned-QR payments. A customer paid the merchant
 * QR and submitted a receipt (the account they paid from + amount
 * deposited). The officer checks those two details against the bank
 * statement, then either confirms — cutting the EMI by the verified amount —
 * or rejects with a reason so the customer can resubmit.
 */
export function OfficerPayments() {
  const [payments, setPayments] = useState<PendingPayment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [openId, setOpenId] = useState("");
  const [verifiedAmount, setVerifiedAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [rejectingId, setRejectingId] = useState("");
  const [busyId, setBusyId] = useState("");

  useEffect(() => {
    load();
  }, []);

  async function load() {
    setIsLoading(true);
    try {
      const r = await fetch("/api/officer/payments/pending");
      const p = await r.json().catch(() => ({}));
      if (r.ok) setPayments(p.payments ?? []);
      else setError(p.error ?? "Could not load pending payments.");
    } catch {
      setError("Could not reach the payment service.");
    } finally {
      setIsLoading(false);
    }
  }

  function openReview(payment: PendingPayment) {
    setOpenId(payment.id);
    setRejectingId("");
    setVerifiedAmount(
      payment.amount_deposited != null ? String(payment.amount_deposited) : String(payment.amount)
    );
    setNotes("");
    setError("");
    setSuccess("");
  }

  async function confirm(paymentId: string) {
    setBusyId(paymentId);
    setError("");
    setSuccess("");
    try {
      const r = await fetch(`/api/officer/payments/${encodeURIComponent(paymentId)}/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          verified_amount: verifiedAmount ? Number(verifiedAmount) : undefined,
          notes: notes.trim() || undefined
        })
      });
      const p = await r.json().catch(() => ({}));
      if (!r.ok) {
        setError(p.error ?? "Could not confirm the payment.");
        return;
      }
      setPayments((current) => current.filter((payment) => payment.id !== paymentId));
      setOpenId("");
      setSuccess(
        p.payment?.is_partial
          ? "Partial payment applied — the shortfall is still due for this EMI."
          : "Payment confirmed and applied to the loan."
      );
    } catch {
      setError("Could not reach the payment service.");
    } finally {
      setBusyId("");
    }
  }

  async function reject(paymentId: string) {
    if (rejectReason.trim().length < 3) {
      setError("Enter a reason so the customer knows what to fix.");
      return;
    }
    setBusyId(paymentId);
    setError("");
    setSuccess("");
    try {
      const r = await fetch(`/api/officer/payments/${encodeURIComponent(paymentId)}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: rejectReason.trim() })
      });
      const p = await r.json().catch(() => ({}));
      if (!r.ok) {
        setError(p.error ?? "Could not reject the payment.");
        return;
      }
      setPayments((current) => current.filter((payment) => payment.id !== paymentId));
      setOpenId("");
      setRejectingId("");
      setRejectReason("");
      setSuccess("Payment rejected — the customer can resubmit.");
    } catch {
      setError("Could not reach the payment service.");
    } finally {
      setBusyId("");
    }
  }

  return (
    <section className="page-wrap">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Loan officer</p>
          <h1 className="mt-3 text-3xl font-bold text-slate-950 sm:text-4xl">Confirm payments</h1>
          <p className="mt-3 max-w-3xl text-base leading-7 text-slate-700">
            Customers who scanned the QR and paid appear here with the account number and amount
            they deposited. Check it against the bank statement, then confirm or reject.
          </p>
        </div>
        <Link className="btn-secondary px-4 py-2 text-sm" href="/dashboard/officer">
          Back to applications
        </Link>
      </div>

      {error ? <p className="alert-error mt-6">{error}</p> : null}
      {success ? <p className="alert-success mt-6">{success}</p> : null}

      <div className="mt-6 grid gap-4">
        {isLoading ? (
          <p className="panel-pad text-slate-600">Loading pending payments...</p>
        ) : payments.length > 0 ? (
          payments.map((payment) => {
            const isOpen = openId === payment.id;
            return (
              <article key={payment.id} className="panel-pad">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="text-sm">
                    <p className="text-base font-bold text-slate-950">{formatMoney(payment.amount)}</p>
                    <p className="mt-1 text-slate-600">
                      {payment.kind === "prepayment" ? "Advance payment" : "EMI"} · to{" "}
                      {payment.merchant_name || "merchant"}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      Loan {payment.loan_id} · marked paid {new Date(payment.updated_at).toLocaleString()}
                    </p>
                  </div>
                  {!isOpen ? (
                    <button
                      className="btn-primary px-4 py-2 text-sm"
                      onClick={() => openReview(payment)}
                      type="button"
                    >
                      Review receipt
                    </button>
                  ) : null}
                </div>

                {isOpen ? (
                  <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Customer's receipt
                    </p>
                    <dl className="mt-2 space-y-1 text-sm">
                      <div className="flex items-center justify-between gap-3">
                        <dt className="text-slate-500">Account number</dt>
                        <dd className="font-semibold text-slate-950">
                          {payment.depositor_account_number || "—"}
                        </dd>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <dt className="text-slate-500">Amount deposited</dt>
                        <dd className="font-semibold text-slate-950">
                          {payment.amount_deposited != null ? formatMoney(payment.amount_deposited) : "—"}
                        </dd>
                      </div>
                      {payment.customer_remarks ? (
                        <div className="flex items-center justify-between gap-3">
                          <dt className="text-slate-500">Remarks</dt>
                          <dd className="text-right text-slate-800">{payment.customer_remarks}</dd>
                        </div>
                      ) : null}
                    </dl>

                    {rejectingId !== payment.id ? (
                      <>
                        <label
                          className="mt-4 block text-xs font-semibold text-slate-600"
                          htmlFor={`verified-${payment.id}`}
                        >
                          Verified amount (from the bank statement)
                        </label>
                        <input
                          className="mt-1 w-full px-3 py-2.5"
                          id={`verified-${payment.id}`}
                          min="0"
                          onChange={(event) => setVerifiedAmount(event.target.value)}
                          step="0.01"
                          type="number"
                          value={verifiedAmount}
                        />
                        <p className="mt-1 text-xs text-slate-500">
                          If this is less than the EMI, it's applied as a partial payment — the
                          due date won't move and the customer still owes the difference.
                        </p>

                        <label
                          className="mt-3 block text-xs font-semibold text-slate-600"
                          htmlFor={`notes-${payment.id}`}
                        >
                          Notes (optional)
                        </label>
                        <input
                          className="mt-1 w-full px-3 py-2.5"
                          id={`notes-${payment.id}`}
                          onChange={(event) => setNotes(event.target.value)}
                          placeholder="e.g. matches statement line 12"
                          type="text"
                          value={notes}
                        />

                        <div className="mt-4 flex flex-wrap gap-2">
                          <button
                            className="btn-primary px-4 py-2 text-sm"
                            disabled={busyId === payment.id}
                            onClick={() => confirm(payment.id)}
                            type="button"
                          >
                            {busyId === payment.id ? "Confirming…" : "Confirm & cut EMI"}
                          </button>
                          <button
                            className="btn-secondary px-4 py-2 text-sm text-rose-700"
                            disabled={busyId === payment.id}
                            onClick={() => setRejectingId(payment.id)}
                            type="button"
                          >
                            Reject
                          </button>
                          <button
                            className="btn-muted px-4 py-2 text-sm"
                            disabled={busyId === payment.id}
                            onClick={() => setOpenId("")}
                            type="button"
                          >
                            Close
                          </button>
                        </div>
                      </>
                    ) : (
                      <>
                        <label
                          className="mt-4 block text-xs font-semibold text-slate-600"
                          htmlFor={`reason-${payment.id}`}
                        >
                          Reason (shown to the customer)
                        </label>
                        <input
                          className="mt-1 w-full px-3 py-2.5"
                          id={`reason-${payment.id}`}
                          onChange={(event) => setRejectReason(event.target.value)}
                          placeholder="e.g. account number doesn't match any deposit"
                          type="text"
                          value={rejectReason}
                        />
                        <div className="mt-4 flex flex-wrap gap-2">
                          <button
                            className="btn-primary bg-rose-700 px-4 py-2 text-sm hover:bg-rose-800"
                            disabled={busyId === payment.id}
                            onClick={() => reject(payment.id)}
                            type="button"
                          >
                            {busyId === payment.id ? "Rejecting…" : "Confirm rejection"}
                          </button>
                          <button
                            className="btn-muted px-4 py-2 text-sm"
                            disabled={busyId === payment.id}
                            onClick={() => setRejectingId("")}
                            type="button"
                          >
                            Back
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                ) : null}
              </article>
            );
          })
        ) : (
          <p className="panel-pad text-slate-600">No payments awaiting confirmation.</p>
        )}
      </div>
    </section>
  );
}
