"use client";

import { formatMoney } from "@/lib/officer";

/**
 * Reusable EMI summary card (requirement #13).
 *
 * Displays Monthly EMI, Total Interest, Total Payment and the Affordability
 * status. The project does not ship shadcn/ui, so this mirrors the existing
 * Tailwind card pattern used across the app (`panel-pad`, status pills, etc.)
 * to stay consistent with the current architecture (requirement #15).
 *
 * It is presentational only — callers pass already-calculated values (from
 * POST /emi/calculate or from a stored application document).
 */

export type EMISummary = {
  monthly_emi?: number | null;
  total_interest?: number | null;
  total_payment?: number | null;
  affordability?: string | null;
  dti_ratio?: number | null;
  interest_rate?: number | null;
};

type EMICardProps = {
  summary: EMISummary;
  /** Optional heading override. */
  title?: string;
  /** Optional context line rendered under the title (e.g. amount @ rate). */
  subtitle?: string;
  /** Shown instead of figures when there is nothing to display yet. */
  emptyMessage?: string;
};

export function EMICard({
  summary,
  title = "EMI summary",
  subtitle,
  emptyMessage = "Enter loan amount, interest rate and tenure to see your EMI."
}: EMICardProps) {
  const hasEMI = typeof summary.monthly_emi === "number";

  return (
    <section className="panel-pad">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-slate-950">{title}</h3>
          {subtitle ? (
            <p className="mt-1 text-sm text-slate-600">{subtitle}</p>
          ) : null}
        </div>
        {hasEMI && summary.affordability ? (
          <AffordabilityBadge affordability={summary.affordability} />
        ) : null}
      </div>

      {hasEMI ? (
        <>
          {typeof summary.interest_rate === "number" ? (
            <p className="mt-3 inline-flex rounded-md bg-emerald-50 px-3 py-1.5 text-sm font-medium text-emerald-800">
              Bank interest rate: {summary.interest_rate}% p.a.
            </p>
          ) : null}
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <Figure label="Monthly EMI" value={formatMoney(summary.monthly_emi)} emphasis />
            <Figure label="Total interest" value={formatMoney(summary.total_interest)} />
            <Figure label="Total repayment" value={formatMoney(summary.total_payment)} />
          </div>
          {typeof summary.dti_ratio === "number" ? (
            <p className="mt-3 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-700">
              Debt-to-income ratio (incl. this EMI):{" "}
              <span className="font-semibold text-slate-950">
                {summary.dti_ratio.toFixed(2)}%
              </span>
            </p>
          ) : null}
        </>
      ) : (
        <p className="mt-4 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600">
          {emptyMessage}
        </p>
      )}
    </section>
  );
}

function Figure({
  label,
  value,
  emphasis = false
}: {
  label: string;
  value: string;
  emphasis?: boolean;
}) {
  return (
    <div className="rounded-md bg-slate-50 p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </p>
      <p
        className={`mt-1 font-bold text-slate-950 ${
          emphasis ? "text-xl" : "text-lg"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

export function AffordabilityBadge({ affordability }: { affordability: string }) {
  const tone =
    affordability === "Affordable"
      ? "bg-emerald-100 text-emerald-800"
      : affordability === "Moderate"
        ? "bg-amber-100 text-amber-800"
        : "bg-red-100 text-red-700";

  return <span className={`status-pill ${tone}`}>{affordability}</span>;
}
