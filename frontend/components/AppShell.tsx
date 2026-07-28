import Link from "next/link";
import type { ReactNode } from "react";

import { NotificationMenu } from "./NotificationMenu";

const navItems = [
  { href: "/", label: "Home" },
  { href: "/#process", label: "Process" },
  { href: "/#features", label: "Features" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/login", label: "Login" },
  { href: "/register", label: "Apply" }
];

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  return (
    <main className="min-h-screen bg-slate-100 text-slate-950">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 shadow-sm backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-5 py-3 sm:px-6 lg:flex-row lg:items-center lg:justify-between">
          <Link href="/" className="flex items-center gap-3 text-xl font-bold text-slate-950">
            <span className="flex h-10 w-10 items-center justify-center rounded-md bg-emerald-700 text-sm font-bold text-white shadow-sm">
              SL
            </span>
            <span>Sajilo Loan</span>
          </Link>
          <nav className="flex flex-wrap items-center gap-2 text-sm font-medium text-slate-700">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="rounded-md px-3 py-2 transition hover:bg-emerald-50 hover:text-emerald-800"
              >
                {item.label}
              </Link>
            ))}
            <NotificationMenu />
          </nav>
        </div>
      </header>
      {children}
    </main>
  );
}
