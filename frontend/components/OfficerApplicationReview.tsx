"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { EMICard } from "@/components/EMICard";
import { StatusBadge } from "@/components/OfficerDashboard";
import {
  ApplicationStatus,
  OfficerApplicationDetail,
  formatDate,
  formatLabel,
  formatMoney,
  requestDocumentOptions
} from "@/lib/officer";

type OfficerApplicationReviewProps = {
  applicationId: string;
};

export function OfficerApplicationReview({ applicationId }: OfficerApplicationReviewProps) {
  const [detail, setDetail] = useState<OfficerApplicationDetail | null>(null);
  const [selectedDocuments, setSelectedDocuments] = useState<string[]>(["salary_slip"]);
  const [requestMessage, setRequestMessage] = useState("");
  const [offerAmount, setOfferAmount] = useState("");
  const [offerMessage, setOfferMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const loadDetail = useCallback(async () => {
    setIsLoading(true);
    setError("");

    try {
      const response = await fetch(`/api/officer/applications/${applicationId}`);
      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(payload.error ?? "Could not load application review.");
        return;
      }

      setDetail(payload.detail ?? null);
    } catch {
      setError("Could not reach the officer application service.");
    } finally {
      setIsLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  async function updateStatus(status: Extract<ApplicationStatus, "approved" | "rejected">) {
    setIsSaving(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch(`/api/officer/applications/${applicationId}/status`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status,
          note: status === "approved" ? "Approved from officer review" : "Rejected from officer review"
        })
      });
      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(payload.error ?? "Could not update application status.");
        return;
      }

      setSuccess(`Application ${formatLabel(status).toLowerCase()}.`);
      await loadDetail();
    } catch {
      setError("Could not reach the officer status service.");
    } finally {
      setIsSaving(false);
    }
  }

  async function toggleVerification(key: string, value: boolean) {
    setError("");
    setSuccess("");
    try {
      const response = await fetch(
        `/api/officer/applications/${applicationId}/verification`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ [key]: value })
        }
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(payload.error ?? "Could not save verification.");
        return;
      }
      await loadDetail();
    } catch {
      setError("Could not reach the verification service.");
    }
  }

  async function requestDocuments() {
    setIsSaving(true);
    setError("");
    setSuccess("");

    if (selectedDocuments.length === 0) {
      setError("Select at least one document type.");
      setIsSaving(false);
      return;
    }

    try {
      const response = await fetch(
        `/api/officer/applications/${applicationId}/request-document`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            document_types: selectedDocuments,
            message: requestMessage.trim() || null
          })
        }
      );
      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(payload.error ?? "Could not request documents.");
        return;
      }

      setRequestMessage("");
      setSuccess("Document request sent.");
      await loadDetail();
    } catch {
      setError("Could not reach the officer document request service.");
    } finally {
      setIsSaving(false);
    }
  }

  async function sendCounterOffer() {
    setIsSaving(true);
    setError("");
    setSuccess("");

    const amount = Number(offerAmount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setError("Enter a valid offered loan amount.");
      setIsSaving(false);
      return;
    }
    if (!offerMessage.trim()) {
      setError("Enter a message for the customer.");
      setIsSaving(false);
      return;
    }

    try {
      const response = await fetch(
        `/api/officer/applications/${applicationId}/counter-offer`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            offered_loan_amount: amount,
            message: offerMessage.trim()
          })
        }
      );
      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(payload.error ?? "Could not send counter offer.");
        return;
      }

      setOfferAmount("");
      setOfferMessage("");
      setSuccess("Counter offer sent to customer.");
      await loadDetail();
    } catch {
      setError("Could not reach the counter offer service.");
    } finally {
      setIsSaving(false);
    }
  }

  function toggleDocument(documentType: string) {
    setSelectedDocuments((current) =>
      current.includes(documentType)
        ? current.filter((item) => item !== documentType)
        : [...current, documentType]
    );
  }

  if (isLoading && !detail) {
    return (
      <section className="mx-auto max-w-7xl px-5 py-10 sm:px-6 lg:py-14">
        <p className="rounded-md border border-slate-200 bg-white px-4 py-3 text-slate-600">
          Loading application review...
        </p>
      </section>
    );
  }

  if (!detail) {
    return (
      <section className="mx-auto max-w-7xl px-5 py-10 sm:px-6 lg:py-14">
        <Link className="font-semibold text-emerald-700" href="/dashboard/officer">
          Back to applications
        </Link>
        <p className="mt-5 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error || "Application review was not found."}
        </p>
      </section>
    );
  }

  const { application, documents, credit_risk_score: riskScore, suspicious_flags: flags } =
    detail;

  return (
    <section className="mx-auto max-w-7xl px-5 py-10 sm:px-6 lg:py-14">
      <div className="flex flex-col gap-4 border-b border-slate-200 pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <Link className="text-sm font-semibold text-emerald-700" href="/dashboard/officer">
            Back to applications
          </Link>
          <h1 className="mt-3 text-3xl font-bold text-slate-950 sm:text-4xl">
            {application.full_name || "N/A"}
          </h1>
          <p className="mt-2 text-slate-600">{application.citizenship_number || "N/A"}</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <StatusBadge status={application.status} />
          <button
            className="rounded-md bg-emerald-700 px-4 py-2.5 font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            disabled={isSaving}
            onClick={() => updateStatus("approved")}
            type="button"
          >
            Approve
          </button>
          <button
            className="rounded-md bg-red-700 px-4 py-2.5 font-semibold text-white transition hover:bg-red-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            disabled={isSaving}
            onClick={() => updateStatus("rejected")}
            type="button"
          >
            Reject
          </button>
        </div>
      </div>

      {error ? (
        <p className="mt-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      ) : null}

      {success ? (
        <p className="mt-6 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {success}
        </p>
      ) : null}

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_380px]">
        <div className="grid gap-6">
          <InfoGrid
            title="Applicant details"
            rows={[
              ["Email", application.applicant_email || "N/A"],
              ["Phone", application.phone || "N/A"],
              ["Address", application.address || "N/A"],
              ["Employment", formatLabel(application.employment_type)],
              ["Dependents", application.dependents == null ? "N/A" : String(application.dependents)]
            ]}
          />

          <InfoGrid
            title="Loan details"
            rows={[
              ["Loan type", formatLabel(application.loan_type)],
              ["Requested amount", formatMoney(application.requested_loan_amount)],
              [
                "Interest rate used",
                application.interest_rate_used != null
                  ? `${application.interest_rate_used}% p.a.`
                  : "N/A"
              ],
              [
                "Duration",
                application.loan_duration_months
                  ? `${application.loan_duration_months} months`
                  : "N/A"
              ],
              ["Monthly income", formatMoney(application.monthly_income)],
              ["Existing monthly debt", formatMoney(application.existing_monthly_debt)],
              ["PAN number", application.pan_number || "N/A"],
              [
                "Collateral",
                application.collateral_value
                  ? `${formatMoney(application.collateral_value)}${
                      application.collateral_type ? ` (${application.collateral_type})` : ""
                    }`
                  : "None"
              ],
              ["Loan purpose", application.loan_purpose || "N/A"]
            ]}
          />

          <EMICard
            title="EMI and affordability"
            subtitle="Auto-calculated when the customer submitted loan details."
            summary={{
              interest_rate: application.interest_rate_used,
              monthly_emi: application.monthly_emi,
              total_interest: application.total_interest,
              total_payment: application.total_payment,
              dti_ratio: application.emi_dti_ratio,
              affordability: application.affordability
            }}
            emptyMessage="No EMI calculated for this application yet."
          />

          <DocumentsCard documents={documents} ocrResults={detail.ocr_results} />
        </div>

        <div className="grid content-start gap-6">
          <RiskCard riskScore={riskScore} />
          <VerificationChecklist
            verification={application.verification ?? {}}
            onToggle={toggleVerification}
          />
          <FlagsCard flags={flags} />
          <CounterOfferCard
            amount={offerAmount}
            application={application}
            isSaving={isSaving}
            message={offerMessage}
            onAmountChange={setOfferAmount}
            onMessageChange={setOfferMessage}
            onSubmit={sendCounterOffer}
          />
          <RequestDocumentCard
            isSaving={isSaving}
            message={requestMessage}
            onMessageChange={setRequestMessage}
            onSubmit={requestDocuments}
            onToggle={toggleDocument}
            selectedDocuments={selectedDocuments}
          />
        </div>
      </div>
    </section>
  );
}

