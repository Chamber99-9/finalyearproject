"use client";

import { useEffect, useState } from "react";

import { AdminNav } from "@/components/AdminNav";
import { AuditLog, formatAdminDate, formatAdminLabel } from "@/lib/admin";

function formatDetailValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "N/A";
  }

  if (Array.isArray(value)) {
    return value.join(", ");
  }

  if (typeof value === "object") {
    return JSON.stringify(value);
  }

  return String(value);
}

export function AdminAuditLogs() {
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadAuditLogs() {
      setIsLoading(true);
      setError("");

      try {
        const response = await fetch("/api/admin/audit-logs");
        const payload = await response.json().catch(() => ({}));

        if (!response.ok) {
          setError(payload.error ?? "Could not load audit logs.");
          return;
        }

        setAuditLogs(payload.audit_logs ?? []);
      } catch {
        setError("Could not reach the admin audit log service.");
      } finally {
        setIsLoading(false);
      }
    }

    loadAuditLogs();
  }, []);

  return (
    <section className="page-wrap">
      <div className="page-heading">
        <div>
          <p className="eyebrow">
            Admin dashboard
          </p>
          <h1 className="mt-3 text-3xl font-bold text-slate-950 sm:text-4xl">
            Audit logs
          </h1>
        </div>
        <AdminNav />
      </div>

      {error ? (
        <p className="alert-error mt-6">
          {error}
        </p>
      ) : null}

      <div className="table-shell">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="table-head">
              <tr>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">User</th>
                <th className="px-4 py-3">Entity</th>
                <th className="px-4 py-3">Details</th>
                <th className="px-4 py-3">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {isLoading ? (
                <tr>
                  <td className="px-4 py-8 text-center text-slate-600" colSpan={5}>
                    Loading audit logs...
                  </td>
                </tr>
              ) : auditLogs.length > 0 ? (
                auditLogs.map((log) => (
                  <tr key={log.id} className="align-top">
                    <td className="px-4 py-4">
                      <p className="font-semibold text-slate-950">
                        {formatAdminLabel(log.action)}
                      </p>
                    </td>
                    <td className="px-4 py-4 text-slate-700">
                      <p className="text-xs text-slate-500">{log.user_id}</p>
                    </td>
                    <td className="px-4 py-4 text-slate-700">
                      <p>{formatAdminLabel(log.entity_type)}</p>
                      <p className="mt-1 text-xs text-slate-500">{log.entity_id}</p>
                    </td>
                    <td className="px-4 py-4 text-slate-700">
                      <dl className="grid max-w-md grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-xs">
                        {Object.entries(log.details).map(([key, value]) => (
                          <div className="contents" key={key}>
                            <dt className="font-semibold text-slate-500">
                              {formatAdminLabel(key)}
                            </dt>
                            <dd className="break-words text-slate-700">
                              {formatDetailValue(value)}
                            </dd>
                          </div>
                        ))}
                      </dl>
                    </td>
                    <td className="px-4 py-4 text-slate-600">
                      {formatAdminDate(log.created_at)}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="px-4 py-8 text-center text-slate-600" colSpan={5}>
                    No audit logs found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
