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
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {isLoading ? (
                <tr>
                  <td className="px-4 py-8 text-center text-slate-600" colSpan={4}>
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
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="px-4 py-8 text-center text-slate-600" colSpan={4}>
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
