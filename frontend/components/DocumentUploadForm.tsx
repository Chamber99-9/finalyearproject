"use client";

import { useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";

type DocumentType =
  | "citizenship_document"
  | "salary_slip"
  | "bank_statement"
  | "supporting_document";

type UploadedDocument = {
  id: string;
  document_type: DocumentType;
  filename: string;
  content_type: string;
  uploaded_at: string;
};

type ApplicationResponse = {
  status?: string | null;
};

type DocumentRequest = {
  id: string;
  document_types: DocumentType[];
  message?: string | null;
  created_at: string;
};

const documentOptions: Array<{
  value: DocumentType;
  label: string;
  required: boolean;
}> = [
  { value: "citizenship_document", label: "Citizenship document", required: true },
  { value: "salary_slip", label: "Salary slip", required: true },
  { value: "bank_statement", label: "Bank statement", required: true },
  { value: "supporting_document", label: "Optional supporting document", required: false }
];
const maxUploadBytes = 10 * 1024 * 1024;

export function DocumentUploadForm() {
  const searchParams = useSearchParams();
  const [applicationId, setApplicationId] = useState(
    searchParams.get("applicationId") ?? ""
  );
  const [documentType, setDocumentType] = useState<DocumentType>("citizenship_document");
  const [file, setFile] = useState<File | null>(null);
  const [fileInputVersion, setFileInputVersion] = useState(0);
  const [uploadedDocuments, setUploadedDocuments] = useState<UploadedDocument[]>([]);
  const [documentRequest, setDocumentRequest] = useState<DocumentRequest | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

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
    const trimmedApplicationId = applicationId.trim();
    if (trimmedApplicationId.length !== 24) {
      setUploadedDocuments([]);
      return;
    }

    let isCurrent = true;

    async function loadSavedDocuments() {
      setError("");

      try {
        const [documentsResponse, requestResponse] = await Promise.all([
          fetch(`/api/applications/${encodeURIComponent(trimmedApplicationId)}/documents`),
          fetch(`/api/applications/${encodeURIComponent(trimmedApplicationId)}/document-request`)
        ]);
        const documentsPayload = await documentsResponse.json().catch(() => ({}));
        const requestPayload = await requestResponse.json().catch(() => ({}));

        if (!isCurrent) {
          return;
        }

        if (!documentsResponse.ok) {
          setError(documentsPayload.error ?? "Could not load uploaded documents.");
          setUploadedDocuments([]);
          return;
        }
        if (!requestResponse.ok) {
          setError(requestPayload.error ?? "Could not load document request.");
          setDocumentRequest(null);
          return;
        }

        const latestRequest = requestPayload.document_request ?? null;
        setUploadedDocuments(documentsPayload.documents ?? []);
        setDocumentRequest(latestRequest);
        if (
          latestRequest?.document_types?.length &&
          !latestRequest.document_types.includes(documentType)
        ) {
          setDocumentType(latestRequest.document_types[0]);
        }
      } catch {
        if (isCurrent) {
          setError("Could not reach the document service.");
        }
      }
    }

    loadSavedDocuments();

    return () => {
      isCurrent = false;
    };
  }, [applicationId, documentType]);

  function isDocumentTypeAllowed(type: DocumentType) {
    if (!documentRequest) {
      return true;
    }

    return documentRequest.document_types.includes(type);
  }

  function validateForm() {
    if (!applicationId.trim()) {
      return "Application id is required.";
    }

    if (!file) {
      return "Choose a file to upload.";
    }
    if (!isDocumentTypeAllowed(documentType)) {
      return "You can only upload the document requested by the loan officer.";
    }

    if (file.size === 0) {
      return "Selected file cannot be empty.";
    }

    if (file.size > maxUploadBytes) {
      return "Selected file must be 10 MB or smaller.";
    }

    const allowedTypes = ["application/pdf", "image/jpeg", "image/png", "image/webp"];
    if (!allowedTypes.includes(file.type)) {
      return "Upload a PDF, JPEG, PNG, or WebP file.";
    }

    return "";
  }

  async function getUploadPermission() {
    const response = await fetch(`/api/applications/${encodeURIComponent(applicationId.trim())}`);
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      return payload.error ?? "Could not verify this application.";
    }

    const application = payload.application as ApplicationResponse | undefined;
    if (!["draft", "document_requested"].includes(application?.status ?? "")) {
      return "Documents can only be uploaded for drafts or when an officer requests additional documents.";
    }

    return "";
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSuccess("");

    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    if (!file) {
      return;
    }

    setIsLoading(true);

    try {
      const permissionError = await getUploadPermission();
      if (permissionError) {
        setError(permissionError);
        return;
      }

      const formData = new FormData();
      formData.append("document_type", documentType);
      formData.append("file", file);

      const response = await fetch(
        `/api/applications/${encodeURIComponent(applicationId.trim())}/documents`,
        {
          method: "POST",
          body: formData
        }
      );

      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(payload.error ?? "Could not upload document.");
        return;
      }

      const uploaded = payload.document as UploadedDocument | undefined;
      if (!uploaded) {
        setError("Upload succeeded, but no document metadata was returned.");
        return;
      }

      const updatedDocuments = [
        uploaded,
        ...uploadedDocuments.filter((document) => document.id !== uploaded.id)
      ];
      setUploadedDocuments(updatedDocuments);
      const updatedUploadedTypes = new Set(
        updatedDocuments
          .filter((document) =>
            documentRequest ? isUploadedForCurrentRequest(document, documentRequest) : true
          )
          .map((document) => document.document_type)
      );
      const remainingRequestedDocuments =
        documentRequest?.document_types.filter((type) => !updatedUploadedTypes.has(type)) ?? [];
      setSuccess(
        remainingRequestedDocuments.length > 0
          ? `${labelForDocument(uploaded.document_type)} uploaded. Still needed: ${remainingRequestedDocuments
              .map(labelForDocument)
              .join(", ")}.`
          : `${labelForDocument(uploaded.document_type)} uploaded successfully. All requested documents are uploaded.`
      );
      setFile(null);
      setFileInputVersion((current) => current + 1);
      if (remainingRequestedDocuments.length > 0) {
        setDocumentType(remainingRequestedDocuments[0]);
      }
    } catch {
      setError("Could not reach the upload service. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_360px]">
      <form className="grid gap-5" onSubmit={handleSubmit}>
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

        <label className="block">
          <span className="text-sm font-medium text-slate-700">Application id</span>
          <input
            className="mt-2 w-full px-3 py-2.5"
            onChange={(event) => setApplicationId(event.target.value)}
            placeholder="Paste your application id"
            required
            value={applicationId}
          />
        </label>

        <label className="block">
          <span className="text-sm font-medium text-slate-700">Document type</span>
          <select
            className="mt-2 w-full px-3 py-2.5"
            onChange={(event) => setDocumentType(event.target.value as DocumentType)}
            value={documentType}
          >
            {documentOptions.map((option) => (
              <option
                disabled={!isDocumentTypeAllowed(option.value)}
                key={option.value}
                value={option.value}
              >
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-sm font-medium text-slate-700">File</span>
          <input
            accept="application/pdf,image/jpeg,image/png,image/webp"
            className="mt-2 w-full px-3 py-2 text-sm file:mr-4 file:rounded-md file:border-0 file:bg-emerald-700 file:px-4 file:py-2 file:font-semibold file:text-white"
            key={fileInputVersion}
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            required
            type="file"
          />
        </label>

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

        <button
          className="btn-primary px-5 py-3"
          disabled={isLoading}
          type="submit"
        >
          {isLoading ? "Uploading document..." : "Upload document"}
        </button>
      </form>

      <aside className="panel-pad bg-slate-50">
        <h2 className="text-lg font-semibold text-slate-950">Uploaded documents</h2>
        <div className="mt-4 space-y-3">
          {uploadedDocuments.length > 0 ? (
            uploadedDocuments.map((document) => (
              <article
                className="rounded-md border border-slate-200 bg-white p-4"
                key={document.id}
              >
                <p className="font-semibold text-slate-950">
                  {labelForDocument(document.document_type)}
                </p>
                <p className="mt-1 break-words text-sm text-slate-600">{document.filename}</p>
                <p className="mt-2 text-xs text-slate-500">
                  {new Date(document.uploaded_at).toLocaleString()}
                </p>
              </article>
            ))
          ) : (
            <p className="text-sm leading-6 text-slate-600">
              Uploaded documents will appear here after each successful upload.
            </p>
          )}
        </div>

        <div className="mt-6 border-t border-slate-200 pt-4">
          <p className="text-sm font-medium text-slate-700">Required documents</p>
          <ul className="mt-3 space-y-2 text-sm text-slate-600">
            {documentOptions.map((option) => (
              <li key={option.value}>
                {option.label}
                {option.required ? "" : " (optional)"}
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}

function labelForDocument(documentType: DocumentType) {
  return (
    documentOptions.find((option) => option.value === documentType)?.label ??
    "Uploaded document"
  );
}

function isUploadedForCurrentRequest(
  document: UploadedDocument,
  documentRequest: DocumentRequest
) {
  return new Date(document.uploaded_at).getTime() >= new Date(documentRequest.created_at).getTime();
}
