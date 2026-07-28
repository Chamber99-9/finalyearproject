export type ApplicationStatus =
  | "draft"
  | "submitted"
  | "under_review"
  | "document_requested"
  | "counter_offered"
  | "approved"
  | "rejected";

export type LoanApplication = {
  id: string;
  applicant_id: string;
  full_name?: string | null;
  citizenship_number?: string | null;
  phone?: string | null;
  address?: string | null;
  loan_type: string;
  monthly_income?: number | null;
  employment_type?: string | null;
  existing_monthly_debt?: number | null;
  requested_loan_amount?: number | null;
  loan_duration_months?: number | null;
  // Bank-defined rate applied to this application + auto-calculated EMI outputs.
  interest_rate_used?: number | null;
  loan_tenure?: number | null;
  tenure_unit?: string | null;
  monthly_emi?: number | null;
  total_interest?: number | null;
  total_payment?: number | null;
  emi_dti_ratio?: number | null;
  affordability?: string | null;
  pan_number?: string | null;
  collateral_type?: string | null;
  collateral_value?: number | null;
  collateral_description?: string | null;
  verification?: Record<string, boolean> | null;
  loan_purpose?: string | null;
  dependents?: number | null;
  savings_buffer?: string | null;
  repayment_history?: string | null;
  offered_loan_amount?: number | null;
  offer_message?: string | null;
  offer_status?: string | null;
  status: ApplicationStatus;
  created_at: string;
  updated_at: string;
};

export type UploadedDocument = {
  id: string;
  application_id: string;
  user_id: string;
  document_type: string;
  filename: string;
  content_type: string;
  uploaded_at: string;
};

export type OCRResult = {
  id: string;
  document_id: string;
  application_id: string;
  extracted_text: string;
  confidence_score: number | null;
  verified_by_user: boolean;
  corrected_data: Record<string, unknown>;
  created_at: string;
};

export type CreditRiskScore = {
  application_id: string;
  score_type: string;
  raw_score: number;
  normalized_score: number;
  risk_level: string;
  dti_ratio: number;
  lti_ratio: number;
  monthly_emi?: number | null;
  affordability?: string | null;
  score_breakdown: Record<string, number>;
  repayment_history_used: string;
  repayment_history_score: number;
  scoring_model_version: string;
  disclaimer: string;
  created_at: string;
};

export type SuspiciousFlag = {
  code: string;
  message: string;
  severity: string;
};

export type SuspiciousFlags = {
  application_id: string;
  total_flags: number;
  suspicion_level: string;
  flags: SuspiciousFlag[];
};

export type OfficerApplicationDetail = {
  application: LoanApplication;
  documents: UploadedDocument[];
  ocr_results: OCRResult[];
  credit_risk_score: CreditRiskScore | null;
  suspicious_flags: SuspiciousFlags | null;
};

export const statusOptions: Array<{ value: "all" | ApplicationStatus; label: string }> = [
  { value: "all", label: "All statuses" },
  { value: "submitted", label: "Submitted" },
  { value: "under_review", label: "Under review" },
  { value: "document_requested", label: "Document requested" },
  { value: "counter_offered", label: "Counter offered" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" }
];

export const requestDocumentOptions = [
  { value: "citizenship_document", label: "Citizenship document" },
  { value: "salary_slip", label: "Salary slip" },
  { value: "bank_statement", label: "Bank statement" },
  { value: "supporting_document", label: "Supporting document" }
];

export function formatLabel(value?: string | null) {
  if (!value) {
    return "N/A";
  }

  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function formatMoney(value?: number | null) {
  if (typeof value !== "number") {
    return "N/A";
  }

  return new Intl.NumberFormat("en-NP", {
    maximumFractionDigits: 0,
    style: "currency",
    currency: "NPR"
  }).format(value);
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-NP", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}