function CounterOfferCard({
  amount,
  application,
  isSaving,
  message,
  onAmountChange,
  onMessageChange,
  onSubmit
}: {
  amount: string;
  application: OfficerApplicationDetail["application"];
  isSaving: boolean;
  message: string;
  onAmountChange: (value: string) => void;
  onMessageChange: (value: string) => void;
  onSubmit: () => void;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-950">Offer lower amount</h2>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        Requested amount: {formatMoney(application.requested_loan_amount)}
      </p>
      {application.offer_status === "pending" ? (
        <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Pending customer response for {formatMoney(application.offered_loan_amount)}.
        </p>
      ) : null}
      <label className="mt-4 block">
        <span className="text-sm font-medium text-slate-700">Maximum offer amount</span>
        <input
          className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none ring-emerald-600 focus:ring-2"
          min={1}
          onChange={(event) => onAmountChange(event.target.value)}
          placeholder="Example: 500000"
          type="number"
          value={amount}
        />
      </label>
      <textarea
        className="mt-4 min-h-24 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none ring-emerald-600 focus:ring-2"
        maxLength={500}
        onChange={(event) => onMessageChange(event.target.value)}
        placeholder="Explain why this is the maximum amount the institution can offer."
        value={message}
      />
      <button
        className="mt-4 w-full rounded-md bg-emerald-700 px-4 py-2.5 font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:bg-slate-400"
        disabled={isSaving}
        onClick={onSubmit}
        type="button"
      >
        {isSaving ? "Sending offer..." : "Send Offer to Customer"}
      </button>
    </section>
  );
}

