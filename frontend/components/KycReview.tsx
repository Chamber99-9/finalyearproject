"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type KycRecord = {
  id: string;
  user_id: string;
  full_name: string;
  pan_number: string;
  citizenship_number: string;
  date_of_birth: string;
  status: string;
  checks: Record<string, boolean>;
};

/**
 * Officer KYC review queue. Approve or reject pending identity verifications;
 * the automated checks are shown to assist the manual decision. A customer
 * cannot apply for a loan until their KYC is approved here.
 */
export function KycReview() {
  const [records, setRecords] = useState<KycRecord[]>([]);
  const [savingId, setSavingId] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    loadQueue();
  }, []);

  async function loadQueue() {
    setIsLoading(true);
    try {
      const response = await fetch("/api/kyc");
      const payload = await response.json().catch(() => ({}));
      if (response.ok) setRecords(payload.records ?? []);
      else setError(payload.error ?? "Could not load the KYC queue.");
    } catch {
      setError("Could not reach the KYC service.");
    } finally {
      setIsLoading(false);
    }
  }

  async function review(userId: string, approved: boolean) {
    setSavingId(userId);
    setError("");
    setSuccess("");
    try {
      const response = await fetch(`/api/kyc/${encodeURIComponent(userId)}/review`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved })
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(payload.error ?? "Could not review KYC.");
        return;
      }
      setRecords((current) => current.filter((record) => record.user_id !== userId));
      setSuccess(`KYC ${approved ? "approved" : "rejected"}.`);
    } catch {
      setError("Could not reach the KYC service.");
    } finally {
      setSavingId("");
    }
  }

  return (
    <section className="page-wrap">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Loan officer</p>
          <h1 className="mt-3 text-3xl font-bold text-slate-950 sm:text-4xl">KYC review</h1>
          <p className="mt-3 max-w-3xl text-base leading-7 text-slate-700">
            Review pending identity verifications. Automated checks are shown to assist your
            manual decision. Customers cannot request a loan until their KYC is approved.
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
          <p className="panel-pad text-slate-600">Loading KYC queue...</p>
        ) : records.length > 0 ? (
          records.map((record) => (
            <article key={record.id} className="panel-pad">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="grid gap-1 text-sm">
                  <p className="text-base font-semibold text-slate-950">{record.full_name}</p>
                  <p className="text-slate-600">PAN: {record.pan_number}</p>
                  <p className="text-slate-600">Citizenship: {record.citizenship_number}</p>
                  <p className="text-slate-600">DOB: {record.date_of_birth}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {Object.entries(record.checks).map(([key, value]) => (
                      <span
                        key={key}
                        className={`rounded-md px-2 py-0.5 text-xs font-semibold ${
                          value ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-700"
                        }`}
                      >
                        {key.replace(/_/g, " ")}: {value ? "yes" : "no"}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    className="btn-primary px-4 py-2 text-sm"
                    disabled={savingId === record.user_id}
                    onClick={() => review(record.user_id, true)}
                    type="button"
                  >
                    Approve
                  </button>
                  <button
                    className="rounded-md bg-red-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-800 disabled:bg-slate-400"
                    disabled={savingId === record.user_id}
                    onClick={() => review(record.user_id, false)}
                    type="button"
                  >
                    Reject
                  </button>
                </div>
              </div>
            </article>
          ))
        ) : (
          <p className="panel-pad text-slate-600">No pending KYC submissions.</p>
        )}
      </div>
    </section>
  );
}
