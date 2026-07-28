import { AppShell } from "@/components/AppShell";
import { OCRVerificationForm } from "@/components/OCRVerificationForm";

export default function OCRVerifyPage() {
  return (
    <AppShell>
      <section className="mx-auto max-w-6xl px-5 py-10 sm:px-6 lg:py-14">
        <div className="panel-pad p-6 sm:p-8">
          <p className="eyebrow">
            OCR verification
          </p>
          <h1 className="mt-3 text-3xl font-bold text-slate-950 sm:text-4xl">
            Review extracted document text
          </h1>
          <p className="mt-3 max-w-3xl text-base leading-7 text-slate-700">
            Load an OCR result, review the extracted text, add corrected data, and confirm
            the result for the application workflow.
          </p>
          <OCRVerificationForm />
        </div>
      </section>
    </AppShell>
  );
}