function InfoGrid({ title, rows }: { title: string; rows: Array<[string, string]> }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        {rows.map(([label, value]) => (
          <div key={label}>
            <p className="text-sm font-medium text-slate-500">{label}</p>
            <p className="mt-1 break-words text-sm font-semibold text-slate-950">
              {value}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

function DocumentsCard({
  documents,
  ocrResults
}: {
  documents: OfficerApplicationDetail["documents"];
  ocrResults: OfficerApplicationDetail["ocr_results"];
}) {
  const detectionByDocument = new Map(
    ocrResults.map((result) => [result.document_id, result] as const)
  );
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-950">Uploaded documents</h2>
      <p className="mt-1 text-sm text-slate-600">
        Verify each document manually. The detected type is only an automated hint.
      </p>
      <div className="mt-4 grid gap-4">
        {documents.length > 0 ? (
          documents.map((document) => {
            const detection = detectionByDocument.get(document.id);
            return (
            <article
              className="rounded-md border border-slate-200 bg-slate-50 p-4"
              key={document.id}
            >
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="font-semibold text-slate-950">
                    {formatLabel(document.document_type)}
                  </p>
                  <p className="mt-1 break-words text-sm text-slate-600">
                    {document.filename}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Uploaded {formatDate(document.uploaded_at)}
                  </p>
                </div>
                <span className="rounded-md bg-white px-2.5 py-1 text-xs font-semibold text-slate-600">
                  {document.content_type}
                </span>
              </div>
              {detection && detection.detected_label ? (
                <p
                  className={`mt-3 inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-semibold ${
                    detection.type_match === false
                      ? "bg-red-100 text-red-700"
                      : detection.type_match === true
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-amber-100 text-amber-800"
                  }`}
                >
                  Detected hint: {detection.detected_label}
                  {typeof detection.detection_confidence === "number"
                    ? ` (${Math.round(detection.detection_confidence * 100)}%)`
                    : ""}
                  {detection.type_match === false ? " · does not match" : ""}
                </p>
              ) : null}
              <a
                className="mt-4 inline-flex rounded-md bg-emerald-700 px-3 py-2 text-sm font-semibold text-white transition hover:bg-emerald-800"
                href={`/api/officer/documents/${encodeURIComponent(document.id)}/download`}
                rel="noreferrer"
                target="_blank"
              >
                Open document
              </a>
            </article>
            );
          })
        ) : (
          <p className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600">
            No documents uploaded.
          </p>
        )}
      </div>
    </section>
  );
}

function RiskCard({ riskScore }: { riskScore: OfficerApplicationDetail["credit_risk_score"] }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-950">
        Rule-based Credit Risk Score
      </h2>
      {riskScore ? (
        <div className="mt-4 grid gap-4">
          <div className="grid grid-cols-2 gap-3">
            <ScoreBox label="Raw score" value={`${riskScore.raw_score}/100`} />
            <ScoreBox
              label="Normalized"
              value={`${riskScore.normalized_score}/850`}
            />
          </div>
          <p className="rounded-md bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-800">
            {riskScore.risk_level}
          </p>
          <div className="grid grid-cols-2 gap-3">
            <ScoreBox
              label="DTI (incl. EMI)"
              value={`${riskScore.dti_ratio.toFixed(2)}%`}
            />
            <ScoreBox
              label="Affordability"
              value={riskScore.affordability ?? "N/A"}
            />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-600">Repayment history used</p>
            <p className="mt-1 text-sm font-semibold text-slate-950">
              {formatLabel(riskScore.repayment_history_used)}
            </p>
          </div>
          <div>
            <p className="text-sm font-medium text-slate-600">Scoring model</p>
            <p className="mt-1 text-sm font-semibold text-slate-950">
              {riskScore.scoring_model_version}
            </p>
          </div>
          <div>
            <p className="text-sm font-medium text-slate-600">Score breakdown</p>
            <div className="mt-2 grid gap-2">
              {Object.entries(riskScore.score_breakdown).map(([key, value]) => (
                <div
                  className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-2 text-sm"
                  key={key}
                >
                  <span className="text-slate-600">{formatLabel(key)}</span>
                  <span className="font-semibold text-slate-950">{value}</span>
                </div>
              ))}
            </div>
          </div>
          <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
            {riskScore.disclaimer}
          </p>
        </div>
      ) : (
        <p className="mt-4 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600">
          No credit risk score available.
        </p>
      )}
    </section>
  );
}

function ScoreBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-slate-50 p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </p>
      <p className="mt-1 text-xl font-bold text-slate-950">{value}</p>
    </div>
  );
}

