export type LoanTypeInfo = {
  loan_type: string;
  label: string;
  base_rate: number;
  type_spread: number;
  indicative_rate: number;
  requires_collateral_above: number | null;
  max_tenure_years: number;
};

export type RateQuote = {
  loan_type: string;
  base_rate: number;
  type_spread: number;
  tenure_adjustment: number;
  effective_rate: number;
};

export type Eligibility = {
  loan_type: string;
  monthly_income: number;
  requested_amount: number;
  max_amount: number;
  within_cap: boolean;
  min_amount: number;
  meets_minimum: boolean;
  requires_collateral: boolean;
  collateral_threshold: number;
  instant_cap: number | null;
};

export type PanCheck = {
  pan_number: string;
  valid_format: boolean;
  tax_registered: boolean;
  reason: string;
};

export type LoanAccount = {
  id: string;
  application_id: string;
  principal: number;
  interest_rate: number;
  tenure_months: number;
  monthly_emi: number;
  total_payment: number;
  total_interest: number;
  outstanding_balance: number;
  installments_paid: number;
  installments_total: number;
  missed_installments: number;
  penalty_due?: number;
  next_due_date: string | null;
  status: string;
};

export type EMIScheduleRow = {
  month: number;
  emi: number;
  principalPaid: number;
  interestPaid: number;
  remainingBalance: number;
};

/** Convert tenure + unit into a month count (matches the backend). */
export function tenureToMonths(tenure: number, unit: string): number {
  if (!Number.isFinite(tenure) || tenure <= 0) return 0;
  return unit === "years" ? Math.round(tenure * 12) : Math.round(tenure);
}

/**
 * Build the amortization schedule client-side for the live preview, mirroring
 * the backend engine: interest on the running balance, principal = EMI - interest,
 * final month clears any rounding remainder.
 */
export function buildSchedule(
  loanAmount: number,
  annualRate: number,
  months: number,
  monthlyEmi: number
): EMIScheduleRow[] {
  const monthlyRate = annualRate / 12 / 100;
  const rows: EMIScheduleRow[] = [];
  let balance = loanAmount;
  for (let month = 1; month <= months; month += 1) {
    const interestPaid = Math.round(balance * monthlyRate * 100) / 100;
    let principalPaid = Math.round((monthlyEmi - interestPaid) * 100) / 100;
    let emi = monthlyEmi;
    if (month === months) {
      principalPaid = Math.round(balance * 100) / 100;
      emi = Math.round((principalPaid + interestPaid) * 100) / 100;
    }
    balance = Math.round((balance - principalPaid) * 100) / 100;
    if (balance < 0) balance = 0;
    rows.push({ month, emi, principalPaid, interestPaid, remainingBalance: balance });
  }
  return rows;
}
