"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  ApplicationStatus,
  LoanApplication,
  formatDate,
  formatLabel,
  formatMoney,
  statusOptions
} from "@/lib/officer";

export function OfficerDashboard() {
  const [applications, setApplications] = useState<LoanApplication[]>([]);
  const [statusFilter, setStatusFilter] = useState<"all" | ApplicationStatus>("all");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadApplications() {
      setIsLoading(true);
      setError("");

      try {
        const response = await fetch("/api/officer/applications");
        const payload = await response.json().catch(() => ({}));

        if (!response.ok) {
          setError(payload.error ?? "Could not load submitted applications.");
          return;
        }

        setApplications(payload.applications ?? []);
      } catch {
        setError("Could not reach the officer application service.");
      } finally {
        setIsLoading(false);
      }
    }

    loadApplications();
  }, []);

  const filteredApplications = useMemo(() => {
    if (statusFilter === "all") {
      return applications;
    }
    return applications.filter((application) => application.status === statusFilter);
  }, [applications, statusFilter]);

  const counts = useMemo(
    () => ({
      submitted: applications.filter((item) => item.status === "submitted").length,
      underReview: applications.filter((item) => item.status === "under_review").length,
      documentRequested: applications.filter(
        (item) => item.status === "document_requested"
      ).length,
      counterOffered: applications.filter((item) => item.status === "counter_offered").length,
      completed: applications.filter((item) =>
        ["approved", "rejected"].includes(item.status)
      ).length
    }),
    [applications]
  );

  return (
    <section className="page-wrap">
      <div className="page-heading">
        <div>
          <p className="eyebrow">
            Loan officer
          </p>
          <h1 className="mt-3 text-3xl font-bold text-slate-950 sm:text-4xl">
            Submitted applications
          </h1>
        </div>
        <label className="w-full max-w-xs">
          <span className="text-sm font-medium text-slate-700">Status</span>
          <select
            className="mt-2 w-full px-3 py-2.5"
            onChange={(event) =>
              setStatusFilter(event.target.value as "all" | ApplicationStatus)
            }
            value={statusFilter}
          >
            {statusOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Submitted" value={counts.submitted} />
        <Metric label="Under review" value={counts.underReview} />
        <Metric label="Documents requested" value={counts.documentRequested} />
        <Metric label="Offers sent" value={counts.counterOffered} />
        <Metric label="Completed" value={counts.completed} />
      </div>

      {error ? (
        <p className="alert-error mt-6">
          {error}
        </p>
      ) : null}

      <div className="table-shell">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="table-head">
              <tr>
                <th className="px-4 py-3">Applicant</th>
                <th className="px-4 py-3">Loan</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Submitted</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {isLoading ? (
                <tr>
                  <td className="px-4 py-8 text-center text-slate-600" colSpan={5}>
                    Loading applications...
                  </td>
                </tr>
              ) : filteredApplications.length > 0 ? (
                filteredApplications.map((application) => (
                  <tr key={application.id} className="align-top">
                    <td className="px-4 py-4">
                      <p className="font-semibold text-slate-950">
                        {application.full_name || "N/A"}
                      </p>
                      <p className="mt-1 text-slate-600">{application.phone || "N/A"}</p>
                      <p className="mt-1 text-slate-500">
                        {application.citizenship_number || "N/A"}
                      </p>
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
                      </p>
                    </td>
                    <td className="px-4 py-4">
                      <StatusBadge status={application.status} />
                    </td>
                    <td className="px-4 py-4 text-slate-600">
                      {formatDate(application.created_at)}
                    </td>
                    <td className="px-4 py-4 text-right">
                      <Link
                        className="btn-primary px-3 py-2"
                        href={`/dashboard/officer/applications/${application.id}`}
                      >
                        Review
                      </Link>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="px-4 py-8 text-center text-slate-600" colSpan={5}>
                    No applications match this status.
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

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric-card">
      <p className="text-sm font-medium text-slate-600">{label}</p>
      <p className="mt-2 text-3xl font-bold text-slate-950">{value}</p>
    </div>
  );
}

export function StatusBadge({ status }: { status: ApplicationStatus }) {
  const tone =
    status === "approved"
      ? "bg-emerald-100 text-emerald-800"
      : status === "rejected"
        ? "bg-red-100 text-red-700"
        : status === "document_requested"
          ? "bg-amber-100 text-amber-800"
          : status === "counter_offered"
            ? "bg-violet-100 text-violet-800"
            : "bg-slate-100 text-slate-700";

  return (
    <span className={`status-pill ${tone}`}>
      {formatLabel(status)}
    </span>
  );
}
