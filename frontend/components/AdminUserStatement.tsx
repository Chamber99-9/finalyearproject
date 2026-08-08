"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { AdminNav } from "@/components/AdminNav";
import { LoanAccount } from "@/lib/loans";

type Payment = {
  id: string;
  loan_id: string;
  amount: number;
  amount_paid?: number | null;
  status: string;
  provider: string;
  provider_ref: string;
  kind?: string | null;
  outstanding_after?: number | null;
  installments_paid_after?: number | null;
  installments_total?: number | null;
  next_due_date?: string | null;
  settled_at?: string | null;
  is_partial?: boolean | null;
  shortfall?: number | null;
  depositor_account_number?: string | null;
  amount_deposited?: number | null;
  created_at: string;
  updated_at: string;
};

function money(n?: number | null) {
  return n == null ? "—" : `NPR ${Number(n).toLocaleString()}`;
}
function dt(s?: string | null) {
  return s ? new Date(s).toLocaleString() : "—";
}
function statusPill(status: string) {
  const map: Record<string, string> = {
    success: "bg-emerald-100 text-emerald-800",
    awaiting_confirmation: "bg-amber-100 text-amber-800",
    pending: "bg-slate-100 text-slate-700",
    rejected: "bg-red-100 text-red-700",
    failed: "bg-red-100 text-red-700"
  };
  return map[status] ?? "bg-slate-100 text-slate-700";
}

