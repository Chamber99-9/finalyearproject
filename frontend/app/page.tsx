import Link from "next/link";

import { AppShell } from "@/components/AppShell";

const outcomes = [
  "Reduce repeated branch visits",
  "Digitize document-heavy loan workflows",
  "Support faster officer review",
  "Keep audit-ready application activity"
];

const processSteps = [
  {
    title: "Create account",
    description: "Customers register and start a secure online loan application."
  },
  {
    title: "Submit details",
    description: "Applicant, income, employment, loan amount, and repayment details are captured."
  },
  {
    title: "Upload documents",
    description: "Citizenship, salary slip, bank statement, and supporting files are prepared for review."
  },
  {
    title: "Verify and review",
    description: "OCR output, risk score, and suspicious flags help officers make the final decision."
  }
];

const features = [
  {
    title: "Online loan application",
    description: "A responsive form flow for collecting customer and financial information."
  },
  {
    title: "Document upload",
    description: "A planned upload workflow for citizenship, income, and bank documents."
  },
  {
    title: "OCR verification",
    description: "Tesseract OCR will extract document details for customer confirmation."
  },
  {
    title: "Credit risk scoring",
    description: "Rule-based scoring will support, not replace, officer decision-making."
  },
  {
    title: "Suspicious application flagging",
    description: "Mismatch and duplicate checks will highlight applications needing closer review."
  },
  {
    title: "Officer dashboard",
    description: "A dedicated workspace for reviewing applications, documents, scores, and status."
  }
];

export default function Home() {
  return (
    <AppShell>
      <section className="border-b border-slate-200 bg-white">
        <div className="mx-auto grid max-w-7xl gap-10 px-5 py-14 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:py-20">
          <div>
            <p className="eyebrow">
              Digital Loan Origination System
            </p>
            <h1 className="mt-4 max-w-4xl text-4xl font-bold leading-tight text-slate-950 sm:text-6xl">
              A simpler way to apply, verify, and review loans online
            </h1>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-700">
              Sajilo Loan helps Nepal's banks, cooperatives, and finance companies move
              loan applications from paper-heavy branch workflows to a secure digital
              review process.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link
                className="btn-primary px-5 py-3"
                href="/register"
              >
                Apply for Loan
              </Link>
              <Link
                className="btn-secondary px-5 py-3"
                href="/login"
              >
                Login
              </Link>
            </div>
          </div>

          <div className="panel-pad bg-slate-50">
            <div className="rounded-md bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between gap-4 border-b border-slate-200 pb-4">
                <div>
                  <p className="text-sm font-medium text-slate-500">Application status</p>
                  <p className="mt-1 text-2xl font-bold text-slate-950">Track in dashboard</p>
                </div>
                <span className="rounded-md bg-emerald-100 px-3 py-2 text-sm font-semibold text-emerald-800">
                  Live after login
                </span>
              </div>
              <p className="mt-5 text-sm leading-6 text-slate-700">
                Customers can view real application status, continue drafts, upload
                documents, and follow officer decisions from the dashboard after login.
              </p>
              <Link
                className="btn-primary mt-5 inline-flex px-4 py-2.5"
                href="/dashboard/customer"
              >
                View my status
              </Link>
              <div className="mt-5 space-y-3">
                {outcomes.map((item) => (
                  <p key={item} className="rounded-md border border-slate-100 bg-slate-50 px-4 py-3 text-sm text-slate-700">
                    {item}
                  </p>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-14 sm:px-6">
        <div className="max-w-3xl">
          <p className="eyebrow">
            What Sajilo Loan does
          </p>
          <h2 className="mt-3 text-3xl font-bold text-slate-950 sm:text-4xl">
            One digital workspace for customers, officers, and administrators
          </h2>
          <p className="mt-4 text-base leading-7 text-slate-700">
            The platform is designed to collect loan applications online, organize
            uploaded documents, support OCR-based verification, surface rule-based risk
            insights, and keep status updates visible throughout the process.
          </p>
        </div>
      </section>

      <section id="process" className="border-y border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-5 py-14 sm:px-6">
          <div className="max-w-3xl">
            <p className="eyebrow">
              Online loan process
            </p>
            <h2 className="mt-3 text-3xl font-bold text-slate-950 sm:text-4xl">
              From application to officer review
            </h2>
          </div>
          <div className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {processSteps.map((step, index) => (
              <article key={step.title} className="panel-pad">
                <span className="flex h-10 w-10 items-center justify-center rounded-md bg-emerald-700 text-sm font-bold text-white">
                  {index + 1}
                </span>
                <h3 className="mt-5 text-lg font-semibold text-slate-950">{step.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-700">{step.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="features" className="mx-auto max-w-7xl px-5 py-14 sm:px-6">
        <div className="max-w-3xl">
          <p className="eyebrow">
            Features
          </p>
          <h2 className="mt-3 text-3xl font-bold text-slate-950 sm:text-4xl">
            Built for practical loan origination workflows
          </h2>
        </div>
        <div className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <article key={feature.title} className="panel-pad">
              <h3 className="text-lg font-semibold text-slate-950">{feature.title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-700">{feature.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-col gap-6 px-5 py-12 text-white sm:px-6 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-emerald-300">
              Ready when backend integration begins
            </p>
            <h2 className="mt-3 text-3xl font-bold">Start the digital loan journey</h2>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Link
              className="inline-flex items-center justify-center rounded-md bg-emerald-500 px-5 py-3 text-center font-semibold text-slate-950 transition hover:bg-emerald-400"
              href="/register"
            >
              Apply for Loan
            </Link>
            <Link
              className="inline-flex items-center justify-center rounded-md border border-slate-600 px-5 py-3 text-center font-semibold text-white transition hover:bg-slate-800"
              href="/login"
            >
              Login
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-5 py-6 text-sm text-slate-600 sm:px-6 md:flex-row md:items-center md:justify-between">
          <p>© 2026 Sajilo Loan. Digital loan origination starter.</p>
          <p>Frontend only. Backend integration is not connected yet.</p>
        </div>
      </footer>
    </AppShell>
  );
}
