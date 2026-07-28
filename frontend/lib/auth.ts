export type UserRole = "customer" | "officer" | "admin";

export type AuthUser = {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  role: UserRole;
  created_at: string;
};

export function getDashboardPath(role: UserRole): string {
  const paths: Record<UserRole, string> = {
    customer: "/dashboard/customer",
    officer: "/dashboard/officer",
    admin: "/dashboard/admin"
  };

  return paths[role];
}