export function AdminUserStatement({ userId }: { userId: string }) {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loans, setLoans] = useState<LoanAccount[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [openReceipt, setOpenReceipt] = useState<Payment | null>(null);
  const [busyLoanId, setBusyLoanId] = useState("");
  const [extendMonths, setExtendMonths] = useState<Record<string, string>>({});
  const [restructureMsg, setRestructureMsg] = useState("");

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      try {
        const [statementRes, loansRes] = await Promise.all([
          fetch(`/api/admin/users/${encodeURIComponent(userId)}/statement`),
          fetch(`/api/admin/users/${encodeURIComponent(userId)}/loans`)
        ]);
        const p = await statementRes.json().catch(() => ({}));
        if (statementRes.ok) setPayments(p.payments ?? []);
        else setError(p.error ?? "Could not load statement.");
        const l = await loansRes.json().catch(() => ({}));
        if (loansRes.ok) setLoans(l.loans ?? []);
      } catch {
        setError("Could not reach the service.");
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [userId]);

  async function restructure(loanId: string, action: "extend" | "defer" | "waive_penalty") {
    setRestructureMsg("");
    setError("");
    const body: { action: string; extend_months?: number } = { action };
    if (action === "extend") {
      const months = Number(extendMonths[loanId]);
      if (!(months >= 1)) {
        setError("Enter how many months to extend by.");
        return;
      }
      body.extend_months = months;
    }
    setBusyLoanId(loanId);
    try {
      const r = await fetch(`/api/admin/loans/${encodeURIComponent(loanId)}/restructure`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const p = await r.json().catch(() => ({}));
      if (!r.ok) {
        setError(p.error ?? "Could not restructure the loan.");
        return;
      }
      setLoans((current) => current.map((loan) => (loan.id === p.loan.id ? p.loan : loan)));
      setRestructureMsg("Loan restructured. The customer has been notified.");
    } catch {
      setError("Could not reach the service.");
    } finally {
      setBusyLoanId("");
    }
  }

  const totals = useMemo(() => {
    const paid = payments
      .filter((x) => x.status === "success")
      .reduce((sum, x) => sum + Number(x.amount_paid ?? x.amount ?? 0), 0);
    return { count: payments.length, paid };
  }, [payments]);

  return (
    <section className="page-wrap">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Admin dashboard</p>
          <h1 className="mt-3 text-3xl font-bold text-slate-950 sm:text-4xl">Payment statement</h1>
          <p className="mt-3 max-w-3xl text-base leading-7 text-slate-700">
            Full payment history for customer <span className="font-semibold">{userId}</span>.
            {" "}Total paid: <span className="font-semibold">{money(totals.paid)}</span> across{" "}
            {totals.count} record(s).
          </p>
        </div>
        <AdminNav />
      </div>

      {error ? <p className="alert-error mt-6">{error}</p> : null}
      {restructureMsg ? <p className="alert-success mt-6">{restructureMsg}</p> : null}

      {loans.filter((loan) => loan.status === "active").length > 0 ? (
        <div className="mt-6">
          <h2 className="text-lg font-semibold text-slate-950">Active loans — restructure</h2>
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            {loans
              .filter((loan) => loan.status === "active")
              .map((loan) => (
                <article key={loan.id} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <Detail label="Outstanding" value={money(loan.outstanding_balance)} />
                    <Detail label="Monthly EMI" value={money(loan.monthly_emi)} />
                    <Detail label="Installments" value={`${loan.installments_paid}/${loan.installments_total}`} />
                    <Detail label="Late fees due" value={money(loan.penalty_due ?? 0)} />
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <input
                      className="w-24 px-2 py-1.5 text-sm"
                      inputMode="numeric"
                      placeholder="+months"
                      value={extendMonths[loan.id] ?? ""}
                      onChange={(e) =>
                        setExtendMonths((current) => ({ ...current, [loan.id]: e.target.value }))
                      }
                    />
                    <button
                      className="btn-secondary px-3 py-1.5 text-sm"
                      disabled={busyLoanId === loan.id}
                      onClick={() => restructure(loan.id, "extend")}
                      type="button"
                    >
                      Extend tenure
                    </button>
                    <button
                      className="btn-secondary px-3 py-1.5 text-sm"
                      disabled={busyLoanId === loan.id}
                      onClick={() => restructure(loan.id, "defer")}
                      type="button"
                    >
                      Defer 1 EMI
                    </button>
                    <button
                      className="btn-secondary px-3 py-1.5 text-sm"
                      disabled={busyLoanId === loan.id || !(loan.penalty_due && loan.penalty_due > 0)}
                      onClick={() => restructure(loan.id, "waive_penalty")}
                      type="button"
                    >
                      Waive penalty
                    </button>
                  </div>
                </article>
              ))}
          </div>
        </div>
      ) : null}

      <div className="mt-6 table-shell overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Amount</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Method</th>
              <th className="px-4 py-3">Reference</th>
              <th className="px-4 py-3">Balance after</th>
              <th className="px-4 py-3">Receipt</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {isLoading ? (
              <tr><td className="px-4 py-8 text-center text-slate-600" colSpan={8}>Loading…</td></tr>
            ) : payments.length > 0 ? (
              payments.map((p) => (
                <tr key={p.id} className="align-top">
                  <td className="px-4 py-3 text-slate-600">{dt(p.settled_at ?? p.created_at)}</td>
                  <td className="px-4 py-3">{p.kind === "prepayment" ? "Advance" : "EMI"}</td>
                  <td className="px-4 py-3 font-semibold text-slate-950">{money(p.amount_paid ?? p.amount)}</td>
                  <td className="px-4 py-3">
                    <span className={`status-pill ${statusPill(p.status)}`}>{p.status.replace(/_/g, " ")}</span>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{String(p.provider || "").replace(/_/g, " ")}</td>
                  <td className="px-4 py-3 break-all text-slate-500">{p.provider_ref?.slice(0, 14)}…</td>
                  <td className="px-4 py-3 text-slate-600">{money(p.outstanding_after)}</td>
                  <td className="px-4 py-3">
                    {p.status === "success" ? (
                      <button
                        className="text-xs font-semibold text-emerald-700 hover:text-emerald-800"
                        onClick={() => setOpenReceipt(p)}
                        type="button"
                      >
                        View receipt
                      </button>
                    ) : (
                      <span className="text-xs text-slate-400">—</span>
                    )}
                  </td>
                </tr>
              ))
            ) : (
              <tr><td className="px-4 py-8 text-center text-slate-600" colSpan={8}>No payments for this customer yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <Link className="btn-secondary mt-6 inline-flex px-4 py-2 text-sm" href="/dashboard/admin/users">
        Back to users
      </Link>

      {openReceipt ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
          onClick={() => setOpenReceipt(null)}
        >
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex flex-col items-center text-center">
              <span className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 text-2xl text-emerald-700">✓</span>
              <h2 className="mt-2 text-xl font-bold text-slate-950">
                {openReceipt.is_partial ? "Partial payment received" : "Payment receipt"}
              </h2>
            </div>
            <dl className="mt-4 divide-y divide-slate-100 rounded-lg border border-slate-200 text-sm">
              {[
                ["Amount paid", money(openReceipt.amount_paid ?? openReceipt.amount)],
                ["Type", openReceipt.kind === "prepayment" ? "Advance payment" : "EMI"],
                ["Date", dt(openReceipt.settled_at)],
                ["Method", String(openReceipt.provider || "").replace(/_/g, " ")],
                ["Transaction ref", openReceipt.provider_ref],
                ["Paid from account", openReceipt.depositor_account_number || "—"],
                ["Remaining balance", money(openReceipt.outstanding_after)],
                ["Installments", openReceipt.installments_paid_after != null && openReceipt.installments_total != null
                  ? `${openReceipt.installments_paid_after}/${openReceipt.installments_total}` : "—"],
                ["Next due", openReceipt.next_due_date ? new Date(openReceipt.next_due_date).toLocaleDateString() : "—"]
              ].map(([label, value]) => (
                <div className="flex justify-between gap-3 px-4 py-2.5" key={label}>
                  <dt className="text-slate-500">{label}</dt>
                  <dd className="break-all text-right font-medium text-slate-800">{value}</dd>
                </div>
              ))}
            </dl>
            <div className="mt-4 flex gap-2">
              <button className="btn-secondary flex-1 px-4 py-2 text-sm" onClick={() => window.print()} type="button">Print</button>
              <button className="btn-primary flex-1 px-4 py-2 text-sm" onClick={() => setOpenReceipt(null)} type="button">Close</button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="mt-0.5 font-semibold text-slate-950">{value}</p>
    </div>
  );
}
