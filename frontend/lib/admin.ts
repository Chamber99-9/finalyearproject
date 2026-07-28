export type UserRole = "customer" | "officer" | "admin";

export type AdminOverview = {
  total_users: number;
  total_applications: number;
  pending_applications: number;
};

export type AdminUser = {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  role: UserRole;
  created_at: string;
};

export type AuditLog = {
  id: string;
  action: string;
  user_id: string;
  entity_type: string;
  entity_id: string;
  details: Record<string, unknown>;
  created_at: string;
};

export const adminRoleOptions: Array<{ value: UserRole; label: string }> = [
  { value: "customer", label: "Customer" },
  { value: "officer", label: "Loan Officer" },
  { value: "admin", label: "Admin" }
];

export function formatAdminLabel(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function formatAdminDate(value: string) {
  return new Intl.DateTimeFormat("en-NP", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}
