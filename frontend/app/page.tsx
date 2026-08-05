import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { API_BASE_URL, AUTH_COOKIE_NAME } from "@/app/api/auth/_utils";

/**
 * Public landing page. Intentionally minimal — it does not expose any
 * application internals, module names, or activity. It only introduces the
 * brand and funnels visitors to log in (or create an account). Everything
 * beyond this lives behind authentication.
 *
 * Logged-in visitors are sent straight to their dashboard, so clicking the
 * Sajilo Loan logo (which points here) never drops an authenticated user back
 * onto the public page or appears to log them out.
 */
export default async function Home() {
  const token = (await cookies()).get(AUTH_COOKIE_NAME)?.value;
  let authenticated = false;
  if (token) {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store"
      });
      authenticated = response.ok;
    } catch {
      // Backend unreachable — fall through and show the public landing.
    }
  }
  if (authenticated) {
    redirect("/dashboard");
  }

  return (
    <main className="min-h-screen bg-slate-100 text-slate-950">
      <header className="border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 sm:px-6">
          <div className="flex items-center gap-3 text-xl font-bold">
            <span className="flex h-10 w-10 items-center justify-center rounded-md bg-emerald-700 text-sm font-bold text-white shadow-sm">
              SL
            </span>
            <span>Sajilo Loan</span>
          </div>
          <div className="flex items-center gap-2">
            <Link
              className="rounded-md px-4 py-2 text-sm font-semibold text-slate-700 transition duration-200 hover:bg-emerald-50 hover:text-emerald-800"
              href="/login"
            >
              Login
            </Link>
            <Link
              className="btn-primary px-4 py-2 text-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-md"
              href="/register"
            >
              Create account
            </Link>
          </div>
        </div>
      </header>

      <section className="relative overflow-hidden">
        <div className="mx-auto grid max-w-6xl gap-10 px-5 py-20 sm:px-6 lg:grid-cols-[1.1fr_0.9fr] lg:items-center lg:py-28">
          <div className="animate-fade-in-up">
            <span className="inline-flex items-center rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-emerald-800">
              Borrow with confidence
            </span>
            <h1 className="mt-5 text-4xl font-bold leading-tight text-slate-950 sm:text-6xl">
              Loans made <span className="text-emerald-700">sajilo</span>.
            </h1>
            <p className="mt-5 max-w-xl text-lg leading-8 text-slate-700">
              Apply online, see your rate and monthly EMI instantly, and track everything
              in one place. Secure, simple, and built for you.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link
                className="btn-primary px-6 py-3 transition duration-200 hover:-translate-y-0.5 hover:shadow-lg"
                href="/login"
              >
                Login to continue
              </Link>
              <Link
                className="btn-secondary px-6 py-3 transition duration-200 hover:-translate-y-0.5"
                href="/register"
              >
                Create an account
              </Link>
            </div>
          </div>

          <div className="animate-float justify-self-center">
            <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-xl">
              <div className="flex h-40 w-40 flex-col items-center justify-center rounded-full bg-emerald-700 text-white sm:h-52 sm:w-52">
                <span className="text-sm font-medium text-emerald-100">Your EMI</span>
                <span className="mt-1 text-3xl font-bold">Rs •••</span>
                <span className="mt-1 text-xs text-emerald-100">calculated instantly</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-5 py-6 text-sm text-slate-600 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p>© 2026 Sajilo Loan.</p>
          <p>Secure online lending.</p>
        </div>
      </footer>
    </main>
  );
}
