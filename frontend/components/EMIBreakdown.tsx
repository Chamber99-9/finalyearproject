"use client";

import { useMemo, useState } from "react";

import { InterestPrincipalPie } from "@/components/InterestPrincipalPie";
import { buildSchedule } from "@/lib/loans";
import { formatMoney } from "@/lib/officer";

/**
 * Full EMI breakdown for a preview: interest-vs-principal pie chart plus the
 * month-by-month amortization schedule (EMI, principal, interest, remaining
 * balance). The schedule is computed client-side from the previewed figures.
 */
export function EMIBreakdown({
  loanAmount,
  annualRate,
  months,
  monthlyEmi,
  totalInterest,
  totalPayment
}: {
  loanAmount: number;
  annualRate: number;
  months: number;
  monthlyEmi: number;
  totalInterest: number;
  totalPayment: number;
}) {
  const [showAll, setShowAll] = useState(false);

  const schedule = useMemo(
    () => buildSchedule(loanAmount, annualRate, months, monthlyEmi),
    [loanAmount, annualRate, months, monthlyEmi]
  );

  if (!(months > 0) || !(monthlyEmi > 0)) return null;

  const visibleRows = showAll ? schedule : schedule.slice(0, 12);

  return (
    <section className="panel-pad">
      <h3 className="text-lg font-semibold text-slate-950">Repayment breakdown</h3>
      <p className="mt-1 text-sm text-slate-600">
        {months} monthly installments at {annualRate}% p.a. — where your money goes.
      </p>

      <div className="mt-4">
        <InterestPrincipalPie principal={loanAmount} interest={totalInterest} />
      </div>

      <div className="mt-5 overflow-hidden rounded-lg border border-slate-200">
        <div className="max-h-80 overflow-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="sticky top-0 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
              <tr>
                <th className="px-3 py-2">Month</th>
                <th className="px-3 py-2">EMI</th>
                <th className="px-3 py-2">Principal</th>
                <th className="px-3 py-2">Interest</th>
                <th className="px-3 py-2">Balance</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {visibleRows.map((row) => (
                <tr key={row.month}>
                  <td className="px-3 py-2 text-slate-600">{row.month}</td>
                  <td className="px-3 py-2 text-slate-950">{formatMoney(row.emi)}</td>
                  <td className="px-3 py-2 text-emerald-700">{formatMoney(row.principalPaid)}</td>
                  <td className="px-3 py-2 text-amber-700">{formatMoney(row.interestPaid)}</td>
                  <td className="px-3 py-2 text-slate-600">{formatMoney(row.remainingBalance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {schedule.length > 12 ? (
        <button
          className="btn-secondary mt-3 px-4 py-2 text-sm"
          onClick={() => setShowAll((current) => !current)}
          type="button"
        >
          {showAll ? "Show first 12 months" : `Show full schedule (${schedule.length} months)`}
        </button>
      ) : null}

      <p className="mt-3 text-xs text-slate-500">
        Total repayment {formatMoney(totalPayment)} = principal {formatMoney(loanAmount)} +
        interest {formatMoney(totalInterest)}.
      </p>
    </section>
  );
}
