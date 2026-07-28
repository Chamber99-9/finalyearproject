"use client";

import { FormEvent, useState } from "react";

type OCRResult = {
  id: string;
  document_id: string;
  application_id: string;
  extracted_text: string;
  confidence_score: number | null;
  verified_by_user: boolean;
  corrected_data: Record<string, unknown>;
  created_at: string;
};

export function OCRVerificationForm() {
  const [ocrResultId, setOcrResultId] = useState("");
  const [ocrResult, setOcrResult] = useState<OCRResult | null>(null);
  const [correctedData, setCorrectedData] = useState("{}");
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function loadOCRResult(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSuccess("");
    setOcrResult(null);

    if (!ocrResultId.trim()) {
      setError("OCR result id is required.");
      return;
    }

    setIsLoading(true);

    try {
      const response = await fetch(
        `/api/ocr/results/${encodeURIComponent(ocrResultId.trim())}`
      );
      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(payload.error ?? "Could not load OCR result.");
        return;
      }

      const result = payload.ocr_result as OCRResult;
      setOcrResult(result);
      setCorrectedData(JSON.stringify(result.corrected_data ?? {}, null, 2));
    } catch {
      setError("Could not reach the OCR service. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }

  async function verifyOCRResult() {
    setError("");
    setSuccess("");

    if (!ocrResult) {
      setError("Load an OCR result before verifying.");
      return;
    }

    let parsedData: Record<string, unknown>;
    try {
      parsedData = JSON.parse(correctedData) as Record<string, unknown>;
    } catch {
      setError("Corrected data must be valid JSON.");
      return;
    }

    if (typeof parsedData !== "object" || parsedData === null || Array.isArray(parsedData)) {
      setError("Corrected data must be a JSON object.");
      return;
    }

    setIsSaving(true);

    try {
      const response = await fetch(
        `/api/ocr/verify/${encodeURIComponent(ocrResult.id)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ corrected_data: parsedData })
        }
      );
      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(payload.error ?? "Could not verify OCR result.");
        return;
      }

      const result = payload.ocr_result as OCRResult;
      setOcrResult(result);
      setCorrectedData(JSON.stringify(result.corrected_data ?? {}, null, 2));
      setSuccess("OCR data verified successfully.");
    } catch {
      setError("Could not reach the OCR verification service. Please try again.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="mt-8 grid gap-6">
      <form className="flex flex-col gap-3 sm:flex-row" onSubmit={loadOCRResult}>
        <input
          className="min-w-0 flex-1 px-3 py-2.5"
          onChange={(event) => setOcrResultId(event.target.value)}
          placeholder="Paste OCR result id"
          value={ocrResultId}
        />
        <button
          className="btn-primary px-5 py-3"
          disabled={isLoading}
          type="submit"
        >
          {isLoading ? "Loading..." : "Load OCR result"}
        </button>
      </form>

      {error ? (
        <p className="alert-error">
          {error}
        </p>
      ) : null}

      {success ? (
        <p className="alert-success">
          {success}
        </p>
      ) : null}

      {ocrResult ? (
        <section className="grid gap-5 lg:grid-cols-2">
          <article className="panel-pad bg-slate-50">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <h2 className="text-lg font-semibold text-slate-950">Extracted text</h2>
              <span className="rounded-md bg-white px-3 py-1 text-sm font-medium text-slate-700">
                Confidence: {ocrResult.confidence_score ?? "N/A"}
              </span>
            </div>
            <pre className="mt-4 whitespace-pre-wrap rounded-md bg-white p-4 text-sm leading-6 text-slate-700">
              {ocrResult.extracted_text}
            </pre>
          </article>

          <article className="panel-pad">
            <h2 className="text-lg font-semibold text-slate-950">Corrected data</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Enter corrected OCR data as a JSON object, then confirm it.
            </p>
            <textarea
              className="mt-4 min-h-72 w-full px-3 py-2 font-mono text-sm"
              onChange={(event) => setCorrectedData(event.target.value)}
              value={correctedData}
            />
            <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-slate-600">
                Status: {ocrResult.verified_by_user ? "Verified" : "Not verified"}
              </p>
              <button
                className="btn-primary px-5 py-3"
                disabled={isSaving}
                onClick={verifyOCRResult}
                type="button"
              >
                {isSaving ? "Saving..." : "Confirm and verify"}
              </button>
            </div>
          </article>
        </section>
      ) : null}
    </div>
  );
}
