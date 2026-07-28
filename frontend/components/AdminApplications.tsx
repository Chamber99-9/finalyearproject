"use client";

import { useEffect, useState } from "react";

import { AdminNav } from "@/components/AdminNav";
import { LoanApplication, formatLabel, formatMoney } from "@/lib/officer";

/**
 * Admin-only view for managing the interest rate applied to submitted
 * applications. Displays loan amount, tenure, interest rate used, EMI, totals
 * and affordability, and lets an admin override the rate (recalculates EMI on
 * the backend). Officers see these values read-only on their own review page.
 */
export function AdminApplications() {
  const [applications, setApplications] = useState<LoanApplication[]>([]);
  const [rateInputs, setRateInputs] = useState<Record<string, string>>({});
  const [savingId, setSavingId] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    async function loadApplications() {
      setIsLoading(true);
      setError("");
      try {
        const response = await fetch("/api/admin/applications");
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          setError(payload.error ?? "Could not load applications.");
          return;
        }
        setApplications(payload.applications ?? []);
      } catch {
        setError("Could not reach the admin application service.");
      } finally {
        setIsLoading(false);
      }
    }
    loadApplications();
  }, []);

  async function overrideRate(applicationId: string) {
    const rate = Number(rateInputs[applicationId]);
    if (!Number.isFinite(rate) || rate <= 0) {
      setError("Enter a valid interest rate greater than 0.");
      return;
    }

    setSavingId(applicationId);
    setError("");
    setSuccess("");
    try {
      const response = await fetch(
        `/api/admin/applications/${encodeURIComponent(applicationId)}/interest-rate`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ interest_rate: rate })
        }
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(payload.error ?? "Could not update the interest rate.");
        return;
      }
      const updated = payload.application as LoanApplication;
      setApplications((current) =>
        current.map((application) =>
          application.id === updated.id ? updated : application
        )
      );
      setRateInputs((current) => ({ ...current, [applicationId]: "" }));
      setSuccess("Interest rate updated and EMI recalculated.");
    } catch {
      setError("Could not reach the interest rate service.");
    } finally {
      setSavingId("");
    }
  }

  return (
    <section className="page-wrap">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Admin dashboard</p>
          <h1 className="mt-3 text-3xl font-bold text-slate-950 sm:text-4xl">
            Loan applications and rates
          </h1>
          <p className="mt-3 max-w-3xl text-base leading-7 text-slate-700">
            Review each application&apos;s EMI and override the interest rate when
            authorized. Overriding recalculates the EMI, total interest and total
            repayment.
          </p>
        </div>
        <AdminNav />
      </div>

      {error ? <p className="alert-error mt-6">{error}</p> : null}
      {success ? <p className="alert-success mt-6">{success}</p> : null}

      <div className="table-shell">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="table-head">
              <tr>
                <th className="px-4 py-3">Applicant</th>
                <th className="px-4 py-3">Loan amount</th>
                <th className="px-4 py-3">Tenure</th>
                <th className="px-4 py-3">Rate used</th>
                <th className="px-4 py-3">Monthly EMI</th>
                <th className="px-4 py-3">Total repayment</th>
                <th className="px-4 py-3">Affordability</th>
                <th className="px-4 py-3">Override rate</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {isLoading ? (
                <tr>
                  <td className="px-4 py-8 text-center text-slate-600" colSpan={8}>
                    Loading applications...
                  </td>
                </tr>
              ) : applications.length > 0 ? (
                applications.map((application) => (
                  <tr key={application.id} className="align-top">
                    <td className="px-4 py-4">
                      <p className="font-semibold text-slate-950">
                        {application.full_name || "N/A"}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">{application.id}</p>
                    </td>
                    <td className="px-4 py-4 font-semibold text-slate-950">
                      {formatMoney(application.requested_loan_amount)}
                    </td>
                    <td className="px-4 py-4 text-slate-600">
                      {application.loan_duration_months
                        ? `${application.loan_duration_months} months`
                        : "N/A"}
                    </td>
                    <td className="px-4 py-4 text-slate-600">
                      {application.interest_rate_used != null
                        ? `${application.interest_rate_used}% p.a.`
                        : "N/A"}
                    </td>
                    <td className="px-4 py-4 text-slate-600">
                      {formatMoney(application.monthly_emi)}
                    </td>
                    <td className="px-4 py-4 text-slate-600">
                      {formatMoney(application.total_payment)}
                    </td>
                    <td className="px-4 py-4">
                      {application.affordability ? (
                        <span className="status-pill bg-slate-100 text-slate-700">
                          {application.affordability}
                        </span>
                      ) : (
                        "N/A"
                      )}
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-2">
                        <input
                          className="w-24 rounded-md border border-slate-300 px-2 py-1.5 text-sm outline-none ring-emerald-600 focus:ring-2"
                          min={0}
                          onChange={(event) =>
                            setRateInputs((current) => ({
                              ...current,
                              [application.id]: event.target.value
                            }))
                          }
                          placeholder="%"
                          step="0.1"
                          type="number"
                          value={rateInputs[application.id] ?? ""}
                        />
                        <button
                          className="btn-primary px-3 py-1.5 text-sm"
                          disabled={savingId === application.id}
                          onClick={() => overrideRate(application.id)}
                          type="button"
                        >
                          {savingId === application.id ? "Saving..." : "Apply"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="px-4 py-8 text-center text-slate-600" colSpan={8}>
                    No submitted applications yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
