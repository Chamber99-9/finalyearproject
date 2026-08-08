"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { NotificationMenu } from "@/components/NotificationMenu";
import { AuthUser, getDashboardPath } from "@/lib/auth";

/**
 * Auth-aware navigation. Logged-out visitors see Home + Login. Logged-in users
 * see their dashboard link, notifications bell, and a profile menu with logout —
 * no Home/Login links.
 */
export function AppNav() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    async function loadUser() {
      try {
        const response = await fetch("/api/auth/me");
        const payload = await response.json().catch(() => ({}));
        if (response.ok && payload.user) setUser(payload.user);
      } catch {
        // Not logged in — leave user null.
      } finally {
        setLoaded(true);
      }
    }
    loadUser();
  }, []);

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => undefined);
    setUser(null);
    setMenuOpen(false);
    router.push("/login");
    router.refresh();
  }

  async function toggleMfa() {
    if (!user) return;
    const endpoint = user.mfa_enabled ? "/api/auth/mfa/disable" : "/api/auth/mfa/enable";
    try {
      const response = await fetch(endpoint, { method: "POST" });
      const payload = await response.json().catch(() => ({}));
      if (response.ok) {
        setUser({ ...user, mfa_enabled: Boolean(payload.mfa?.mfa_enabled) });
      }
    } catch {
      // Non-fatal.
    }
  }

  if (!loaded) {
    return <div className="h-9 w-24" aria-hidden="true" />;
  }

  if (!user) {
    return (
      <nav className="flex items-center gap-2 text-sm font-medium text-slate-700">
        <Link
          className="rounded-md px-3 py-2 transition hover:bg-emerald-50 hover:text-emerald-800"
          href="/"
        >
          Home
        </Link>
        <Link
          className="rounded-md px-3 py-2 transition hover:bg-emerald-50 hover:text-emerald-800"
          href="/login"
        >
          Login
        </Link>
      </nav>
    );
  }

  const initials = (user.full_name || user.email || "U")
    .split(" ")
    .map((part) => part.charAt(0))
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <nav className="flex items-center gap-2 text-sm font-medium text-slate-700">
      <Link
        className="rounded-md px-3 py-2 transition hover:bg-emerald-50 hover:text-emerald-800"
        href={getDashboardPath(user.role)}
      >
        Dashboard
      </Link>
      <NotificationMenu />
      <div className="relative">
        <button
          aria-label="Profile menu"
          className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-700 text-xs font-bold text-white transition hover:scale-105"
          onClick={() => setMenuOpen((open) => !open)}
          type="button"
        >
          {initials}
        </button>
        {menuOpen ? (
          <div className="absolute right-0 z-50 mt-2 w-56 rounded-lg border border-slate-200 bg-white shadow-lg">
            <div className="border-b border-slate-200 px-4 py-3">
              <p className="font-semibold text-slate-950">{user.full_name}</p>
              <p className="mt-0.5 truncate text-xs text-slate-500">{user.email}</p>
              <p className="mt-1 text-xs font-medium capitalize text-emerald-700">{user.role}</p>
            </div>
            <Link
              className="block px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
              href={getDashboardPath(user.role)}
              onClick={() => setMenuOpen(false)}
            >
              My dashboard
            </Link>
            {user.role === "customer" ? (
              <Link
                className="block px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
                href="/dashboard/customer/statement"
                onClick={() => setMenuOpen(false)}
              >
                My statement
              </Link>
            ) : null}
            <button
              className="flex w-full items-center justify-between px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
              onClick={toggleMfa}
              type="button"
            >
              <span>Two-factor (email OTP)</span>
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                  user.mfa_enabled ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"
                }`}
              >
                {user.mfa_enabled ? "On" : "Off"}
              </span>
            </button>
            <button
              className="block w-full px-4 py-2 text-left text-sm font-medium text-red-700 hover:bg-red-50"
              onClick={logout}
              type="button"
            >
              Log out
            </button>
          </div>
        ) : null}
      </div>
    </nav>
  );
}
