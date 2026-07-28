"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { EMICard, EMISummary } from "@/components/EMICard";

type Step = "loan" | "documents" | "verify" | "details" | "done";
type DocumentType =
  | "citizenship_document"
  | "salary_slip"
  | "bank_statement"
  | "supporting_document";

type ApplicationResponse = {
  id: string;
  status: string;
  full_name?: string | null;
  citizenship_number?: string | null;
  phone?: string | null;
  address?: string | null;
  loan_type?: string | null;
  monthly_income?: number | null;
  employment_type?: string | null;
  existing_monthly_debt?: number | null;
  requested_loan_amount?: number | null;
  loan_duration_months?: number | null;
  annual_interest_rate?: number | null;
  loan_tenure?: number | null;
  tenure_unit?: string | null;
  monthly_emi?: number | null;
  total_interest?: number | null;
  total_payment?: number | null;
  emi_dti_ratio?: number | null;
  affordability?: string | null;
  loan_purpose?: string | null;
  dependents?: number | null;
  savings_buffer?: string | null;
  repayment_history?: string | null;
};

type UploadedDocument = {
  id: string;
  document_type: DocumentType;
  filename: string;
  content_type: string;
  uploaded_at: string;
};

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

type DocumentRequest = {
  id: string;
  document_types: DocumentType[];
  message?: string | null;
  created_at: string;
};

const documentOptions: Array<{ value: DocumentType; label: string; required: boolean }> = [
  { value: "citizenship_document", label: "Citizenship document", required: true },
  { value: "salary_slip", label: "Salary slip", required: true },
  { value: "bank_statement", label: "Bank statement", required: true },
  { value: "supporting_document", label: "Optional supporting document", required: false }
];

const employmentOptions = [
  { value: "salaried", label: "Salaried" },
  { value: "self_employed", label: "Self-employed" },
  { value: "business", label: "Business" },
  { value: "contract", label: "Contract" },
  { value: "unemployed", label: "Unemployed" },
  { value: "other", label: "Other" }
];

const savingsOptions = [
  { value: "good", label: "Good savings buffer" },
  { value: "average", label: "Average savings buffer" },
  { value: "low", label: "Low savings buffer" }
];

const repaymentOptions = [
  { value: "no_previous_default", label: "No previous default" },
  { value: "minor_late_payment", label: "Minor late payment" },
  { value: "previous_default", label: "Previous default" }
];

const tenureUnitOptions = [
  { value: "years", label: "Years" },
  { value: "months", label: "Months" }
];

const initialForm = {
  full_name: "",
  citizenship_number: "",
  phone: "",
  address: "",
  loan_type: "personal",
  monthly_income: "",
  employment_type: "salaried",
  existing_monthly_debt: "0",
  requested_loan_amount: "",
  annual_interest_rate: "",
  loan_tenure: "",
  tenure_unit: "years",
  loan_purpose: "",
  dependents: "0",
  savings_buffer: "average",
  repayment_history: "no_previous_default"
};

/** Convert a tenure + unit into a number of monthly installments (N). */
function tenureToMonths(tenure: string, unit: string) {
  const value = Number(tenure);
  if (!Number.isFinite(value) || value <= 0) {
    return 0;
  }
  return unit === "years" ? Math.round(value * 12) : Math.round(value);
}

type FormState = typeof initialForm;
type FormField = keyof FormState;

const maxUploadBytes = 10 * 1024 * 1024;
const emptyDocumentFiles: Record<DocumentType, File | null> = {
  citizenship_document: null,
  salary_slip: null,
  bank_statement: null,
  supporting_document: null
};
const emptyInputVersions: Record<DocumentType, number> = {
  citizenship_document: 0,
  salary_slip: 0,
  bank_statement: 0,
  supporting_document: 0
};

