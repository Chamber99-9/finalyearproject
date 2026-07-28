import { Suspense } from "react";

import { AppShell } from "@/components/AppShell";
import { LoanApplicationForm } from "@/components/LoanApplicationForm";

export default function NewApplicationPage() {
  return (
    <AppShell>
      <section className="mx-auto max-w-5xl px-5 py-10 sm:px-6 lg:py-14">
        <div className="panel-pad p-6 sm:p-8">
          <p className="eyebrow">
            Customer application
          </p>
          <h1 className="mt-3 text-3xl font-bold text-slate-950 sm:text-4xl">
            Apply for a loan
          </h1>
          <Suspense
            fallback={
              <p className="alert-info mt-8">
                Loading application flow...
              </p>
            }
          >
            <LoanApplicationForm />
          </Suspense>
        </div>
      </section>
    </AppShell>
  );
}
