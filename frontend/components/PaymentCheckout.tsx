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
};

/**
 * Scan-to-pay checkout. The customer scans the merchant's personal eSewa QR,
 * pays that account directly, then taps "I've completed the payment" — which
 * marks the payment awaiting officer confirmation. An officer confirms receipt
 * and the EMI is applied.
 */
export function PaymentCheckout({ paymentId }: { paymentId: string }) {
  const [payment, setPayment] = useState<Payment | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isPaying, setIsPaying] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const response = await fetch(`/api/payments/${encodeURIComponent(paymentId)}`);
        const data = await response.json().catch(() => ({}));
        if (response.ok) setPayment(data.payment);
        else setError(data.error ?? "Payment not found.");
      } catch {
        setError("Could not reach the payment service.");
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [paymentId]);

  async function markPaid() {
    setIsPaying(true);
    setError("");
    try {
      const response = await fetch(`/api/payments/${encodeURIComponent(paymentId)}/submitted`, {
        method: "POST"
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(data.error ?? "Could not submit the payment.");
        return;
      }
      setPayment(data.payment);
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

        {awaiting ? (
          <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-5 text-center">
            <p className="text-lg font-bold text-amber-900">Payment submitted</p>
            <p className="mt-1 text-sm text-amber-800">
              Waiting for the bank to confirm your payment was received. Your EMI updates once an
              officer confirms it.
            </p>
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

            <button
              className="btn-primary mt-5 w-full px-5 py-3"
              disabled={isPaying}
              onClick={markPaid}
              type="button"
            >
              {isPaying ? "Submitting..." : "I've completed the payment"}
            </button>
            <Link
              className="mt-3 block text-center text-sm font-semibold text-slate-500 hover:text-slate-700"
              href="/dashboard/customer"
            >
              Cancel
            </Link>
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
        <h1 className="mt-3 text-2xl font-bold text-slate-950">Payment successful</h1>
        <p className="mt-1 text-sm text-slate-600">Your EMI has been received.</p>
      </div>

      <div className="mt-6 rounded-lg border border-slate-200">
        <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
          <p className="text-sm font-semibold text-slate-950">Payment receipt</p>
        </div>
        <dl className="divide-y divide-slate-100 text-sm">
          <Row label="Amount paid" value={formatMoney(payment.amount_paid ?? payment.amount)} strong />
          <Row label="Status" value="Paid" />
          <Row
            label="Date"
            value={payment.settled_at ? new Date(payment.settled_at).toLocaleString() : "—"}
          />
          <Row label="Transaction ref" value={payment.provider_ref} />
          <Row label="Method" value={payment.provider.replace(/_/g, " ")} />
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

      <div className="mt-5 flex flex-col gap-3 sm:flex-row">
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
