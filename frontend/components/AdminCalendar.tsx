"use client";

import { useEffect, useState } from "react";

import { AdminNav } from "@/components/AdminNav";

type Clock = { offset_days: number; simulated_now: string };
type BillingResult = {
  reminded: number;
  overdue: number;
  blacklisted: number;
  simulated_now: string;
};

/**
 * Testing calendar. Skip the simulated date forward, then run the billing jobs
 * to see reminders (email), overdue counting, and blacklisting fire without
 * waiting a real month.
 */
export function AdminCalendar() {
  const [clock, setClock] = useState<Clock | null>(null);
  const [result, setResult] = useState<BillingResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    loadClock();
  }, []);

  async function loadClock() {
    try {
      const r = await fetch("/api/admin/clock");
      const p = await r.json().catch(() => ({}));
      if (r.ok) setClock(p.clock);
      else setError(p.error ?? "Could not load the clock.");
    } catch {
      setError("Could not reach the service.");
    }
  }

  async function advance(days: number) {
    setBusy(true);
    setError("");
    try {
      const r = await fetch("/api/admin/clock/advance", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ days })
      });
      const p = await r.json().catch(() => ({}));
      if (r.ok) setClock(p.clock);
      else setError(p.error ?? "Could not advance the clock.");
    } catch {
      setError("Could not reach the service.");
    } finally {
      setBusy(false);
    }
  }

  async function reset() {
    setBusy(true);
    setError("");
    try {
      const r = await fetch("/api/admin/clock/reset", { method: "POST" });
      const p = await r.json().catch(() => ({}));
      if (r.ok) {
        setClock(p.clock);
        setResult(null);
      } else setError(p.error ?? "Could not reset the clock.");
    } catch {
      setError("Could not reach the service.");
    } finally {
      setBusy(false);
    }
  }

  async function runBilling() {
    setBusy(true);
    setError("");
    try {
      const r = await fetch("/api/admin/run-billing", { method: "POST" });
      const p = await r.json().catch(() => ({}));
      if (r.ok) setResult(p.result);
      else setError(p.error ?? "Could not run billing.");
    } catch {
      setError("Could not reach the service.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page-wrap">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Admin dashboard</p>
          <h1 className="mt-3 text-3xl font-bold text-slate-950 sm:text-4xl">Testing calendar</h1>
          <p className="mt-3 max-w-3xl text-base leading-7 text-slate-700">
            Skip the simulated date forward, then run the billing jobs to test EMI email
            reminders (3 days before due), overdue counting, and automatic blacklisting.
          </p>
        </div>
        <AdminNav />
      </div>

      {error ? <p className="alert-error mt-6">{error}</p> : null}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="panel-pad">
          <p className="text-sm font-medium text-slate-600">Simulated date</p>
          <p className="mt-1 text-2xl font-bold text-slate-950">
            {clock ? new Date(clock.simulated_now).toLocaleString() : "…"}
          </p>
          <p className="mt-1 text-sm text-slate-500">
            Offset: {clock ? `${clock.offset_days} day(s)` : "…"} from real time
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {[1, 3, 7, 30].map((d) => (
              <button
                key={d}
                className="btn-secondary px-3 py-2 text-sm"
                disabled={busy}
                onClick={() => advance(d)}
                type="button"
              >
                +{d} day{d > 1 ? "s" : ""}
              </button>
            ))}
            <button className="btn-muted px-3 py-2 text-sm" disabled={busy} onClick={reset} type="button">
              Reset
            </button>
          </div>
        </div>

        <div className="panel-pad">
          <p className="text-sm font-medium text-slate-600">Run daily billing jobs</p>
          <p className="mt-1 text-sm text-slate-500">
            Sends due reminders and processes overdue loans at the simulated date.
          </p>
          <button className="btn-primary mt-4 px-5 py-2.5" disabled={busy} onClick={runBilling} type="button">
            {busy ? "Running…" : "Run billing now"}
          </button>
          {result ? (
            <dl className="mt-4 grid grid-cols-3 gap-3 text-center">
              <Stat label="Reminded" value={result.reminded} />
              <Stat label="Overdue" value={result.overdue} />
              <Stat label="Blacklisted" value={result.blacklisted} tone="red" />
            </dl>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: "red" }) {
  return (
    <div className={`rounded-md p-3 ${tone === "red" ? "bg-red-50" : "bg-slate-50"}`}>
      <p className={`text-2xl font-bold ${tone === "red" ? "text-red-700" : "text-slate-950"}`}>{value}</p>
      <p className="mt-1 text-xs font-medium text-slate-600">{label}</p>
    </div>
  );
}
