import { redirect } from "next/navigation";

// KYC review moved to loan officers. Admins are redirected to the overview.
export default function AdminKycPage() {
  redirect("/dashboard/admin");
}
