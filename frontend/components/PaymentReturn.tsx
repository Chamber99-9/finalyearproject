"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Payment, Receipt } from "@/components/PaymentCheckout";

/** Extract the gateway reference from the return URL (Khalti pidx or eSewa data). */
function readProviderRef(params: URLSearchParams): string {
  const direct = params.get("pidx") ?? params.get("provider_ref");
  if (direct) return direct;
  // eSewa redirects back with a base64-encoded JSON `data` payload.
  const data = params.get("data");
  if (data) {
    try {
      const decoded = JSON.parse(atob(data)) as { transaction_uuid?: string };
      return decoded.transaction_uuid ?? "";
    } catch {
      return "";
    }
  }
  return "";
}

/**
 * Landing page the gateway (Khalti) redirects back to. It reads the reference
 * (pidx) and asks the backend to confirm the payment via a server-side lookup —
 * the redirect params are never trusted on their own — then shows the receipt.
 */
export function PaymentReturn() {
  const params = useSearchParams();
  const providerRef = useMemo(() => readProviderRef(params), [params]);
  const [payment, setPayment] = useState<Payment | null>(null);
  const [state, setState] = useState<"verifying" | "done" | "error">("verifying");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!providerRef) {
      setState("error");
      // No reference means eSewa sent us to the failure/cancel URL — the payment
      // did not complete, so no money was charged.
      setError(
        params.get("status") === "failed"
          ? "Your eSewa payment was cancelled or did not complete — no amount was charged. Please try paying again."
          : "Your payment could not be confirmed. If money was deducted it will be reflected shortly; otherwise please try again."
      );
      return;
    }
    async function verify() {
      try {
        const response = await fetch("/api/payments/verify", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider_ref: providerRef })
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          setState("error");
          setError(data.error ?? "Could not verify your payment.");
          return;
        }
        setPayment(data.payment);
        setState("done");
      } catch {
        setState("error");
        setError("Could not reach the payment service.");
      }
    }
    verify();
  }, [providerRef]);

  return (
    <section className="mx-auto max-w-lg px-5 py-10 sm:py-14">
      {state === "verifying" ? (
        <p className="panel-pad text-slate-600">Verifying your payment...</p>
      ) : null}
      {state === "error" ? (
        <div className="panel-pad">
          <p className="alert-error">{error}</p>
          <Link className="btn-secondary mt-4 inline-flex px-4 py-2" href="/dashboard/customer">
            Back to dashboard
          </Link>
        </div>
      ) : null}
      {state === "done" && payment ? (
        payment.status === "success" ? (
          <Receipt payment={payment} />
        ) : (
          <div className="panel-pad">
            <p className="alert-error">Payment not completed (status: {payment.status}).</p>
            <Link className="btn-secondary mt-4 inline-flex px-4 py-2" href="/dashboard/customer">
              Back to dashboard
            </Link>
          </div>
        )
      ) : null}
    </section>
  );
}
