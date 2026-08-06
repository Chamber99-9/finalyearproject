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
};

/**
 * Officer confirmation queue for scanned-QR payments. A customer paid the
 * merchant QR and marked it done; the officer confirms receipt, which settles
 * the EMI against the loan.
 */
export function OfficerPayments() {
  const [payments, setPayments] = useState<PendingPayment[]>([]);
  const [confirmingId, setConfirmingId] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

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

  async function confirm(paymentId: string) {
    setConfirmingId(paymentId);
    setError("");
    setSuccess("");
    try {
      const r = await fetch(`/api/officer/payments/${encodeURIComponent(paymentId)}/confirm`, {
        method: "POST"
      });
      const p = await r.json().catch(() => ({}));
      if (!r.ok) {
        setError(p.error ?? "Could not confirm the payment.");
        return;
      }
      setPayments((current) => current.filter((payment) => payment.id !== paymentId));
      setSuccess("Payment confirmed and applied to the loan.");
    } catch {
      setError("Could not reach the payment service.");
    } finally {
      setConfirmingId("");
    }
  }

  return (
    <section className="page-wrap">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Loan officer</p>
          <h1 className="mt-3 text-3xl font-bold text-slate-950 sm:text-4xl">Confirm payments</h1>
          <p className="mt-3 max-w-3xl text-base leading-7 text-slate-700">
            Customers who scanned the QR and paid appear here. Confirm receipt to apply the payment.
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
          payments.map((payment) => (
            <article key={payment.id} className="panel-pad flex flex-wrap items-center justify-between gap-3">
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
              <button
                className="btn-primary px-4 py-2 text-sm"
                disabled={confirmingId === payment.id}
                onClick={() => confirm(payment.id)}
                type="button"
              >
                {confirmingId === payment.id ? "Confirming…" : "Confirm received"}
              </button>
            </article>
          ))
        ) : (
          <p className="panel-pad text-slate-600">No payments awaiting confirmation.</p>
        )}
      </div>
    </section>
  );
}