export function LoanApplicationForm() {
  const searchParams = useSearchParams();
  const [step, setStep] = useState<Step>("loan");
  const [applicationId, setApplicationId] = useState(searchParams.get("applicationId") ?? "");
  const [form, setForm] = useState<FormState>(initialForm);
  const [documentFiles, setDocumentFiles] =
    useState<Record<DocumentType, File | null>>(emptyDocumentFiles);
  const [inputVersions, setInputVersions] =
    useState<Record<DocumentType, number>>(emptyInputVersions);
  const [uploadedDocuments, setUploadedDocuments] = useState<UploadedDocument[]>([]);
  const [documentRequest, setDocumentRequest] = useState<DocumentRequest | null>(null);
  const [ocrResults, setOcrResults] = useState<OCRResult[]>([]);
  const [activeOcrId, setActiveOcrId] = useState("");
  const [correctedData, setCorrectedData] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [emiSummary, setEmiSummary] = useState<EMISummary | null>(null);

  const activeOcr = ocrResults.find((result) => result.id === activeOcrId) ?? null;
  const activeDocument = activeOcr
    ? uploadedDocuments.find((document) => document.id === activeOcr.document_id)
    : null;

  const missingRequiredDocuments = useMemo(() => {
    const uploadedTypes = new Set(uploadedDocuments.map((document) => document.document_type));
    return documentOptions.filter((option) => option.required && !uploadedTypes.has(option.value));
  }, [uploadedDocuments]);
  const missingRequestedDocuments = useMemo(() => {
    if (!documentRequest) {
      return [];
    }

    const uploadedTypes = new Set(
      uploadedDocuments
        .filter((document) => isUploadedForCurrentRequest(document, documentRequest))
        .map((document) => document.document_type)
    );
    return documentRequest.document_types.filter((type) => !uploadedTypes.has(type));
  }, [documentRequest, uploadedDocuments]);

  useEffect(() => {
    if (!applicationId) {
      return;
    }

    async function loadApplication() {
      setIsLoading(true);
      setError("");

      try {
        const response = await fetch(`/api/applications/${encodeURIComponent(applicationId)}`);
        const payload = await response.json().catch(() => ({}));

        if (!response.ok) {
          setError(payload.error ?? "Could not load draft application.");
          return;
        }

        const application = payload.application as ApplicationResponse;
        applyApplicationToForm(application);
        const [documents] = await Promise.all([
          loadSavedDocuments(applicationId),
          loadDocumentRequest(applicationId)
        ]);
        await loadSavedOCRResults(applicationId, documents);
        setStep(application.status === "draft" ? "documents" : "done");
      } catch {
        setError("Could not reach the application service.");
      } finally {
        setIsLoading(false);
      }
    }

    loadApplication();
  }, [applicationId]);

  // Live EMI preview (requirements #6, #11): recalculates the EMI whenever the
  // loan amount, interest rate or tenure change and all are valid. Calls the
  // backend calculator, then derives an EMI-inclusive DTI + affordability
  // client-side so the card can show the same recommendation as the server.
  useEffect(() => {
    const loanAmount = Number(form.requested_loan_amount);
    const interestRate = Number(form.annual_interest_rate);
    const months = tenureToMonths(form.loan_tenure, form.tenure_unit);

    if (!(loanAmount > 0) || !(interestRate > 0) || months < 1) {
      setEmiSummary(null);
      return;
    }

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const response = await fetch("/api/emi/calculate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            loan_amount: loanAmount,
            annual_interest_rate: interestRate,
            tenure: Number(form.loan_tenure),
            tenure_unit: form.tenure_unit
          }),
          signal: controller.signal
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          setEmiSummary(null);
          return;
        }

        const emi = payload.emi as {
          monthly_emi: number;
          total_interest: number;
          total_payment: number;
        };

        // Derive DTI + affordability for the preview when income is available.
        const income = Number(form.monthly_income);
        const existingDebt = Number(form.existing_monthly_debt);
        let dtiRatio: number | null = null;
        let affordability: string | null = null;
        if (income > 0 && Number.isFinite(existingDebt)) {
          dtiRatio =
            Math.round(((existingDebt + emi.monthly_emi) / income) * 100 * 100) / 100;
          affordability = classifyAffordability(dtiRatio);
        }

        setEmiSummary({
          monthly_emi: emi.monthly_emi,
          total_interest: emi.total_interest,
          total_payment: emi.total_payment,
          dti_ratio: dtiRatio,
          affordability
        });
      } catch {
        // Aborted or network error — leave the last summary in place.
      }
    }, 300);

    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [
    form.requested_loan_amount,
    form.annual_interest_rate,
    form.loan_tenure,
    form.tenure_unit,
    form.monthly_income,
    form.existing_monthly_debt
  ]);

  async function loadSavedDocuments(id: string) {
    const response = await fetch(`/api/applications/${encodeURIComponent(id)}/documents`);
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      setError(payload.error ?? "Could not load uploaded documents.");
      return [];
    }

    const documents = (payload.documents ?? []) as UploadedDocument[];
    setUploadedDocuments(documents);
    return documents;
  }

  async function loadDocumentRequest(id: string) {
    const response = await fetch(`/api/applications/${encodeURIComponent(id)}/document-request`);
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      setError(payload.error ?? "Could not load document request.");
      setDocumentRequest(null);
      return;
    }

    setDocumentRequest(payload.document_request ?? null);
  }

  async function loadSavedOCRResults(id: string, documents: UploadedDocument[]) {
    const response = await fetch(`/api/applications/${encodeURIComponent(id)}/ocr-results`);
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      setError(payload.error ?? "Could not load OCR results.");
      return;
    }

    const results = (payload.ocr_results ?? []) as OCRResult[];
    setOcrResults(results);

    const documentsById = new Map(
      documents.map((document) => [document.id, document.document_type])
    );
    for (const result of results.slice().reverse()) {
      const documentType = documentsById.get(result.document_id);
      if (documentType) {
        mergeCorrectedDataIntoForm(defaultCorrectedData(documentType, result));
      }
    }
  }

  function isDocumentTypeAllowed(type: DocumentType) {
    if (!documentRequest) {
      return true;
    }

    return documentRequest.document_types.includes(type);
  }

  function canLeaveDocumentStep() {
    return !documentRequest || missingRequestedDocuments.length === 0;
  }

  function continueFromDocuments() {
    resetMessages();

    if (!canLeaveDocumentStep()) {
      setError(
        `Upload all requested documents first. Still needed: ${missingRequestedDocuments
          .map(labelForDocument)
          .join(", ")}.`
      );
      return;
    }

    setStep(ocrResults.length > 0 ? "verify" : "details");
  }

  function selectStep(nextStep: Step) {
    resetMessages();

    if (
      step === "documents" &&
      documentRequest &&
      missingRequestedDocuments.length > 0 &&
      !["loan", "documents"].includes(nextStep)
    ) {
      setError(
        `Upload all requested documents first. Still needed: ${missingRequestedDocuments
          .map(labelForDocument)
          .join(", ")}.`
      );
      return;
    }

    setStep(nextStep);
  }

  function resetMessages() {
    setError("");
    setSuccess("");
  }

  function updateField(name: FormField, value: string) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  function applyApplicationToForm(application: ApplicationResponse) {
    setForm((current) => ({
      ...current,
      full_name: application.full_name ?? current.full_name,
      citizenship_number: application.citizenship_number ?? current.citizenship_number,
      phone: application.phone ?? current.phone,
      address: application.address ?? current.address,
      loan_type: application.loan_type ?? current.loan_type,
      monthly_income: valueToInput(application.monthly_income, current.monthly_income),
      employment_type: application.employment_type ?? current.employment_type,
      existing_monthly_debt: valueToInput(
        application.existing_monthly_debt,
        current.existing_monthly_debt
      ),
      requested_loan_amount: valueToInput(
        application.requested_loan_amount,
        current.requested_loan_amount
      ),
      annual_interest_rate: valueToInput(
        application.annual_interest_rate,
        current.annual_interest_rate
      ),
      loan_tenure: valueToInput(application.loan_tenure, current.loan_tenure),
      tenure_unit: application.tenure_unit ?? current.tenure_unit,
      loan_purpose: application.loan_purpose ?? current.loan_purpose,
      dependents: valueToInput(application.dependents, current.dependents),
      savings_buffer: application.savings_buffer ?? current.savings_buffer,
      repayment_history: application.repayment_history ?? current.repayment_history
    }));
  }

  async function startDraft() {
    resetMessages();
    setIsLoading(true);

    try {
      const response = await fetch("/api/applications/draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ loan_type: form.loan_type })
      });
      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(payload.error ?? "Could not start loan application.");
        return;
      }

      const application = payload.application as ApplicationResponse;
      setApplicationId(application.id);
      applyApplicationToForm(application);
      setStep("documents");
      setSuccess("Draft started. Upload the required documents next.");
    } catch {
      setError("Could not reach the application service.");
    } finally {
      setIsLoading(false);
    }
  }

  async function uploadDocument(documentType: DocumentType) {
    resetMessages();

    const file = documentFiles[documentType];

    if (!applicationId) {
      setError("Start a draft application before uploading documents.");
      return;
    }
    if (!file) {
      setError(`Choose a file for ${labelForDocument(documentType)}.`);
      return;
    }
    if (!isDocumentTypeAllowed(documentType)) {
      setError("You can only upload the document requested by the loan officer.");
      return;
    }
    if (file.size === 0) {
      setError("Selected file cannot be empty.");
      return;
    }
    if (file.size > maxUploadBytes) {
      setError("Selected file must be 10 MB or smaller.");
      return;
    }
    if (!["application/pdf", "image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      setError("Upload a PDF, JPEG, PNG, or WebP file.");
      return;
    }

    setIsLoading(true);

    try {
      const formData = new FormData();
      formData.append("document_type", documentType);
      formData.append("file", file);

      const response = await fetch(
        `/api/applications/${encodeURIComponent(applicationId)}/documents`,
        { method: "POST", body: formData }
      );
      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(payload.error ?? "Could not upload document.");
        return;
      }

      const uploaded = payload.document as UploadedDocument;
      const nextUploadedDocuments = [
        uploaded,
        ...uploadedDocuments.filter((document) => document.id !== uploaded.id)
      ];
      const nextUploadedTypes = new Set(
        nextUploadedDocuments
          .filter((document) =>
            documentRequest ? isUploadedForCurrentRequest(document, documentRequest) : true
          )
          .map((document) => document.document_type)
      );
      const remainingRequestedDocuments =
        documentRequest?.document_types.filter((type) => !nextUploadedTypes.has(type)) ?? [];

      setUploadedDocuments(nextUploadedDocuments);
      setDocumentFiles((current) => ({ ...current, [documentType]: null }));
      setInputVersions((current) => ({
        ...current,
        [documentType]: current[documentType] + 1
      }));

      if (uploaded.content_type === "application/pdf") {
        setSuccess(
          remainingRequestedDocuments.length > 0
            ? `${labelForDocument(uploaded.document_type)} uploaded. Still needed: ${remainingRequestedDocuments
                .map(labelForDocument)
                .join(", ")}.`
            : `${labelForDocument(uploaded.document_type)} uploaded. PDF OCR is not supported yet, so continue by filling the application fields manually.`
        );
        return;
      }

      await extractOCR(uploaded, {
        stayOnDocuments: remainingRequestedDocuments.length > 0,
        remainingRequestedDocuments
      });
    } catch {
      setError("Could not reach the upload service. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }

  async function extractOCR(
    document: UploadedDocument,
    options?: {
      stayOnDocuments?: boolean;
      remainingRequestedDocuments?: DocumentType[];
    }
  ) {
    const response = await fetch(`/api/ocr/extract/${encodeURIComponent(document.id)}`, {
      method: "POST"
    });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      setSuccess(
        `${labelForDocument(document.document_type)} uploaded, but OCR could not run: ${
          payload.error ?? "unsupported or unreadable file"
        }.`
      );
      return;
    }

      const result = payload.ocr_result as OCRResult;
      const suggestedData = defaultCorrectedData(document.document_type, result);
      setOcrResults((current) => [result, ...current]);
      setActiveOcrId(result.id);
      setCorrectedData(suggestedData);
      mergeCorrectedDataIntoForm(suggestedData);
      if (!options?.stayOnDocuments) {
        setStep("verify");
      }
      setSuccess(
        options?.stayOnDocuments && options.remainingRequestedDocuments?.length
          ? `${labelForDocument(document.document_type)} uploaded and OCR text extracted. Still needed: ${options.remainingRequestedDocuments
              .map(labelForDocument)
              .join(", ")}.`
          : `${labelForDocument(document.document_type)} uploaded and OCR text extracted.`
      );
  }

  async function verifyOCR() {
    resetMessages();

    if (!activeOcr) {
      setError("Select an OCR result to verify.");
      return;
    }
    if (activeOcr.verified_by_user) {
      setStep("documents");
      setSuccess("OCR data is already verified. You can upload another document.");
      return;
    }

    const cleanedData = Object.fromEntries(
      Object.entries(correctedData)
        .map(([key, value]) => [key, value.trim()])
        .filter(([, value]) => value)
    );

    setIsLoading(true);

    try {
      const response = await fetch(`/api/ocr/verify/${encodeURIComponent(activeOcr.id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ corrected_data: cleanedData })
      });
      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(payload.error ?? "Could not verify OCR result.");
        return;
      }

      const verified = payload.ocr_result as OCRResult;
      setOcrResults((current) =>
        current.map((result) => (result.id === verified.id ? verified : result))
      );
      mergeCorrectedDataIntoForm(cleanedData);
      setStep("documents");
      setSuccess("OCR data verified. Upload another document or continue.");
    } catch {
      setError("Could not reach the OCR verification service.");
    } finally {
      setIsLoading(false);
    }
  }

function mergeCorrectedDataIntoForm(data: Record<string, string>) {
    setForm((current) => ({
      ...current,
      full_name:
        data.full_name ||
        data.employee_name ||
        data.account_holder_name ||
        current.full_name,
      citizenship_number: data.citizenship_number || current.citizenship_number,
      phone: data.phone || current.phone,
      address: data.address || current.address,
      monthly_income: numericText(data.monthly_income) || current.monthly_income
    }));
  }

  function validateFinalForm() {
    if (form.full_name.trim().length < 2) return "Full name is required.";
    if (form.citizenship_number.trim().length < 3) return "Citizenship number is required.";
    if (form.phone.trim().length < 7) return "Enter a valid phone number.";
    if (form.address.trim().length < 3) return "Address is required.";
    if (Number(form.monthly_income) <= 0) return "Monthly income must be greater than 0.";
    if (Number(form.existing_monthly_debt) < 0) return "Existing monthly debt cannot be negative.";
    if (Number(form.requested_loan_amount) <= 0) return "Requested loan amount is required.";
    if (Number(form.annual_interest_rate) <= 0) {
      return "Annual interest rate must be greater than 0.";
    }
    if (Number(form.loan_tenure) <= 0) return "Loan tenure must be greater than 0.";
    const duration = tenureToMonths(form.loan_tenure, form.tenure_unit);
    if (!Number.isInteger(duration) || duration < 1 || duration > 360) {
      return "Loan tenure must resolve to between 1 and 360 months.";
    }
    if (form.loan_purpose.trim().length < 3) return "Loan purpose is required.";
    const dependents = Number(form.dependents);
    if (!Number.isInteger(dependents) || dependents < 0) {
      return "Dependents must be a whole number.";
    }
    return "";
  }

  async function saveFinalDetails({ submit }: { submit: boolean }) {
    resetMessages();

    if (!applicationId) {
      setError("Start a draft application first.");
      return;
    }

    const validationError = validateFinalForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    setIsLoading(true);

    try {
      const updateResponse = await fetch(`/api/applications/${encodeURIComponent(applicationId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(applicationPayload(form))
      });
      const updatePayload = await updateResponse.json().catch(() => ({}));

      if (!updateResponse.ok) {
        setError(updatePayload.error ?? "Could not save application details.");
        return;
      }

      if (!submit) {
        setSuccess("Application details saved as draft.");
        return;
      }

      const submitResponse = await fetch(
        `/api/applications/${encodeURIComponent(applicationId)}/submit`,
        { method: "POST" }
      );
      const submitPayload = await submitResponse.json().catch(() => ({}));

      if (!submitResponse.ok) {
        setError(submitPayload.error ?? "Could not submit application.");
        return;
      }

      setStep("done");
      setSuccess("Application submitted for officer review.");
    } catch {
      setError("Could not reach the application service.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="mt-8 grid gap-6">
      <StepTabs step={step} onSelect={selectStep} applicationStarted={Boolean(applicationId)} />

      {error ? <Alert tone="error" message={error} /> : null}
      {success ? <Alert tone="success" message={success} /> : null}
      {isLoading ? <Alert tone="info" message="Working on your application..." /> : null}

      {step === "loan" ? (
        <section className="grid gap-5">
          <div>
            <h2 className="text-xl font-semibold text-slate-950">Choose loan type</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Sajilo Loan currently uses one common document checklist for all loan types.
            </p>
          </div>
          <label className="block max-w-md">
            <span className="text-sm font-medium text-slate-700">Loan type</span>
            <select
              className="mt-2 w-full px-3 py-2.5"
              onChange={(event) => updateField("loan_type", event.target.value)}
              value={form.loan_type}
            >
              <option value="personal">Personal loan</option>
            </select>
          </label>
          <button
            className="btn-primary w-fit px-5 py-3"
            disabled={isLoading}
            onClick={startDraft}
            type="button"
          >
            Start and upload documents
          </button>
        </section>
      ) : null}

      {step === "documents" ? (
        <section className="grid gap-6 lg:grid-cols-[1fr_340px]">
          <div className="grid gap-5">
            <div>
              <h2 className="text-xl font-semibold text-slate-950">Upload documents</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                Application reference: <span className="font-semibold">{applicationId}</span>
              </p>
            </div>
            {documentRequest ? (
              <div className="alert-info">
                <p className="font-semibold">Loan officer requested documents</p>
                <p className="mt-1">
                  {documentRequest.message ||
                    "Please upload only the requested document type below."}
                </p>
                <p className="mt-2 text-sm">
                  Requested:{" "}
                  {documentRequest.document_types.map(labelForDocument).join(", ")}
                </p>
                {missingRequestedDocuments.length > 0 ? (
                  <p className="mt-2 text-sm font-semibold text-amber-800">
                    Still needed: {missingRequestedDocuments.map(labelForDocument).join(", ")}
                  </p>
                ) : (
                  <p className="mt-2 text-sm font-semibold text-emerald-800">
                    All requested documents are uploaded.
                  </p>
                )}
              </div>
            ) : null}
            <div className="grid gap-4">
              {documentOptions.map((option) => {
                const uploaded = uploadedDocuments.find(
                  (document) =>
                    document.document_type === option.value &&
                    (!documentRequest ||
                      isUploadedForCurrentRequest(document, documentRequest))
                );
                const previousUpload = uploadedDocuments.find(
                  (document) => document.document_type === option.value
                );
                const selectedFile = documentFiles[option.value];
                const isAllowed = isDocumentTypeAllowed(option.value);

                return (
                  <article
                    className={`panel-pad p-4 ${isAllowed ? "" : "opacity-60"}`}
                    key={option.value}
                  >
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <h3 className="font-semibold text-slate-950">{option.label}</h3>
                        <p className="mt-1 text-sm text-slate-600">
                          {isAllowed
                            ? option.required
                              ? "Required document"
                              : "Optional document"
                            : "Not requested right now"}
                        </p>
                        {uploaded ? (
                          <p className="mt-2 break-words text-sm text-emerald-700">
                            Uploaded: {uploaded.filename}
                          </p>
                        ) : null}
                        {!uploaded && previousUpload && documentRequest ? (
                          <p className="mt-2 break-words text-sm text-slate-500">
                            Previous upload: {previousUpload.filename}
                          </p>
                        ) : null}
                      </div>
                      <span
                        className={`w-fit rounded-md px-2.5 py-1 text-xs font-semibold ${
                          uploaded
                            ? "bg-emerald-100 text-emerald-800"
                            : option.required
                              ? "bg-amber-100 text-amber-800"
                              : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {uploaded ? "Uploaded" : option.required ? "Required" : "Optional"}
                      </span>
                    </div>
                    <label className="mt-4 block">
                      <span className="text-sm font-medium text-slate-700">
                        {option.label} file
                      </span>
                      <input
                        accept="application/pdf,image/jpeg,image/png,image/webp"
                        className="mt-2 w-full px-3 py-2 text-sm file:mr-4 file:rounded-md file:border-0 file:bg-emerald-700 file:px-4 file:py-2 file:font-semibold file:text-white"
                        disabled={!isAllowed}
                        key={`${option.value}-${inputVersions[option.value]}`}
                        onChange={(event) =>
                          setDocumentFiles((current) => ({
                            ...current,
                            [option.value]: event.target.files?.[0] ?? null
                          }))
                        }
                        type="file"
                      />
                    </label>
                    {selectedFile ? (
                      <p className="mt-2 break-words text-xs text-slate-500">
                        Selected: {selectedFile.name}
                      </p>
                    ) : null}
                    <button
                      className="btn-primary mt-4"
                      disabled={isLoading || !isAllowed}
                      onClick={() => uploadDocument(option.value)}
                      type="button"
                    >
                      Upload {option.required ? "required document" : "optional document"}
                    </button>
                  </article>
                );
              })}
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <button
                className="btn-secondary px-5 py-3"
                disabled={!canLeaveDocumentStep()}
                onClick={continueFromDocuments}
                type="button"
              >
                Continue
              </button>
            </div>
          </div>

          <DocumentChecklist
            missingRequiredDocuments={missingRequiredDocuments}
            uploadedDocuments={uploadedDocuments}
          />
        </section>
      ) : null}

      {step === "verify" ? (
        <section className="grid gap-6 lg:grid-cols-[300px_1fr]">
          <aside className="grid content-start gap-3">
            <h2 className="text-xl font-semibold text-slate-950">Verify OCR data</h2>
            {ocrResults.map((result) => {
              const document = uploadedDocuments.find((item) => item.id === result.document_id);
              return (
                <button
                  className={`rounded-md border px-3 py-2 text-left text-sm transition ${
                    activeOcrId === result.id
                      ? "border-emerald-700 bg-emerald-50 text-emerald-900"
                      : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                  }`}
                  key={result.id}
                  onClick={() => {
                    setActiveOcrId(result.id);
                    setCorrectedData(
                      defaultCorrectedData(document?.document_type ?? "supporting_document", result)
                    );
                  }}
                  type="button"
                >
                  <span className="font-semibold">
                    {labelForDocument(document?.document_type ?? "supporting_document")}
                  </span>
                  <span className="mt-1 block text-xs">
                    {result.verified_by_user ? "Verified" : "Needs checking"}
                  </span>
                </button>
              );
            })}
            <button
              className="btn-secondary"
              onClick={() => setStep("details")}
              type="button"
            >
              Continue to application details
            </button>
          </aside>

          {activeOcr ? (
            <div className="grid gap-5">
              <article className="panel-pad bg-slate-50">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <h3 className="font-semibold text-slate-950">
                    {labelForDocument(activeDocument?.document_type ?? "supporting_document")}
                  </h3>
                  <span className="rounded-md bg-white px-3 py-1 text-sm font-medium text-slate-700">
                    Confidence: {activeOcr.confidence_score ?? "N/A"}
                  </span>
                </div>
                <pre className="mt-4 max-h-56 overflow-auto whitespace-pre-wrap rounded-md bg-white p-4 text-sm leading-6 text-slate-700">
                  {activeOcr.extracted_text}
                </pre>
              </article>
              <article className="panel-pad">
                <h3 className="font-semibold text-slate-950">Correct extracted fields</h3>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  {Object.entries(correctedData).map(([key, value]) => (
                    <label className="block" key={key}>
                      <span className="text-sm font-medium text-slate-700">
                        {formatLabel(key)}
                      </span>
                      <input
                        className="mt-2 w-full px-3 py-2.5"
                        onChange={(event) =>
                          setCorrectedData((current) => ({
                            ...current,
                            [key]: event.target.value
                          }))
                        }
                        value={value}
                      />
                    </label>
                  ))}
                </div>
                <button
                  className="btn-primary mt-5 px-5 py-3"
                  disabled={isLoading || activeOcr.verified_by_user}
                  onClick={verifyOCR}
                  type="button"
                >
                  {activeOcr.verified_by_user ? "OCR data verified" : "Confirm OCR data"}
                </button>
              </article>
            </div>
          ) : (
            <Alert tone="info" message="Upload an image document to extract OCR data." />
          )}
        </section>
      ) : null}

      {step === "details" ? (
        <FinalDetailsForm
          emiSummary={emiSummary}
          form={form}
          isLoading={isLoading}
          onChange={updateField}
          onSave={() => saveFinalDetails({ submit: false })}
          onSubmit={() => saveFinalDetails({ submit: true })}
        />
      ) : null}

      {step === "done" ? (
        <section className="rounded-lg border border-emerald-200 bg-emerald-50 p-5">
          <h2 className="text-xl font-semibold text-emerald-950">Application submitted</h2>
          <p className="mt-2 text-sm leading-6 text-emerald-900">
            Your application is ready for loan officer review. Reference:{" "}
            <span className="font-semibold">{applicationId}</span>
          </p>
        </section>
      ) : null}
    </div>
  );
}

function FinalDetailsForm({
  emiSummary,
  form,
  isLoading,
  onChange,
  onSave,
  onSubmit
}: {
  emiSummary: EMISummary | null;
  form: FormState;
  isLoading: boolean;
  onChange: (name: FormField, value: string) => void;
  onSave: () => void;
  onSubmit: () => void;
}) {
  return (
    <section className="grid gap-5">
      <div>
        <h2 className="text-xl font-semibold text-slate-950">Complete application details</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          OCR-filled values can be edited before you submit.
        </p>
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <TextField label="Full name" name="full_name" onChange={onChange} value={form.full_name} />
        <TextField
          label="Citizenship number"
          name="citizenship_number"
          onChange={onChange}
          value={form.citizenship_number}
        />
        <TextField label="Phone" name="phone" onChange={onChange} type="tel" value={form.phone} />
        <TextField label="Address" name="address" onChange={onChange} value={form.address} />
        <TextField
          label="Monthly income"
          name="monthly_income"
          onChange={onChange}
          type="number"
          value={form.monthly_income}
        />
        <SelectField
          label="Employment type"
          name="employment_type"
          onChange={(_, value) => onChange("employment_type", value)}
          options={employmentOptions}
          value={form.employment_type}
        />
        <TextField
          label="Existing monthly debt"
          name="existing_monthly_debt"
          onChange={onChange}
          type="number"
          value={form.existing_monthly_debt}
        />
        <TextField
          label="Requested loan amount"
          name="requested_loan_amount"
          onChange={onChange}
          type="number"
          value={form.requested_loan_amount}
        />
        <TextField
          label="Annual interest rate (%)"
          name="annual_interest_rate"
          onChange={onChange}
          type="number"
          value={form.annual_interest_rate}
        />
        <TextField
          label="Loan tenure"
          name="loan_tenure"
          onChange={onChange}
          type="number"
          value={form.loan_tenure}
        />
        <SelectField
          label="Tenure unit"
          name="tenure_unit"
          onChange={(_, value) => onChange("tenure_unit", value)}
          options={tenureUnitOptions}
          value={form.tenure_unit}
        />
        <TextField
          label="Number of dependents"
          name="dependents"
          onChange={onChange}
          type="number"
          value={form.dependents}
        />
        <SelectField
          label="Savings buffer"
          name="savings_buffer"
          onChange={(_, value) => onChange("savings_buffer", value)}
          options={savingsOptions}
          value={form.savings_buffer}
        />
        <SelectField
          label="Repayment history"
          name="repayment_history"
          onChange={(_, value) => onChange("repayment_history", value)}
          options={repaymentOptions}
          value={form.repayment_history}
        />
      </div>
      <label className="block">
        <span className="text-sm font-medium text-slate-700">Loan purpose</span>
        <textarea
          className="mt-2 min-h-28 w-full px-3 py-2"
          maxLength={300}
          onChange={(event) => onChange("loan_purpose", event.target.value)}
          value={form.loan_purpose}
        />
      </label>
      <EMICard
        subtitle="Auto-calculated from your loan amount, interest rate and tenure."
        summary={emiSummary ?? {}}
      />
      <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
        <button
          className="btn-secondary px-5 py-3"
          disabled={isLoading}
          onClick={onSave}
          type="button"
        >
          Save draft
        </button>
        <button
          className="btn-primary px-5 py-3"
          disabled={isLoading}
          onClick={onSubmit}
          type="button"
        >
          Submit application
        </button>
      </div>
    </section>
  );
}

function StepTabs({
  applicationStarted,
  onSelect,
  step
}: {
  applicationStarted: boolean;
  onSelect: (step: Step) => void;
  step: Step;
}) {
  const steps: Array<{ value: Step; label: string; needsDraft?: boolean }> = [
    { value: "loan", label: "Loan type" },
    { value: "documents", label: "Documents", needsDraft: true },
    { value: "verify", label: "OCR check", needsDraft: true },
    { value: "details", label: "Application", needsDraft: true }
  ];

  return (
    <div className="flex flex-wrap gap-2">
      {steps.map((item) => (
        <button
          className={`rounded-md px-3 py-2 text-sm font-semibold transition ${
            step === item.value
              ? "bg-emerald-700 text-white"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          } disabled:cursor-not-allowed disabled:opacity-50`}
          disabled={item.needsDraft && !applicationStarted}
          key={item.value}
          onClick={() => onSelect(item.value)}
          type="button"
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

function DocumentChecklist({
  missingRequiredDocuments,
  uploadedDocuments
}: {
  missingRequiredDocuments: Array<{ value: DocumentType; label: string; required: boolean }>;
  uploadedDocuments: UploadedDocument[];
}) {
  return (
    <aside className="panel-pad bg-slate-50">
      <h2 className="text-lg font-semibold text-slate-950">Document checklist</h2>
      <div className="mt-4 grid gap-2">
        {documentOptions.map((option) => {
          const uploaded = uploadedDocuments.find(
            (document) => document.document_type === option.value
          );
          return (
            <div
              className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
              key={option.value}
            >
              <p className="font-semibold text-slate-800">{option.label}</p>
              <p className="mt-1 text-xs text-slate-500">
                {uploaded ? uploaded.filename : option.required ? "Required" : "Optional"}
              </p>
            </div>
          );
        })}
      </div>
      {missingRequiredDocuments.length > 0 ? (
        <p className="mt-4 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Missing: {missingRequiredDocuments.map((item) => item.label).join(", ")}
        </p>
      ) : (
        <p className="mt-4 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          Required documents uploaded in this session.
        </p>
      )}
    </aside>
  );
}

function TextField({
  label,
  name,
  onChange,
  type = "text",
  value
}: {
  label: string;
  name: FormField;
  onChange: (name: FormField, value: string) => void;
  type?: "text" | "tel" | "number";
  value: string;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input
        className="mt-2 w-full px-3 py-2.5"
        min={type === "number" ? 0 : undefined}
        onChange={(event) => onChange(name, event.target.value)}
        type={type}
        value={value}
      />
    </label>
  );
}

function SelectField({
  label,
  name,
  onChange,
  options,
  value
}: {
  label: string;
  name: string;
  onChange: (name: FormField | string, value: string) => void;
  options: Array<{ value: string; label: string }>;
  value: string;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <select
        className="mt-2 w-full px-3 py-2.5"
        onChange={(event) => onChange(name, event.target.value)}
        value={value}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function Alert({ message, tone }: { message: string; tone: "error" | "success" | "info" }) {
  const styles = {
    error: "alert-error",
    success: "alert-success",
    info: "alert-info"
  };

  return (
    <p className={styles[tone]}>
      {message}
    </p>
  );
}

function applicationPayload(form: FormState) {
  return {
    full_name: form.full_name.trim(),
    citizenship_number: form.citizenship_number.trim(),
    phone: form.phone.trim(),
    address: form.address.trim(),
    loan_type: form.loan_type,
    monthly_income: Number(form.monthly_income),
    employment_type: form.employment_type,
    existing_monthly_debt: Number(form.existing_monthly_debt),
    requested_loan_amount: Number(form.requested_loan_amount),
    // Backend keeps loan_duration_months as the canonical installment count (N),
    // derived here from the tenure + unit the customer entered.
    loan_duration_months: tenureToMonths(form.loan_tenure, form.tenure_unit),
    annual_interest_rate: Number(form.annual_interest_rate),
    loan_tenure: Number(form.loan_tenure),
    tenure_unit: form.tenure_unit,
    loan_purpose: form.loan_purpose.trim(),
    dependents: Number(form.dependents),
    savings_buffer: form.savings_buffer,
    repayment_history: form.repayment_history
  };
}

function defaultCorrectedData(documentType: DocumentType, result: OCRResult) {
  const existing = Object.fromEntries(
    Object.entries(result.corrected_data ?? {}).map(([key, value]) => [
      key,
      value == null ? "" : String(value)
    ])
  );
  const keysByDocumentType: Record<DocumentType, string[]> = {
    citizenship_document: ["full_name", "citizenship_number", "address"],
    salary_slip: ["employee_name", "monthly_income", "employer_name"],
    bank_statement: ["account_holder_name", "bank_name", "account_number"],
    supporting_document: ["document_date"]
  };
  const suggested = extractSuggestedData(documentType, result.extracted_text);

  return Object.fromEntries(
    keysByDocumentType[documentType].map((key) => [
      key,
      existing[key] ?? suggested[key] ?? ""
    ])
  );
}

function extractSuggestedData(
  documentType: DocumentType,
  extractedText: string
): Record<string, string> {
  const normalizedText = extractedText.replace(/\s+/g, " ").trim();
  if (documentType === "salary_slip") {
    const monthlyIncome =
      matchFirst(
        normalizedText,
        /(?:NET\s*SALARY|NETSALARY|SALARY\s*\(GROSS\)\s*\/\s*PM|GROSS\s*SALARY)\s*(?:Rs\.?|NPR)?\s*([0-9][0-9,]*(?:\.\d+)?)/i
      ) ||
      matchFirst(
        normalizedText,
        /(?:Basic|SalaryHead)\s*(?:Rs\.?|NPR)?\s*([0-9][0-9,]*(?:\.\d+)?)/i
      );
    const employerName = matchFirst(
      normalizedText,
      /^(.{3,100}?)\s+Salary\s+Slip(?:\s+for)?\b/i
    );
    const employeeName = matchFirst(
      normalizedText,
      /Employee\s+Name\s*:?\s*([A-Z][A-Z .'-]+?)(?=\s+Date\b|\s+Designation\b|\s+Month\b|$)/i
    );

    return {
      monthly_income: numericText(monthlyIncome),
      employer_name: cleanName(employerName),
      employee_name: cleanName(employeeName)
    };
  }

  if (documentType === "bank_statement") {
    const bankName =
      matchFirst(normalizedText, /^(.{3,80}?Bank)(?=\s|$)/i) ||
      matchFirst(normalizedText, /^(.{3,80}?Bank.{0,40}?)(?:\s+P\.?O\.?\s+Box|\s+[A-Z][a-z]+,|\s+Your)/i) ||
      matchFirst(normalizedText, /(Royal\s+Bank\s+of\s+Canada)/i);
    const accountNumber = matchFirst(
      normalizedText,
      /(?:account\s+number|account\s+no\.?)\s*:?\s*([0-9-]{5,})/i
    );
    const accountHolderName =
      matchFirst(
        normalizedText,
        /Account\s+Name\s*[\[:\-]?\s*([A-Z][A-Z .'-]+?)(?=\s+Opening\s+Balance|\s+Account\s+Number|\s+Closing\s+Balance|$)/i
      ) ||
      matchFirst(
        normalizedText,
        /(?:Toronto,\s*ON\s+[A-Z0-9 ]+\s+|^)([A-Z][A-Z .'-]{2,60}?)\s+\d{2,}/i
      );

    return {
      account_holder_name: cleanName(accountHolderName),
      bank_name: cleanName(bankName),
      account_number: accountNumber
    };
  }

  if (documentType !== "citizenship_document") {
    return {};
  }

  const citizenshipNumber = matchFirst(
    normalizedText,
    /Citizenship\s+Certificate\s+No\.?\s*:?\s*([A-Za-z0-9/-]+)/i
  );
  const fullName = matchFirst(
    normalizedText,
    /Full\s+Name\.?\s*:?\s*([A-Z][A-Z .'’-]+?)(?=\s+Date\s+of\s+Birth|\s+DOB|\s+Birth\s+Place|$)/i
  );
  const permanentAddress = matchFirst(
    normalizedText,
    /Permanent\s+Address\s*:?\s*(.+?)(?=\s+[A-Z]{2,}\s+Arar|\s+Government\s+of\s+Nepal|$)/i
  );

  return {
    citizenship_number: citizenshipNumber,
    full_name: fullName,
    address: permanentAddress
  };
}

function classifyAffordability(dtiRatio: number) {
  if (dtiRatio <= 35) return "Affordable";
  if (dtiRatio <= 50) return "Moderate";
  return "High Risk";
}

function matchFirst(text: string, pattern: RegExp) {
  return text.match(pattern)?.[1]?.trim() ?? "";
}

function numericText(value: string | undefined) {
  if (!value) {
    return "";
  }

  return value.replace(/,/g, "").match(/\d+(?:\.\d+)?/)?.[0] ?? "";
}

function cleanName(value: string | undefined) {
  if (!value) {
    return "";
  }

  return value.replace(/\s+/g, " ").replace(/[|_]+/g, " ").trim();
}

function labelForDocument(documentType: DocumentType) {
  return (
    documentOptions.find((option) => option.value === documentType)?.label ??
    "Uploaded document"
  );
}

function formatLabel(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function valueToInput(value: number | string | null | undefined, fallback: string) {
  if (value === null || value === undefined) {
    return fallback;
  }
  return String(value);
}

function isUploadedForCurrentRequest(
  document: UploadedDocument,
  documentRequest: DocumentRequest
) {
  return new Date(document.uploaded_at).getTime() >= new Date(documentRequest.created_at).getTime();
}
