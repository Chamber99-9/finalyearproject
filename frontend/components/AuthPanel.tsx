"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { AuthUser, getDashboardPath } from "@/lib/auth";

type AuthPanelProps = {
  mode: "login" | "register";
};

export function AuthPanel({ mode }: AuthPanelProps) {
  const isRegister = mode === "register";
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  function validateForm() {
    const normalizedEmail = email.trim();

    if (isRegister && fullName.trim().length < 2) {
      return "Full name must be at least 2 characters.";
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail)) {
      return "Enter a valid email address.";
    }

    if (isRegister && phone.trim().length < 7) {
      return "Enter a valid phone number.";
    }

    if (!password) {
      return "Password is required.";
    }

    if (
      isRegister &&
      (password.length < 8 ||
        !/[a-z]/.test(password) ||
        !/[A-Z]/.test(password) ||
        !/\d/.test(password) ||
        !/[^A-Za-z0-9]/.test(password))
    ) {
      return "Password must be 8+ characters with uppercase, lowercase, number, and symbol.";
    }

    return "";
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    setIsLoading(true);

    try {
      const response = await fetch(isRegister ? "/api/auth/register" : "/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          isRegister
            ? {
                full_name: fullName,
                email,
                phone,
                password
              }
            : {
                email,
                password
              }
        )
      });

      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(payload.error ?? "Authentication failed. Please try again.");
        return;
      }

      const user = payload.user as AuthUser | undefined;
      if (!user?.role) {
        setError("Authentication succeeded, but user role was missing.");
        return;
      }

      router.push(getDashboardPath(user.role));
      router.refresh();
    } catch {
      setError("Could not reach the authentication service. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="mx-auto grid min-h-[calc(100vh-73px)] max-w-7xl gap-8 px-5 py-10 sm:px-6 lg:grid-cols-[1fr_420px] lg:items-center lg:py-16">
      <section>
        <p className="eyebrow">
          Secure access
        </p>
        <h1 className="mt-3 max-w-3xl text-3xl font-bold text-slate-950 sm:text-5xl">
          {isRegister ? "Create your Sajilo Loan account" : "Welcome back to Sajilo Loan"}
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-slate-700">
          {isRegister
            ? "Create a customer account to start the online loan journey."
            : "Sign in to continue to your role-based Sajilo Loan dashboard."}
        </p>
      </section>

      <section className="panel-pad p-6">
        <h2 className="text-2xl font-semibold text-slate-950">
          {isRegister ? "Register" : "Login"}
        </h2>
        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          {isRegister ? (
            <label className="block">
              <span className="text-sm font-medium text-slate-700">Full name</span>
              <input
                className="mt-2 w-full px-3 py-2.5"
                placeholder="Aarav Sharma"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                required
                minLength={2}
                type="text"
              />
            </label>
          ) : null}
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Email address</span>
            <input
              className="mt-2 w-full px-3 py-2.5"
              placeholder="customer@example.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
            />
          </label>
          {isRegister ? (
            <label className="block">
              <span className="text-sm font-medium text-slate-700">Phone number</span>
              <input
                className="mt-2 w-full px-3 py-2.5"
                placeholder="+977 9800000000"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                required
                minLength={7}
                type="tel"
              />
            </label>
          ) : null}
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Password</span>
            <input
              className="mt-2 w-full px-3 py-2.5"
              placeholder="Enter password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={isRegister ? 8 : 1}
              type="password"
            />
            {isRegister ? (
              <span className="mt-1 block text-xs text-slate-500">
                Use uppercase, lowercase, number, and symbol.
              </span>
            ) : null}
          </label>
          {error ? (
            <p className="alert-error px-3 py-2">
              {error}
            </p>
          ) : null}
          <button
            className="btn-primary w-full"
            disabled={isLoading}
            type="submit"
          >
            {isLoading
              ? isRegister
                ? "Creating account..."
                : "Signing in..."
              : isRegister
                ? "Create account"
                : "Sign in"}
          </button>
        </form>
        <p className="mt-5 text-sm text-slate-600">
          {isRegister ? "Already have an account? " : "Need an account? "}
          <Link
            className="font-semibold text-emerald-700 hover:text-emerald-800"
            href={isRegister ? "/login" : "/register"}
          >
            {isRegister ? "Login" : "Register"}
          </Link>
        </p>
      </section>
    </div>
  );
}
