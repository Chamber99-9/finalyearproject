import Link from "next/link";

const adminLinks = [
  { href: "/dashboard/admin", label: "Overview" },
  { href: "/dashboard/admin/applications", label: "Applications & rates" },
  { href: "/dashboard/admin/users", label: "Manage users" },
  { href: "/dashboard/admin/calendar", label: "Testing calendar" },
  { href: "/dashboard/admin/audit-logs", label: "Audit logs" }
];

export function AdminNav() {
  return (
    <nav className="flex flex-wrap gap-2">
      {adminLinks.map((link) => (
        <Link
          className="btn-secondary px-3 py-2 text-sm"
          href={link.href}
          key={link.href}
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