function FlagsCard({ flags }: { flags: OfficerApplicationDetail["suspicious_flags"] }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-950">Suspicious flags</h2>
      {flags ? (
        <div className="mt-4 grid gap-3">
          <div className="grid grid-cols-2 gap-3">
            <ScoreBox label="Total flags" value={String(flags.total_flags)} />
            <ScoreBox label="Suspicion" value={flags.suspicion_level} />
          </div>
          {flags.flags.length > 0 ? (
            flags.flags.map((flag) => (
              <article className="rounded-md border border-slate-200 p-3" key={flag.code}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
                    {flag.code}
                  </span>
                  <span className="rounded-md bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-800">
                    {flag.severity}
                  </span>
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-700">{flag.message}</p>
              </article>
            ))
          ) : (
            <p className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600">
              No suspicious flags.
            </p>
          )}
        </div>
      ) : (
        <p className="mt-4 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600">
          No suspicious flag result available.
        </p>
      )}
    </section>
  );
}

const verificationItems: Array<{ key: string; label: string }> = [
  { key: "pan_verified", label: "PAN verified" },
  { key: "income_verified", label: "Income verified" },
  { key: "salary_statement_verified", label: "Salary statement valid" },
  { key: "stamp_verified", label: "Stamp verified" },
  { key: "signature_verified", label: "Signature verified" },
  { key: "collateral_verified", label: "Collateral verified" },
  { key: "valuation_report_verified", label: "Valuation report verified" },
  { key: "recommendation_letter_verified", label: "Recommendation letter verified" }
];

function VerificationChecklist({
  verification,
  onToggle
}: {
  verification: Record<string, boolean>;
  onToggle: (key: string, value: boolean) => void;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-950">Verification checklist</h2>
      <p className="mt-1 text-sm text-slate-600">Confirm each check during review.</p>
      <div className="mt-4 grid gap-2">
        {verificationItems.map((item) => (
          <label
            className="flex items-center gap-3 rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700"
            key={item.key}
          >
            <input
              checked={Boolean(verification[item.key])}
              onChange={(event) => onToggle(item.key, event.target.checked)}
              type="checkbox"
            />
            {item.label}
          </label>
        ))}
      </div>
    </section>
  );
}

function RequestDocumentCard({
  isSaving,
  message,
  onMessageChange,
  onSubmit,
  onToggle,
  selectedDocuments
}: {
  isSaving: boolean;
  message: string;
  onMessageChange: (value: string) => void;
  onSubmit: () => void;
  onToggle: (documentType: string) => void;
  selectedDocuments: string[];
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-950">Request document</h2>
      <div className="mt-4 grid gap-3">
        {requestDocumentOptions.map((option) => (
          <label
            className="flex items-center gap-3 rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700"
            key={option.value}
          >
            <input
              checked={selectedDocuments.includes(option.value)}
              onChange={() => onToggle(option.value)}
              type="checkbox"
            />
            {option.label}
          </label>
        ))}
      </div>
      <textarea
        className="mt-4 min-h-24 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none ring-emerald-600 focus:ring-2"
        maxLength={500}
        onChange={(event) => onMessageChange(event.target.value)}
        placeholder="Message to customer"
        value={message}
      />
      <button
        className="mt-4 w-full rounded-md bg-slate-900 px-4 py-2.5 font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
        disabled={isSaving}
        onClick={onSubmit}
        type="button"
      >
        {isSaving ? "Sending request..." : "Request Document"}
      </button>
    </section>
  );
}
