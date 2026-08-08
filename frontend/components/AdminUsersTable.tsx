"use client";

import { useEffect, useState } from "react";

import { AdminNav } from "@/components/AdminNav";
import {
  AdminUser,
  UserRole,
  adminRoleOptions,
  formatAdminDate,
  formatAdminLabel
} from "@/lib/admin";

export function AdminUsersTable() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [updatingUserId, setUpdatingUserId] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    async function loadUsers() {
      setIsLoading(true);
      setError("");

      try {
        const response = await fetch("/api/admin/users");
        const payload = await response.json().catch(() => ({}));

        if (!response.ok) {
          setError(payload.error ?? "Could not load users.");
          return;
        }

        setUsers(payload.users ?? []);
      } catch {
        setError("Could not reach the admin user service.");
      } finally {
        setIsLoading(false);
      }
    }

    loadUsers();
  }, []);

  async function updateRole(userId: string, role: UserRole) {
    setUpdatingUserId(userId);
    setError("");
    setSuccess("");

    try {
      const response = await fetch(`/api/admin/users/${userId}/role`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role })
      });
      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(payload.error ?? "Could not update user role.");
        return;
      }

      const updatedUser = payload.user as AdminUser;
      setUsers((current) =>
        current.map((user) => (user.id === updatedUser.id ? updatedUser : user))
      );
      setSuccess(`${updatedUser.full_name} is now ${formatAdminLabel(updatedUser.role)}.`);
    } catch {
      setError("Could not reach the admin role service.");
    } finally {
      setUpdatingUserId("");
    }
  }

  async function toggleBlacklist(user: AdminUser) {
    setUpdatingUserId(user.id);
    setError("");
    setSuccess("");
    const next = !(user as AdminUser & { is_blacklisted?: boolean }).is_blacklisted;
    try {
      const response = await fetch(`/api/admin/users/${user.id}/blacklist`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ blacklisted: next })
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(payload.error ?? "Could not update user.");
        return;
      }
      const updated = payload.user as AdminUser;
      setUsers((current) => current.map((u) => (u.id === updated.id ? updated : u)));
      setSuccess(`${updated.full_name} ${next ? "blacklisted" : "restored"}.`);
    } catch {
      setError("Could not reach the service.");
    } finally {
      setUpdatingUserId("");
    }
  }

  return (
    <section className="page-wrap">
      <div className="page-heading">
        <div>
          <p className="eyebrow">
            Admin dashboard
          </p>
          <h1 className="mt-3 text-3xl font-bold text-slate-950 sm:text-4xl">
            Manage users
          </h1>
        </div>
        <AdminNav />
      </div>

      {error ? (
        <p className="alert-error mt-6">
          {error}
        </p>
      ) : null}

      {success ? (
        <p className="alert-success mt-6">
          {success}
        </p>
      ) : null}

      <div className="table-shell">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="table-head">
              <tr>
                <th className="px-4 py-3">User</th>
                <th className="px-4 py-3">Contact</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {isLoading ? (
                <tr>
                  <td className="px-4 py-8 text-center text-slate-600" colSpan={5}>
                    Loading users...
                  </td>
                </tr>
              ) : users.length > 0 ? (
                users.map((user) => (
                  <tr key={user.id} className="align-top">
                    <td className="px-4 py-4">
                      <p className="font-semibold text-slate-950">{user.full_name}</p>
                      <p className="mt-1 text-xs text-slate-500">{user.id}</p>
                    </td>
                    <td className="px-4 py-4 text-slate-700">
                      <p>{user.email}</p>
                      <p className="mt-1">{user.phone}</p>
                    </td>
                    <td className="px-4 py-4">
                      <select
                        className="px-3 py-2"
                        disabled={updatingUserId === user.id}
                        onChange={(event) =>
                          updateRole(user.id, event.target.value as UserRole)
                        }
                        value={user.role}
                      >
                        {adminRoleOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-4 text-slate-600">
                      {formatAdminDate(user.created_at)}
                    </td>
                    <td className="px-4 py-4">
                      {(user as AdminUser & { is_blacklisted?: boolean }).is_blacklisted ? (
                        <span className="status-pill bg-red-100 text-red-700">Blacklisted</span>
                      ) : (
                        <span className="status-pill bg-emerald-100 text-emerald-800">Active</span>
                      )}
                      <button
                        className="mt-2 block text-xs font-semibold text-slate-600 hover:text-red-700 disabled:opacity-50"
                        disabled={updatingUserId === user.id}
                        onClick={() => toggleBlacklist(user)}
                        type="button"
                      >
                        {(user as AdminUser & { is_blacklisted?: boolean }).is_blacklisted
                          ? "Restore access"
                          : "Blacklist user"}
                      </button>
                      <a
                        className="mt-2 block text-xs font-semibold text-emerald-700 hover:text-emerald-800"
                        href={`/dashboard/admin/users/${user.id}/statement`}
                      >
                        View statement
                      </a>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="px-4 py-8 text-center text-slate-600" colSpan={5}>
                    No users found.
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
