"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AdminNav } from "@/components/AdminNav";
import { AdminOverview as AdminOverviewData } from "@/lib/admin";

export function AdminOverview() {
  const [overview, setOverview] = useState<AdminOverviewData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadOverview() {
      setIsLoading(true);
      setError("");

      try {
        const response = await fetch("/api/admin/overview");
        const payload = await response.json().catch(() => ({}));

        if (!response.ok) {
          setError(payload.error ?? "Could not load admin overview.");
          return;
        }

        setOverview(payload.overview ?? null);
      } catch {
        setError("Could not reach the admin overview service.");
      } finally {
        setIsLoading(false);
      }
    }

    loadOverview();
  }, []);

  return (
    <section className="page-wrap">
      <div className="page-heading">
        <div>
          <p className="eyebrow">
            Admin dashboard
          </p>
          <h1 className="mt-3 text-3xl font-bold text-slate-950 sm:text-4xl">
            System overview
          </h1>
        </div>
        <AdminNav />
      </div>

      {error ? (
        <p className="alert-error mt-6">
          {error}
        </p>
      ) : null}

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <Metric label="Total users" loading={isLoading} value={overview?.total_users} />
        <Metric
          label="Total applications"
          loading={isLoading}
          value={overview?.total_applications}
        />
        <Metric
          label="Pending applications"
          loading={isLoading}
          value={overview?.pending_applications}
        />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <ActionCard
          description="Review all registered users and change customer, officer, or admin roles."
          href="/dashboard/admin/users"
          title="Manage users"
        />
        <ActionCard
          description="Inspect recorded status changes and workflow activity for audit review."
          href="/dashboard/admin/audit-logs"
          title="View audit logs"
        />
      </div>
    </section>
  );
}

function Metric({
  label,
  loading,
  value
}: {
  label: string;
  loading: boolean;
  value?: number;
}) {
  return (
    <article className="metric-card">
      <p className="text-sm font-medium text-slate-600">{label}</p>
      <p className="mt-3 text-3xl font-bold text-slate-950">
        {loading ? "..." : value ?? 0}
      </p>
    </article>
  );
}

function ActionCard({
  description,
  href,
  title
}: {
  description: string;
  href: string;
  title: string;
}) {
  return (
    <Link
      className="panel-pad transition hover:border-emerald-300 hover:bg-emerald-50"
      href={href}
    >
      <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-slate-700">{description}</p>
    </Link>
  );
}
