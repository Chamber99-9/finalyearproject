"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  ApplicationStatus,
  LoanApplication,
  formatDate,
  formatLabel,
  formatMoney
} from "@/lib/officer";
import { CustomerLoans } from "@/components/CustomerLoans";

export function CustomerDashboard() {
  const [applications, setApplications] = useState<LoanApplication[]>([]);
  const [customerName, setCustomerName] = useState("Customer");
  const [isLoading, setIsLoading] = useState(true);
  const [respondingOfferId, setRespondingOfferId] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    async function loadDashboard() {
      setIsLoading(true);
      setError("");
      setSuccess("");

      try {
        const [sessionResponse, applicationsResponse] = await Promise.all([
          fetch("/api/auth/me"),
          fetch("/api/applications")
        ]);

        const sessionPayload = await sessionResponse.json().catch(() => ({}));
        if (sessionResponse.ok && sessionPayload.user?.full_name) {
          setCustomerName(sessionPayload.user.full_name);
        }

        const applicationsPayload = await applicationsResponse.json().catch(() => ({}));
        if (!applicationsResponse.ok) {
          setError(applicationsPayload.error ?? "Could not load your applications.");
          return;
        }

        setApplications(applicationsPayload.applications ?? []);
      } catch {
        setError("Could not reach the customer dashboard service.");
      } finally {
        setIsLoading(false);
      }
    }

    loadDashboard();
  }, []);

  async function respondToCounterOffer(applicationId: string, accepted: boolean) {
    setRespondingOfferId(applicationId);
    setError("");
    setSuccess("");

    try {
      const response = await fetch(
        `/api/applications/${encodeURIComponent(applicationId)}/counter-offer/respond`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ accepted })
        }
      );
      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(payload.error ?? "Could not respond to loan amount offer.");
        return;
      }

      const updatedApplication = payload.application as LoanApplication;
      setApplications((current) =>
        current.map((application) =>
          application.id === updatedApplication.id ? updatedApplication : application
        )
      );
      setSuccess(
        accepted
          ? "Loan amount offer accepted."
          : "Loan amount offer declined."
      );
    } catch {
      setError("Could not reach the counter offer service.");
    } finally {
      setRespondingOfferId("");
    }
  }

  const latestApplication = applications[0];
  const summary = useMemo(
    () => ({
      total: applications.length,
      drafts: applications.filter((application) => application.status === "draft").length,
      pending: applications.filter((application) =>
        ["submitted", "under_review", "document_requested", "counter_offered"].includes(
          application.status
        )
      ).length,
      completed: applications.filter((application) =>
        ["approved", "rejected"].includes(application.status)
      ).length
    }),
    [applications]
  );

  return (
    <section className="page-wrap">
      <div className="page-heading">
        <div>
          <p className="eyebrow">
            Customer dashboard
          </p>
          <h1 className="mt-3 text-3xl font-bold text-slate-950 sm:text-4xl">
            Welcome, {customerName}
          </h1>
          <p className="mt-3 max-w-3xl text-base leading-7 text-slate-700">
            Track your Sajilo Loan applications, continue drafts, and upload supporting
            documents for officer review.
          </p>
        </div>
        <Link
          className="btn-primary px-5 py-3"
          href="/applications/new"
        >
          Start new loan application
        </Link>
      </div>

      {error ? (
        <p className="alert-error mt-6">
          {error}
        </p>
      ) : null}
      {success ? (
        <p className="alert-success mt-6">
          {success}
        </p>
      ) : null}

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Applications" loading={isLoading} value={summary.total} />
        <Metric
          label="Current status"
          loading={isLoading}
          value={latestApplication ? formatLabel(latestApplication.status) : "No application"}
        />
        <Metric label="Drafts" loading={isLoading} value={summary.drafts} />
        <Metric label="Pending review" loading={isLoading} value={summary.pending} />
      </div>

      <div className="mt-6">
        <CustomerLoans />
      </div>

      <div className="table-shell">
        <div className="flex flex-col gap-2 border-b border-slate-200 bg-slate-50 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">
              Your loan applications
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Review current progress and choose the next action.
            </p>
          </div>
          <span className="text-sm font-semibold text-slate-600">
            Completed: {summary.completed}
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="table-head">
              <tr>
                <th className="px-4 py-3">Application</th>
                <th className="px-4 py-3">Loan</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Updated</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {isLoading ? (
                <tr>
                  <td className="px-4 py-8 text-center text-slate-600" colSpan={5}>
                    Loading your applications...
                  </td>
                </tr>
              ) : applications.length > 0 ? (
                applications.map((application) => (
                  <tr key={application.id} className="align-top">
                    <td className="px-4 py-4">
                      <p className="font-semibold text-slate-950">
                        {application.full_name || "Draft application"}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">{application.id}</p>
                    </td>
                    <td className="px-4 py-4">
                      <p className="font-semibold text-slate-950">
                        {formatMoney(application.requested_loan_amount)}
                      </p>
                      <p className="mt-1 text-slate-600">
                        {formatLabel(application.loan_type)}
                      </p>
                      <p className="mt-1 text-slate-500">
                        {application.loan_duration_months
                          ? `${application.loan_duration_months} months`
                          : "N/A"}
                        {typeof application.interest_rate_used === "number"
                          ? ` · ${application.interest_rate_used}% p.a.`
                          : ""}
                      </p>
                      {typeof application.monthly_emi === "number" ? (
                        <p className="mt-1 text-xs font-semibold text-emerald-700">
                          EMI {formatMoney(application.monthly_emi)}/mo
                        </p>
                      ) : null}
                      {application.affordability ? (
                        <p className="mt-1 text-xs font-medium text-slate-600">
                          {application.affordability}
                        </p>
                      ) : null}
                    </td>
                    <td className="px-4 py-4">
                      <StatusBadge status={application.status} />
                    </td>
                    <td className="px-4 py-4 text-slate-600">
                      {formatDate(application.updated_at)}
                    </td>
                    <td className="px-4 py-4">
                      {application.offer_status === "pending" ? (
                        <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-left">
                          <p className="text-sm font-semibold text-amber-900">
                            Officer offered {formatMoney(application.offered_loan_amount)}
                          </p>
                          <p className="mt-1 text-sm leading-5 text-amber-800">
                            {application.offer_message ||
                              "Do you want to accept this offered loan amount?"}
                          </p>
                          <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:justify-end">
                            <button
                              className="btn-primary px-3 py-2"
                              disabled={respondingOfferId === application.id}
                              onClick={() => respondToCounterOffer(application.id, true)}
                              type="button"
                            >
                              Accept offer
                            </button>
                            <button
                              className="btn-secondary px-3 py-2"
                              disabled={respondingOfferId === application.id}
                              onClick={() => respondToCounterOffer(application.id, false)}
                              type="button"
                            >
                              Decline
                            </button>
                          </div>
                        </div>
                      ) : null}
                      <div className="flex flex-col gap-2 sm:items-end">
                        {canUploadDocuments(application.status) ? (
                          <Link
                            className="btn-secondary px-3 py-2"
                            href={`/applications/documents?applicationId=${encodeURIComponent(application.id)}`}
                          >
                            Upload requested documents
                          </Link>
                        ) : null}
                        {application.status === "draft" ? (
                          <Link
                            className="btn-primary px-3 py-2"
                            href={`/applications/new?applicationId=${encodeURIComponent(application.id)}`}
                          >
                            Continue draft
                          </Link>
                        ) : null}
                        <button
                          className="btn-muted px-3 py-2"
                          type="button"
                        >
                          View status
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="px-4 py-8 text-center text-slate-600" colSpan={5}>
                    No loan applications yet. Start a new application when you are ready.
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

function canUploadDocuments(status: ApplicationStatus) {
  return status === "document_requested";
}

function Metric({
  label,
  loading,
  value
}: {
  label: string;
  loading: boolean;
  value: number | string;
}) {
  return (
    <article className="metric-card">
      <p className="text-sm font-medium text-slate-600">{label}</p>
      <p className="mt-3 text-2xl font-bold text-slate-950">
        {loading ? "..." : value}
      </p>
    </article>
  );
}

function StatusBadge({ status }: { status: ApplicationStatus }) {
  const tone =
    status === "approved"
      ? "bg-emerald-100 text-emerald-800"
      : status === "rejected"
        ? "bg-red-100 text-red-700"
        : status === "document_requested"
          ? "bg-amber-100 text-amber-800"
          : status === "counter_offered"
            ? "bg-violet-100 text-violet-800"
            : status === "draft"
              ? "bg-slate-100 text-slate-700"
              : "bg-blue-100 text-blue-800";

  return (
    <span className={`status-pill ${tone}`}>
      {formatLabel(status)}
    </span>
  );
}
