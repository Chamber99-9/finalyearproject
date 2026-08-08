import { AppShell } from "@/components/AppShell";
import { AdminUserStatement } from "@/components/AdminUserStatement";

export default async function AdminUserStatementPage({
  params
}: {
  params: Promise<{ userId: string }>;
}) {
  const { userId } = await params;
  return (
    <AppShell>
      <AdminUserStatement userId={userId} />
    </AppShell>
  );
}
