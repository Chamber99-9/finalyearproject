"use client";

import { useEffect, useState } from "react";

type KycRecord = {
  id: string;
  status: string;
  full_name: string;
  pan_number: string;
  citizenship_number: string;
  date_of_birth: string;
  review_note?: string | null;
};

const statusTone: Record<string, string> = {
  verified: "bg-emerald-100 text-emerald-800",
  pending: "bg-amber-100 text-amber-800",
  rejected: "bg-red-100 text-red-700"
};

/**
 * Customer KYC panel. Shows current KYC status, or a submission form when not
 * yet submitted (or after a rejection).
 */
export function KycPanel() {
  const [kyc, setKyc] = useState<KycRecord | null>(null);
  const [form, setForm] = useState({
    full_name: "",
    pan_number: "",
    citizenship_number: "",
    date_of_birth: ""
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadKyc() {
      try {
        const response = await fetch("/api/kyc/me");
        const payload = await response.json().catch(() => ({}));
        if (response.ok) setKyc(payload.kyc ?? null);
      } catch {
        // Non-fatal.
      } finally {
        setIsLoading(false);
      }
    }
    loadKyc();
  }, []);

  async function submit() {
    setError("");
    if (!/^\d{9}$/.test(form.pan_number.trim())) {
      setError("PAN number must be exactly 9 digits.");
      return;
    }
    setIsSaving(true);
    try {
      const response = await fetch("/api/kyc/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form)
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(payload.error ?? "Could not submit KYC.");
        return;
      }
      setKyc(payload.kyc);
    } catch {
      setError("Could not reach the KYC service.");
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) return null;

  const showForm = !kyc || kyc.status === "rejected";

  return (
    <section className="panel-pad">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-slate-950">KYC verification</h2>
        {kyc ? (
          <span className={`status-pill ${statusTone[kyc.status] ?? "bg-slate-100 text-slate-700"}`}>
            {kyc.status}
          </span>
        ) : (
          <span className="status-pill bg-slate-100 text-slate-700">not started</span>
        )}
      </div>

      {kyc && kyc.status === "verified" ? (
        <p className="mt-3 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          Your identity is verified. You can apply for loans.
        </p>
      ) : null}
      {kyc && kyc.status === "pending" ? (
        <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Your KYC is under review.
        </p>
      ) : null}
      {kyc && kyc.status === "rejected" ? (
        <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          KYC rejected{kyc.review_note ? `: ${kyc.review_note}` : ""}. Please resubmit.
        </p>
      ) : null}

      {showForm ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Full name</span>
            <input
              className="mt-2 w-full px-3 py-2.5"
              onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
              value={form.full_name}
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">PAN number (9 digits)</span>
            <input
              className="mt-2 w-full px-3 py-2.5"
              inputMode="numeric"
              maxLength={9}
              onChange={(e) => setForm((f) => ({ ...f, pan_number: e.target.value }))}
              value={form.pan_number}
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Citizenship number</span>
            <input
              className="mt-2 w-full px-3 py-2.5"
              onChange={(e) => setForm((f) => ({ ...f, citizenship_number: e.target.value }))}
              value={form.citizenship_number}
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Date of birth</span>
            <input
              className="mt-2 w-full px-3 py-2.5"
              max={new Date().toISOString().slice(0, 10)}
              onChange={(e) => setForm((f) => ({ ...f, date_of_birth: e.target.value }))}
              type="date"
              value={form.date_of_birth}
            />
          </label>
          {error ? <p className="alert-error px-3 py-2 sm:col-span-2">{error}</p> : null}
          <button
            className="btn-primary px-5 py-2.5 sm:col-span-2 sm:w-fit"
            disabled={isSaving}
            onClick={submit}
            type="button"
          >
            {isSaving ? "Submitting..." : "Submit KYC"}
          </button>
        </div>
      ) : null}
    </section>
  );
}
