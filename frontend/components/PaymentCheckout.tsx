"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ESEWA_QR_DATA_URI } from "@/lib/esewaQr";
import { formatMoney } from "@/lib/officer";

export type Payment = {
  id: string;
  loan_id: string;
  amount: number;
  status: string;
  provider: string;
  provider_ref: string;
  merchant_name?: string | null;
  merchant_phone?: string | null;
  qr_url?: string | null;
  amount_paid?: number | null;
  outstanding_after?: number | null;
  installments_paid_after?: number | null;
  installments_total?: number | null;
  next_due_date?: string | null;
  settled_at?: string | null;
  depositor_account_number?: string | null;
  amount_deposited?: number | null;
  customer_remarks?: string | null;
  officer_notes?: string | null;
  is_partial?: boolean | null;
  shortfall?: number | null;
};

/**
 * Scan-to-pay checkout. The customer scans the merchant's personal eSewa QR,
 * pays that account directly, then fills in a short receipt — the account
 * number they paid from and the amount they deposited — before submitting.
 * That receipt goes to an officer, who checks it against the bank statement
 * and confirms (or rejects) it; the EMI is only cut once confirmed.
 */
export function PaymentCheckout({ paymentId }: { paymentId: string }) {
  const [payment, setPayment] = useState<Payment | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isPaying, setIsPaying] = useState(false);
  const [error, setError] = useState("");
  const [showReceiptForm, setShowReceiptForm] = useState(false);
  const [accountNumber, setAccountNumber] = useState("");
  const [amountDeposited, setAmountDeposited] = useState("");
  const [remarks, setRemarks] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const response = await fetch(`/api/payments/${encodeURIComponent(paymentId)}`);
        const data = await response.json().catch(() => ({}));
        if (response.ok) {
          setPayment(data.payment);
          if (data.payment?.amount) setAmountDeposited(String(data.payment.amount));
        } else {
          setError(data.error ?? "Payment not found.");
        }
      } catch {
        setError("Could not reach the payment service.");
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [paymentId]);

  async function submitReceipt() {
    setError("");
    if (accountNumber.trim().length < 4) {
      setError("Enter the bank/eSewa account number you paid from.");
      return;
    }
    const amount = Number(amountDeposited);
    if (!amount || amount <= 0) {
      setError("Enter the amount you deposited.");
      return;
    }

    setIsPaying(true);
    try {
      const response = await fetch(`/api/payments/${encodeURIComponent(paymentId)}/submitted`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          depositor_account_number: accountNumber.trim(),
          amount_deposited: amount,
          remarks: remarks.trim() || undefined
        })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(data.error ?? "Could not submit the payment.");
        return;
      }
      setPayment(data.payment);
      setShowReceiptForm(false);
    } catch {
      setError("Could not reach the payment service.");
    } finally {
      setIsPaying(false);
    }
  }

  if (isLoading) {
    return <section className="mx-auto max-w-lg px-5 py-16 text-slate-600">Loading checkout...</section>;
  }
  if (!payment) {
    return (
      <section className="mx-auto max-w-lg px-5 py-16">
        <p className="alert-error">{error || "Payment not found."}</p>
        <Link className="btn-secondary mt-4 inline-flex px-4 py-2" href="/dashboard/customer">
          Back to dashboard
        </Link>
      </section>
    );
  }

  if (payment.status === "success") {
    return (
      <section className="mx-auto max-w-lg px-5 py-10 sm:py-14">
        <Receipt payment={payment} />
      </section>
    );
  }

  const awaiting = payment.status === "awaiting_confirmation";
  const rejected = payment.status === "rejected";
  // Use a full http(s)/data URL if configured; otherwise the embedded real QR.
  const qrSrc =
    (payment.qr_url && /^(https?:|data:)/.test(payment.qr_url) ? payment.qr_url : null) ||
    process.env.NEXT_PUBLIC_MERCHANT_QR_URL ||
    ESEWA_QR_DATA_URI;

  return (
    <section className="mx-auto max-w-lg px-5 py-10 sm:py-14">
      <div className="panel-pad p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-lg font-bold text-slate-950">
            <span className="flex h-8 w-8 items-center justify-center rounded-md bg-emerald-700 text-xs text-white">
              SL
            </span>
            Sajilo Pay
          </div>
          <span className="rounded-md bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">
            eSewa QR
          </span>
        </div>

        <div className="mt-5 rounded-lg bg-slate-50 p-4 text-center">
          <p className="text-sm text-slate-600">Amount due</p>
          <p className="mt-1 text-3xl font-bold text-slate-950">{formatMoney(payment.amount)}</p>
          <p className="mt-1 text-xs text-slate-500">Ref {payment.provider_ref.slice(0, 12)}…</p>
        </div>

        {rejected ? (
          <div className="mt-6 rounded-lg border border-rose-200 bg-rose-50 p-5">
            <p className="text-lg font-bold text-rose-900">Receipt could not be verified</p>
            <p className="mt-1 text-sm text-rose-800">
              {payment.officer_notes || "The bank statement didn't match what you submitted."}
            </p>
            <p className="mt-2 text-sm text-rose-800">
              Double-check the account number and amount, then submit again below.
            </p>
          </div>
        ) : null}

        {awaiting ? (
          <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-5 text-center">
            <p className="text-lg font-bold text-amber-900">Payment submitted</p>
            <p className="mt-1 text-sm text-amber-800">
              Waiting for the bank to confirm your payment was received. Your EMI updates once an
              officer confirms it.
            </p>
            <dl className="mt-4 space-y-1 text-left text-sm">
              <Row label="Paid from account" value={payment.depositor_account_number || "—"} />
              <Row
                label="Amount deposited"
                value={payment.amount_deposited != null ? formatMoney(payment.amount_deposited) : "—"}
              />
            </dl>
            <Link className="btn-secondary mt-4 inline-flex px-4 py-2" href="/dashboard/customer">
              Back to dashboard
            </Link>
          </div>
        ) : (
          <>
            <div className="mt-4 flex flex-col items-center gap-3">
              <div className="rounded-xl border-2 border-emerald-500 bg-white p-2">
                <img
                  alt="eSewa payment QR"
                  className="h-56 w-56 rounded-lg object-contain"
                  src={qrSrc}
                />
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-slate-800">
                  {payment.merchant_name || "Merchant"} · {payment.merchant_phone || ""}
                </p>
                <p className="mt-0.5 text-xs text-slate-500">
                  Open eSewa → Scan &amp; Pay → send {formatMoney(payment.amount)} to this QR.
                </p>
              </div>
            </div>

            {error ? <p className="alert-error mt-4 px-3 py-2">{error}</p> : null}

            {!showReceiptForm ? (
              <>
                <button
                  className="btn-primary mt-5 w-full px-5 py-3"
                  onClick={() => setShowReceiptForm(true)}
                  type="button"
                >
                  I've completed the payment
                </button>
                <Link
                  className="mt-3 block text-center text-sm font-semibold text-slate-500 hover:text-slate-700"
                  href="/dashboard/customer"
                >
                  Cancel
                </Link>
              </>
            ) : (
              <div className="mt-5 rounded-lg border border-slate-200 p-4">
                <p className="text-sm font-semibold text-slate-950">Confirm your deposit receipt</p>
                <p className="mt-1 text-xs text-slate-500">
                  An officer checks this against the bank statement before your EMI is updated.
                </p>

                <label className="mt-4 block text-xs font-semibold text-slate-600" htmlFor="depositor-account">
                  Account number you paid from
                </label>
                <input
                  className="mt-1 w-full px-3 py-2.5"
                  id="depositor-account"
                  onChange={(event) => setAccountNumber(event.target.value)}
                  placeholder="e.g. 9801234567"
                  type="text"
                  value={accountNumber}
                />

                <label className="mt-3 block text-xs font-semibold text-slate-600" htmlFor="amount-deposited">
                  Amount deposited
                </label>
                <input
                  className="mt-1 w-full px-3 py-2.5"
                  id="amount-deposited"
                  min="1"
                  onChange={(event) => setAmountDeposited(event.target.value)}
                  step="0.01"
                  type="number"
                  value={amountDeposited}
                />

                <label className="mt-3 block text-xs font-semibold text-slate-600" htmlFor="remarks">
                  Remarks (optional)
                </label>
                <input
                  className="mt-1 w-full px-3 py-2.5"
                  id="remarks"
                  onChange={(event) => setRemarks(event.target.value)}
                  placeholder="e.g. transaction ID from the eSewa app"
                  type="text"
                  value={remarks}
                />

                <div className="mt-4 flex flex-col gap-2 sm:flex-row">
                  <button
                    className="btn-primary flex-1 px-5 py-2.5"
                    disabled={isPaying}
                    onClick={submitReceipt}
                    type="button"
                  >
                    {isPaying ? "Submitting..." : "Submit receipt"}
                  </button>
                  <button
                    className="btn-secondary flex-1 px-5 py-2.5"
                    disabled={isPaying}
                    onClick={() => setShowReceiptForm(false)}
                    type="button"
                  >
                    Back
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}

export function Receipt({ payment }: { payment: Payment }) {
  return (
    <div className="panel-pad p-6">
      <div className="flex flex-col items-center text-center">
        <span className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-2xl text-emerald-700">
          ✓
        </span>
        <h1 className="mt-3 text-2xl font-bold text-slate-950">
          {payment.is_partial ? "Partial payment received" : "Payment successful"}
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          {payment.is_partial
            ? "Your deposit was verified and applied, but it didn't cover the full EMI."
            : "Your EMI has been received."}
        </p>
      </div>

      {payment.is_partial ? (
        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          NPR {payment.shortfall != null ? formatMoney(payment.shortfall) : "—"} is still due to
          complete this installment. The due date has not moved — pay the difference to avoid
          being marked overdue.
        </div>
      ) : null}

      <div className="mt-6 rounded-lg border border-slate-200">
        <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
          <p className="text-sm font-semibold text-slate-950">Payment receipt</p>
        </div>
        <dl className="divide-y divide-slate-100 text-sm">
          <Row label="Amount paid" value={formatMoney(payment.amount_paid ?? payment.amount)} strong />
          <Row label="Status" value={payment.is_partial ? "Partially paid" : "Paid"} />
          <Row
            label="Date"
            value={payment.settled_at ? new Date(payment.settled_at).toLocaleString() : "—"}
          />
          <Row label="Transaction ref" value={payment.provider_ref} />
          <Row label="Method" value={payment.provider.replace(/_/g, " ")} />
          {payment.depositor_account_number ? (
            <Row label="Paid from account" value={payment.depositor_account_number} />
          ) : null}
          <Row
            label="Remaining balance"
            value={
              payment.outstanding_after != null ? formatMoney(payment.outstanding_after) : "—"
            }
          />
          <Row
            label="Installments paid"
            value={
              payment.installments_paid_after != null && payment.installments_total != null
                ? `${payment.installments_paid_after}/${payment.installments_total}`
                : "—"
            }
          />
          <Row
            label="Next due"
            value={
              payment.next_due_date
                ? new Date(payment.next_due_date).toLocaleDateString()
                : "—"
            }
          />
        </dl>
      </div>

      <div className="no-print mt-5 flex flex-col gap-3 sm:flex-row">
        <button
          className="btn-secondary px-5 py-2.5"
          onClick={() => window.print()}
          type="button"
        >
          Print / save receipt
        </button>
        <Link className="btn-primary px-5 py-2.5 text-center" href="/dashboard/customer">
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}

function Row({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-2.5">
      <dt className="text-slate-500">{label}</dt>
      <dd className={`break-all text-right ${strong ? "text-base font-bold text-slate-950" : "font-medium text-slate-800"}`}>
        {value}
      </dd>
    </div>
  );
}
