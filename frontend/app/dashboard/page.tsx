import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { API_BASE_URL, AUTH_COOKIE_NAME } from "@/app/api/auth/_utils";
import { getDashboardPath, type AuthUser } from "@/lib/auth";

export default async function DashboardRedirectPage() {
  const token = (await cookies()).get(AUTH_COOKIE_NAME)?.value;

  if (!token) {
    redirect("/login");
  }

  let user: AuthUser | null = null;
  try {
    const response = await fetch(`${API_BASE_URL}/auth/me`, {
      headers: {
        Authorization: `Bearer ${token}`
      },
      cache: "no-store"
    });

    if (response.ok) {
      user = (await response.json()) as AuthUser;
    }
  } catch {
    redirect("/login");
  }

  if (!user) {
    redirect("/login");
  }

  redirect(getDashboardPath(user.role));
}
