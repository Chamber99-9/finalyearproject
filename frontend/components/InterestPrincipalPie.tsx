"use client";

import { formatMoney } from "@/lib/officer";

/**
 * Dependency-free SVG donut chart showing principal vs total interest.
 * No charting library is added to the project — this keeps the bundle small
 * and portable.
 */
export function InterestPrincipalPie({
  principal,
  interest
}: {
  principal: number;
  interest: number;
}) {
  const total = principal + interest;
  if (!(total > 0)) return null;

  const principalPct = (principal / total) * 100;
  const interestPct = 100 - principalPct;

  const radius = 60;
  const circumference = 2 * Math.PI * radius;
  const principalLen = (principalPct / 100) * circumference;
  const interestLen = circumference - principalLen;

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center">
      <svg viewBox="0 0 160 160" className="h-40 w-40 -rotate-90">
        <circle cx="80" cy="80" r={radius} fill="none" stroke="#e2e8f0" strokeWidth="20" />
        <circle
          cx="80"
          cy="80"
          r={radius}
          fill="none"
          stroke="#047857"
          strokeWidth="20"
          strokeDasharray={`${principalLen} ${circumference}`}
        />
        <circle
          cx="80"
          cy="80"
          r={radius}
          fill="none"
          stroke="#f59e0b"
          strokeWidth="20"
          strokeDasharray={`${interestLen} ${circumference}`}
          strokeDashoffset={-principalLen}
        />
      </svg>
      <div className="grid gap-2">
        <LegendRow
          color="#047857"
          label="Principal"
          value={formatMoney(principal)}
          pct={principalPct}
        />
        <LegendRow
          color="#f59e0b"
          label="Total interest"
          value={formatMoney(interest)}
          pct={interestPct}
        />
        <div className="mt-1 border-t border-slate-200 pt-2 text-sm">
          <span className="text-slate-600">Total repayment: </span>
          <span className="font-semibold text-slate-950">{formatMoney(total)}</span>
        </div>
      </div>
    </div>
  );
}

function LegendRow({
  color,
  label,
  value,
  pct
}: {
  color: string;
  label: string;
  value: string;
  pct: number;
}) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span
        className="inline-block h-3 w-3 rounded-sm"
        style={{ backgroundColor: color }}
        aria-hidden="true"
      />
      <span className="text-slate-600">{label}</span>
      <span className="font-semibold text-slate-950">{value}</span>
      <span className="text-slate-500">({pct.toFixed(1)}%)</span>
    </div>
  );
}
