"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { formatMoney } from "@/lib/officer";

export type Payment = {
  id: string;
  loan_id: string;
  amount: number;
  status: string;
  provider: string;
  provider_ref: string;
  amount_paid?: number | null;
  outstanding_after?: number | null;
  installments_paid_after?: number | null;
  installments_total?: number | null;
  next_due_date?: string | null;
  settled_at?: string | null;
};

type WalletKey = "esewa" | "khalti";

/**
 * Your real personal wallet QR codes. Drop the QR screenshots into
 * frontend/public as esewa-qr.png and khalti-qr.png (or override the paths with
 * the NEXT_PUBLIC_*_QR_URL env vars) and the customer scans the real thing.
 */
const WALLETS: Record<WalletKey, { label: string; src: string; accent: string; note: string }> = {
  esewa: {
    label: "eSewa",
    src: process.env.NEXT_PUBLIC_ESEWA_QR_URL || "/esewa-qr.png",
    accent: "#60bb46",
    note: "Open eSewa → Scan & Pay"
  },
  khalti: {
    label: "Khalti",
    src: process.env.NEXT_PUBLIC_KHALTI_QR_URL || "/khalti-qr.png",
    accent: "#5c2d91",
    note: "Open Khalti → Scan QR"
  }
};

/**
 * Scan-to-pay checkout. The customer picks eSewa or Khalti, scans the real
 * personal QR, pays, then confirms — which runs the signed-webhook settlement on
 * the backend and shows a receipt.
 */
export function PaymentCheckout({ paymentId }: { paymentId: string }) {
  const [payment, setPayment] = useState<Payment | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isPaying, setIsPaying] = useState(false);
  const [error, setError] = useState("");
  // Which real wallet QR the customer is scanning.
  const [wallet, setWallet] = useState<WalletKey>("esewa");

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

  async function pay() {
    setIsPaying(true);
    setError("");
    try {
      const response = await fetch(`/api/payments/${encodeURIComponent(paymentId)}/simulate`, {
        method: "POST"
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || data.payment?.status !== "success") {
        setError(data.error ?? "Payment could not be completed.");
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

  const settled = payment.status === "success";
  const active = WALLETS[wallet];

  return (
    <section className="mx-auto max-w-lg px-5 py-10 sm:py-14">
      {settled ? (
        <Receipt payment={payment} />
      ) : (
        <div className="panel-pad p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-lg font-bold text-slate-950">
              <span className="flex h-8 w-8 items-center justify-center rounded-md bg-emerald-700 text-xs text-white">
                SL
              </span>
              Sajilo Pay
            </div>
            <span className="rounded-md bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">
              Secure gateway
            </span>
          </div>

          <div className="mt-5 rounded-lg bg-slate-50 p-4 text-center">
            <p className="text-sm text-slate-600">Amount due</p>
            <p className="mt-1 text-3xl font-bold text-slate-950">{formatMoney(payment.amount)}</p>
            <p className="mt-1 text-xs text-slate-500">Ref {payment.provider_ref.slice(0, 12)}…</p>
          </div>

          <div className="mt-5 grid grid-cols-2 gap-2">
            {(Object.keys(WALLETS) as WalletKey[]).map((key) => {
              const w = WALLETS[key];
              const selected = key === wallet;
              return (
                <button
                  key={key}
                  className={`rounded-lg border px-3 py-2.5 text-sm font-semibold transition ${
                    selected
                      ? "border-transparent text-white"
                      : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                  }`}
                  onClick={() => setWallet(key)}
                  style={selected ? { backgroundColor: w.accent } : undefined}
                  type="button"
                >
                  {w.label}
                </button>
              );
            })}
          </div>

          <div className="mt-4 flex flex-col items-center gap-3">
            <div
              className="rounded-xl border-2 bg-white p-2"
              style={{ borderColor: active.accent }}
            >
              <img
                alt={`${active.label} payment QR`}
                className="h-52 w-52 rounded-lg object-contain"
                src={active.src}
              />
            </div>
            <p className="text-sm font-medium text-slate-700">
              {active.note} · pay {formatMoney(payment.amount)}
            </p>
            <p className="text-center text-xs text-slate-500">
              After paying on {active.label}, tap below to confirm and get your receipt.
            </p>
          </div>

          {error ? <p className="alert-error mt-4 px-3 py-2">{error}</p> : null}

          <button
            className="btn-primary mt-5 w-full px-5 py-3"
            disabled={isPaying}
            onClick={pay}
            type="button"
          >
            {isPaying ? "Confirming payment..." : "I've completed the payment"}
          </button>
          <Link
            className="mt-3 block text-center text-sm font-semibold text-slate-500 hover:text-slate-700"
            href="/dashboard/customer"
          >
            Cancel
          </Link>
        </div>
      )}
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
