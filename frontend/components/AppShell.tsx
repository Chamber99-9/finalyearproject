import Link from "next/link";
import type { ReactNode } from "react";

import { AppNav } from "./AppNav";

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  return (
    <main className="min-h-screen bg-slate-100 text-slate-950">
      <header className="no-print sticky top-0 z-40 border-b border-slate-200 bg-white/90 shadow-sm backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-3 sm:px-6">
          <Link href="/" className="flex items-center gap-3 text-xl font-bold text-slate-950">
            <span className="flex h-10 w-10 items-center justify-center rounded-md bg-emerald-700 text-sm font-bold text-white shadow-sm">
              SL
            </span>
            <span>Sajilo Loan</span>
          </Link>
          <AppNav />
        </div>
      </header>
      {children}
    </main>
  );
}
