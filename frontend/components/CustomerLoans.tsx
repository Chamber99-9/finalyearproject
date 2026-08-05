"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { LoanAccount } from "@/lib/loans";
import { formatMoney } from "@/lib/officer";

/**
 * Customer's active loans with a Pay EMI action. Paying reduces the outstanding
 * balance and advances the next due date (EMI is due on the 10th each month).
 */
export function CustomerLoans() {
  const router = useRouter();
  const [loans, setLoans] = useState<LoanAccount[]>([]);
  const [payingId, setPayingId] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    loadLoans();
  }, []);

  async function loadLoans() {
    setIsLoading(true);
    try {
      const response = await fetch("/api/loans/my");
      const payload = await response.json().catch(() => ({}));
      if (response.ok) setLoans(payload.loans ?? []);
      else setError(payload.error ?? "Could not load your loans.");
    } catch {
      setError("Could not reach the loan service.");
    } finally {
      setIsLoading(false);
    }
  }

  async function payEmi(loanId: string) {
    setPayingId(loanId);
    setError("");
    setSuccess("");
    try {
      // Create a payment intent, then send the customer to the gateway checkout
      // (in production the intent returns the gateway's own checkout URL).
      const initiate = await fetch(
        `/api/loans/${encodeURIComponent(loanId)}/payments/initiate`,
        { method: "POST" }
      );
      const initiatePayload = await initiate.json().catch(() => ({}));
      if (!initiate.ok) {
        setError(initiatePayload.error ?? "Could not start the payment.");
        return;
      }
      // Send the customer to the gateway. eSewa needs a signed form POST to its
      // hosted page; Khalti returns a hosted URL; the mock provider returns our
      // internal checkout page.
      const payment = initiatePayload.payment;
      const esewaForm = payment?.esewa_form as
        | { action: string; fields: Record<string, string> }
        | undefined;
      if (esewaForm?.action && esewaForm.fields) {
        submitEsewaForm(esewaForm);
        return;
      }
      const checkoutUrl = payment?.checkout_url as string | undefined;
      if (checkoutUrl) {
        window.location.href = checkoutUrl;
      } else {
        router.push(`/payments/${encodeURIComponent(payment?.id)}/checkout`);
      }
    } catch {
      setError("Could not reach the payment service.");
    } finally {
      setPayingId("");
    }
  }

  if (!isLoading && loans.length === 0) return null;

  return (
    <div className="table-shell">
      <div className="border-b border-slate-200 bg-slate-50 px-5 py-4">
        <h2 className="text-lg font-semibold text-slate-950">Your active loans</h2>
        <p className="mt-1 text-sm text-slate-600">
          EMI is due on the 10th of each month. Paying reduces your balance.
        </p>
      </div>
      {error ? <p className="alert-error m-4">{error}</p> : null}
      {success ? <p className="alert-success m-4">{success}</p> : null}
      <div className="grid gap-4 p-4 sm:grid-cols-2">
        {loans.map((loan) => {
          const progress = loan.installments_total
            ? Math.round((loan.installments_paid / loan.installments_total) * 100)
            : 0;
          return (
            <article
              key={loan.id}
              className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-950">
                  {formatMoney(loan.principal)} loan
                </span>
                <span
                  className={`status-pill ${
                    loan.status === "active"
                      ? "bg-blue-100 text-blue-800"
                      : loan.status === "completed"
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-red-100 text-red-700"
                  }`}
                >
                  {loan.status}
                </span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                <Fact label="Outstanding" value={formatMoney(loan.outstanding_balance)} />
                <Fact label="Monthly EMI" value={formatMoney(loan.monthly_emi)} />
                <Fact
                  label="Next due"
                  value={loan.next_due_date ? new Date(loan.next_due_date).toLocaleDateString() : "—"}
                />
                <Fact
                  label="Installments"
                  value={`${loan.installments_paid}/${loan.installments_total}`}
                />
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
                <div className="h-full bg-emerald-600" style={{ width: `${progress}%` }} />
              </div>
              {loan.status === "active" ? (
                <button
                  className="btn-primary mt-4 w-full px-4 py-2.5"
                  disabled={payingId === loan.id}
                  onClick={() => payEmi(loan.id)}
                  type="button"
                >
                  {payingId === loan.id ? "Processing..." : `Pay EMI ${formatMoney(loan.monthly_emi)}`}
                </button>
              ) : (
                <p className="mt-4 rounded-md bg-emerald-50 px-3 py-2 text-center text-sm font-medium text-emerald-800">
                  Loan fully repaid
                </p>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}

/** Build and submit a hidden form that POSTs the signed fields to eSewa. */
function submitEsewaForm(esewaForm: { action: string; fields: Record<string, string> }) {
  const form = document.createElement("form");
  form.method = "POST";
  form.action = esewaForm.action;
  for (const [name, value] of Object.entries(esewaForm.fields)) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value;
    form.appendChild(input);
  }
  document.body.appendChild(form);
  form.submit();
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="mt-0.5 font-semibold text-slate-950">{value}</p>
    </div>
  );
}
